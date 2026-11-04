#!/usr/bin/env python3
"""Google Slides の決まった操作（作るのは slides.py。ここは確かめると流用）。
usage:
  gslides.py check  <URL か ID> [--talk] [--all | --pages 3,5]   組んだあとの確認。JSON・テキスト・lint と、前に取ったときから変わったページの画像（p-NN.webp）を /tmp/slides_<ID の先頭 8 字>/ に出し、
                   画像で箱の下の余白を測る（box_pad.py）。取ったページと指摘を changed.json に書く。--all で全ページの画像（/deck-review の前などの区切り）
  gslides.py wording <URL か ID>                  保存した資料との照合（build/ で回す。日本語の点検そのものは組む前に slides.py wording）。Google に保存された資料の文とノートが
                   点検した文と同じか、組んだリビジョンか、組んだあとの画像を check で取ったか、組んでいない直しがないかを確かめ、wording.json に残す（lint.md の「Japanese check」）
  gslides.py pages  <URL か ID>                    ページ番号・objectId・最初の文字を一覧にする
  gslides.py thumb  <URL か ID> <ページ番号> <出力.png>   Google が描いたページの画像（1600 × 900）を保存する
  gslides.py export <URL か ID> <出力.pptx>          pptx で書き出す（Drive に置かれた pptx はそのまま落とす）。名前と更新日も出す（references.md に書く）
  gslides.py keep   <URL か ID> <Drive のフォルダ> <Drive 上の名前> <ページ番号 ...>   複製して、指定したページだけをその順に残す（流用の段階 1）
  gslides.py jp     <URL か ID> [置き換え.json]     すべての文字を Noto Sans JP にし、置き換え（[["元の文", "訳した文"], …]）を入れる（keep で作った複製に使う）
python3 gslides.py --selftest で自己確認。
認証は gapi.py（環境変数 GOOGLE_OAUTH_ACCESS_TOKEN か、gcloud の ADC のファイル）。401・403 なら desk-init の doctor.py で確かめる。"""
import contextlib, glob, io, json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True  # scripts/ に __pycache__ を残さない
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi, lint, textlint, wording
from slides import STAMP, page_numbers, revision, slide_units
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
            print(f"\n（ページの画像を WebP にできなかったので、この回に取ったページの画像はない: {conv.stderr.strip()[-300:]}。uv が要る。desk-init の doctor.py で確かめる）")
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


def unbuilt(src):
    """手元の原稿に、まだ組んでいない直しがあるか: 通らない理由の文の並び（なければ []）。照合した Google の資料と、点検した手元のファイルを結び付けるため。
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
                   + "）。slides.py wording で点検してから slides.py build で組み、check で画像を見てから回す（組んでいない原稿を、保存した資料と照合済みにしない）")
    if x.get("notes"):
        out.append(f"組んでいないノートの直しがある（slides.py plan: {', '.join(f'p{n}' for n in x['notes'][:12])}）。slides.py wording で点検してから slides.py build で組んで回す")
    return out


def cmd_wording(src):
    """slides-lint-035 の最後の照合（保存した資料との照合）。日本語の点検そのもの（slides.py wording）は組む前のページの JSON で回し、ここでは Google に保存された
    資料（presentations.get）の文とノートが、点検した文と同じかを確かめる（同じ集め方の slides.slide_units）。通らない理由: 点検が済んでいない・点検のあとに
    原稿のファイルが変わった、保存した文が点検した文と違う（画面で直されたか、組んでいない）、組んだリビジョンでない、組んだあとのページの画像を check で取っていない、
    手元に組んでいない直しがある（slides.py plan。ノートも）。記録は wording.json の照合（saved）で、点検（last）とは別の事実。"""
    if os.path.basename(os.getcwd()) != "build":
        sys.exit("wording は資料の build/ で回す（資料のフォルダの wording.json の点検と比べる）")
    pid = file_id(src)
    p = request("GET", f"{SLIDES}/{pid}")
    rev, stamp = built(pid), request("GET", f"{DRIVE}/files/{pid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(STAMP)
    problems = []
    if rev is None or rev != stamp:
        problems.append("slides.py build で組んだリビジョンでない（画面で直されたか、ほかの道具で変えた）。直しをページの JSON に写し、slides.py wording で点検してから組み直す")
    ids = [s["objectId"] for s in p["slides"]]
    try:
        shots = json.load(open(f"/tmp/slides_{pid[:8]}/shots.json"))
    except (OSError, ValueError):
        shots = []
    if miss := [n for n, o in enumerate(ids, 1) if n > len(shots) or shots[n - 1] != o]:
        problems.append(f"組んだあとの画像を取っていないページ: {', '.join(f'p{n}' for n in miss[:12])}{' ほか' if len(miss) > 12 else ''}"
                        f"（gslides.py check {src} で取り、直したページの画像を見てから回す）")
    problems += unbuilt(src)
    if not wording.verify(os.path.dirname(os.getcwd()), f"https://docs.google.com/presentation/d/{pid}/edit", rev, slide_units(p), problems, "slides.py wording"):
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
    """cmd_wording（保存した資料との照合）: 点検した文と保存した文が同じで、組んだリビジョンで、画像を取っていて、組んでいない直しがないときだけ通す。Google は呼ばない。"""
    import copy, shutil, tempfile
    from slides import EMU
    shape = lambda oid, y, *lines: {"objectId": oid, "size": {"width": {"magnitude": 8 * EMU, "unit": "EMU"}, "height": {"magnitude": 1 * EMU, "unit": "EMU"}},
                                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0.5 * EMU, "translateY": y * EMU, "unit": "EMU"},
                                    "shape": {"shapeType": "TEXT_BOX", "text": {"textElements": [x for t in lines for x in ({"paragraphMarker": {"style": {}}},
                                              {"textRun": {"content": t + "\n", "style": {"fontFamily": lint.FONT, "fontSize": {"magnitude": 14, "unit": "PT"}}}})]}}}
    sid = "x_k0000h0000"
    deck = {"title": "tmp", "masters": [{"objectId": "m", "pageProperties": {"colorScheme": {"colors": []}}}], "layouts": [], "slides": [
        {"objectId": sid, "pageElements": [shape("t1", 0.6, "4 つの構成の比べ"), shape("b1", 2, "顧客は「前の版の比べ」と言った", "出典: 前の版の比べ", "Run the build")],
         "slideProperties": {"masterObjectId": "m", "notesPage": {"notesProperties": {"speakerNotesObjectId": "n"}, "pageElements": [shape("n", 0, "前の版の手順を話す") | {"objectId": "n"}]}}}]}
    saved = {"deck": deck}
    state = {"rev": "rev", "stamp": "rev"}
    real = {k: globals()[k] for k in ("request", "built", "unbuilt")}
    globals()["unbuilt"] = lambda src: state.get("unbuilt", [])
    globals().update(request=lambda m, u, *a, **k: {"appProperties": {STAMP: state["stamp"]}} if "/files/" in u else saved["deck"], built=lambda pid: state["rev"])
    cwd, d, shots = os.getcwd(), tempfile.mkdtemp(), "/tmp/slides_zzwordin/shots.json"
    shutil.rmtree(os.path.dirname(shots), ignore_errors=True)
    try:
        os.makedirs(f"{d}/build")
        open(f"{d}/build/p01.json", "w").write("{}")
        os.chdir(f"{d}/build")
        with contextlib.redirect_stdout(io.StringIO()):
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and any("点検を回していない" in x for x in wording.load(d)["saved"]["problems"])  # 点検の前に照合だけを済みにしない
            units = slide_units(deck)  # 点検（slides.py wording）が手元で集めた文の代わり（集め方は同じ）
            assert {u["kind"] for u in units} == {"本文", "ノート"} and "出典: 前の版の比べ" not in [u["text"] for u in units]
            wording.run(d, "slides", units, wording.input_files(["p01.json"]), (), "slides.py wording", "build/deck.json")
            wording.decide(d, "keep", [f["id"] for f in wording.load(d)["last"]["findings"]], "selftest")
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and any("画像を取っていない" in x for x in wording.load(d)["saved"]["problems"])
            os.makedirs(os.path.dirname(shots))
            json.dump([sid], open(shots, "w"))
            assert _exit(lambda: cmd_wording("zzwording")) == 0 and wording.saved_state(wording.load(d), d) == "済み"
            assert wording.load(d)["summary"]["状態"] == "済み"  # 照合は点検の記録を変えない
            saved["deck"] = copy.deepcopy(deck)  # 組んだあとに画面でノートを直した（リビジョンの印は同じでも、文で分かる）
            saved["deck"]["slides"][0]["slideProperties"]["notesPage"]["pageElements"][0]["shape"]["text"]["textElements"][1]["textRun"]["content"] = "前の版の手順を飛ばす\n"
            assert _exit(lambda: cmd_wording("zzwording")) == 1
            bad = " ".join(wording.load(d)["saved"]["problems"])
            assert "p1 ノート: 保存した資料にだけある「前の版の手順を飛ばす」" in bad and "p1 ノート: 点検した文にだけある「前の版の手順を話す」" in bad
            saved["deck"] = deck
            state["unbuilt"] = ["手元のページの JSON に、組んでいない直しがある"]  # 組んだあとに手元だけ直した（Google は前のまま）
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and "手元のページの JSON に、組んでいない直しがある" in wording.load(d)["saved"]["problems"]
            state["unbuilt"] = []
            open("p01.json", "w").write('{"直した": 1}')  # 点検のあとに原稿を直した
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and any("点検のあとに変わったファイル: build/p01.json" in x for x in wording.load(d)["saved"]["problems"])
            open("p01.json", "w").write("{}")
            assert _exit(lambda: cmd_wording("zzwording")) == 0
            state["rev"] = "rev2"  # 組んだあとに画面で直された
            assert _exit(lambda: cmd_wording("zzwording")) == 1 and any("slides.py build で組んだリビジョンでない" in x for x in wording.load(d)["saved"]["problems"])
            # unbuilt は slides.py plan の出力を読む（ページの直しとノートの直しを分けて出す。plan が止まったら通さない）
            globals()["unbuilt"] = real["unbuilt"]
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
        globals().update(real)
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
