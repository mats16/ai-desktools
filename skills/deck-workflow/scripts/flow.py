#!/usr/bin/env python3
"""usage: flow.py <資料のフォルダ>     手順ごとの記録と、ファイルと台帳から分かる事実
       flow.py record <資料のフォルダ> <手順の番号> <始めた|済んだ|飛ばした|止まった> [--out <名前>=<値> ...] [--note <ひとこと>] [--next <次にすること>] [--by <誰>]
                                    手順の記録を資料のフォルダの progress.jsonl に 1 行足す（使うか、いつ使うかはエージェントが決める）
       （--selftest で自己確認）
記録は資料を作るワークフロー（deck-workflow）のもので、道具（slides.py・docs.py など）は書かない。項目と値は deck-workflow の progress.md。
表示は、手順ごとの最後の記録と、ファイルと台帳から分かる事実を並べる。手順が済んだかは、記録だけが言い、ファイルの形からは決めない
（予定の枚数、どの URL が組んだ資料か、節の中身が決まりか下書きかは、ファイルからは決めきれないため。2026-11-01 の「決めたこと」）。
事実は手順ごとに調べ、崩れた手順だけを「調べられない」と出して先へ進む。標準ライブラリだけ。"""
import argparse, contextlib, functools, io, json, posixpath, re, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import desk, ledger, refs  # noqa: E402  ワークスペースの探し方・決まりの台帳・出典の台帳

try:
    import fcntl
except ImportError:  # shortcut: Windows では鍵をかけない（ledger.py と同じ）。子が同時に書いて行が壊れたら msvcrt で鍵をかける
    fcntl = None

PROGRESS = "progress.jsonl"  # 資料のフォルダに置く手順の記録。足すだけで書き換えない。build/ を消しても残る
STEPS = ("1–4 準備", "5 構成", "6 代表の 3 枚", "7 ページを書く", "8 全体を組む", "9 /deck-review", "10 渡す", "11 片付け")
STATUSES = ("始めた", "済んだ", "飛ばした", "止まった")  # 止まったは、ユーザーの答えか別の作業を待つもの
URL = re.compile(r"(?<![\w.-])(?:docs|drive)\.google\.com/(?:a/[\w.-]+/|u/\d+/)?(?P<kind>presentation|document|spreadsheets|file)/(?:u/\d+/)?d/(?P<id>[\w-]+)", re.ASCII)  # /u/0/ は種類の前にも後にも付く
KINDS = {"presentation": "スライド", "document": "文書", "spreadsheets": "表計算", "file": "Drive のファイル"}


def read(p):
    """ファイルの文字。ないか読めなければ None。UTF-8 でない字は置き換える（読めない 1 つのファイルで、全体の報告を止めない）。"""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_json(p, build):
    """(JSON の値, 読めないときの文)。文のパスは build/ から。"""
    where = f"build/{posixpath.relpath(p.as_posix(), build.as_posix())}"
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{where} がない"
    except (OSError, ValueError, RecursionError):  # 深すぎる入れ子も、読めないファイルとして出す
        return None, f"{where} を JSON として読めない"


def listed(build, name="deck.json", seen=frozenset()):
    """deck.json の pages が指すページのファイル（build/ からのパス。pages_<担当>.json は中を開く）。
    pages の中のパスは、それを書いたデッキのファイルのあるフォルダから読む（slides.py の spec_files と同じ）。
    (ファイルの並び〔同じファイルが 2 度出てよい〕, JSON の中に直に書いたページの数, 読めないものの文の並び)。"""
    o, err = read_json(build / name, build)
    pages = o.get("pages") if isinstance(o, dict) else None
    if err or not isinstance(pages, list):
        return [], 0, [err or f"build/{name} の pages が並び（[...]）でない"]
    files, inline, bad = [], 0, []  # 同じページを 2 度並べてもよいので、並びのまま数える
    for x in pages:
        if isinstance(x, dict):
            inline += 1
        elif not isinstance(x, str):
            bad.append(f"build/{name} の pages に、ファイルの名前でもページでもないもの（{x!r}）")
        elif posixpath.isabs(x) or (x := posixpath.normpath(posixpath.join(posixpath.dirname(name), x))) == ".." or x.startswith("../"):
            bad.append(f"build/{name} の pages が build/ の外を指す（{x}）")
        elif x in seen | {name}:
            bad.append(f"build/{name} の pages が自分を指す（{x}）")
        else:
            sub, e = read_json(build / x, build)
            if isinstance(sub, dict) and sub.get("kind") == "deck":  # pages_<担当>.json（slides-pages-031 の形）
                f, i, b = listed(build, x, seen | {name})
                files, inline, bad = files + f, inline + i, bad + b
            else:
                files.append(x)
                if e and (build / x).is_file():
                    bad.append(e)
    return files, inline, bad


def headed(text):
    """[(見出し, 深さ, 本文の行)]。最初の見出しの前の行は、見出し ""・深さ 0 に入れる。``` や ~~~ の囲みの中の # は見出しにしない。"""
    out, fence = [("", 0, [])], None  # fence は開いた囲みの印（``` か ~~~ の並び）
    for line in text.splitlines():
        f = re.match(r" {0,3}(`{3,}|~{3,})(.*)", line)  # 4 字以上の字下げは囲みでない（字下げのコード）
        if f and f.group(1)[0] == "`" and "`" in f.group(2):
            f = None  # ``` のあとに ` のある行は囲みでない（`` ```a``` `` のような文中のコード。CommonMark）
        if f and fence is None:
            fence = f.group(1)
        elif f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not f.group(2).strip():
            fence = None  # 開いたのと同じ字で、同じか長い並びだけが閉じる
        elif fence is None and (m := re.match(r"(#{1,6})\s+(.+)", line)):
            out.append((m.group(2).strip(), len(m.group(1)), []))
            continue
        out[-1][2].append(line)
    return out


def sections(text, title):
    """見出しに title を含む節ごとの (見出し, 本文の行)。本文は、下の深さの見出しの節も含む（「## 3. 書き方の取り決め」も拾う）。"""
    hs, out = headed(text), []
    for i, (h, depth, body) in enumerate(hs):
        if depth and re.search(title, h):
            lines = list(body)
            for _, d2, b2 in hs[i + 1:]:
                if d2 <= depth:
                    break
                lines += b2
            out.append((h, lines))
    return out


def when(ts):
    """ISO 8601 の時刻を UTC の datetime に。読めなければ None。"""
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def short(names, n=8):
    names = sorted(names)
    return ", ".join(names[:n]) + (f" ほか {len(names) - n}" if len(names) > n else "")


def step_of(n):
    """手順の番号（1〜11）→ STEPS の名前。1〜4 は 1 つにまとめる。"""
    n = int(n) if re.fullmatch(r"[0-9]{1,2}", str(n)) else 0
    return STEPS[0] if 1 <= n <= 4 else next((s for s in STEPS[1:] if s.split()[0] == str(n)), None)


def records(folder):
    """(手順の名前 → その手順の記録の並び〔古い順〕, 読めない行の数か、ファイルを読めないときの文)。記録の "_n" は、ファイルの中の何行目か（同じ秒の記録の前後）。"""
    got, bad, p = {}, 0, folder / PROGRESS
    if p.exists() and not p.is_file():
        return {}, f"{PROGRESS} がファイルでない（フォルダなど）"
    text = read(p)
    if text is None and p.exists():
        return {}, f"{PROGRESS} を読めない（読む権限など）"
    for n, line in enumerate((text or "").lstrip("\ufeff").split("\n")):  # エディタが先頭に付ける BOM は外す  # splitlines は U+2028 などでも切り、1 件の記録を 2 つに割る
        try:
            r = json.loads(line)
        except (ValueError, RecursionError):  # 深すぎる入れ子の行も、その行だけを読めないとする
            r = None
        if isinstance(r, dict) and r.get("step") in STEPS and r.get("status") in STATUSES and when(r.get("ts")):
            got.setdefault(r["step"], []).append({**r, "_n": n})
        else:
            bad += bool(line.strip())
    for rs in got.values():
        rs.sort(key=lambda r: (when(r["ts"]), r["_n"]))  # 時刻の順。同じ秒はファイルの順（あとから足した子の記録も時刻で並ぶ）
    return got, bad


def out_arg(s):
    """--out の <名前>=<値>。"""
    k, eq, v = s.partition("=")
    if not (eq and re.fullmatch(r"[\w.-]+", k)):
        raise argparse.ArgumentTypeError(f"--out は <名前>=<値>（url=https://… など。名前は英数字と _ . -）: {s}")
    return k, v


def record(folder, n, status, out=(), note="", next_="", by=""):
    """手順の記録を 1 行足す。足すだけで、前の行は書き換えない（同じ手順は、最後の行が今の状態）。"""
    folder = Path(folder).resolve()
    folder.is_dir() or sys.exit(f"資料のフォルダがない: {folder}")
    step = step_of(n) or sys.exit(f"手順の番号は 1〜11: {n}")
    status in STATUSES or sys.exit(f"状態は {'・'.join(STATUSES)} のどれか: {status}")
    rec = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "step": step, "status": status,
           **({"out": dict(out)} if out else {}), **({"note": note} if note else {}), **({"next": next_} if next_ else {}), **({"by": by} if by else {})}
    p = folder / PROGRESS
    p.exists() and not p.is_file() and sys.exit(f"{p} がファイルでない（フォルダなど）。名前を変えてから回す")
    with p.open("a+b") as f:
        if fcntl:  # 子が同時に書いても行が混ざらないように（長い --note は 1 回の書き込みで収まらない）
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0, 2)
        torn = f.tell() > 0 and (f.seek(-1, 2), f.read(1))[1] != b"\n"  # 途中で切れた最後の行に、新しい記録をつなげない（鍵をかけてから見る）
        f.write((("\n" if torn else "") + json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
    return rec


def shown(r):
    """記録の 1 行の見せ方。"""
    out = "".join(f" {k}={v}" for k, v in (r.get("out") or {}).items()) if isinstance(r.get("out"), dict) else ""
    return (f"記録: {r['status']} {r['ts']}" + (f"（{r['by']}）" if r.get("by") else "") + out
            + (f"。{r['note']}" if r.get("note") else "") + (f"。次: {r['next']}" if r.get("next") else ""))


def google_urls(folder, o, text):
    """構成案と社内メモ_*.md の Google の URL。{(種類, ID): (最初に見つけた書き方, 書いた場所の並び)}。同じファイルは ID で 1 つにまとめる（/a/<ドメイン>/・/u/0/ の書き方も）。"""
    places = [(o.name if o else "", h, body) for h, _, body in headed(text)] + [(p.name, "", (read(p) or "").splitlines()) for p in sorted(folder.glob("社内メモ_*.md"))]
    where = {}
    for f, h, body in places:
        for m in URL.finditer("\n".join(body)):
            where.setdefault((m["kind"], m["id"]), (m.group(0), []))[1].append(f + ("・" + h if h else ""))
    return where


def facts(folder, ws):
    """([(手順, [事実の文])], 記録と突き合わせるもの {"files": build/ のファイルの時刻, "ids": Google の URL})。手順ごとに調べ、崩れたら（読めないファイル・思わない形の値）、その手順に「調べられない」と出して次へ進む。
    壊れ方を 1 つずつ数え上げず、どの壊れ方でも 1 つの手順だけで止まるようにする。手順が済んだかは決めない。"""
    build, name, out = folder / "build", folder.name, []

    @functools.cache
    def outline():
        o = refs.outline(folder)
        return o, ((read(o) or "") if o else "")

    @functools.cache
    def table():
        """(出典の表の行, refs.py check の形の誤りの数)。UTF-8 でない構成案・references.md は、ここで崩れる（refs は字を置き換えずに読む）。"""
        with contextlib.redirect_stdout(io.StringIO()):
            errs = refs.check(folder)
        return refs.facts(folder), errs

    @functools.cache
    def changed():
        """build/ のページの元（.json・doc.md・pages.py）の [(最後に変えた時刻, build/ からのパス)]。
        画像・控え（*.bak*）・. で始まるファイル・__pycache__ は見ない（道具が書くもので、ページの中身の変更でない）。"""
        source = lambda p: p.suffix == ".json" or p.name in ("doc.md", "pages.py")
        files = [p for p in build.rglob("*") if p.is_file() and source(p) and ".bak" not in p.name
                 and not any(x.startswith(".") or x == "__pycache__" for x in p.relative_to(build).parts)] if build.is_dir() else []
        return [(p.stat().st_mtime, p.relative_to(build).as_posix()) for p in files]

    @functools.cache
    def ledger_facts():
        """(取り込んだレビューの行, 戻し先が「未」の指摘の数)。ワークスペースがないか、その外の資料なら None。"""
        if not ws or not folder.is_relative_to(ws):
            return None
        key = ledger.rel(ws, folder)
        mine = [r for r in ledger.records(ws) if isinstance(r, dict) and r.get("deck") == key and r.get("kind") in ("review", "harness")]
        return mine, sum(isinstance(c, dict) and c.get("deck") == key and c.get("to") == "未" for c in ledger.state(ws)[0].values())

    no_ledger = "ワークスペースが見つからない（台帳を読めない）" if not ws else "資料のフォルダがワークスペースの外（台帳を引けない）"

    def prep():
        src = read(folder / "references.md")
        return ["references.md がない" if src is None else f"references.md の出典 {len(refs.sources(src)[1])} 件"]

    def plan():
        o, text = outline()
        items = [f"構成案: {o.name}" if o else "構成案*.md がない"]
        if o:
            found = (("使う決まり", r"使う決まり"), ("テーマ:", r"テーマ\s*[:：]"), ("言語:", r"言語\s*[:：]"))
            items.append("・".join(f"「{k}」{'あり' if re.search(p, text) else 'なし'}" for k, p in found))
            items.append(f"出典の照合の 1 回目（sources_{name}_1）を構成案に{'書いた' if f'sources_{name}_1' in text else '書いていない'}")
        rows, errs = table()
        return items + [f"出典の表 {len(rows)} 行・refs.py check の形の誤り {errs} 件"]

    def rules():
        secs = sections(outline()[1], r"書き方の(取り)?決め")  # 2026-11-01 より前の構成案は「書き方の決め」
        return [f"「{h}」の節: 空でない行 {sum(bool(x.strip()) for x in body)}" for h, body in secs] or ["「書き方の取り決め」の節がない"]

    def pages():
        items, written = [], {p.name for p in build.glob("p*.json") if re.fullmatch(r"p[0-9]+\.json", p.name)}  # p03_old.json などの控えは数えない
        if (build / "pages.py").is_file():
            items.append("build/pages.py がある（前の書き方。ページは数えない）")
        if (build / "deck.json").is_file() or written:
            files, inline, bad = listed(build)
            have = {x for x in files if (build / x).is_file()}
            items.append(f"deck.json が並べるページ {sum(x in have for x in files) + inline} 枚・p<番号>.json {len(written)} 個")
            items += bad
            if not bad and (left := written - set(files)):
                items.append(f"deck.json の pages にない p<番号>.json: {short(left)}")
            if gone := set(files) - have:
                items.append(f"deck.json の pages が指すのにないファイル: {short(gone)}")
        if (doc := read(build / "doc.md")) is not None:
            items.append(f"build/doc.md {len(doc.strip())} 字")
        return items or ["build/ にページがない"]

    @functools.cache
    def gurls():
        return google_urls(folder, *outline())

    def urls():
        found = [f"{KINDS[k]} {u}（{'、'.join(dict.fromkeys(w))}）" for (k, _), (u, w) in gurls().items()]
        return found[:6] + ([f"ほか {len(found) - 6} 件（構成案と社内メモを grep -n docs.google.com で見る）"] if len(found) > 6 else []) or ["構成案にも社内メモにも Google の URL がない"]

    def review():
        got = ledger_facts()
        items = [no_ledger] if got is None else [f"台帳に取り込んだレビュー {len(got[0])} 行" + (
            f"・最後 {t:%Y-%m-%d %H:%M:%S}Z" if (t := max((x for r in got[0] if (x := when(r.get("ts")))), default=None)) else "")]
        c = max(changed(), default=None)
        items.append(f"build/ の最後の変更: {datetime.fromtimestamp(c[0], timezone.utc):%Y-%m-%d %H:%M:%S}Z（{c[1]}）" if c else "build/ にページの元のファイル（.json・doc.md・pages.py）がない")
        return items + [f"出典の照合の 2 回目（sources_{name}_2）を構成案に{'書いた' if f'sources_{name}_2' in outline()[1] else '書いていない'}"]

    def deliver():
        kinds = {}
        for r in table()[0]:
            k = {"-": "空か -", "?": "読めない値"}.get(s := refs.state(r["確認"]), s)
            kinds[k] = kinds.get(k, 0) + 1
        return ["出典の表の確認: " + "・".join(f"{k} {n}" for k, n in kinds.items())] if kinds else ["出典の表がない"]

    def clean():
        got = ledger_facts()
        return [no_ledger] if got is None else [f"戻し先が「未」の指摘 {got[1]} 件"]

    def guarded(fn):
        try:
            return fn()
        except (Exception, SystemExit) as e:  # noqa: BLE001  どの壊れ方でも（refs・ledger の sys.exit も）、その手順だけを「調べられない」にして先へ進む
            return [f"調べられない（{type(e).__name__}: {e}）"]

    for step, fn in zip(STEPS, (prep, plan, rules, pages, urls, review, deliver, clean)):
        out.append((step, guarded(fn)))
    extra = {}  # 記録と突き合わせるもの。調べられなければ入れない（その手順の事実に「調べられない」と出ている）
    with contextlib.suppress(Exception, SystemExit):
        extra["files"] = changed()
    with contextlib.suppress(Exception, SystemExit):
        extra["ids"] = {i for _, i in gurls()}
    return out, extra


def report(folder):
    folder = Path(folder).resolve()
    folder.is_dir() or sys.exit(f"資料のフォルダがない: {folder}")
    try:
        found = desk.locate(folder)  # 回した場所でなく、資料のフォルダのワークスペース
    except SystemExit:  # 読めない ~/.desk.toml。記録とファイルの事実は、台帳がなくても出す
        found = None
    ws = found[1] if found else None
    try:
        recs, bad = records(folder)
    except (Exception, SystemExit) as e:  # noqa: BLE001
        recs, bad = {}, f"{PROGRESS} を調べられない（{type(e).__name__}: {e}）"
    rows, extra = facts(folder, ws)
    files, ids = extra.get("files"), extra.get("ids")
    print(f"資料: {ledger.rel(ws, folder) if ws else folder}")
    every = sorted((r for rs in recs.values() for r in rs), key=lambda r: (when(r["ts"]), r["_n"]))
    if every:
        print(f"最後の記録: {every[-1]['step']}。{shown(every[-1])}")
    elif not isinstance(bad, str):
        print(f"記録なし（{PROGRESS} に読める記録がない）" if (folder / PROGRESS).exists() else f"記録なし（{PROGRESS} がない。手順が済んだかは、記録とファイルを読んで決める）")
    if bad:
        print(f"{PROGRESS} に読めない行 {bad}" if isinstance(bad, int) else bad)
    for step, items in rows:
        print(f"\n{step}")
        rs = recs.get(step, [])
        if rs:
            r = rs[-1]
            print(f"  - {shown(r)}" + (f"（この手順の記録 {len(rs)} 件）" if len(rs) > 1 else ""))
            at = when(r["ts"]).timestamp()
            end = min((x for s in STEPS[STEPS.index(step) + 1:] for y in recs.get(s, []) if (x := when(y["ts"]).timestamp()) >= at), default=float("inf"))
            done = r["status"] == "済んだ" and STEPS.index(step) >= STEPS.index("7 ページを書く")  # 6 までが済んだあとにページを書くのは、ふつうの流れ
            if done and (late := [f for m, f in files or [] if at + 1 <= m < end]):  # 時刻は秒まで。あとの手順を始めてからの変更は、その手順のもの
                print(f"  - 済んだと記録したあと、次の手順の記録より前に build/ が変わった: {short(late)}（そのあとにまた変えたファイルは見えない）")
            u = r["out"].get("url") if isinstance(r.get("out"), dict) else None
            if step == "8 全体を組む" and isinstance(u, str) and ids is not None:
                if not (m := URL.search(u)):
                    print("  - 記録の url から Google のファイルの ID を読めない（突き合わせない）")
                elif m["id"] not in ids:
                    print("  - 記録の url の ID が構成案にも社内メモにもない")
        print(*(f"  - {x}" for x in items), sep="\n")
    print("\nコマンドで確かめる（結果は会話の中にしかない）: slides.py lint・gslides.py check <URL> --all（slides-build）か docs.py check <URL>（docs-build）の要修正、"
          f"refs.py check {folder} --fetch（10 の前）")
    return rows


def _exits(fn):
    """fn() が止まる（SystemExit）ときの言葉。"""
    try:
        fn()
    except SystemExit as e:
        return str(e)
    raise AssertionError("止まらなかった")


def selftest():
    import os, tempfile
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d).resolve()
        (ws / "desk.toml").write_text("")
        f = ws / "Customers" / "acme" / "deck_202611"
        (f / "build").mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            quiet = lambda: contextlib.redirect_stdout(io.StringIO())
            got = lambda g=f, w=ws: {s.split()[0]: "\n".join(x) for s, x in facts(g, w)[0]}

            def page(g=f):
                with quiet() as o:
                    report(g)
                return o.getvalue()

            s = got()
            assert "references.md がない" in s["1–4"] and "構成案*.md がない" in s["5"] and "build/ にページがない" in s["7"] and "出典の表がない" in s["10"]
            assert "記録なし" in page()
            # 記録: 足すだけで、手順ごとに最後の 1 件が今の状態
            r1 = record(f, 5, "済んだ", [("pages", "20")], "4 つの答えに合意", "代表の 3 枚を組む", "親")
            assert r1["step"] == "5 構成" and r1["out"] == {"pages": "20"} and r1["by"] == "親"
            assert record(f, 3, "飛ばした")["step"] == "1–4 準備"
            for bad in ((12, "済んだ"), ("²", "済んだ"), (8, "終わった")):
                assert "1〜11" in _exits(lambda: record(f, *bad)) or "状態は" in _exits(lambda: record(f, *bad))
            assert out_arg("url=https://x/y?a=b") == ("url", "https://x/y?a=b")
            try:
                out_arg("=x")
                raise AssertionError("通した")
            except argparse.ArgumentTypeError:
                pass
            p = page()
            assert "最後の記録: 1–4 準備。記録: 飛ばした" in p and "記録: 済んだ" in p and "pages=20。4 つの答えに合意。次: 代表の 3 枚を組む" in p and "（親）" in p
            (f / "references.md").write_text("| " + " | ".join(refs.SRC_COLS) + " |\n|" + "---|" * len(refs.SRC_COLS) + "\n"
                                             "| S1 | 製品の docs | https://example.com | 公式 | 2026-10-01 | 2026-11-01 | 可 | 価格 |\n")
            for i in range(1, 13):
                (f / "build" / f"p{i:02d}.json").write_text("{}")
            (f / "build" / "p03_old.json").write_text("{}")  # 控えは数えない
            (f / "build" / "pages_a.json").write_text(json.dumps({"kind": "deck", "pages": [f"p{i:02d}.json" for i in range(4, 13)]}))
            (f / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["./p01.json", "p02.json", "p03.json", {"type": "text"}, "p99.json"]}))
            s = got()
            assert "出典 1 件" in s["1–4"] and "ページ 4 枚・p<番号>.json 12 個" in s["7"]  # ./ を外して数える。直に書いたページも数える。ないファイルは数えない
            assert "pages にない p<番号>.json: p04.json" in s["7"] and "ないファイル: p99.json" in s["7"]
            (f / "構成案.md").write_text("- **使う決まり:** なし\n- テーマ: navy\n/tmp/sources_deck_202611_1.md\n#タグ\n\n## 3. 書き方の取り決め\n\n### デッキで共通\n\n- 見出しは 1 行\n\n"
                                       "````\n```\n# コードの中\n````\n\n作業中: https://docs.google.com/presentation/d/built_1/edit\n\n## 流用元\n\n- https://docs.google.com/presentation/d/reused_1/edit\n"
                                       "- 同じ: https://docs.google.com/presentation/d/reused_1/edit\n\n"
                                       "## 出典の表\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n| F1 | 月 100 円 | 数字 | S1 の価格 | 未 |\n| F2 | 月 200 円 | 数字 | S1 の価格 |  |\n"
                                       "| F3 | x | 数字 | S1 |  |\n")
            (f / "社内メモ_deck.md").write_text("https://docs.google.com/document/d/memo_1/edit\nhttps://docs.google.com/presentation/d/reused_1/edit\n")
            s = got()
            assert "「使う決まり」あり・「テーマ:」あり・「言語:」なし" in s["5"] and "1 回目（sources_deck_202611_1）を構成案に書いた" in s["5"] and "出典の表 3 行" in s["5"]
            assert "「3. 書き方の取り決め」の節: 空でない行 6" in s["6"]  # 番号の付いた見出しも、下の深さの節も、囲みの中の行も節の中（中身が決まりか下書きかは見ない）
            assert "スライド docs.google.com/presentation/d/built_1（構成案.md・デッキで共通）" in s["8"]  # #タグ と囲みの中の # は見出しでない
            assert "reused_1（構成案.md・流用元、社内メモ_deck.md）" in s["8"] and s["8"].count("reused_1") == 1  # 同じ URL は 1 つにまとめる
            assert "未 1" in s["10"] and "空か - 2" in s["10"]
            (f / "社内メモ_urls.md").write_text("".join(f"https://docs.google.com/document/d/many_{i}/edit\n" for i in range(8)))
            assert "ほか 5 件" in got()["8"]
            (f / "社内メモ_urls.md").unlink()
            for bad, want in (('{"pages": ["/etc/hosts", "../x.json"]}', "build/ の外を指す"), ('{"pages": null}', "の pages が並び"),
                              ('{"pages": [1]}', "ファイルの名前でもページでもない"), ('{"pages": ["p01.json",]}', "JSON として読めない")):
                (f / "build" / "deck.json").write_text(bad)
                assert want in got()["7"], bad
            (f / "build" / "pages_c.json").write_text('{"kind": "deck", "pages": null}')
            (f / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["p01.json", "pages_c.json"]}))
            assert "build/pages_c.json の pages が並び" in got()["7"] and "ページ 1 枚" in got()["7"]  # 入れ子の pages_*.json の誤りも、その文で出す
            (f / "build" / "sub").mkdir()
            (f / "build" / "sub" / "pages_s.json").write_text(json.dumps({"kind": "deck", "pages": ["p01.json", "../p02.json", "../../x.json"]}))
            (f / "build" / "sub" / "p01.json").write_text("{}")
            (f / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["sub/pages_s.json"]}))
            s = got()
            assert "ページ 2 枚" in s["7"] and "ないファイル" not in s["7"] and "build/ の外を指す（../x.json）" in s["7"]  # 入れ子のデッキのページは、そのフォルダから読む
            for x in ("pages_s.json", "p01.json"):
                (f / "build" / "sub" / x).unlink()
            (f / "build" / "sub").rmdir()
            (f / "build" / "pages_b.json").write_text("{書きかけ")
            (f / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["pages_b.json", "deck.json"]}))
            assert "build/pages_b.json を JSON として読めない" in got()["7"] and "自分を指す" in got()["7"]
            (f / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["p01.json", "p02.json", "p03.json", "pages_a.json"]}))
            # 台帳
            t = ws / "review.md"
            t.write_text("p1 | 画像 | 5 | 直す | 図 | 直す | 直した | slides-visual-012\n")
            with quiet():
                ledger.main(["review", "--deck", str(f), "--table", str(t)])
                ledger.main(["add", "--deck", str(f), "--quote", "表を分けて"])
            s = got()
            assert "取り込んだレビュー 2 行・最後 " in s["9"] and "build/ の最後の変更: " in s["9"] and "戻し先が「未」の指摘 1 件" in s["11"]
            with open(ws / ".desk" / "ledger.jsonl", "a") as x:
                x.write("[1]\n")
            s = got()
            assert "調べられない" in s["9"] and "調べられない" in s["11"] and "出典 1 件" in s["1–4"]  # JSON だが行の形でない。ほかの手順は出る
            (ws / ".desk" / "ledger.jsonl").write_text("".join(l for l in (ws / ".desk" / "ledger.jsonl").read_text().splitlines(True) if l != "[1]\n"))
            assert when("2026-11-01T00:00:00.5+00:00") and when("壊れた") is None and when("0001-01-01T00:00:00+05:00") is None
            # 済んだと記録したあとの build/ の変更（7 から後の手順だけ）。記録の url が構成案にない
            r8 = record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/elsewhere/edit")])
            old = when(r8["ts"]).timestamp() - 10
            for x in (f / "build").rglob("*"):
                os.utime(x, (old, old))
            p = page()
            assert "済んだと記録したあと" not in p and "記録の url の ID が構成案にも社内メモにもない" in p
            os.utime(f / "build" / "p02.json", (old + 20, old + 20))
            (f / "build" / ".DS_Store").write_bytes(b"")
            os.utime(f / "build" / ".DS_Store", (old + 99, old + 99))
            p = page()
            assert p.count("次の手順の記録より前に build/ が変わった: p02.json") == 1  # 5 の記録には出さない。. で始まるファイルは見ない
            r9 = record(f, 9, "始めた")
            os.utime(f / "build" / "p02.json", (when(r9["ts"]).timestamp() + 5,) * 2)
            assert "済んだと記録したあと" not in page()  # 9 を始めてからの変更は 9 のもの（8 に出さない）
            os.utime(f / "build" / "p02.json", (old, old))  # 未来の時刻のままにすると、あとで足す記録の窓に入る（速く走る CI で落ちた）
            record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/built_1/edit")])
            assert "記録の url" not in page() and "この手順の記録 2 件" in page()
            record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/built/edit")])
            assert "記録の url の ID が構成案にも社内メモにもない" in page()  # built_1 の先頭だけでは合わない
            (f / "社内メモ_urls.md").write_text("".join(f"https://docs.google.com/document/d/many_{i}/edit\n" for i in range(8)) + "https://docs.google.com/presentation/d/built/edit\n")
            assert "ほか" in got()["8"] and "記録の url" not in page()  # 7 つ目より後の URL も、全部の中から探す
            (f / "社内メモ_urls.md").unlink()
            record(f, 8, "済んだ", [("url", "https://docs.google.com/a/example.com/presentation/d/built_1/edit")])
            assert "記録の url" not in page()  # /a/<ドメイン>/ の書き方も、ID で同じファイル
            for u in ("https://docs.google.com/presentation/u/0/d/built_1/edit", "https://docs.google.com/u/1/presentation/d/built_1/edit"):
                record(f, 8, "済んだ", [("url", u)])
                assert "記録の url" not in page(), u  # /u/0/ は種類の前にも後にも付く
            (f / "社内メモ_u.md").write_text("https://docs.google.com/presentation/u/0/d/only_u/edit\n")
            record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/only_u/edit")])
            assert "記録の url" not in page()  # 構成案の側が /u/0/ の形でも
            (f / "社内メモ_u.md").unlink()
            record(f, 8, "済んだ", [("url", "組んだ資料")])
            assert "記録の url から Google のファイルの ID を読めない" in page()
            record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/built_1/edit")])
            for n in ("p02.json.bak1", "assets/a.png"):
                (f / "build" / n).parent.mkdir(exist_ok=True)
                (f / "build" / n).write_bytes(b"x")
            assert "済んだと記録したあと" not in page()  # 控えと画像は、ページの中身の変更に数えない
            record(f, 9, "止まった", note="答え待ち\u20282 行目")
            assert "答え待ち\u20282 行目" in page() and "読めない行" not in page()  # U+2028 で記録を割らない
            with open(f / PROGRESS, "a") as x:
                x.write('{"切れた')
            record(f, 9, "始めた")
            assert "progress.jsonl に読めない行 1" in page() and "最後の記録: 9 /deck-review。記録: 始めた" in page()  # 切れた行に新しい記録をつなげない
            with open(f / PROGRESS, "a") as x:
                x.write("[" * 100000 + "\n")
            assert "読めない行 2" in page() and "記録なし" not in page()  # 深すぎる入れ子は、その行だけ
            assert "1〜11" in _exits(lambda: record(f, "9" * 5000, "済んだ"))
            with open(f / PROGRESS, "a") as x:
                x.write('{壊れた\n{"step": "8 全体を組む", "status": "済んだ", "ts": "x"}\n')
            assert "progress.jsonl に読めない行 4" in page()  # 時刻の読めない記録も数えない（前の 2 行と合わせて 4）
            (f / "構成案.md").write_bytes("言語: ja\n".encode("utf-16"))
            s = got()
            assert "調べられない（UnicodeDecodeError" in s["5"] and "調べられない（UnicodeDecodeError" in s["10"] and "出典 1 件" in s["1–4"]
            os.chdir(Path(d).parent)  # ワークスペースの外から回しても、資料のフォルダのワークスペースを読む
            assert "資料: Customers/acme/deck_202611" in page()
            os.chdir(ws)
            # 時刻を決めた記録: 7 を済んだあとの変更は、8 を始めたあとに別のファイルを変えても見える。同じ秒の記録はファイルの順
            h = ws / "Internal" / "times_202611"
            (h / "build").mkdir(parents=True)
            T = 2_000_000_000
            ts = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (h / PROGRESS).write_text("".join(json.dumps({"ts": ts(T + a), "step": s, "status": st}, ensure_ascii=False) + "\n"
                                              for a, s, st in ((-10, "8 全体を組む", "始めた"), (0, "7 ページを書く", "済んだ"), (6, "8 全体を組む", "始めた"), (6, "9 /deck-review", "始めた"), (6, "8 全体を組む", "済んだ"))))
            for n, a in (("p03.json", 3), ("p04.json", 9)):
                (h / "build" / n).write_text("{}")
                os.utime(h / "build" / n, (T + a, T + a))
            p = page(h)
            assert "次の手順の記録より前に build/ が変わった: p03.json" in p and "p04.json（" not in p.split("7 ページを書く")[1].split("8 全体を組む")[0]
            assert "最後の記録: 8 全体を組む。記録: 済んだ" in p  # 同じ秒の 9 と 8 は、ファイルの順で 8 が後
            with open(h / PROGRESS, "a") as x:  # あとから足した、前の時刻の記録（遅れて書いた子など）
                x.write(json.dumps({"ts": ts(T + 2), "step": "8 全体を組む", "status": "始めた"}, ensure_ascii=False) + "\n")
            assert "記録: 済んだ" in page(h).split("\n8 全体を組む")[1].split("\n9 ")[0]  # 手順の中も時刻の順
            (h / PROGRESS).unlink()
            (h / PROGRESS).mkdir()
            assert "ファイルでない" in _exits(lambda: record(h, 5, "済んだ")) and "progress.jsonl がファイルでない" in page(h) and "記録なし" not in page(h)
            (h / PROGRESS).rmdir()
            (h / PROGRESS).write_bytes(b"\xef\xbb\xbf" + json.dumps({"ts": ts(T), "step": "5 構成", "status": "済んだ"}).encode() + b"\n")
            assert "読めない行" not in page(h) and "記録: 済んだ" in page(h)  # 先頭の BOM は外す
            (h / PROGRESS).write_text("ごみ\n")
            assert "記録なし（progress.jsonl に読める記録がない）" in page(h)
            (h / PROGRESS).unlink()
            (h / "build" / "p٣.json").write_text("{}")  # ASCII でない数字は数えない
            (h / "build" / "deep.json").write_text("[" * 100000)
            (h / "build" / "deck.json").write_text(json.dumps({"kind": "deck", "pages": ["p03.json", "p03.json", "deep.json"]}))
            s = got(h)
            assert "ページ 3 枚・p<番号>.json 2 個" in s["7"] and "build/deep.json を JSON として読めない" in s["7"]  # 2 度並べたページも数える
            (h / "構成案.md").write_text("```a``` は文中のコード\n\n    ```\n    字下げのコード\n\n## 書き方の取り決め\n\n- 見出しは 1 行\n"
                                       "https://docs.google.com/presentation/d/abc全体/edit xdocs.google.com/presentation/d/zzz\n")
            s = got(h)
            assert "「書き方の取り決め」の節: 空でない行 2" in s["6"]  # 文中の ``` も、4 字下げの ``` も囲みにしない
            assert "presentation/d/abc（" in s["8"] and "zzz" not in s["8"]  # ID は ASCII だけ。xdocs. は Google の URL でない
            os.environ["DESK_CONFIG"], keep = str(h / "bad.toml"), os.environ.get("DESK_CONFIG")
            (h / "bad.toml").write_text('workspace = "/nonexistent/flow_selftest"\n')
            try:
                with tempfile.TemporaryDirectory() as lone:
                    assert "ワークスペースが見つからない" in page(Path(lone))  # 読めない ~/.desk.toml でも、記録と事実は出す
            finally:
                os.environ.pop("DESK_CONFIG") if keep is None else os.environ.__setitem__("DESK_CONFIG", keep)
            g = ws / "Internal" / "doc_202611"
            (g / "build").mkdir(parents=True)
            (g / "build" / "doc.md").write_text("# 文書\n本文\n")
            (g / "build" / "pages.py").write_text("")
            s = got(g, ws / "Customers")
            assert "ワークスペースの外" in s["9"] and "ワークスペースの外" in s["11"]
            s = got(g, None)
            assert "build/doc.md 7 字" in s["7"] and "pages.py がある" in s["7"] and "ワークスペースが見つからない" in s["9"] and "ワークスペースが見つからない" in s["11"]
        finally:
            os.chdir(cwd)
    print("selftest ok")


def main(argv):
    if argv[:1] == ["record"]:
        ap = argparse.ArgumentParser(prog="flow.py record", description="手順の記録を progress.jsonl に 1 行足す（項目は deck-workflow の progress.md）")
        ap.add_argument("folder"); ap.add_argument("step", help="手順の番号（1〜11）"); ap.add_argument("status", choices=STATUSES)
        ap.add_argument("--out", type=out_arg, action="append", default=[], help="<名前>=<値>（url=…・pages=20・round=2 など。くり返してよい）")
        ap.add_argument("--note", default="", help="決めたこと・やめたこととその理由・待っていること")
        ap.add_argument("--next", dest="next_", default="", help="次にすること")
        ap.add_argument("--by", default="", help="誰が（親・子の名前）")
        a = ap.parse_args(argv[1:])
        print(json.dumps(record(a.folder, a.step, a.status, a.out, a.note, a.next_, a.by), ensure_ascii=False))
    elif len(argv) == 1 and not argv[0].startswith("-"):
        report(argv[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
