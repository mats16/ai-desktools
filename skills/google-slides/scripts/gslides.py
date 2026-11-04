#!/usr/bin/env python3
"""Google Slides の決まった操作（作るのは slides.py。ここは確かめると流用）。
usage:
  gslides.py check  <URL か ID> [--talk] [--all | --pages 3,5]   組んだあとの確認。JSON・テキスト・lint と、前に取ったときから変わったページの画像（p-NN.webp）を /tmp/slides_<ID の先頭 8 字>/ に出し、
                   画像で箱の下の余白を測る（box_pad.py）。取ったページと指摘を changed.json に書く。--all で全ページの画像（/deck-review の前などの区切り）
  gslides.py wording <URL か ID>                  日本語の点検（build/ で回す）。Google の資料の文とノートの言い回しの指摘を、ページのファイルと JSON の場所つきで出し、
                   直す前に通した文と比べて意味の変わる恐れを出し、資料のフォルダの wording.json に残す（wording.py。lint.md の「Japanese check」）
  gslides.py pages  <URL か ID>                    ページ番号・objectId・最初の文字を一覧にする
  gslides.py thumb  <URL か ID> <ページ番号> <出力.png>   Google が描いたページの画像（1600 × 900）を保存する
  gslides.py export <URL か ID> <出力.pptx>          pptx で書き出す（Drive に置かれた pptx はそのまま落とす）。名前と更新日も出す（references.md に書く）
  gslides.py keep   <URL か ID> <Drive のフォルダ> <Drive 上の名前> <ページ番号 ...>   複製して、指定したページだけをその順に残す（流用の段階 1）
  gslides.py jp     <URL か ID> [置き換え.json]     すべての文字を Noto Sans JP にし、置き換え（[["元の文", "訳した文"], …]）を入れる（keep で作った複製に使う）
python3 gslides.py --selftest で自己確認。
認証は gapi.py（環境変数 GOOGLE_OAUTH_ACCESS_TOKEN か、gcloud の ADC のファイル）。401・403 なら desk-doctor で確かめる。"""
import contextlib, glob, io, json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True  # scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi, lint, textlint, wording
from notes import PAGE_KEY, page_key
from slides import STAMP, page_numbers, revision
from gapi import DRIVE, PPTX, SLIDES, batch, file_id, folder_id, request, run, slide_ids, thumbnail, trash

SHEET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sheet.py")  # 隣の sheet.py（このスキルが持ち主）
THREADS = 6  # サムネイルを並べて取る数。12 枚で約 5 秒（2026-10-07 に測った。PDF に書き出して画像にするのと同じ）


def save_thumb(pid, obj, out):
    meta = thumbnail(pid, obj)
    with urllib.request.urlopen(meta["contentUrl"], timeout=gapi.TIMEOUT) as r, open(out, "wb") as f:
        f.write(r.read())
    return meta


def text_of(p):
    """ページごとの文字とノート（レビューに渡すテキスト）。表は 1 行を「 | 」でつなぐ。"""
    out = []
    for i, s in enumerate(p.get("slides", []), 1):
        out.append(f"## p{i}")
        for e, _ in lint.flatten(s.get("pageElements", [])):
            if "image" in e:
                out.append("［画像］")
            elif "table" in e:
                out += [" | ".join("".join(lint.ptext(x) for x in lint.paras(c.get("text"))).strip() for c in row.get("tableCells", []))
                        for row in e["table"].get("tableRows", [])]
            else:
                t = "\n".join(lint.ptext(x) for text, _ in lint.cells(e) for x in lint.paras(text)).strip()
                if t:
                    out.append(t)
        out += ["", "### Notes:", lint.note_text(s).strip(), ""]
    return "\n".join(out)


def write_json(path, obj):
    """書きかけで止まっても、前の中身か新しい中身のどちらかが残るように書く（別の名前に書いてから置き換える）。"""
    with open(path + ".tmp", "w") as f:
        json.dump(obj, f)
    os.replace(path + ".tmp", path)


def reuse_shots(d, ids, prev):
    """前に取った画像（prev は p-NN.webp ごとの、取ったときのページの objectId）のうち、今もあるページのものを今の番号に移し、古いものは消す。
    戻り: (取るページの番号, 前の画像を使ったページのうち番号の変わった数)。build は中身の変わったページを新しい ID で作るので、ID が同じなら中身も同じ。"""
    have = {o: f"{d}/p-{m:02d}.webp" for m, o in enumerate(prev, 1) if o and os.path.exists(f"{d}/p-{m:02d}.webp")}
    keep = {n: have[o] for n, o in enumerate(ids, 1) if o in have}
    for n, f in keep.items():
        os.replace(f, f"{d}/.p-{n:02d}.webp")  # 番号がずれると、移す先がまだ移していない画像のことがあるので、いったん別の名前にする
    for f in glob.glob(f"{d}/p-*.webp"):
        os.remove(f)
    for n in keep:
        os.replace(f"{d}/.p-{n:02d}.webp", f"{d}/p-{n:02d}.webp")
    return [n for n in range(1, len(ids) + 1) if n not in keep], sum(n != prev.index(ids[n - 1]) + 1 for n in keep)


def by_page(lines):
    """「p<番号>: …」「p<番号> の…」で始まる指摘を、ページの番号ごとに分ける。"""
    out = {}
    for k, h in lines:
        if (n := lint.hit_page(h)) is not None:
            out.setdefault(n, []).append(f"[{k}] {h}" + ("（見積もり）" if k in lint.ESTIMATE else ""))
    return out


def built(pid):
    """今のリビジョン（slides.revision）。リビジョンの一覧は編集できる人しか読めないので、読めなければ None（組んだリビジョンと比べて違うことにし、全ページを取る）。"""
    try:
        return revision(pid)
    except gapi.ApiError:
        return None


def cmd_check(src, *opts):
    """[slides-lint-028] 画像は、前に取ったときから変わったページだけを取る（テストの e2e。ページの objectId で見る。build が中身の変わったページだけを新しい ID で作る）。
    前に組んだあとに画面で直されていたら（組んだときのリビジョンと今のリビジョンが違う）、全ページを取る。--all で全ページ、--pages 3,5 でそのページだけ。
    取ったページの番号・画像・そのページの lint と box_pad の指摘を changed.json に書く（親がページ担当の子に渡す。../SKILL.md の「Reading the results」）。"""
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    gapi.CLOCK.lap("GET")
    d = f"/tmp/slides_{pid[:8]}"
    os.makedirs(d, exist_ok=True)
    json.dump(p, open(f"{d}/deck.json", "w", encoding="utf-8"), ensure_ascii=False)
    open(f"{d}/deck.md", "w", encoding="utf-8").write(text_of(p))
    print(f"{p['title']}（{len(p['slides'])} 枚）\n")
    hard = lint.lint_slides(p, r := lint.Report(), "差し替え用" in p["title"], "--talk" in opts)
    if not any(w in p["title"].lower() for w in ("tmp", "template", "作業用", "テンプレート")):  # 一時のデッキ・流用元の作業用の写し・テンプレートは、組み直して直すものでないので数えない
        textlint.log_run(r, pid)  # 要確認の残り方を textlint.py --stats で数える（desk-dreaming/run.md の 5）
    gapi.CLOCK.lap("lint")
    ids = [s["objectId"] for s in p["slides"]]
    shots = f"{d}/shots.json"  # p-NN.webp ごとの、取ったときのページの objectId
    try:
        prev = json.load(open(shots))
    except (OSError, ValueError):  # ない、か書きかけで切れた（止まったときなど）。記録がないものとして全ページを取る
        prev = []
    for f in glob.glob(f"{d}/p-*.png") + glob.glob(f"{d}/p-*.webp.tmp"):  # WebP にする前やその途中で止まった回の PNG と書きかけ、前のバージョンの PNG。使わない
        os.remove(f)
    old = glob.glob(f"{d}/p-*.webp")
    moved, why = 0, None
    if "--pages" in opts and len(old) != len(ids):  # ページが増えたり減ったりしたあとは、番号がずれるので全部を取り直す
        print(f"ページの数が変わった（画像 {len(old)} 枚 → {len(ids)} 枚）ので、--pages を使わずに全ページを取り直す")
        opts, why = [o for o in opts if o != "--pages"], "ページの数が変わった"
    if os.path.exists(shots):  # 画像を動かす・取るあいだに止まっても、次の check が古い記録で別のページの画像を使わないように、先に消す
        os.remove(shots)
    if "--pages" in opts:
        want = sorted(page_numbers(opts))
        if over := [n for n in want if n > len(ids)]:
            sys.exit(f"--pages の {', '.join(map(str, over))} がない（{len(ids)} 枚）")
        man = [o if n in want else prev[n - 1] if len(prev) == len(ids) else None for n, o in enumerate(ids, 1)]
    else:
        if not why:  # ページの数が変わったとき（上）は、もう全ページ
            if "--all" in opts:
                why = "--all"
            elif not prev:
                why = "前に取った画像の記録がない"
            elif (now := built(pid)) is None or now != request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(STAMP):
                why = "slides.py build で組んだリビジョンでない（画面で直されたか、ほかの道具で変えた）"
        if why:
            want = list(range(1, len(ids) + 1))
            for f in old:  # ページが減ったときに古い画像を残さない
                os.remove(f)
        else:
            want, moved = reuse_shots(d, ids, prev)
        man = ids
    write_json(shots, [None if n in want else o for n, o in enumerate(man, 1)])  # 取り終えるまで、取るページの画像は記録に入れない
    gapi.CLOCK.lap("リビジョンの確認")
    for n in want:  # 取り直すページの前の画像（--pages では reuse_shots を通らないので残っている）。WebP にできなかったとき、古い画像を今の画像と取り違えない
        if os.path.exists(f := f"{d}/p-{n:02d}.webp"):
            os.remove(f)
    with ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(lambda n: save_thumb(pid, ids[n - 1], f"{d}/p-{n:02d}.png"), want))
    failed = []  # WebP にできず、画像のないページ
    if want:  # Slides API は PNG でしか返さない。同じ画素の WebP（PNG の 4 割ほど）にして、会話に積もるバイトを減らす（Pillow が要るので uv）
        try:
            conv = subprocess.run(["uv", "run", "-q", SHEET, "--webp", *(f"{d}/p-{n:02d}.png" for n in want)], capture_output=True, text=True)
        except OSError as e:  # uv がない・動かせない
            conv = subprocess.CompletedProcess([], 1, "", f"uv を動かせない（{e}）")
        if conv.returncode:  # 画像は p-NN.webp だけにする（PNG を混ぜると、読む側がどちらを読むかで取り違える）。この回のページは画像なし。記録に入れないので、次の check が取り直す
            for n in want:
                for f in (f"{d}/p-{n:02d}.png", f"{d}/p-{n:02d}.webp"):  # sheet.py が置き換えの途中で止まると、両方あるページも残る
                    if os.path.exists(f):
                        os.remove(f)
            print(f"\n（ページの画像を WebP にできなかったので、この回に取ったページの画像はない: {conv.stderr.strip()[-300:]}。uv が要る。desk-doctor で確かめる）")
            want, failed = [], want
    gapi.CLOCK.lap(f"画像 {len(want)} 枚")
    if not failed:
        write_json(shots, man)
    pad = subprocess.run(["uv", "run", "-q", os.path.join(os.path.dirname(os.path.abspath(__file__)), "box_pad.py"), f"{d}/deck.json", d, *map(str, want)],
                         capture_output=True, text=True) if want else None  # 箱の下端と文字の間は、JSON では見積もれないので画像で測る（Pillow が要るので uv）
    gapi.CLOCK.lap("box_pad")
    if pad:
        print(pad.stdout.rstrip() if pad.returncode == 0 else f"\n（box_pad.py が止まった: {pad.stderr.strip()[-300:]}）")
    if why:
        shown = f"全ページ（{why}）"
    else:
        shown = f"{len(want)} 枚（{'指定したページ' if '--pages' in opts else '前に取ったときから変わったページ'}）"
        if len(want) + len(failed) < len(ids):
            shown += f"。ほかの {len(ids) - len(want) - len(failed)} 枚は前の画像" + (f"（うち {moved} 枚は番号が変わったので、右下のページ番号だけ古い）" if moved else "")
    if failed:
        shown += "。WebP にできず、この回の画像はない"
    print(f"\nテキスト: {d}/deck.md\n画像: {d}/p-NN.webp。取ったのは {shown}: {', '.join(f'p{n}' for n in want) or 'なし'}" + (f"\n画像のないページ（WebP にできなかった）: {', '.join(f'p{n}' for n in failed)}" if failed else "") + f"\nJSON: {d}/deck.json\n変えたページ: {d}/changed.json")
    hits, pads = by_page((k, h) for k, hs in r.hits.items() for h in hs), by_page(re.findall(r"^\[(.+?)\] (.*)$", pad.stdout if pad else "", re.M))
    json.dump({"url": f"https://docs.google.com/presentation/d/{pid}/edit", "by": "check", "slides": len(ids), "lint_hard": hard, "deck_md": f"{d}/deck.md",
               "pages": [{"page": n, "objectId": ids[n - 1], "image": f"{d}/p-{n:02d}.webp" if n in want else None, "lint": hits.get(n, []), "box_pad": pads.get(n, [])} for n in sorted(want + failed)]},
              open(f"{d}/changed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    gapi.CLOCK.show("check ")
    if hard:
        sys.exit("lint の要修正が残っている（上の出力を直す）")


def json_leaves(o, path=""):
    """JSON の文字の値と、その場所（body.items[2].text）。"""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from json_leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from json_leaves(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


def locate(units, slides, build="."):
    """Google の資料の文を、build/ のページのファイルと JSON の場所に戻す（u の file・loc を埋める）。ページの objectId の印（PAGE_KEY）でファイルを決め、
    その中の文字の値から文の先頭 20 字を探す。印のないページ（pages.py・印を付ける前に組んだもの）は、build/ のどのファイルからも探す。見つからなければ空のまま。"""
    files = sorted((p for p in glob.glob(os.path.join(build, "**", "*.json"), recursive=True) if not os.path.basename(p).startswith(".")),
                   key=lambda p: (p.count(os.sep), p))  # 同じ名前なら build/ の直下を先に（サブフォルダの控えに印を取られない）
    by_key, leaves = {}, {}
    for f in files:
        rel = os.path.relpath(f, build)
        by_key.setdefault(page_key(os.path.splitext(os.path.basename(f))[0]), rel)
        try:
            leaves[rel] = [(loc, wording.flat(v)) for loc, v in json_leaves(json.load(open(f, encoding="utf-8")))]  # 突き合わせの形にして 1 度だけ持つ
        except (OSError, ValueError):
            leaves[rel] = []
    py = os.path.join(build, "pages.py")
    lines = [wording.flat(x) for x in open(py, encoding="utf-8").read().splitlines()] if os.path.isfile(py) else []
    for u in units:
        want = wording.flat(u["text"])[:20]
        m = PAGE_KEY.search(slides[u["page"] - 1]["objectId"]) if u["page"] and u["page"] <= len(slides) else None
        for rel in ([by_key[m.group(1)]] if m and m.group(1) in by_key else list(leaves)):
            if hit := [loc for loc, v in leaves[rel] if want and v == want] or [loc for loc, v in leaves[rel] if want and want in v]:  # 短い文（表のセル）は、同じ文の値を先に
                u["file"], u["loc"] = rel, "・".join(dict.fromkeys(hit))
                break
        else:
            if (n := next((i for i, x in enumerate(lines, 1) if want and want in x), None)):
                u["file"], u["loc"] = "pages.py", f"{n} 行"
        if m and m.group(1) in by_key:  # 直す前後を組にするページの名前（並べ替えても同じ）。文が JSON に見つからなくても、ページの印で決める
            u["key"] = os.path.splitext(by_key[m.group(1)])[0]
    return units


def slide_units(p):
    """lint が言い回しを見る文（lint_slides の wording の呼び出し）と、ノートの行。"""
    units = []
    key = lambda where, kw: "#"  # 印のないページ（pages.py など）は 1 つの並びにして、ページを足しても消してもあとのページがずれない（印のあるページは locate がファイル名にする）
    r = wording.collector(lint.Report(), units, key, lambda kw: "表" if kw.get("table") else "本文")
    real = lint.segment, lint.workspace_checks  # 文を集めるだけなので、文節の切れ目（BudouX）とワークスペースの点検は呼ばない（どちらも言い回しを見る文を変えない）
    lint.segment, lint.workspace_checks = (lambda ts: {t: set(range(len(t) + 1)) for t in ts}), (lambda *a: 0)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            lint.lint_slides(p, r, "差し替え用" in p["title"])
    finally:
        lint.segment, lint.workspace_checks = real
    for i, s in enumerate(p.get("slides", []), 1):
        for line in lint.note_text(s).splitlines():
            if textlint.wording_text(line):
                units.append(wording.unit(f"p{i} ノート", line, "#", "ノート", slides=False, page=i))
    return sorted(units, key=lambda u: (u["page"] or 0, u["kind"] == "ノート"))  # ページの順、ノートはそのページの後ろ（同じページの中は lint が見た順）


def unbuilt(src):
    """手元の原稿に、まだ組んでいない直しがあるか: 通らない理由の文の並び（なければ []）。点検した Google の資料と、記録する手元のファイルを結び付けるため。
    slides.py plan（build と同じデッキを作り、build が送るものを出す。Google には書かない）の rebuild・frozen・remove・moves・theme と、build が書き換えるノート（notes）で見る。
    ノートは deck.json が指すページと pages.py の d.note から build と同じに決まり、ないページは空のノートと比べる。plan が止まったら、確かめられないとして通さない。"""
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slides.py"), "plan", src], capture_output=True, text=True)
    try:
        x = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else None
    except (ValueError, IndexError):
        x = None
    if x is None:
        return [f"slides.py plan が止まり、手元のページと Google の資料が同じかを確かめられない（{(r.stderr or r.stdout).strip()[-200:]}）"]
    out = []
    if x.get("rebuild") or x.get("frozen") or x.get("remove") or x.get("moves") or x.get("theme"):
        pages = sorted(set(x.get("rebuild") or []) | set(x.get("frozen") or []))
        out.append("手元のページの JSON に、組んでいない直しがある（slides.py plan: " + (f"ページ {', '.join(f'p{n}' for n in pages[:12])}" if pages else "ページの並び・テーマ")
                   + "）。slides.py build で組み、check で画像を見てから回す（組んでいない原稿を点検済みにしない）")
    if x.get("notes"):
        out.append(f"組んでいないノートの直しがある（slides.py plan: {', '.join(f'p{n}' for n in x['notes'][:12])}）。slides.py build で組んでから回す")
    return out


def cmd_wording(src):
    """slides-lint-035 の日本語の点検。Google に保存された資料（presentations.get）を読むので、手元の JSON だけが直っていて Google が古いまま、という取りこぼしがない。
    通らない理由: 組んだあとに画面で直された（JSON と Google の資料が違う。直しを JSON に写して組み直す）、組んだあとのページの画像を check で取っていない（直して文が延びたページの見た目を見ていない）。"""
    if os.path.basename(os.getcwd()) != "build":
        sys.exit("wording は資料の build/ で回す（ページのファイルの場所を出し、資料のフォルダに wording.json を書く）")
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    rev, stamp = built(pid), request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(STAMP)
    problems = []
    if rev is None or rev != stamp:
        problems.append("slides.py build で組んだリビジョンでない（画面で直されたか、ほかの道具で変えた）。直しをページの JSON に写して slides.py build で組み直す")
    ids = [s["objectId"] for s in p["slides"]]
    try:
        shots = json.load(open(f"/tmp/slides_{pid[:8]}/shots.json"))
    except (OSError, ValueError):
        shots = []
    if miss := [n for n, o in enumerate(ids, 1) if n > len(shots) or shots[n - 1] != o]:
        problems.append(f"組んだあとの画像を取っていないページ: {', '.join(f'p{n}' for n in miss[:12])}{' ほか' if len(miss) > 12 else ''}"
                        f"（gslides.py check {src} で取り、直したページの画像を見てから回す）")
    problems += unbuilt(src)
    units = locate(slide_units(p), p["slides"])
    ok = wording.run(os.path.dirname(os.getcwd()), "slides", f"https://docs.google.com/presentation/d/{pid}/edit", rev, units, wording.build_files(), problems, f"gslides.py wording {src}")
    if not ok:
        sys.exit(1)


def cmd_pages(src):
    p = request("GET", f"{SLIDES}/{file_id(src)}?fields=slides(objectId,pageElements(shape(text(textElements(textRun(content))))))")
    for n, s in enumerate(p["slides"], 1):
        t = "".join(r.get("textRun", {}).get("content", "") for e in s.get("pageElements", [])
                    for r in e.get("shape", {}).get("text", {}).get("textElements", []))
        print(f"p{n}\t{s['objectId']}\t{' '.join(t.split())[:60]}")


def cmd_thumb(src, page, out):
    pid = file_id(src)
    meta = save_thumb(pid, slide_ids(pid)[int(page) - 1], out)
    print(out, meta["width"], "x", meta["height"])


def cmd_export(src, out):
    fid = file_id(src)
    meta = request("GET", f"{DRIVE}/files/{fid}?fields=mimeType,name,modifiedTime,exportLinks&supportsAllDrives=true")
    # files.export は 10 MB で止まる。exportLinks からは 65 枚の社内テンプレート（14.6 MB）も書き出せた（2026-10-07）
    url = f"{DRIVE}/files/{fid}?alt=media&supportsAllDrives=true" if meta["mimeType"] == PPTX else meta["exportLinks"][PPTX]
    open(out, "wb").write(request("GET", url, binary=True))
    print(f"{out}\t{os.path.getsize(out)} bytes\t{meta['name']}\t更新 {meta['modifiedTime'][:10]}")


def cmd_keep(src, folder, name, *pages):
    sid = file_id(src)
    n = len(slide_ids(sid))
    if not pages or any(not x.isdigit() or not 1 <= int(x) <= n for x in pages):  # 複製を作る前に確かめる（作ってから失敗すると、空の複製が残る）
        sys.exit(f"ページ番号は 1〜{n} で 1 つ以上: {' '.join(pages) or '（なし）'}")
    pid = request("POST", f"{DRIVE}/files/{sid}/copy?supportsAllDrives=true&fields=id", {"name": name, "parents": [folder_id(folder)]})["id"]
    try:
        ids = slide_ids(pid)
        keep = [ids[int(x) - 1] for x in pages]
        reqs = [{"deleteObject": {"objectId": o}} for o in ids if o not in keep]
        reqs += [{"updateSlidesPosition": {"slideObjectIds": [o], "insertionIndex": k}} for k, o in enumerate(keep)]  # 並べ替えは 1 枚ずつ（まとめると元の順に限られる）
        batch(pid, reqs)
    except BaseException:
        trash(pid)
        raise
    print(f"https://docs.google.com/presentation/d/{pid}/edit\tpages: {' '.join(pages)}")


def cmd_jp(src, pairs=None):
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    reqs = [{"replaceAllText": {"containsText": {"text": a, "matchCase": True}, "replaceText": b}}
            for a, b in (json.load(open(pairs, encoding="utf-8")) if pairs else [])]
    font = {"style": {"fontFamily": lint.FONT}, "fields": "fontFamily", "textRange": {"type": "ALL"}}
    for s in p["slides"]:
        for e, _ in lint.flatten(s.get("pageElements", [])):
            if e.get("shape", {}).get("text"):
                reqs.append({"updateTextStyle": {"objectId": e["objectId"], **font}})
            for r, row in enumerate(e.get("table", {}).get("tableRows", [])):
                for c, cell in enumerate(row.get("tableCells", [])):
                    if cell.get("text"):
                        reqs.append({"updateTextStyle": {"objectId": e["objectId"], "cellLocation": {"rowIndex": r, "columnIndex": c}, **font}})
    batch(pid, reqs)
    print(f"{len(reqs)} 件（置き換えと書体）")


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for n, o in enumerate("abc", 1):
            open(f"{d}/p-{n:02d}.webp", "w").write(o)
        want, moved = reuse_shots(d, ["c", "x", "a"], ["a", "b", "c"])  # c を先頭に、b を消して x を足した
        assert want == [2] and moved == 2 and sorted(os.listdir(d)) == ["p-01.webp", "p-03.webp"]
        assert open(f"{d}/p-01.webp").read() == "c" and open(f"{d}/p-03.webp").read() == "a"
    check_selftest()
    wording_selftest()
    hits = by_page([(lint.TWO_LINES, "p3 の見出し: 「x」"), ("絵文字", "p12: 「✅」"), ("扉", "13 枚。…")])
    assert hits == {3: [f"[{lint.TWO_LINES}] p3 の見出し: 「x」（見積もり）"], 12: ["[絵文字] p12: 「✅」"]}
    print("selftest ok")


def check_selftest():
    """cmd_check の画像と記録（shots.json）: 取る途中で止まっても、次の check が別のページの画像を使わない。Google は呼ばない。"""
    import contextlib, io, shutil
    pid, deck, fail = "zzselftest", {"ids": ["a", "b", "c"]}, set()
    d = f"/tmp/slides_{pid[:8]}"
    real = {k: globals()[k] for k in ("request", "save_thumb", "revision")}, lint.lint_slides, subprocess.run

    def thumb(_, obj, out):
        if obj in fail:
            raise gapi.ApiError("429")
        open(out, "w").write(obj)

    globals().update(request=lambda m, u, *a, **k: {"appProperties": {STAMP: "rev"}} if "/files/" in u else
                     {"title": "tmp", "slides": [{"objectId": o} for o in deck["ids"]]}, save_thumb=thumb, revision=lambda pid: "rev")
    nowebp = []  # 中身があれば、sheet.py --webp が失敗する（uv か Pillow がない）

    def run(cmd, **_):  # sheet.py --webp の代わりに、名前だけ変える（box_pad.py は何も出さない）
        if "--webp" in cmd and nowebp:  # 置き換えの途中で止まった形（1 枚目は WebP にして PNG を消した）
            os.replace(cmd[cmd.index("--webp") + 1], cmd[cmd.index("--webp") + 1][:-4] + ".webp")
            return subprocess.CompletedProcess(cmd, 1, "", "Pillow がない")
        for f in cmd[cmd.index("--webp") + 1:] if "--webp" in cmd else []:
            os.replace(f, f[:-4] + ".webp")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    lint.lint_slides, subprocess.run = lambda *a, **k: 0, run
    shutil.rmtree(d, ignore_errors=True)
    page = lambda n: open(f"{d}/p-{n:02d}.webp").read()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cmd_check(pid)
            assert [page(n) for n in (1, 2, 3)] == ["a", "b", "c"]
            deck["ids"], fail = ["c", "x", "a"], {"x"}  # 並べ替えて 1 枚足し、その画像を取るところで止まる
            try:
                cmd_check(pid)
                raise AssertionError("止まらなかった")
            except gapi.ApiError:
                pass
            fail.clear()
            cmd_check(pid)
            assert json.load(open(f"{d}/changed.json"))["pages"][0]["page"] == 2 and [page(n) for n in (1, 2, 3)] == ["c", "x", "a"]
            open(f"{d}/shots.json", "w").write("[")  # 書きかけで切れた記録でも止まらず、全ページを取る
            cmd_check(pid)
            assert len(json.load(open(f"{d}/changed.json"))["pages"]) == 3
            deck["ids"] = ["c", "x"]
            cmd_check(pid, "--pages", "1")  # ページの数が変わったら、--pages でも全ページ
            assert [x["page"] for x in json.load(open(f"{d}/changed.json"))["pages"]] == [1, 2]
            cmd_check(pid)
            assert json.load(open(f"{d}/changed.json"))["pages"] == []
            stamped = request
            for req in (stamped, lambda m, u, *a, **k: {} if "/files/" in u else stamped(m, u)):  # リビジョンの一覧を読めない（編集できない人）なら、組んだリビジョンを残していなくても、止まらず全ページを取る
                globals().update(revision=lambda pid: (_ for _ in ()).throw(gapi.ApiError("403")), request=req)
                cmd_check(pid)
                assert len(json.load(open(f"{d}/changed.json"))["pages"]) == 2
            files = lambda: sorted(f for f in os.listdir(d) if f.startswith("p-"))
            globals().update(revision=lambda pid: "rev", request=stamped)
            cmd_check(pid, "--all")
            nowebp.append(1)  # WebP にできなければ止まらず、この回のページは画像なし。--pages で残っていた古い画像も消す
            cmd_check(pid, "--pages", "2")
            assert [(x["page"], x["image"]) for x in json.load(open(f"{d}/changed.json"))["pages"]] == [(2, None)] and files() == ["p-01.webp"]
            assert json.load(open(f"{d}/shots.json")) == ["c", None]  # 記録に入れないので、次の check が取り直す
            nowebp.clear()
            cmd_check(pid)
            assert [x["page"] for x in json.load(open(f"{d}/changed.json"))["pages"]] == [2] and files() == ["p-01.webp", "p-02.webp"]
    finally:
        globals().update(real[0])
        lint.lint_slides, subprocess.run = real[1], real[2]
        shutil.rmtree(d, ignore_errors=True)


def wording_selftest():
    """cmd_wording: Google の資料の文とノートを集め、ページのファイルと JSON の場所に戻し、画面で直したことと画像を取っていないことを通らない理由にする。Google は呼ばない。"""
    import shutil, tempfile
    from slides import EMU
    sid = f"x_k{page_key('p01')}h{'0' * 16}"
    shape = lambda oid, y, *lines: {"objectId": oid, "size": {"width": {"magnitude": 8 * EMU, "unit": "EMU"}, "height": {"magnitude": 1 * EMU, "unit": "EMU"}},
                                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0.5 * EMU, "translateY": y * EMU, "unit": "EMU"},
                                    "shape": {"shapeType": "TEXT_BOX", "text": {"textElements": [x for t in lines for x in ({"paragraphMarker": {"style": {}}},
                                              {"textRun": {"content": t + "\n", "style": {"fontFamily": lint.FONT, "fontSize": {"magnitude": 14, "unit": "PT"}}}})]}}}
    deck = {"title": "tmp", "masters": [{"objectId": "m", "pageProperties": {"colorScheme": {"colors": []}}}], "layouts": [], "slides": [
        {"objectId": sid, "pageElements": [shape("t1", 0.6, "4 つの構成の比べ"), shape("b1", 2, "顧客は「前の版の比べ」と言った", "出典: 前の版の比べ", "Run the build")],
         "slideProperties": {"masterObjectId": "m", "notesPage": {"notesProperties": {"speakerNotesObjectId": "n"}, "pageElements": [shape("n", 0, "前の版の手順を話す") | {"objectId": "n"}]}}}]}
    state = {"rev": "rev", "stamp": "rev"}
    real = {k: globals()[k] for k in ("request", "built", "unbuilt")}, lint.workspace_checks, lint.segment
    globals()["unbuilt"] = lambda src: state.get("unbuilt", [])
    globals().update(request=lambda m, u, *a, **k: {"appProperties": {STAMP: state["stamp"]}} if "/files/" in u else deck, built=lambda pid: state["rev"])
    lint.workspace_checks, lint.segment = (lambda *a: 0), (lambda ts: {t: set(range(len(t) + 1)) for t in ts})
    cwd, d, shots = os.getcwd(), tempfile.mkdtemp(), "/tmp/slides_zzwordin/shots.json"
    shutil.rmtree(os.path.dirname(shots), ignore_errors=True)
    try:
        os.makedirs(f"{d}/build")
        os.makedirs(f"{d}/build/_old")
        json.dump({"kind": "page", "title": "4 つの構成の比べ"}, open(f"{d}/build/_old/p01.json", "w", encoding="utf-8"), ensure_ascii=False)  # 同じ名前の控え（直下のファイルを先に取る）
        json.dump({"kind": "page", "title": "**4 つの構成の比べ**", "body": {"items": ["顧客は「前の版の比べ」と言った"]}, "speakerNotes": "前の版の手順を話す"},
                  open(f"{d}/build/p01.json", "w", encoding="utf-8"), ensure_ascii=False)
        os.chdir(f"{d}/build")
        with contextlib.redirect_stdout(io.StringIO()):
            assert _exit(lambda: cmd_wording("zzwording")) == 1
            st = wording.load(d)
            fs = {f["rule"]: f for f in st["last"]["findings"]}
            assert set(fs) == {"動詞を名詞にした語", "直訳の語"} and fs["動詞を名詞にした語"]["file"] == "p01.json" and fs["動詞を名詞にした語"]["loc"] == "title"
            assert fs["直訳の語"]["where"] == "p1 ノート" and fs["直訳の語"]["loc"] == "speakerNotes"  # ノートも点検し、JSON の場所に戻す。かぎかっこの中・出典の行・英字だけの文は見ない
            assert any("画像を取っていない" in x for x in st["last"]["problems"]) and "build/p01.json" in st["last"]["files"]
            os.makedirs(os.path.dirname(shots))
            json.dump([sid], open(shots, "w"))
            wording.decide(d, "keep", [f["id"] for f in fs.values()], "selftest")
            assert _exit(lambda: cmd_wording("zzwording")) == 0 and wording.load(d)["summary"]["状態"] == "済み"
            state["unbuilt"] = ["手元のページの JSON に、組んでいない直しがある"]  # 組んだあとに手元だけ直した（Google は前のまま）
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and "手元のページの JSON に、組んでいない直しがある" in wording.load(d)["last"]["problems"]
            state["unbuilt"] = []
            assert _exit(lambda: cmd_wording("zzwording")) == 0
            state["rev"] = "rev2"  # 組んだあとに画面で直された
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and any("slides.py build で組んだリビジョンでない" in x for x in wording.load(d)["last"]["problems"])
            # unbuilt は slides.py plan の出力を読む（ページの直しとノートの直しを分けて出す。plan が止まったら通さない）
            globals()["unbuilt"] = real[0]["unbuilt"]
            saved_run = subprocess.run
            for out_, want in (('{"rebuild": [], "frozen": [], "remove": 0, "moves": 0, "theme": [], "notes": []}', []),
                               ('{"rebuild": [], "frozen": [], "remove": 0, "moves": 0, "theme": [], "notes": [1, 3]}', ["組んでいないノートの直しがある（slides.py plan: p1, p3）"]),
                               ('{"rebuild": [2], "frozen": [], "remove": 0, "moves": 0, "theme": [], "notes": null}', ["手元のページの JSON に、組んでいない直しがある（slides.py plan: ページ p2）"])):
                subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, 0, out_ + "\n", "")
                try:
                    assert [x.split("。")[0] for x in unbuilt("zzwording")] == want, unbuilt("zzwording")
                finally:
                    subprocess.run = saved_run
            subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "plan できない")
            try:
                assert any("plan が止まり" in x for x in unbuilt("zzwording"))
            finally:
                subprocess.run = saved_run
        os.chdir(d)
        assert "build/ で回す" in str(_exit(lambda: cmd_wording("zzwording"), message=True))
    finally:
        os.chdir(cwd)
        globals().update(real[0])
        lint.workspace_checks, lint.segment = real[1], real[2]
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(os.path.dirname(shots), ignore_errors=True)


def _exit(fn, message=False):
    """fn() の終わり方: sys.exit の値（message なら文）か、止まらなければ 0。"""
    try:
        fn()
    except SystemExit as e:
        return e.code if not message else str(e)
    return 0


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if len(sys.argv) < 3 or "cmd_" + sys.argv[1] not in globals():
        sys.exit(__doc__)
    globals()["cmd_" + sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    run(main)
