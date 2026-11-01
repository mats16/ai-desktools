#!/usr/bin/env python3
"""usage: flow.py <資料のフォルダ>     手順ごとの記録と、ファイルと台帳から分かる事実
       flow.py record <資料のフォルダ> <手順の番号> <始めた|済んだ|飛ばした|止まった> [--files <ファイル> ...] [--out <名前>=<値> ...] [--note <ひとこと>]
                                    自分の範囲の記録を資料のフォルダの progress.jsonl に 1 行足す（使うか、いつ使うかはエージェントが決める）
       （--selftest で自己確認）
記録は資料を作るワークフロー（deck-workflow）のもので、道具（slides.py・docs.py など）は書かない。項目と値は deck-workflow の progress.md。
記録を書く側（親・子・各手順）は自分の範囲（--files。なければ資料全体）のことだけを書き、次の手順は書かない。
まとめるのはこのスクリプト: 手順ごと・範囲ごとに最後の記録を今の状態にし、範囲の状態から手順の状態を、手順の並びから次を決め、
記録したときのファイルの sha256 と今の中身を比べる（時刻では比べない）。手順が済んだかは記録だけが言い、ファイルの形からは決めない
（予定の枚数、どの URL が組んだ資料か、節の中身が決まりか下書きかは、ファイルからは決めきれないため。2026-11-01 の「決めたこと」）。
事実は手順ごとに調べ、崩れた手順だけを「調べられない」と出して先へ進む。標準ライブラリだけ。"""
import argparse, contextlib, functools, hashlib, io, json, posixpath, re, sys
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


def good_inputs(v):
    """記録の inputs の形か: 資料のフォルダからの素直なパス（.. で外へ出ない・絶対でない）→ sha256 か null。手で直して崩れた行は、読めない行に数える。"""
    path = lambda k: isinstance(k, str) and k not in ("", ".", "..", PROGRESS) and "\0" not in k and not posixpath.isabs(k) and posixpath.normpath(k) == k and not k.startswith("../")
    return isinstance(v, dict) and all(path(k) and (h is None or isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h)) for k, h in v.items())


def records(folder):
    """(手順の名前 → その手順の記録の並び〔書いた順〕, 読めない行の数か、ファイルを読めないときの文)。
    順はファイルの行の順だけで決める（足すだけのファイルを鍵をかけて書くので、行の順が書いた順。時計のずれに左右されない）。"""
    got, bad, p = {}, 0, folder / PROGRESS
    if p.exists() and not p.is_file() or p.is_symlink():
        return {}, f"{PROGRESS} がファイルでない（フォルダかリンク）"
    text = read(p)
    if text is None and p.exists():
        return {}, f"{PROGRESS} を読めない（読む権限など）"
    for line in (text or "").lstrip("\ufeff").split("\n"):  # エディタが先頭に付ける BOM は外す  # splitlines は U+2028 などでも切り、1 件の記録を 2 つに割る
        try:
            r = json.loads(line)
        except (ValueError, RecursionError):  # 深すぎる入れ子の行も、その行だけを読めないとする
            r = None
        if isinstance(r, dict) and r.get("step") in STEPS and r.get("status") in STATUSES and when(r.get("ts")) and good_inputs(r.get("inputs", {})):
            got.setdefault(r["step"], []).append(r)
        else:
            bad += bool(line.strip())
    return got, bad


def out_arg(s):
    """--out の <名前>=<値>。"""
    k, eq, v = s.partition("=")
    if not (eq and re.fullmatch(r"[\w.-]+", k)):
        raise argparse.ArgumentTypeError(f"--out は <名前>=<値>（url=https://… など。名前は英数字と _ . -）: {s}")
    return k, v


def sha(p):
    """ファイルの中身の sha256。読めなければ None。"""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def record(folder, n, status, out=(), note="", files=()):
    """自分の範囲の記録を 1 行足す。足すだけで、前の行は書き換えない（同じ手順・同じ範囲は、最後の行が今の状態）。
    files は範囲のファイル（資料のフォルダからのパス）。記録には、そのときの中身の sha256 を inputs として残す。"""
    folder = Path(folder).resolve()
    folder.is_dir() or sys.exit(f"資料のフォルダがない: {folder}")
    step = step_of(n) or sys.exit(f"手順の番号は 1〜11: {n}")
    status in STATUSES or sys.exit(f"状態は {'・'.join(STATUSES)} のどれか: {status}")
    inputs, bad = {}, []
    for x in files:
        try:
            p = (folder / x).resolve()  # 先に解く: リンクで外を指すファイルは読まずに止め、中を指すリンクは指す先のファイルとして数える
        except (OSError, ValueError, RuntimeError):  # NUL の入った名前・リンクの輪
            bad.append(x)
            continue
        h = sha(p) if p.is_relative_to(folder) and p != folder / PROGRESS else None  # 記録のファイルそのものは、書くたびに変わるので範囲にしない
        if not p.is_relative_to(folder) or p == folder / PROGRESS or h is None and (p.exists() or status == "済んだ"):  # まだないページ（始める・外した）は書ける。済んだはあるファイルだけ
            bad.append(x)
        else:
            inputs[p.relative_to(folder).as_posix()] = h
    bad and sys.exit(f"--files は資料のフォルダの中の読めるファイル（build/p06.json など。まだないファイルは 済んだ 以外で書ける）: {', '.join(bad)}")
    rec = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "step": step, "status": status,
           **({"inputs": inputs} if inputs else {}), **({"out": dict(out)} if out else {}), **({"note": note} if note else {})}
    p = folder / PROGRESS
    p.exists() and not p.is_file() and sys.exit(f"{p} がファイルでない（フォルダなど）。名前を変えてから回す")
    p.is_symlink() and sys.exit(f"{p} がリンク。資料のフォルダの外に書かないよう、ふつうのファイルにしてから回す")
    with p.open("a+b") as f:
        if fcntl:  # 子が同時に書いても行が混ざらないように（長い --note は 1 回の書き込みで収まらない）
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0, 2)
        torn = f.tell() > 0 and (f.seek(-1, 2), f.read(1))[1] != b"\n"  # 途中で切れた最後の行に、新しい記録をつなげない（鍵をかけてから見る）
        f.write((("\n" if torn else "") + json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
    return rec


def scope(r):
    """記録の範囲（inputs のファイルの組）。なければ資料全体 ()。"""
    return tuple(sorted(r["inputs"])) if isinstance(r.get("inputs"), dict) else ()


def state(rs):
    """手順の記録（書いた順）→ (手順の状態, 今の状態を決めている記録の並び, {ファイルか None〔資料全体〕: それを最後に書いた記録})。
    ファイルごとと資料全体ごとに、最後に書いた記録が今の状態で、ほかの記録を置き換えない（範囲を分け直しても、前のファイルの状態はそのファイルの次の記録で変わる）。
    止まったが 1 つでもあれば止まった、始めたが残っていれば始めた、残りがなければ済んだ（全部が飛ばしたなら飛ばした）。Airflow の all_success と同じ合流。"""
    last = {}
    for r in rs:
        last.update((x, r) for x in (r["inputs"] if scope(r) else [None]))  # None は資料全体
    live = list({id(r): r for r in last.values()}.values())
    sts = {r["status"] for r in live}
    return next(s for s in ("止まった", "始めた", "済んだ", "飛ばした") if s in sts), live, last


def where(recs):
    """(いまの手順, その状態, 次)。始めた・止まったのままの手順があれば、その最初のもの（返したあとに前の手順に戻った直しも見える）。
    なければ、記録のあるいちばん先の手順と、手順の並びで決める。記録がなければ None。"""
    if not (logged := [s for s in STEPS if s in recs]):
        return None
    open_ = [(s, st) for s in logged if (st := state(recs[s])[0]) in ("始めた", "止まった")]
    if open_:
        s, st = open_[0]
        opened = [x for x, r in state(recs[s])[2].items() if r["status"] in ("始めた", "止まった")]
        still = ["資料全体"] * (None in opened) + ([short([x for x in opened if x], 4)] if any(opened) else [])
        far = f"（記録のあるいちばん先の手順は {logged[-1]}・{state(recs[logged[-1]])[0]}。前の手順に戻った直しか、閉じ忘れか）" if logged[-1] != s else ""
        return s, st, (f"{s} を続ける" if st == "始めた" else f"{s} の止まった理由（記録の note）を片付ける") + f"（開いている範囲: {'、'.join(still)}）" + far
    s = logged[-1]
    i = STEPS.index(s) + 1
    return s, state(recs[s])[0], f"{STEPS[i]} を始める（当てはまらない手順なら、飛ばした と記録して次へ）" if i < len(STEPS) else "なし（11 まで済んだ）"


def shown(r, keys):
    """記録の 1 行の見せ方。keys は、その記録が今も最後の記録であるファイル（None は資料全体）。あとの記録が書いたファイルは、範囲に出さない。"""
    flat = lambda v: " ".join(str(v).split())  # 改行で、報告の別の行に見せない
    out = "".join(f" {flat(k)}={flat(v)}" for k, v in r["out"].items()) if isinstance(r.get("out"), dict) else ""
    files = [k for k in keys if k]
    where_ = "資料全体" if None in keys else "範囲 " + short(files, 4) + (f"。記録したときの {len(scope(r))} ファイルのうち、ほかはあとの記録" if len(files) < len(scope(r)) else "")
    return f"記録: {r['status']} {r['ts']}（{where_}）" + out + (f"。{flat(r['note'])}" if r.get("note") else "")


def google_urls(folder, o, text):
    """構成案と社内メモ_*.md の Google の URL。{(種類, ID): (最初に見つけた書き方, 書いた場所の並び)}。同じファイルは ID で 1 つにまとめる（/a/<ドメイン>/・/u/0/ の書き方も）。"""
    places = [(o.name if o else "", h, body) for h, _, body in headed(text)] + [(p.name, "", (read(p) or "").splitlines()) for p in sorted(folder.glob("社内メモ_*.md"))]
    where = {}
    for f, h, body in places:
        for m in URL.finditer("\n".join(body)):
            where.setdefault((m["kind"], m["id"]), (m.group(0), []))[1].append(f + ("・" + h if h else ""))
    return where


def facts(folder, ws):
    """([(手順, [事実の文])], 構成案と社内メモの Google の ID の集合か None)。手順ごとに調べ、崩れたら（読めないファイル・思わない形の値）、その手順に「調べられない」と出して次へ進む。
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
    ids = None  # 8 の記録の url と突き合わせる Google の ID。調べられなければ None（8 の事実に「調べられない」と出ている）
    with contextlib.suppress(Exception, SystemExit):
        ids = {i for _, i in gurls()}
    return out, ids


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
    rows, ids = facts(folder, ws)
    def inside(x):  # 記録のあとにリンクに差し替えて外を指すようにしたパスは読まない
        try:
            return (folder / x).resolve().is_relative_to(folder)
        except (OSError, ValueError, RuntimeError):
            return False
    moved = {s: [x for x, r in state(rs)[2].items() if x and r["status"] == "済んだ" and inside(x) and sha(folder / x) != r["inputs"][x]] for s, rs in recs.items()}
    print(f"資料: {ledger.rel(ws, folder) if ws else folder}")
    if now := where(recs):
        print(f"いま: {now[0]}（{now[1]}）。次: {now[2]}")
    elif not isinstance(bad, str):
        print(f"記録なし（{PROGRESS} に読める記録がない）" if (folder / PROGRESS).exists() else f"記録なし（{PROGRESS} がない。手順が済んだかは、記録とファイルを読んで決める）")
    if bad:
        print(f"{PROGRESS} に読めない行 {bad}" if isinstance(bad, int) else bad)
    if any(moved.values()):  # 記録しないまま直したページも、いちばん上に出す
        print("済んだと記録したあとに中身が変わった（か、なくなった）: " + "、".join(f"{s} の {short(xs)}" for s, xs in moved.items() if xs))
    for step, items in rows:
        print(f"\n{step}")
        if rs := recs.get(step, []):
            st, _, last = state(rs)
            print(f"  - 状態: {st}" + (f"（範囲 {len(last)}: " + "・".join(f"{s} {n}" for s in STATUSES if (n := sum(r['status'] == s for r in last.values()))) + "）" if len(last) > 1 else ""))
            owns = {}  # 記録 → その記録が今も最後の記録であるファイル
            for k, r in last.items():
                owns.setdefault(id(r), (r, []))[1].append(k)
            for r, keys in owns.values():
                print(f"  - {shown(r, keys)}")
                u = r["out"].get("url") if isinstance(r.get("out"), dict) else None
                if step == "8 全体を組む" and isinstance(u, str) and ids is not None:
                    if not (m := URL.search(u)):
                        print("  - 記録の url から Google のファイルの ID を読めない（突き合わせない）")
                    elif m["id"] not in ids:
                        print("  - 記録の url の ID が構成案にも社内メモにもない")
            if moved[step]:
                print(f"  - 済んだと記録したあとに中身が変わった（か、なくなった）: {short(moved[step])}")
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
            # 記録: 足すだけで、手順ごと・範囲ごとに最後の 1 件が今の状態。次は手順の並びから決める
            r1 = record(f, 5, "済んだ", [("pages", "20")], "4 つの答えに合意")
            assert r1["step"] == "5 構成" and r1["out"] == {"pages": "20"} and "inputs" not in r1
            assert record(f, 3, "飛ばした")["step"] == "1–4 準備"
            for bad in ((12, "済んだ"), ("²", "済んだ"), (8, "終わった")):
                assert "1〜11" in _exits(lambda: record(f, *bad)) or "状態は" in _exits(lambda: record(f, *bad))
            (f / "build" / "link.json").symlink_to("/etc/hosts")
            for x in ("build/nothing.json", "../x.json", "/etc/hosts", "build/link.json"):
                assert "--files は" in _exits(lambda: record(f, 7, "済んだ", files=[x])), x
            (f / "build" / "link.json").unlink()
            (f / "..notes.json").write_text("{}")
            assert record(f, 3, "飛ばした", files=["..notes.json"])["inputs"]  # .. で始まる名前は外ではない
            (f / "..notes.json").unlink()
            assert out_arg("url=https://x/y?a=b") == ("url", "https://x/y?a=b")
            try:
                out_arg("=x")
                raise AssertionError("通した")
            except argparse.ArgumentTypeError:
                pass
            p = page()
            assert "いま: 5 構成（済んだ）。次: 6 代表の 3 枚 を始める" in p and "記録: 済んだ" in p and "（資料全体） pages=20。4 つの答えに合意" in p
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
            assert "取り込んだレビュー 2 行・最後 " in s["9"] and "最後の変更" not in s["9"] and "戻し先が「未」の指摘 1 件" in s["11"]  # 古さは時刻で比べない
            with open(ws / ".desk" / "ledger.jsonl", "a") as x:
                x.write("[1]\n")
            s = got()
            assert "調べられない" in s["9"] and "調べられない" in s["11"] and "出典 1 件" in s["1–4"]  # JSON だが行の形でない。ほかの手順は出る
            (ws / ".desk" / "ledger.jsonl").write_text("".join(l for l in (ws / ".desk" / "ledger.jsonl").read_text().splitlines(True) if l != "[1]\n"))
            assert when("2026-11-01T00:00:00.5+00:00") and when("壊れた") is None and when("0001-01-01T00:00:00+05:00") is None
            # 子は自分の範囲だけを書き、合流はこのスクリプトが決める（全部の範囲が済むまで、手順は始めたまま）
            record(f, 7, "始めた", note="子 2 つに分けた")
            record(f, 7, "始めた", files=["build/p13.json"])  # 子に渡した、まだないページ
            assert "開いている範囲: 資料全体、build/p13.json" in page()
            for x in ("progress.jsonl", "a\0b"):
                assert "--files は" in _exits(lambda: record(f, 7, "始めた", files=[x])), x
            record(f, 7, "始めた", files=["build/p13.json", "build/p14.json"])
            record(f, 7, "飛ばした", files=["build/p13.json"])
            assert "開いている範囲: 資料全体、build/p14.json）" in page()  # 閉じたファイルは開いている範囲に出さない
            record(f, 7, "飛ばした", files=["build/p14.json"])
            (f / "build" / "p15.json").write_text("{}")
            record(f, 7, "始めた", files=["build/p15.json", "build/p16.json"], note="2 枚を作成中")
            record(f, 7, "済んだ", files=["build/p15.json"])
            p = page()
            assert "記録: 始めた" in p and "（範囲 build/p16.json。記録したときの 2 ファイルのうち、ほかはあとの記録）。2 枚を作成中" in p and "build/p15.json, build/p16.json" not in p  # 済んだ p15 を、古い始めたの範囲に出さない
            record(f, 7, "飛ばした", files=["build/p16.json"])
            record(f, 7, "飛ばした", files=["build/p13.json"])
            record(f, 7, "済んだ", files=["build/p04.json", "build/p05.json"])
            record(f, 7, "始めた", files=["build/p06.json"])
            p = page()
            assert "いま: 7 ページを書く（始めた）。次: 7 ページを書く を続ける" in p and "範囲 8: 始めた 2・済んだ 3・飛ばした 3" in p and "範囲 build/p04.json, build/p05.json" in p
            record(f, 7, "済んだ", files=["build/p06.json", "build/p07.json"])  # 範囲を分け直しても、前の範囲（p06 の始めた）は残らない
            assert "いま: 7 ページを書く（始めた）" in page()  # 資料全体の始めたが残っている（親が閉じるまで）
            # 古さは中身の sha256 で見る（時刻では見ない）。元に戻せば出ない
            (f / "build" / "p05.json").write_text('{"直した": 1}')
            assert "済んだと記録したあとに中身が変わった（か、なくなった）: build/p05.json" in page()
            (f / "build" / "p05.json").write_text("{}")
            assert "中身が変わった" not in page()
            (f / "build" / "p08.json").write_text("{}")
            record(f, 7, "始めた", files=["build/p08.json"])
            (f / "build" / "p08.json").unlink()  # 計画から外して消したページ
            record(f, 7, "済んだ", note="全部の子が戻った")
            assert "いま: 7 ページを書く（始めた）" in page()  # 子の範囲が 1 つでも開いていれば、親が閉じても済まない（all_success）
            assert "--files は" in _exits(lambda: record(f, 7, "済んだ", files=["build/p08.json"]))
            assert "--files は" in _exits(lambda: record(f, 7, "飛ばした", files=["build"]))  # フォルダは外したページでない
            record(f, 7, "飛ばした", files=["build/p08.json"])
            p = page()
            assert "いま: 7 ページを書く（済んだ）。次: 8 全体を組む を始める" in p and "範囲 build/p04.json" in p  # 親の記録は子の記録を置き換えない（ハッシュも残る）
            (f / "build" / "p05.json").write_text('{"直した": 1}')
            p = page()
            assert "中身が変わった（か、なくなった）: build/p05.json" in p and "\n済んだと記録したあとに中身が変わった（か、なくなった）: 7 ページを書く の build/p05.json" in p  # 親が閉じたあとの変更も、いちばん上に見える
            with open(f / PROGRESS, "a") as x:  # 手で直した記録の外を指すパスは読まない
                for bad in ({"../../../etc/hosts": None}, {"/etc/hosts": None}, {"build/p01.json": 123}, {"build/./p01.json": None}, {"progress.jsonl": None}, {".": None}):
                    x.write(json.dumps({"ts": "2026-11-01T00:00:00Z", "step": "6 代表の 3 枚", "status": "始めた", "inputs": bad}, ensure_ascii=False) + "\n")
            p = page()
            assert "etc/hosts" not in p and "progress.jsonl に読めない行 6" in p and "\n6 代表の 3 枚\n  - 状態" not in p  # 崩れた inputs の行は、読めない行に数える
            (f / PROGRESS).write_text("".join(l for l in (f / PROGRESS).read_text().splitlines(True) if '"6 代表の 3 枚", "status": "始めた"' not in l))
            (f / "build" / "p05.json").write_text("{}")
            (f / "build" / "alias.json").symlink_to("p06.json")
            assert record(f, 7, "済んだ", files=["build/alias.json"])["inputs"] == {"build/p06.json": sha(f / "build" / "p06.json")}  # 中を指すリンクは指す先のファイル
            (f / "build" / "alias.json").unlink()
            record(f, 5, "始めた", note="返したあとの直しで構成に戻った")
            assert "いま: 5 構成（始めた）。次: 5 構成 を続ける（開いている範囲: 資料全体）（記録のあるいちばん先の手順は 7 ページを書く・済んだ" in page()  # 前の手順に戻った直しも見える
            record(f, 5, "済んだ")
            r8 = record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/elsewhere/edit")])
            assert "記録の url の ID が構成案にも社内メモにもない" in page()
            record(f, 8, "済んだ", [("url", "https://docs.google.com/presentation/d/built_1/edit")])
            assert "記録の url" not in page()
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
            record(f, 9, "止まった", note="答え待ち\u20282 行目\n  - 記録の url の ID が構成案にも社内メモにもない")
            p = page()
            assert "答え待ち 2 行目 - 記録の url" in p and "\n  - 記録の url の ID" not in p and "読めない行" not in p  # U+2028 で記録を割らない。改行で報告の行に見せない
            with open(f / PROGRESS, "a") as x:
                x.write('{"切れた')
            record(f, 9, "始めた")
            assert "progress.jsonl に読めない行 1" in page() and "いま: 9 /deck-review（始めた）" in page()  # 切れた行に新しい記録をつなげない
            with open(f / PROGRESS, "a") as x:
                x.write("[" * 100000 + "\n")
            assert "読めない行 2" in page() and "記録なし" not in page()  # 深すぎる入れ子は、その行だけ
            assert "1〜11" in _exits(lambda: record(f, "9" * 5000, "済んだ"))
            with open(f / PROGRESS, "a") as x:
                x.write('{壊れた\n{"step": "8 全体を組む", "status": "済んだ", "ts": "x"}\n{"step": "8 全体を組む", "status": "済んだ", "ts": "2026-11-01T00:00:00Z", "inputs": 1}\n')
            assert "progress.jsonl に読めない行 5" in page()  # 時刻の読めない記録、形の違う inputs も数えない（前の 2 行と合わせて 5）
            (f / "構成案.md").write_bytes("言語: ja\n".encode("utf-16"))
            s = got()
            assert "調べられない（UnicodeDecodeError" in s["5"] and "調べられない（UnicodeDecodeError" in s["10"] and "出典 1 件" in s["1–4"]
            os.chdir(Path(d).parent)  # ワークスペースの外から回しても、資料のフォルダのワークスペースを読む
            assert "資料: Customers/acme/deck_202611" in page()
            os.chdir(ws)
            # 時計のずれに左右されない: 最後の記録はファイルの行の順で決める
            h = ws / "Internal" / "times_202611"
            (h / "build").mkdir(parents=True)
            T = 2_000_000_000
            ts = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (h / PROGRESS).write_text("".join(json.dumps({"ts": ts(T + a), "step": s, "status": st}, ensure_ascii=False) + "\n"
                                              for a, s, st in ((6, "8 全体を組む", "始めた"), (6, "8 全体を組む", "済んだ"), (2, "8 全体を組む", "始めた"))))
            assert "いま: 8 全体を組む（始めた）" in page(h)  # 順はファイルの行の順だけ（あとに書いた始めたが、前の時刻でも今の状態）
            for n in ("p03.json", "p04.json"):
                (h / "build" / n).write_text("{}")
            (h / PROGRESS).unlink()
            (h / PROGRESS).mkdir()
            assert "ファイルでない" in _exits(lambda: record(h, 5, "済んだ")) and "progress.jsonl がファイルでない" in page(h) and "記録なし" not in page(h)
            (h / PROGRESS).rmdir()
            (h / PROGRESS).symlink_to(ws / "outside.jsonl")  # 外を指すリンクには書かない・読まない
            assert "リンク" in _exits(lambda: record(h, 5, "済んだ")) and not (ws / "outside.jsonl").exists() and "ファイルでない（フォルダかリンク）" in page(h)
            (h / PROGRESS).unlink()
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
        ap.add_argument("--files", nargs="+", default=[], help="自分の範囲のファイル（資料のフォルダからのパス。なければ資料全体）")
        a = ap.parse_args(argv[1:])
        print(json.dumps(record(a.folder, a.step, a.status, a.out, a.note, a.files), ensure_ascii=False))
    elif len(argv) == 1 and not argv[0].startswith("-"):
        report(argv[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
