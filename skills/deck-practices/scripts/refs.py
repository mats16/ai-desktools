#!/usr/bin/env python3
"""出典の台帳（資料のフォルダの references.md）と、構成案の「出典の表」（ページに出す事実の台帳）を足し、確かめる。標準ライブラリだけ。
書き方は ../materials.md の "Ledger"。出典は S<番号>、事実は F<番号> の ID で引き合う。
usage:
  refs.py add <資料のフォルダ> <URL・会議の ID・パス> [--name <名前>] [--kind <種類>] [--use <使い道>] [--updated <元の更新日>] [--out 可|不可]
      references.md に 1 行足し、ID（S<番号>）を出す（同じ出典がもうあれば、その ID を出して足さない）。確かめた日は今日。
      種類と社外は URL から決め（決まらなければ --kind を求める）、元の更新日は、Google の文書なら Drive、GitHub ならリポジトリの最後の push、
      手元のファイルなら更新の時刻、ほかは HTTP の Last-Modified から取る（取れなければ「不明」）
  refs.py seen <資料のフォルダ> <S-ID> …   読み直した出典の、確かめた日を今日にする
  refs.py check <資料のフォルダ> [--fetch] [--days 14]
      台帳と出典の表の形の誤り（あれば exit 1）、照合していない行（危ない順。照合の子に渡す）、確認が「未」の行、
      古い行（確かめてから --days 日を過ぎた出典を使う、提供・数字の行）、確かめたあとに元が更新された出典。
      --fetch は元の更新日を取り直して台帳に書く（渡す前に回す）
  refs.py index [<ワークスペース>]
      ワークスペースの台帳（Customers/・Internal/・Research/ の下の references.md）から、全体の索引 references_index.md を作り直す。
      1 つの出典を 1 行にし、同じ出典を使ったフォルダはまとめ、確かめた日の新しい順に並べる。add と seen のあとにも作り直す。
      手で書いた前の形の索引は上書きしない（desk-migrate で移す）
  refs.py --selftest"""
import argparse, contextlib, html, json, os, re, subprocess, sys, urllib.request
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows。並んで足す子がいなければ要らない
    fcntl = None

SRC_COLS = ("ID", "名前", "場所", "種類", "元の更新日", "確かめた日", "社外", "使い道")
FACT_COLS = ("ID", "言うこと", "種類", "出典", "確認")
SRC_KINDS = ("公式", "記事", "社内資料", "会議", "チャット", "データ", "口頭")  # 公式は一次の情報（製品の docs・リポジトリ・価格表・著者の論文）、記事はほかの人のまとめ
FACT_KINDS = ("提供", "計算", "数字", "顧客", "名前", "見立て")  # 照合の順（危ない順）。見立ては照合しない（ページで見立てと分かる形にする）
PRODUCT = {"提供", "数字", "名前"}  # 製品の事実。一次の情報（公式）か、手元のデータで確かめる
WEAK = {"記事", "会議", "チャット", "口頭"}  # 製品の事実の出典として弱い（顧客の環境の出典としては会議・チャットでよい）
AGING = {"提供", "数字"}  # 時点で変わる（提供ステージ・リージョン・上限・価格・モデルの世代・測った値）
STATES = ("照合済", "済", "未")  # 照合済は会話を持たない子が出典を開いて確かめたもの、済は作り手が開いて確かめたもの、未はまだ開いていないもの
INTERNAL = re.compile(r"docs\.google\.com|drive\.google\.com|slack\.com|teams\.microsoft\.com|atlassian\.net|confluence|sharepoint\.com|"
                      r"force\.com|salesforce\.com|glean|notion\.so")  # 社内の道具の URL（社外は「不可」にする）
HEAD = ("# 出典の台帳\n\n社内の URL と会議の ID が入る。納品物に写さない。書き方は deck-practices の materials.md の \"Ledger\"。"
        "足すときは `refs.py add`、読み直したら `refs.py seen`。\n\n")
ID_RUN = re.compile(r"^\s*([SF]\d+(?:\s*[・,、÷×/*+＋−-]\s*[SF]\d+)*)")  # 出典の列の頭の ID の並び（「S3 の Regions の表」「F4÷F5」）。頭だけを読む（「Amazon S3」を ID にしない）
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
INDEX, INDEX_DIRS = "references_index.md", ("Customers", "Internal", "Research")  # 全体の索引と、台帳を探すフォルダ
INDEX_NOTE = "`refs.py index` が"  # 作った索引の頭の印。ないものは手で書いた前の形（2026-10-29 まで）で、上書きしない
LINE_MAX, PLACES_MAX = 200, 3  # 索引の 1 行の字数（URL までは切らない。末尾のフォルダを除く）と、並べるフォルダの数。前の索引は「使った」が伸び続け、広い語の grep が 10 万字を超えた
URL = re.compile(r"https?://[^\s)|>\]」）、。]+")
MTG = re.compile(r"(?<!\w)mtg_\w+")  # 会議の ID（Dahlia）


def row(line):
    """markdown の表の 1 行のセル。表の行でなければ None（\\| はセルの中の |）。"""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
        return None
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s[1:-1])]


def table(lines, start=0, stop=None):
    """lines[start:stop] の最初の表。(見出しのセル, [(行の番号, {列: 値})])。表がなければ (None, [])。"""
    stop = len(lines) if stop is None else stop
    for i in range(start, stop):
        head = row(lines[i])
        if head and i + 1 < stop and (sep := row(lines[i + 1])) and all(re.fullmatch(r":?-+:?", c) for c in sep):
            out = []
            for k in range(i + 2, stop):
                if (c := row(lines[k])) is None:
                    break
                out.append((k, dict(zip(head, c + [""] * (len(head) - len(c))))))
            return head, out
    return None, []


def sources(text):
    """references.md の出典の表（見出しが SRC_COLS のもの）。(行の番号の並びの最後, {ID: 列})。新しい形の表がなければ (None, {})。"""
    lines = text.splitlines()
    for i in range(len(lines)):
        if row(lines[i]) == list(SRC_COLS):
            _, rows = table(lines, i)
            out = {}
            for k, r in rows:
                out[r["ID"]] = r | {"_line": k, "_dup": r["ID"] in out}  # 同じ ID の行は後ろが残る。check が形の誤りに出す
            return (rows[-1][0] if rows else i + 1), out
    return None, {}


def outline(folder):
    """資料のフォルダのいちばん新しい構成案（構成案_v3.md > 構成案_v2.md > 構成案.md。同じ版なら更新の新しいほう）。この形のものがなければ、ほかの
    構成案*.md（構成案_GoogleSlides.md など）から選ぶ（構成案_メモ.md のようなファイルに、正の構成案が負けない）。なければ None。"""
    all_ = list(Path(folder).glob("構成案*.md"))
    cands = [p for p in all_ if re.fullmatch(r"構成案(_v\d+)?\.md", p.name)] or all_
    ver = lambda p: (int(m.group(1)) if (m := re.search(r"_v(\d+)", p.stem)) else 1, p.stat().st_mtime)
    return max(cands, key=ver) if cands else None


def fact_section(folder):
    """「出典の表」の節の (ファイル, 行, 節の頭の行, 節の終わりの行)。構成案になければ references.md（構成案のない資料）。なければ None。"""
    for f in (outline(folder), Path(folder) / "references.md"):
        if not (f and f.is_file()):
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, l in enumerate(lines):
            if m := re.match(r"(#{1,6})\s*出典の表", l):
                end = next((k for k in range(i + 1, len(lines)) if (h := re.match(r"(#{1,6})\s", lines[k])) and len(h.group(1)) <= len(m.group(1))), len(lines))
                return f, lines, i, end
    return None


def facts(folder):
    """出典の表の行。[{ID, 言うこと, 種類, 出典, 確認, _file, _legacy}]。ID の列のない前の形の表は、行の順に「行<番号>」を付け、列の名前から読む。"""
    if not (sec := fact_section(folder)):
        return []
    f, lines, a, z = sec
    head, rows = table(lines, a, z)
    if not head:
        return []
    legacy = "ID" not in head
    pick = lambda r, *names: next((r[n] for n in names if n in r), "")
    out = []
    for n, (_, r) in enumerate(rows, 1):
        first = next((v for k, v in r.items() if k != "ID"), "")
        out.append({"ID": r.get("ID") or f"行{n}", "言うこと": pick(r, "言うこと", "値", "項目", "数字", "事実") or first, "種類": pick(r, "種類"),
                    "出典": pick(r, "出典"), "確認": pick(r, "確認", "確認済み", "確かめた"), "_file": f.name, "_legacy": legacy})
    return out


def facts_text(folder):
    """lint が数字を探す文字: 出典の表の「言うこと」の列（出典・確認の列の日付や場所の数は入れない）と、その節が `` で指す手元の md（「`build/README_data.md` の「数字の一覧」を出典の表とする」など）。
    構成案も references.md もないフォルダ（見本・試しの組み）は None（lint は見ない）。節がなければ空の文字（lint が「出典の表がない」と出す）。"""
    ledger = Path(folder) / "references.md"
    if outline(folder) is None and not (ledger.is_file() and ledger.stat().st_size):  # 空の台帳は、refs.py add がロックのために作りかけたもの
        return None
    if not (sec := fact_section(folder)):
        return ""
    _, lines, a, z = sec
    text = "\n".join(r["言うこと"] for r in facts(folder))
    for name in re.findall(r"`([^`]+\.md)`", "\n".join(lines[a:z])):
        for p in (Path(folder) / name, Path(folder) / "build" / name):
            if p.is_file() and p.resolve().is_relative_to(Path(folder).resolve()):  # 資料のフォルダの中の md だけ
                text += "\n" + p.read_text(encoding="utf-8", errors="replace")
                break
    return text


def ids(cell, kind="S"):
    m = ID_RUN.match(cell or "")
    return re.findall(rf"{kind}\d+", m.group(1)) if m else []


GDOC = re.compile(r"(?:docs|drive)\.google\.com/.*?(?:/d/|[?&]id=)([\w-]{20,})")  # Google の文書のファイルの ID


def key(t):
    """同じ出典かを見る形。場所の列はそのまま書くので、読み解かずに比べる。Google の文書はファイルの ID（/edit・#slide= を見ない）。"""
    return m.group(1) if (m := GDOC.search(t)) else t.strip().rstrip("/")


def guess_kind(t):
    if re.search(r"(^|[^\w])mtg_\w+|meeting|会議", t):
        return "会議"
    if re.search(r"slack\.com|teams\.microsoft\.com", t):
        return "チャット"
    if INTERNAL.search(t):
        return "社内資料"
    if re.match(r"https://(github\.com|huggingface\.co)/[\w.-]+/[\w.-]+", t):  # リポジトリとモデルカードは、それ自身の事実の一次の情報
        return "公式"
    if not re.match(r"https?://", t) and (t.startswith(("/", "~", ".")) or Path(t).exists()):
        return "データ"
    return None


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "desk-tools-refs"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.headers, res.read(200_000)


def page_meta(h, body):
    """Web のページの更新日と題。ページの中の更新日（dateModified・article:modified_time。docs のサイトは HTTP の Last-Modified を返さないことが多い）、
    なければ Last-Modified（静的なサイトでは、サイト全体を出し直した日になることがある）。"""
    m = re.search(rb'(?:"dateModified"\s*:\s*"|(?:article:modified_time|og:updated_time)"\s+content=")(\d{4}-\d{2}-\d{2})', body)
    title = re.search(rb"<title[^>]*>([^<]{1,200})</title>", body, re.I)
    out = {"name": html.unescape(title.group(1).decode("utf-8", "replace")).strip()} if title else {}
    with contextlib.suppress(Exception):
        out["updated"] = m.group(1).decode() if m else parsedate_to_datetime(h["Last-Modified"]).date().isoformat()
    return out


def fetch(t):
    """出典の今の更新日（と名前）。取れなければ {}。止まらない（網がない・認証がない・サイトが拒む）。"""
    with contextlib.suppress(Exception, SystemExit):
        if m := GDOC.search(t):
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import gapi
            f = gapi.request("GET", f"https://www.googleapis.com/drive/v3/files/{m.group(1)}?supportsAllDrives=true&fields=name,modifiedTime")
            return {"updated": f["modifiedTime"][:10], "name": f["name"]}
        if m := re.match(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/|$)", t):
            r = json.loads(get(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}")[1])
            return {"updated": r["pushed_at"][:10], "name": r["full_name"]}
        if re.match(r"https?://", t):
            return page_meta(*get(t))
        p = Path(t).expanduser()
        if p.is_dir() and (p / ".git").exists():
            return {"updated": subprocess.run(["git", "-C", str(p), "log", "-1", "--format=%cs"], capture_output=True, text=True, timeout=10).stdout.strip()}
        if p.exists():
            return {"updated": date.fromtimestamp(p.stat().st_mtime).isoformat()}
    return {}


@contextlib.contextmanager
def locked(p):
    """台帳を読み書きするあいだ、references.md そのものをロックする（調べものの子が並んで足しても、ID がぶつからない）。"""
    with open(p, "a", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_UN)


def cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ").strip()


def add(folder, t, name=None, kind=None, use="", updated=None, out=None, today=None):
    p = Path(folder) / "references.md"
    if not Path(folder).is_dir():
        sys.exit(f"資料のフォルダがない: {folder}")
    kind = kind or guess_kind(t)
    if not re.match(r"https?://", t) and Path(t).expanduser().exists():  # 手元のパスは、どこから回しても引けるように絶対のパス（家は ~）にする
        t, home = str(Path(t).expanduser().resolve()), str(Path.home())
        t = "~" + t[len(home):] if t == home or t.startswith(home + "/") else t
    if kind not in SRC_KINDS:
        sys.exit(f"種類が URL から決まらない。--kind で {'・'.join(SRC_KINDS)} のどれかを付ける（製品の docs・リポジトリ・価格表は 公式、ほかの人のまとめ・ブログ・ニュースは 記事、会話でユーザーが言ったことは 口頭）")
    out = out or ("可" if kind in ("公式", "記事") and re.match(r"https?://", t) and not INTERNAL.search(t) else "不可")
    find = lambda rows: next((i for i, r in rows.items() if key(r["場所"]) == key(t)), None)
    if p.is_file() and (hit := find(rows := sources(p.read_text(encoding="utf-8"))[1])):  # 取りに行く前に見る
        print(f"{hit}（もうある: {rows[hit]['場所']}）")
        return hit
    meta = {} if updated else fetch(t)
    updated = updated or meta.get("updated") or "不明"
    name = name or meta.get("name") or ""
    with locked(p):
        text = p.read_text(encoding="utf-8") or HEAD
        last, rows = sources(text)
        if hit := find(rows):
            print(f"{hit}（もうある: {rows[hit]['場所']}）")
            return hit
        sid = "S" + str(max([int(i[1:]) for i in rows if re.fullmatch(r"S\d+", i)] or [0]) + 1)
        line = "| " + " | ".join(map(cell, (sid, name, t, kind, updated, today or date.today().isoformat(), out, use))) + " |"
        lines = text.splitlines()
        if last is None:  # 前の形の台帳か、新しいファイル。新しい形の表を末尾に足す（前の行は残す）
            lines += ([""] if lines and lines[-1].strip() else []) + ["| " + " | ".join(SRC_COLS) + " |", "|" + "---|" * len(SRC_COLS), line]
        else:
            lines.insert(last + 1, line)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(sid)
    return sid


def set_cells(p, changes):
    """changes {S-ID: {列: 値}} を references.md の出典の表に書く。"""
    with locked(p):
        text = p.read_text(encoding="utf-8")
        _, rows = sources(text)
        lines = text.splitlines()
        for sid, ch in changes.items():
            r = rows[sid]
            lines[r["_line"]] = "| " + " | ".join(cell(ch.get(c, r[c])) for c in SRC_COLS) + " |"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def seen(folder, sids, today=None):
    p = Path(folder) / "references.md"
    _, rows = sources(p.read_text(encoding="utf-8")) if p.is_file() else (None, {})
    if miss := [s for s in sids if s not in rows]:
        sys.exit(f"references.md の出典の表にない ID: {', '.join(miss)}")
    set_cells(p, {s: {"確かめた日": today or date.today().isoformat()} for s in sids})
    print(f"確かめた日を {today or date.today().isoformat()} にした: {', '.join(sids)}")


def state(v):
    return next((s for s in STATES if v.startswith(s)), "-" if v.strip() in ("", "-") else "?")


def check(folder, fetch_now=False, days=14, today=None, fetcher=None):
    """出力を出し、形の誤りの数を返す。"""
    today = date.fromisoformat(today) if today else date.today()
    p = Path(folder) / "references.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    _, src = sources(text)
    rows, errs, notes = facts(folder), [], []
    if fetch_now and src:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as ex:  # 1 件 10 秒まで待つので、並べて取る
            got = dict(zip(src, ex.map(lambda r: (fetcher or fetch)(r["場所"]).get("updated"), src.values())))
        ch = {sid: {"元の更新日": u} for sid, u in got.items() if u and u != src[sid]["元の更新日"]}
        miss = [sid for sid, u in got.items() if not u and src[sid]["種類"] not in ("口頭", "会議", "チャット")]  # 会話・会議・チャットは取る手段がない
        if ch:
            set_cells(p, ch)
            _, src = sources(p.read_text(encoding="utf-8"))
        notes.append(f"元の更新日を取り直した: {sum(map(bool, got.values()))} 件（変わった {len(ch)} 件）" + (f"。取れなかった {len(miss)} 件: {', '.join(miss)}（元を開いて確かめる）" if miss else ""))
    if text and not src:
        notes.append("references.md が前の形（ID の列がない）。足すときは refs.py add（新しい形の表を末尾に足し、前の行は残す）")
    for sid, r in src.items():
        if r["_dup"] or not re.fullmatch(r"S\d+", sid):
            errs.append(f"references.md: ID「{sid}」が重なるか S<番号> でない")
        if not r["場所"]:
            errs.append(f"{sid}: 場所（URL・会議の ID・パス）が空")
        if r["種類"] not in SRC_KINDS:
            errs.append(f"{sid}: 種類「{r['種類']}」は {'・'.join(SRC_KINDS)} のどれか")
        for c in ("元の更新日", "確かめた日"):
            if not (DATE.fullmatch(r[c]) or (c == "元の更新日" and r[c] == "不明")):
                errs.append(f"{sid}: {c}「{r[c]}」は YYYY-MM-DD" + ("か「不明」" if c == "元の更新日" else ""))
        if r["社外"] not in ("可", "不可"):
            errs.append(f"{sid}: 社外「{r['社外']}」は 可 か 不可")
    if not rows:
        notes.append("出典の表がない（構成案にも references.md にも「## 出典の表」の節がない）")
    elif rows[0]["_legacy"]:
        notes.append(f"出典の表（{rows[0]['_file']}）が前の形（ID・種類の列がない）。行の順に「行<番号>」で出す。直すときは ID・言うこと・種類・出典・確認 の表にする")
    fids, all_f = set(), {r["ID"] for r in rows}
    for r in rows if rows and not rows[0]["_legacy"] else []:
        f = r["ID"]
        if f in fids or not re.fullmatch(r"F\d+", f):
            errs.append(f"出典の表: ID「{f}」が重なるか F<番号> でない")
        fids.add(f)
        if r["種類"] not in FACT_KINDS:
            errs.append(f"{f}: 種類「{r['種類']}」は {'・'.join(FACT_KINDS)} のどれか")
        if state(r["確認"]) == "?":
            errs.append(f"{f}: 確認「{r['確認']}」は 未・済・照合済 のどれか（見立ては -）")
        if r["種類"] != "見立て" and not ids(r["出典"], "[SF]"):
            errs.append(f"{f}: 出典の頭に S<番号>（計算は使った F<番号>）を書く: 「{r['出典']}」")
        if bad := [s for s in ids(r["出典"]) if s not in src]:
            errs.append(f"{f}: references.md にない出典 {', '.join(bad)}")
        if bad := [x for x in ids(r["出典"], "F") if x not in all_f]:
            errs.append(f"{f}: 出典の表にない {', '.join(bad)}")

    def weak(r):
        ks = {src[s]["種類"] for s in ids(r["出典"]) if s in src}
        return r["種類"] in PRODUCT and ks and ks <= WEAK and "、".join(sorted(ks))

    def aged(r):
        old = [s for s in ids(r["出典"]) if s in src and DATE.fullmatch(src[s]["確かめた日"]) and date.fromisoformat(src[s]["確かめた日"]) < today - timedelta(days=days)]
        return r["種類"] in AGING and old

    def show(r):
        s = "・".join(f"{s}（{src[s]['種類']}・確かめた日 {src[s]['確かめた日']}）{src[s]['場所']}" for s in ids(r["出典"]) if s in src)
        return f"{r['ID']} | {r['種類'] or '-'} | {r['言うこと']} | {r['出典']}" + (f" → {s}" if s else "") + f" | {r['確認'] or '-'}" + (f"（出典が弱い: {w}）" if (w := weak(r)) else "")

    order = lambda r: (FACT_KINDS.index(r["種類"]) if r["種類"] in FACT_KINDS else len(FACT_KINDS), not weak(r))
    todo = sorted((r for r in rows if r["種類"] != "見立て" and state(r["確認"]) != "照合済"), key=order)
    open_ = [r for r in rows if state(r["確認"]) == "未"]
    old = [r for r in rows if aged(r)]
    moved = [f"{s} | {r['場所']} | 元の更新日 {r['元の更新日']} > 確かめた日 {r['確かめた日']}" for s, r in src.items()
             if DATE.fullmatch(r["元の更新日"]) and DATE.fullmatch(r["確かめた日"]) and r["元の更新日"] > r["確かめた日"]]
    print(f"台帳: 出典 {len(src)} 件（references.md）、事実 {len(rows)} 件（{rows[0]['_file'] if rows else '出典の表なし'}）")
    for n in notes:
        print(f"（{n}）")
    for title, items in (("形の誤り（直す）", errs), ("照合していない行（照合の子に渡す。危ない順）", [show(r) for r in todo]),
                         ("確認が「未」の行（渡す前に出典を開くか、ページから外す）", [show(r) for r in open_]),
                         (f"古い行（確かめてから {days} 日を過ぎた出典を使う、提供・数字の行。読み直して refs.py seen）", [show(r) for r in old]),
                         ("確かめたあとに元が更新された出典（読み直して refs.py seen）", moved)):
        print(f"\n== {title}: {len(items)} ==", *items, sep="\n")
    return len(errs)


def keys(t):
    """文の中の出典の形（URL と会議の ID）。全体の索引が同じ出典をまとめ、desk-migrate が台帳にあるかを見る。"""
    return [key(u) for u in URL.findall(t)] + MTG.findall(t)


def ledgers(ws):
    return sorted(p for d in INDEX_DIRS if (Path(ws) / d).is_dir() for p in (Path(ws) / d).rglob("references.md"))


def short(text):
    """索引の 1 行の本文を LINE_MAX 字に詰める。最初の URL までは切らない（開き直すのに要る）。"""
    keep = m.end() + 1 if (m := URL.search(text)) else 0
    return text if len(text) <= max(LINE_MAX, keep + 40) else text[:max(LINE_MAX, keep + 40)] + "…"


def entries(p, folder):
    """台帳の出典: 新しい形の表の行と、前の形の行（表の外の箇条書きと、ほかの表の行）。[(まとめる形, 日付, 索引の 1 行の本文)]。
    まとめる形は URL（Google の文書はファイルの ID）か会議の ID。場所がそのどちらでもない行（手元のファイル・口頭・メモ）は、その資料の中でしか
    使わないので出さない。ただし Research/references.md（資料に結びつかない出典と、前の索引から移した行）は、フォルダごとに別にして出す。"""
    text = p.read_text(encoding="utf-8", errors="replace")
    lines, src = text.splitlines(), sources(text)[1]
    out, skip = [], {r["_line"] for r in src.values()}
    for r in src.values():
        t, name = r["場所"], r["名前"]
        k = key(t) if re.match(r"https?://", t) else m.group(0) if (m := MTG.search(t)) else f"{folder}|{t}"
        head = f"[{name}]({t})" if name and re.match(r"https?://", t) else f"{name}（{t}）" if name else t
        out.append((k, r["確かめた日"] if DATE.fullmatch(r["確かめた日"]) else "",
                    short(f"{head} — {r['種類']}・社外{r['社外']}・{r['確かめた日']}" + (f"。{r['使い道']}" if r["使い道"] else ""))))
    heads = {i for i in range(len(lines) - 1) if row(lines[i]) and (s := row(lines[i + 1])) and all(re.fullmatch(r":?-+:?", c) for c in s)}
    for i, line in enumerate(lines):
        if i in skip or i in heads:
            continue
        if (c := row(line)) is not None:
            if all(re.fullmatch(r":?-*:?", x) for x in c) or re.fullmatch(r"F\d+", c[0]):  # 区切りと、出典の表の事実
                continue
            body = " — ".join(x for x in c if x)
        elif m := re.match(r"\s*[-*] +(.+)", line):
            body = m.group(1).strip()
        else:
            continue
        ks = keys(body)
        out.append((ks[0] if ks else f"{folder}|{body}", max(DATE.findall(body), default=""), short(body)))
    return [e for e in out if folder == "Research" or "|" not in e[0]]


def generated(p):
    """作った索引か（ないか空なら、作ってよい）。頭に印のないものは、手で書いた前の形。"""
    if not p.is_file():
        return True
    with open(p, encoding="utf-8", errors="replace") as f:
        head = f.read(2000)
    return not head.strip() or INDEX_NOTE in head


def index(ws, today=None):
    """全体の索引を作り直し、出典の数を返す。手で書いた前の形なら、作らずに None。"""
    ws, today = Path(ws), today or date.today().isoformat()
    (ws / ".desk").mkdir(exist_ok=True)
    with locked(ws / ".desk" / "index.lock"):  # 台帳を読むところから。並んで足した子の行を、あとから書く索引が落とさない
        p = ws / INDEX
        if not generated(p):
            return None
        groups = {}
        for f in ledgers(ws):
            folder = f.parent.relative_to(ws).as_posix()
            for k, d, body in entries(f, folder):
                groups.setdefault(k, []).append((d, body, folder))  # 日付のない前の形の行は末尾に（ファイルの時刻は、移した日や直した日になる）
        rows = []
        for g in groups.values():
            g.sort(reverse=True)  # 本文は、いちばん新しく確かめた台帳のもの
            d, body, _ = g[0]
            places = list(dict.fromkeys(x[2] for x in g))
            where = "、".join(places[:PLACES_MAX]) + (f" ほか {len(places) - PLACES_MAX} か所" if len(places) > PLACES_MAX else "")
            rows.append((d, f"- {body}（{where}）"))
        rows.sort(key=lambda r: r[0], reverse=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(
            f"# 参考資料の索引\n\n{INDEX_NOTE}、各フォルダの `references.md`（`Customers/`・`Internal/`・`Research/` の下）から作り直す。手で直さない（次に作り直すと消える）。\n\n"
            "- 探すとき: 検索より先に `grep -n <語> references_index.md drive_folders.md`。1 行に 1 つの出典（URL か会議の ID のあるもの。手元のファイルと口頭は、その資料の `references.md` だけにある）。同じ出典を使ったフォルダは行の末尾にまとめ、"
            "確かめた日の新しい順に並ぶ。詳しくは、そのフォルダの `references.md`。\n"
            "- 足すとき: 資料の出典は `refs.py add <資料のフォルダ> <URL>`、資料に結びつかない出典（調べもの・会議）は `refs.py add Research <URL>`。足すと、この索引も作り直す。\n"
            "- Google Drive のフォルダと上げた資料は `drive_folders.md`（手で足す）。\n"
            "- 社内の URL と個人名が入るので、納品物に入れない。社外が「不可」の資料と【社内】の資料は、顧客向けに使う前に、社外に出せるかを確かめる。\n\n"
            f"{len(rows)} 件（{today} に作った）\n\n" + "".join(r + "\n" for _, r in rows), encoding="utf-8")
        os.replace(tmp, p)  # grep が書きかけを読まない
    return len(rows)


def workspace(start="."):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import desk  # ワークスペースの探し方（textlint はこのファイルをパスで読むので、使うときに読む）
    return f[1] if (f := desk.locate(start)) else None


def reindex(folder):
    """add・seen のあとに、その資料のワークスペースの索引を作り直す（ワークスペースが見つからなければ何もしない）。"""
    if (ws := workspace(folder)) and index(ws) is None:
        print(f"（{ws / INDEX} は手で書いた前の形なので、作り直していない。desk-migrate の apply で移す）", file=sys.stderr)


def selftest():
    import io, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "deck"  # 資料のフォルダ。外の md（tmp/outside.md）を読まないかも見る
        d.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert facts_text(d) is None  # 構成案も台帳もないフォルダ（見本の組み）は lint が見ない
            (d / "references.md").write_text("")
            assert facts_text(d) is None  # 空の台帳（add がロックのために作りかけたもの）もないものとみなす
            assert add(d, "https://docs.example.com/regions", name="Regions", kind="公式", updated="2026-10-01", today="2026-10-02") == "S1"
            assert add(d, "https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit", name="社内の紹介", updated="2026-09-01", today="2026-10-02") == "S2"
            assert add(d, "https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit#slide=id.p3") == "S2"  # 同じ文書は足さない
            assert add(d, "meetings mtg_01abc", name="定例 10/21", updated="2026-10-21", today="2026-10-21") == "S3"
            assert add(d, "https://example.com/blog", kind="記事", updated="2026-09-30", today="2026-09-30", use="p.5 の | の例") == "S4"
            assert add(d, "ユーザー（2026-10-21 の会話）", kind="口頭", updated="2026-10-21") == add(d, "ユーザー（2026-10-21 の会話）", kind="口頭") == "S5"  # 口頭も 2 度足さない
            assert add(d, "ユーザー（2026-10-21 の会話）", name="予算", kind="口頭") == add(d, "ユーザー（2026-10-21 の会話）", name="予算", kind="口頭") == "S5"  # 名前を付けても、同じ口頭の出典（S5）は足さない
            assert add(d, "https://en.wikipedia.org/wiki/Foo_(bar)", name="W", kind="記事", updated="2026-10-01") == add(d, "https://en.wikipedia.org/wiki/Foo_(bar)", kind="記事") == "S6"
            assert add(d, "https://drive.google.com/open?id=AAAAAAAAAAAAAAAAAAAAAAAA", name="A", updated="2026-10-01") == "S7" and add(d, "https://drive.google.com/open?id=BBBBBBBBBBBBBBBBBBBBBBBB", name="B", updated="2026-10-01") == "S8"  # id= の別の文書は別
            assert facts_text(d) == ""  # 台帳はあるが出典の表がない
        t = (d / "references.md").read_text()
        assert t.startswith("# 出典の台帳") and "| S2 | 社内の紹介 | https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit | 社内資料 | 2026-09-01 | 2026-10-02 | 不可 |  |" in t
        assert "| S1 | Regions | https://docs.example.com/regions | 公式 | 2026-10-01 | 2026-10-02 | 可 |" in t and "| S3 | 定例 10/21 | meetings mtg_01abc | 会議 |" in t
        assert "p.5 の \\| の例" in t and sources(t)[1]["S4"]["使い道"] == "p.5 の | の例"
        (d / "build").mkdir()
        (d / "build" / "README_data.md").write_text("| 1,200 件 | data.json |\n")
        (d.parent / "outside.md").write_text("| 9,999 件 |\n")
        (d / "構成案.md").write_text("# 構成案\n\n古い版\n")
        (d / "構成案_v2.md").write_text(
            "# 構成案\n\n## 出典の表\n\n`build/README_data.md` の数字も出典の表とする（`../outside.md` は読まない）。\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n"
            "| F1 | 東京リージョンで使える | 提供 | S1 の Regions の表 | 済 |\n| F2 | 3.2 倍 | 計算 | F3÷F4（48÷15） | 済 |\n| F3 | 48 件 | 数字 | S3 の 12:30 ごろ | 済 |\n"
            "| F4 | 15 件 | 数字 | S4 | 照合済 |\n| F5 | 顧客は Airflow で集計を回している | 顧客 | S3 | 未 |\n| F6 | 4 つの型 | 見立て | - | - |\n\n## 流用元\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        (d / "構成案_メモ.md").write_text("メモ\n")
        assert outline(d).name == "構成案_v2.md" and [r["ID"] for r in facts(d)] == ["F1", "F2", "F3", "F4", "F5", "F6"]
        assert "3.2 倍" in facts_text(d) and "1,200 件" in facts_text(d) and "12:30" not in facts_text(d) and "9,999" not in facts_text(d)  # 言うことの列と、節が指す資料のフォルダの中の md だけ
        assert ids("S3 の Regions の表") == ["S3"] and ids("F3÷F4（48÷15）", "F") == ["F3", "F4"] and ids("Amazon S3 の docs") == [] and ids("S1・S4") == ["S1", "S4"]
        with contextlib.redirect_stdout(out := io.StringIO()):
            assert check(d, days=14, today="2026-10-21") == 0
        o = out.getvalue()
        todo = o.split("== 照合していない行")[1].split("==")[1]
        assert [l.split(" |")[0] for l in todo.strip().splitlines()] == ["F1", "F2", "F3", "F5"]  # 提供 → 計算 → 数字 → 顧客。照合済と見立ては出さない
        assert "F3 | 数字 | 48 件 | S3 の 12:30 ごろ → S3（会議・確かめた日 2026-10-21）meetings mtg_01abc | 済（出典が弱い: 会議）" in o
        assert "F5 | 顧客" in o.split("確認が「未」の行")[1] and "出典が弱い" not in o.split("F5 | 顧客")[1].splitlines()[0]  # 顧客の環境は会議でよい
        old = o.split("== 古い行")[1].split("\n== ")[0]
        assert "F1 |" in old and "F4 |" in old and "F3 |" not in old  # 10-02 と 09-30 に確かめた出典は 14 日を過ぎた
        (d / "構成案_v2.md").write_text("## 出典の表\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n"
                                       "| F1 | a | 提供 | S9 | 済 |\n| F1 | b | 推測 | なし | 確認済み |\n| F2 | c | 計算 | F7 | 済 |\n")
        with contextlib.redirect_stdout(out := io.StringIO()):
            assert check(d, today="2026-10-21") == 6
        o = out.getvalue()
        (dup := Path(tmp) / "dup").mkdir()
        (dup / "references.md").write_text("| " + " | ".join(SRC_COLS) + " |\n|" + "---|" * len(SRC_COLS) + "\n"
                                           + "".join(f"| S1 | {n} | https://ex.com/{n} | 公式 | 2026-10-01 | 2026-10-01 | 可 |  |\n" for n in "ab"))
        with contextlib.redirect_stdout(io.StringIO()) as dup_out:
            assert check(dup, today="2026-10-21") == 1 and "ID「S1」が重なる" in dup_out.getvalue()  # 同じ S の ID の 2 行（辞書にすると前の行が消える）
        assert all(s in o for s in ("references.md にない出典 S9", "ID「F1」が重なる", "種類「推測」", "確認「確認済み」", "出典の頭に S<番号>", "出典の表にない F7"))
        (d / "構成案_v2.md").write_text("## 出典の表\n\n| 値 | 出典 | 確認 |\n|---|---|---|\n| 会話 688 | README_data.md | 済（計算） |\n| PR 204 | gh | 未確認 |\n")
        assert [(r["ID"], r["言うこと"], state(r["確認"])) for r in facts(d)] == [("行1", "会話 688", "済"), ("行2", "PR 204", "未")]  # 前の形の表も読む
        with contextlib.redirect_stdout(out := io.StringIO()):
            seen(d, ["S1"], today="2026-10-21")
            assert check(d, fetch_now=True, today="2026-10-21", fetcher=lambda t: {"updated": "2026-10-20"} if "regions" in t else {}) == 0
        s = sources((d / "references.md").read_text())[1]["S1"]
        assert (s["確かめた日"], s["元の更新日"]) == ("2026-10-21", "2026-10-20")  # 読み直した日と、取り直した元の更新日
        assert "S2 |" not in out.getvalue().split("元が更新された出典")[1]
        assert "取り直した: 1 件（変わった 1 件）。取れなかった 5 件: S2, S4, S6, S7, S8" in out.getvalue()  # 取れなかった出典を ID で出す（会議の S3 は取る手段がないので数えない）
        assert page_meta({"Last-Modified": "Mon, 12 Oct 2026 19:13:19 GMT"}, b'<title>A &amp; B</title>') == {"name": "A & B", "updated": "2026-10-12"}
        assert page_meta({}, b'<script>{"dateModified": "2026-10-14 16:26:26Z"}</script>')["updated"] == "2026-10-14" and page_meta({}, b"<p>x</p>") == {}
        assert key("https://a.com/x?id=AAAAAAAAAAAAAAAAAAAAAAAA") != key("https://b.org/x?id=AAAAAAAAAAAAAAAAAAAAAAAA")  # ファイルの ID で比べるのは Google の文書だけ
        assert guess_kind("https://acme.slack.com/archives/C1/p1") == "チャット" and guess_kind("https://example.com") is None and guess_kind("https://github.com/o/r") == "公式" and guess_kind(tmp) == "データ"
    with tempfile.TemporaryDirectory() as tmp:  # 全体の索引: 新しい形と前の形の台帳から、同じ出典を 1 行にまとめる
        ws = Path(tmp)
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("Customers/A/x/references.md", HEAD + "| " + " | ".join(SRC_COLS) + " |\n|" + "---|" * len(SRC_COLS) + "\n"
            "| S1 | A の docs | https://docs.example.com/a | 公式 | 2026-10-01 | 2026-10-20 | 可 | p.3 の表 |\n| S2 | 定例 | meetings mtg_01abc | 会議 | 2026-10-21 | 2026-10-21 | 不可 |  |\n"
            "| S3 | 口頭 | ユーザー（会話） | 口頭 | 2026-10-21 | 2026-10-21 | 不可 |  |\n\n## 出典の表\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n| F1 | https://z.example.com の 3 件 | 数字 | S1 | 済 |\n")
        put("Internal/y/references.md", "# references\n\n形: 元 — 見る箇所 — 確かめた日\n\n- [A docs](https://docs.example.com/a/) — 2026-10-25 — 公開 — p.5 の図\n"
            f"- [長い](https://long.example.com) — {'あ' * 400}\n\n| 資料 | URL・場所 | メモ |\n|---|---|---|\n| B | https://b.example.com/x | 図 |\n")
        put("Internal/z/references.md", "| 資料 | メモ |\n|---|---|\n| ユーザー（会話） | 別の資料の口頭 |\n")
        put("Research/references.md", "## 前の索引から\n\n- 使わなかったもの: C の事例（数字が古い）\n- [定例の続き](Dahlia: mtg_01abc) — 【社内】・2026-10-22\n")
        assert index(ws, today="2026-10-29") == 5
        t = (ws / INDEX).read_text()
        body = t.split("に作った）\n\n")[1].splitlines()
        assert generated(ws / INDEX) and t.startswith("# 参考資料の索引") and "5 件（2026-10-29 に作った）" in t
        assert body[0] == "- [A docs](https://docs.example.com/a/) — 2026-10-25 — 公開 — p.5 の図（Internal/y、Customers/A/x）"  # 同じ URL（末尾の / は見ない）は 1 行に、新しく確かめた台帳の本文で
        assert "- [定例の続き](Dahlia: mtg_01abc) — 【社内】・2026-10-22（Research、Customers/A/x）" in body  # 会議は ID でまとめる
        assert "- B — https://b.example.com/x — 図（Internal/y）" in body and "ユーザー（会話）" not in t  # 前の形の表の行も読む。口頭（場所が URL でも会議でもない）は資料の台帳だけ
        assert "- 使わなかったもの: C の事例（数字が古い）（Research）" in body and not any(s in t for s in ("z.example.com", "資料 — URL", "形: 元", "| S1"))  # Research の場所のない行は出す。事実の行・表の見出し・地の文は出さない
        assert (long := next(b for b in body if "long.example.com" in b)).endswith("…（Internal/y）") and len(long) < LINE_MAX + 20
        g = "https://docs.google.com/presentation/d/" + "x" * 300
        assert short("あ" * 300).endswith("…") and short(f"[a]({g}) — " + "い" * 300).startswith(f"[a]({g})")  # 長い URL も切らない
        assert index(ws, today="2026-10-29") == 5 and (ws / INDEX).read_text() == t  # 何度作り直しても同じ
        (ws / INDEX).write_text("# 参考資料の索引\n\n- [手で書いた](https://x.example.com) — 観点\n")
        assert index(ws) is None and "手で書いた" in (ws / INDEX).read_text() and not generated(ws / INDEX)  # 前の形は上書きしない（desk-migrate で移す）
        assert keys("[a](https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit)、Dahlia: mtg_01x") == ["1AbCdEfGhIjKlMnOpQrStUvWxYz", "mtg_01x"]
    with tempfile.TemporaryDirectory() as tmp:  # desk-init の雛形は、出典のない索引と同じ頭（雛形は手で直すので、ずれたら止める）
        assert index(tmp) == 0
        tpl = Path(__file__).resolve().parents[2] / "desk-init" / "templates" / INDEX
        assert tpl.read_text().split("0 件")[0] == (Path(tmp) / INDEX).read_text().split("0 件")[0] and generated(tpl)
    print("selftest ok")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("folder"); s.add_argument("target")
    s.add_argument("--name"); s.add_argument("--kind", choices=SRC_KINDS); s.add_argument("--use", default="")
    s.add_argument("--updated", type=lambda v: v if DATE.fullmatch(v) else sys.exit(f"--updated は YYYY-MM-DD: {v}")); s.add_argument("--out", choices=("可", "不可"))
    s = sub.add_parser("seen"); s.add_argument("folder"); s.add_argument("ids", nargs="+")
    s = sub.add_parser("check"); s.add_argument("folder"); s.add_argument("--fetch", action="store_true"); s.add_argument("--days", type=int, default=14)
    s = sub.add_parser("index"); s.add_argument("ws", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        add(a.folder, a.target, a.name, a.kind, a.use, a.updated, a.out)
        reindex(a.folder)
    elif a.cmd == "seen":
        seen(a.folder, a.ids)
        reindex(a.folder)
    elif a.cmd == "index":
        ws = Path(a.ws) if a.ws else workspace() or sys.exit("ワークスペースが見つからない（desk.toml も ~/.desk.toml の workspace もない）。ワークスペースを渡す")
        if (n := index(ws)) is None:
            sys.exit(f"{ws / INDEX} は手で書いた前の形なので、上書きしない。desk-migrate の apply で移すと、作り直せる")
        print(f"作り直した: {ws / INDEX}（{n} 件）")
    else:
        return 1 if check(a.folder, a.fetch, a.days) else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
