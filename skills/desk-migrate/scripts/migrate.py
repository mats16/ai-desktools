#!/usr/bin/env python3
"""usage: migrate.py [check]                         前の版のワークスペースで、変えるものを出す（何も変えない）
       migrate.py apply                         控えを .desk/migrate/<時刻>/ に取ってから、rules/ を移し、決まりの ID とパスを書き換え、frontmatter を足し、ワークスペースの決まりの ID を外し、rules/ を recipes/ にする
       migrate.py relink <P-ID> <rules/ のファイル>|--split   分け直しで行き先が決まらない台帳の提案の、行き先を決める（apply の要判断に出る）
       migrate.py relink-id <ws- の ID> <ワークスペースのファイル>|戻さない   ID を外すときにファイルが決まらない ID（2 つのファイルにある・どこにもない）の行き先を決め、ID を外す
       migrate.py to-user                       ワークスペースの desk.toml を個人の設定（~/.desk.toml。DESK_CONFIG があればそのパス）に移し、workspace を足す
       migrate.py --selftest
ワークスペース（desk.toml か、前の版の factory.toml のあるフォルダ）を、今の版へ移す。2026-10-24 の版で、スキルの名前を slides-・docs- で始め、
プラグインのファイルを読む場面ごとに分け、決まりの ID を主題で付け直した（ids_20261024.json）。ID の表は日付の順に当てる（あとの版で足すときは ids_<日付>.json を置く）。
2026-10-25 の版で、名前を AI Desk Tools にそろえた（factory.toml → desk.toml、.factory/ → .desk/、factory-init・doctor・migrate・kaizen → desk-、
[factory] → [desk]、[drive] factory → [drive] desk）。置き場所は変えない（どれもワークスペースの中）。同じ日に、dreaming を desk-dreaming に、
決まりの ID の factory-dreaming を desk-dreaming にした（ids_20261025.json）。記録のフォルダ .desk/dreaming/ と台帳の by の値 dreaming は替えない。
2026-10-27 の版で、ワークスペースの決まりを frontmatter（description・paths）で出すようにした。前の版の rules/<スキル>/<ファイル>（プラグインの同じパスへの上書き）には、
paths にそのパスを書いた frontmatter を足す（出る場面は前と同じ。ファイルは動かさないので、台帳のファイルへのつながりもそのまま）。
同じ日の次の版で、ワークスペースの決まりから ID（[ws-…]）を外した。ID → 書いてあるファイルの対応を台帳の migrated の記録に残し（ledger.py は前の記録の ID をそのファイルとして読む。
台帳の前の行は書き換えない）、ファイルごとに ID を外す前と後の全文を「移行」の版として残す（ledger.py undo で戻せる）。
2026-10-29 の版で、rules/ を recipes/ にし、決まりのファイルを 1 つずつフォルダにした（rules/<…>/<名前>.md → recipes/<名前>/RECIPE.md）。frontmatter の paths は step にする
（当たるプラグインのファイルがどれも材料を集める作業なら gather、どれも組む作業なら build、ほかは書かない）。paths のなかったものは per_material: true（資料ごとに選ぶ）。
点検の checks.py は recipes/slide_checks/・doc_checks/ に、ドキュメントのテンプレートは recipes/doc_templates/templates/ に移す。台帳・AGENTS.md・CLAUDE.md・顧客の memory.md・
レシピ・構成案の中の前のパスも書き換える。前の段の移しは rules/ の中で済ませてから、最後にこの段を回す。
2026-10-29 の版で、source-scout を desk-crawl にした（決まりの ID は ids_20261029.json）。記録の .desk/scout/<話題>/ は、状態・種類・mode を今の形にして .desk/crawl/<話題>/ に移す。
何度回してもよい。標準ライブラリだけ。"""
import fnmatch, json, os, re, shutil, subprocess, sys, tempfile, time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]  # プラグインの skills/
sys.path.insert(0, str(PLUGIN / "deck-practices" / "scripts"))
import desk  # noqa: E402  ワークスペースの探し方
import ledger  # noqa: E402  台帳の提案の状態（state）
from ledger import TOPICS  # noqa: E402  決まりの ID の主題
MAPS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.glob("ids_*.json"))]  # 日付の順。ids: 前の ID → 今の ID、prefixes: 前の接頭辞 → 今の接頭辞（ws- と、もうない ID に使う）
MOVES = [  # rules/ の下の前のパス → 今のパス（上から当てる。フォルダはその下を全部）
    ("deck-practices/visual.md", "slides-build/visual.md"), ("deck-practices/reuse.md", "slides-build/reuse.md"),
    ("deck-practices/visual_doc.md", "docs-build/visual.md"), ("deck-build/slides.md", "slides-build/pages.md"),
    ("deck-build", "slides-build"), ("doc-build", "docs-build"), ("deck-template", "slides-template"),
    ("slides-speaker-notes", "vids-voice"), ("vids-beta", "vids-build"),
    *((f"factory-{s}", f"desk-{s}") for s in ("init", "doctor", "migrate", "kaizen")), ("dreaming", "desk-dreaming"), ("source-scout", "desk-crawl")]
OLD_CONF, OLD_DIR = "factory.toml", ".factory"  # 2026-10-25 より前の設定と記録のフォルダの名前
NAMES = [  # 2026-10-25 の名前の替え。本文・台帳と、設定に当てる（決まりの ID の factory-dreaming は ids_20261025.json で替える。
           # .factory は、パスの頭にあるものだけが記録のフォルダ。~/.factory・${HOME}/.factory・.factory-old はほかのもの）
    (r"(?<![A-Za-z0-9_-])factory-(init|doctor|migrate|kaizen)(?![A-Za-z0-9_-])", r"desk-\1"), (r"(?<![\w-])factory\.toml", "desk.toml"),
    (r"(?<![\w/.~}$-])\.factory(?![\w.-])", ".desk"), (r"\[drive\] factory\b", "[drive] desk"), (r"\bdrive\.factory\b", "drive.desk"), (r"\[factory\] private", "[desk] private")]
SPLIT = {  # 中身を場面ごとに分けたプラグインのファイル。ワークスペースの上書きも、どの節への足しかで分け直す
    "deck-practices/SKILL.md": "deck-practices/SKILL.md・start.md・agents.md・deliver.md・revise.md、slides-build/workflow.md",
    "slides-build/pages.md": "slides-build/pages.md・diagrams.md・commands.md・themes.md・images.md・api.md・legacy.md（前の deck-build/slides.md）",
    "slides-build/SKILL.md": "slides-build/SKILL.md・lint.md、deck-practices/drive.md（前の deck-build/SKILL.md）",
    "docs-build/SKILL.md": "docs-build/SKILL.md・lint.md・api.md・themes.md・templates.md（前の doc-build/SKILL.md）",
    "deck-review/SKILL.md": "deck-review/SKILL.md・ask.md・fix.md・prompt_fix.md、deck-practices/agents.md（子の起こし方）",
    "desk-dreaming/SKILL.md": "desk-dreaming/SKILL.md・run.md・apply.md",
    "desk-dreaming/run.md": "desk-dreaming/run.md・prompt_propose.md（4 の a〜d の案の出し方。2026-10-25）",
    "slides-template/SKILL.md": "slides-template/SKILL.md・create.md・dark.md・fonts.md",
    "vids-build/SKILL.md": "vids-build/SKILL.md・avatars.md",
    "deck-practices/content.md": "deck-practices/content.md・content_customer.md・content_internal.md・content_explain.md（§1 の資料の種類ごとの決まり）"}
B = "A-Za-z0-9_-"  # ID とスキルの名前の前後の区切り（和文は続けて書いてもよいので、英数字だけを見る）
DREAMING = re.compile(rf"(?<![{B}])(?<!\.desk/)dreaming(?![{B}])(?!/(?:last_run|log|backup)\b)")  # 2026-10-25 より前のスキルの名前。記録のフォルダ .desk/dreaming/（中の last_run・log・backup）は替えない
PATHS = [  # 本文の中のパスとスキルの名前（決まりの ID は先に替えるので、deck-build-005 などはもう残っていない）
    (r"deck-practices/visual_doc\.md", "docs-build/visual.md"), (r"deck-practices/visual\.md", "slides-build/visual.md"),
    (r"deck-practices/reuse\.md", "slides-build/reuse.md"), (r"deck-build/slides\.md", "slides-build/pages.md"),
    (r"deck-build/scripts/(docs|doc_layout)\.py", r"docs-build/scripts/\1.py"), (r"deck-build/scripts/(gapi|sheet|drive_put)\.py", r"deck-practices/scripts/\1.py"),
    *((rf"(?<![{B}]){a}(?![{B}])", b) for a, b in (("deck-build", "slides-build"), ("doc-build", "docs-build"), ("deck-template", "slides-template"),
                                                    ("slides-speaker-notes", "vids-voice"), ("vids-beta", "vids-build"))), *NAMES,
    (DREAMING, "desk-dreaming"),  # .factory を .desk にしたあとに当てる
    (rf"(?<![{B}])source-scout(?![{B}])", "desk-crawl"), (rf"(?<![{B}])\.desk/scout(?![{B}])", ".desk/crawl"), (rf"(?<![.{B}])scout\.py(?![{B}])", "crawl.py")]  # 2026-10-29。記録の .desk/scout/ は move_scout が .desk/crawl/ に移す
OLD_IDS = [re.compile(rf"(?<![{B}])(ws-)?(" + "|".join(sorted(map(re.escape, m["prefixes"]), key=len, reverse=True)) + rf")-(\d{{3}})(?![{B}])") for m in MAPS]
WS_ID = re.compile(r"\[(ws-[\w-]+?-\d{3})\]")
WS_FULL = re.compile(r"ws-[a-z][\w-]*?-\d{3}")  # 台帳の値がまるごとワークスペースの ID
unid = lambda t: re.sub(r"\[ws-[\w-]+?-\d{3}\] ?", "", t)  # ワークスペースの [ID] を外した文（TAGS と同じ外し方）
WS_ANY = re.compile(rf"(?<![{B}])ws-[a-z][\w-]*?-\d{{3}}(?![{B}])")  # ワークスペースの決まりの ID（角括弧のあるなしによらない）
PLUGIN_ID = re.compile(rf"(?<![{B}])(?!ws-)([a-z][\w-]*?)-\d{{3}}(?![{B}])")


def workspace(start="."):
    """今の版（desk.toml）か前の版（factory.toml）のワークスペース。上へたどって見つからなければ ~/.desk.toml の workspace（desk.py）。"""
    d = Path(start).resolve()
    if ws := next((x for x in (d, *d.parents) if (x / "desk.toml").is_file() or (x / OLD_CONF).is_file()), None):
        return ws
    return f[1] if (f := desk.locate(d)) else None


def conf_keys(text):
    """設定のキーを今の名前に: [factory] → [desk]、[drive] の中の factory → desk。行ごとに今のテーブルを見る（[slides.templates] のテーマの名前 factory は替えない）。"""
    table, out = None, []
    for line in text.splitlines(keepends=True):
        if m := re.match(r"\s*\[([^\]]+)\]", line):  # テーブルの見出し（字下げしてもよい）
            table = m.group(1).strip()
            line = re.sub(r"^(\s*)\[factory\]", r"\1[desk]", line)
        elif table == "drive":
            line = re.sub(r"^(\s*)factory(\s*=)", r"\1desk\2", line)
        out.append(line)
    return "".join(out)


def data_moves(ws):
    """2026-10-25 より前の名前で残っているもの: [(前, 今)]。"""
    return [(ws / old, ws / new) for old, new in ((OLD_CONF, "desk.toml"), (OLD_DIR, ".desk")) if (ws / old).exists()]


SCOUT_TIER = {"core": "follow", "muted": "candidate"}  # 2026-10-29: source-scout の状態 → desk-crawl の状態（muted は人が休ませた先。読まない dropped にはしない）
SCOUT_KIND = {"gmail": "gmail-search"}  # 種類の名前の替え（wiki は、どの wiki かが分からないので替えない）
SCOUT_MODE = {"filter": "Busy source: scan the first lines and open only posts that look like an announcement or match a marker note.",
              "index": "Digest source: open the original post of each item you pick, because the summary can be wrong."}  # mode は覚え書きになった


def scout_moves(ws):
    """2026-10-29: source-scout の記録 .desk/scout/<話題>/ → desk-crawl の .desk/crawl/<話題>/ [(前, 今)]。"""
    old = ws / ".desk" / "scout"
    return [(p, ws / ".desk" / "crawl" / p.name) for p in sorted(old.iterdir()) if p.is_dir()] if old.is_dir() else []


def scout_id(sid):
    k, _, ref = sid.partition(":") if isinstance(sid, str) else ("", "", "")
    return f"{SCOUT_KIND[k]}:{ref}" if k in SCOUT_KIND and ref else sid


def move_scout(ws):
    """.desk/scout/ の話題を、今の形（状態・種類・mode）にして .desk/crawl/ に移す。前の中身は .desk/migrate/scout_<時刻>/ に控える。
    移す先がもうあれば、上書きせずに出す（寄せるのは人が決める）。前の回の取りこぼし（misses）は、子の読み方の外れだったので写さない
    （今は、使う側が返したものだけを取りこぼしとして数える）。読み手の反応（feedback）と項目の value も、もう使わないので写さない。"""
    old = ws / ".desk" / "scout"
    if not old.is_dir():
        return []
    out, day, stamp = [], time.strftime("%Y-%m-%d"), time.strftime("%Y%m%d-%H%M%S")
    for src, dst in scout_moves(ws):
        if dst.exists():
            out.append(f"移していない（移す先がもうある。中身を寄せて前のほうを消す）: {src.relative_to(ws)}/ → {dst.relative_to(ws)}/")
            continue
        try:  # 1 つの話題が読めなくても（壊れた JSON、思わない形）、ほかの話題とあとの段は止めない
            reg = json.loads((src / "sources.json").read_text(encoding="utf-8")) if (src / "sources.json").is_file() else {"sources": {}, "notes": [], "next_note": 1}
            lines = [json.loads(l) for l in (src / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] if (src / "runs.jsonl").is_file() else []
            n, srcs = reg.get("next_note", 1), {}
            for sid, e in reg.get("sources", {}).items():
                e = {**e, "tier": SCOUT_TIER.get(e.get("tier"), e.get("tier") or "candidate")}
                if text := SCOUT_MODE.get(e.pop("mode", None)):
                    e["notes"] = e.get("notes", []) + [{"id": f"n{n}", "text": text, "added": day, "helpful": 0, "harmful": 0}]
                    n += 1
                srcs[scout_id(sid)] = e
            reg["sources"], reg["next_note"] = srcs, n
            for done in reg.get("applied", {}).values():  # 当てた覚え書きの控え [位置, 先, 文] の先も替える（記録し直したときに、当てたと分かるように）
                done["lessons"] = [[k[0], scout_id(k[1]), *k[2:]] if isinstance(k, list) and len(k) > 1 else k for k in done.get("lessons", [])]
            rows = []
            # ponytail: 前の読み手の反応（feedback・value 0）は手柄から外さずに捨てる。used を消すと「使われた済み」の印も消えるため。source-scout の記録は 3 日分しかない
            for r in lines:
                r.pop("feedback", None), r.pop("misses", None)
                for x in (x for k in ("reads", "discovered", "lessons") for x in r.get(k, []) if isinstance(x, dict) and "source" in x):
                    x["source"] = scout_id(x["source"])
                for i in r.get("items", []):
                    i.pop("value", None)
                    i["seen_in"] = [scout_id(x) for x in i.get("seen_in", [])]
                    if i.get("origin"):
                        i["origin"] = scout_id(i["origin"])
                rows.append(json.dumps(r, ensure_ascii=False))
        except (OSError, ValueError, TypeError, AttributeError) as e:
            out.append(f"要判断: {src.relative_to(ws)}/ を読めないので移していない（{e}）。直してから apply を回し直すか、要らなければ消す")
            continue
        (backup := ws / ".desk" / "migrate" / f"scout_{stamp}").mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, backup / src.name, dirs_exist_ok=True)  # 移す話題だけを控える（移さないものを回すたびに写さない）
        dst.mkdir(parents=True)
        (dst / "sources.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if rows:
            (dst / "runs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
        shutil.rmtree(src)  # plan.json は前の回の読み方なので写さない（次の plan が作る）
        out.append(f"移した: {src.relative_to(ws)}/ → {dst.relative_to(ws)}/（状態・種類・mode を desk-crawl の形にした）")
        if wiki := sorted(x for x in srcs if x.startswith("wiki:")):
            out.append(f"要判断: {dst.relative_to(ws)}/sources.json の {'・'.join(wiki)} は、wiki のサービスの名前（confluence: など）の先にする（desk-crawl の kinds.md）")
    if not any(p.is_dir() for p in old.iterdir()):  # 話題を移し終えたら、残りのファイル（.DS_Store など。話題でないので控えない）ごと消す。残すと crawl.py が止まったままになる
        shutil.rmtree(old)
        out.append("要判断: 定期の集めを前の名前（source-scout）で登録していれば、登録したプロンプトのスキルの名前を desk-crawl に替える（登録はワークスペースの外にあり、ここからは直せない）")
    return out


def move_data(ws):
    """設定を desk.toml に（キーも替える）、記録のフォルダを .desk/ に名前を替える。前の factory.toml は .desk/migrate/ に控える。
    今の名前のものがもうあれば、上書きせずに出す（寄せるのは人が決める）。"""
    out, new = [], ws / ".desk"
    if (old := ws / OLD_DIR).is_dir():
        new.mkdir(exist_ok=True)
        for p in sorted(old.iterdir()):
            if (new / p.name).exists():
                out.append(f"移していない（移す先がもうある。中身を寄せて前のほうを消す）: {p.relative_to(ws)} → {(new / p.name).relative_to(ws)}")
            else:
                p.rename(new / p.name)
        if not any(old.iterdir()):
            old.rmdir()
            out.append(f"移した: {OLD_DIR}/ → .desk/")
    if (src := ws / OLD_CONF).is_file():
        if (dst := ws / "desk.toml").exists():
            out.append(f"移していない（desk.toml がもうある。{OLD_CONF} の値を寄せてから、{OLD_CONF} を消す）: {OLD_CONF}")
        else:
            text = src.read_text(encoding="utf-8")
            for a, b in NAMES:
                text = re.sub(a, b, text)
            dst.write_text(conf_keys(text), encoding="utf-8")
            (new / "migrate").mkdir(parents=True, exist_ok=True)
            src.rename(new / "migrate" / OLD_CONF)
            out.append(f"移した: {OLD_CONF} → desk.toml（[factory] は [desk]、[drive] factory は [drive] desk に。前のものは .desk/migrate/{OLD_CONF} に控えた）")
    gi = ws / ".gitignore"  # 雛形の .gitignore は設定だけを git に入れる。替えないと desk.toml が外れる
    if gi.is_file() and (g := gi.read_text(encoding="utf-8")) != (n := re.sub(r"(?m)^!/factory\.toml$", "!/desk.toml", g)):
        gi.write_text(n, encoding="utf-8")
        out.append(f"書き換えた: .gitignore（!/{OLD_CONF} → !/desk.toml）")
    return out


def to_user(ws):
    """ワークスペースの desk.toml を個人の設定に移し、頭に workspace を足す（全体に入れるとき。頼まれたときだけ回す）。前のものは .desk/migrate/ に控える。
    個人の設定がもうあれば、上書きせずに出す（寄せるのは人が決める）。"""
    src, dst = ws / "desk.toml", desk.user_config()
    if not src.is_file():
        return [f"移していない（{ws} に desk.toml がない。もう {dst} を読んでいる）"]
    if not dst:
        return ["移していない（DESK_CONFIG が空。移すなら DESK_CONFIG を外すか、置くパスにする）"]
    if desk.old(ws):  # 移す前の名前が残っていると、個人の設定から指せない（desk.user が止める）
        return [f"移していない（前の版の {OLD_CONF} が残っている。先に apply で移す）"]
    if dst.exists():
        return [f"移していない（{dst} がもうある。desk.toml の値を寄せてから、desk.toml を .desk/migrate/ に移す）"]
    if up := desk.local(ws.parent):  # 移したあと、中で開くと上の desk.toml が勝つ（init.py --user と同じく作らない）
        return [f"移していない（上の {up[0]} が、{ws} の中では勝つ。中と外で設定が変わるので、{ws} を {up[1]} の外に置いてから回す）"]
    text = desk.with_workspace(src.read_text(encoding="utf-8"), ws)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    bak = ws / ".desk" / "migrate" / "desk.toml"
    if bak.exists():  # 前に移したときの控えを上書きしない
        bak = bak.with_name(f"desk_{time.strftime('%Y%m%d-%H%M%S')}.toml")
    bak.parent.mkdir(parents=True, exist_ok=True)
    src.rename(bak)
    return [f"移した: desk.toml → {dst}（workspace = {ws}。前のものは {bak.relative_to(ws)} に控えた）"]


def rewrite(text, paths=True, seen=None, ws_map=None):
    """前の ID とパスを今のものに。接頭辞だけで決める付け替えは、確かに ID だと言えるとき（ws- で始まる、[ID] と角括弧で囲む、
    台帳の値がまるごと ID）だけにする。前の接頭辞には content・assets・template などのふつうの語があり、memory.md の「assets-100」を替えないため。
    ws_map（ws_plan）は、ワークスペースの ID の付け替えを先に当てる（番号がぶつかったものの付け替えも入る）。seen を渡すと、替えた (前, 今) を足す。"""
    if ws_map:
        def mapped(x):
            if seen is not None and x.group(0) in ws_map:
                seen.add((x.group(0), ws_map[x.group(0)]))
            return ws_map.get(x.group(0), x.group(0))
        text = WS_ANY.sub(mapped, text)
    for pat, m in zip(OLD_IDS, MAPS):
        def new_id(x, ids=m["ids"], pre=m["prefixes"]):
            ws, p, num = x.group(1), x.group(2), x.group(3)
            old, t = x.group(0), x.string
            if not ws and f"{p}-{num}" in ids:
                new = ids[f"{p}-{num}"]
            elif ws or t[x.start() - 1:x.start()] == "[" and t[x.end():x.end() + 1] == "]" or (x.start(), x.end()) == (0, len(t)):
                new = f"{ws or ''}{pre[p]}-{num}"
            else:
                return old
            if seen is not None and new != old:
                seen.add((old, new))
            return new
        text = pat.sub(new_id, text)
    for a, b in PATHS if paths else ():
        text = re.sub(a, b, text)
    return text


def texts(ws):
    """ID とパスを書き換える、人と会話が書くファイル。"""
    return [p for p in [ws / "AGENTS.md", ws / "CLAUDE.md", *sorted((ws / "rules").rglob("*.md")), *sorted((ws / "recipes").rglob("*.md")),
                        *sorted((ws / "Customers").glob("*/memory.md"))] if p.is_file()]  # recipes/ は 2026-10-29 から。そのあとの名前の替え（source-scout）も届くように


VERBATIM = {"quote", "a", "reason"}  # 台帳の、人の言葉をそのまま持つ欄（修正の指示の原文、判断待ちの答え、却下の理由）。書き換えない
KEEP = VERBATIM | {"by"}  # by は書いた者の種類（session・dreaming・import）。ledger.py が値で数えるので、スキルの名前を替えても替えない


def ledger_lines(path, fn):
    """台帳の行ごとに、文字列の値を fn で書き換える（JSON の形は変えない。人の言葉の欄 VERBATIM はそのまま）。"""
    def walk(v):
        if isinstance(v, str):
            return fn(v)
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: x if k in KEEP else walk(x) for k, x in v.items()}
        return v
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        out.append(json.dumps(walk(json.loads(line)), ensure_ascii=False) if line.strip() else line)
    return "\n".join(out) + "\n"


def strings(ws):
    """ID を書き換える文字列: rules/ などの md の本文と、台帳の値（人の言葉の欄 VERBATIM は除く）。"""
    out = [p.read_text(encoding="utf-8") for p in texts(ws)]
    led = ws / ".desk" / "ledger.jsonl"
    if led.is_file():
        ledger_lines(led, lambda v: out.append(v) or v)
    return out


def ws_plan(ws):
    """ワークスペースの ws- の ID の、前 → 今。前に別の接頭辞だったものを 1 つの主題にまとめると番号がぶつかる
    （ws-prompt_doc-001 と ws-prompt_slides-001 がどちらも ws-deck-review-001）ので、あとのものを空いた番号へ移す。
    今の形の ID（付け替えても変わらないもの）は動かさず、その番号も使ったものに数える。定義と台帳に同じ対応を当てるので、履歴は混ざらない。"""
    found = {x for t in strings(ws) for x in WS_ANY.findall(t)}
    target = {x: rewrite(x, paths=False) for x in found}
    taken, out = {x for x in found if target[x] == x}, {}
    for x in sorted(found - taken):
        pre, num = target[x].rsplit("-", 1)
        n = int(num)
        while f"{pre}-{n:03d}" in taken:
            n += 1
        out[x] = f"{pre}-{n:03d}"
        taken.add(out[x])
    return out


def plan(ws):
    """(移すファイル [(前, 今)], 書き換えるファイル [パス], 分け直す上書き [(ファイル, 分けた先)], ワークスペースの ID の対応)。"""
    rules, moves, seen = ws / "rules", [], set()
    for old, new in MOVES:
        src = rules / old
        if src.is_file():
            pairs = [(src, rules / new)]
        elif src.is_dir():
            pairs = [(f, rules / new / f.relative_to(src)) for f in sorted(src.rglob("*")) if f.is_file()]
        else:
            continue
        for f, dst in pairs:
            if f not in seen:  # 上の行で移すと決めたものは、下の行で二度移さない
                seen.add(f)
                moves.append((f, dst))
    led, ws_map = ws / ".desk" / "ledger.jsonl", ws_plan(ws)
    fix = lambda t: rewrite(t, ws_map=ws_map)
    edit = [p for p in texts(ws) if (t := p.read_text(encoding="utf-8")) != fix(t)]
    if led.is_file() and ledger_lines(led, fix) != led.read_text(encoding="utf-8"):
        edit.append(led)
    after = {str(dst.relative_to(rules)) for _, dst in moves}  # 移したあとの rules/ の md
    if rules.is_dir():
        after |= {str(p.relative_to(rules)) for p in rules.rglob("*.md")}
    split = [(k, v) for k, v in SPLIT.items() if k in after]
    return moves, edit, split, ws_map


def relink_files(ws):
    """台帳を合わせる控え: 移行した時点にあった、分け直すファイルへの提案（watch。まだ当てていないものと、文がそのファイルにあった当て済みのもの）と、エージェントが決めた行き先（done: 提案 → {"to": ファイルか "split", "from": 前の変更先}）。
    控えのフォルダ（消してよい）でなく .desk/migrate/ の直下に置く。"""
    d = ws / ".desk" / "migrate"
    load = lambda n, empty: json.loads((d / n).read_text(encoding="utf-8")) if (d / n).is_file() else empty
    return d, load("relink.json", []), load("relink_done.json", {})


def in_split(ws):
    """分け直す上書き（SPLIT）を変更先にする提案のうち、まだ当てていないものと当て済みのもの（却下・取り下げ・戻した・Issue にしたは見ない）。
    プラグインへの提案（plugin。file は skills/ からのパス）は、ワークスペースの上書きを分けても変更先が変わらないので見ない。"""
    if not (ws / ".desk" / "ledger.jsonl").is_file():
        return []
    return [p for p in ledger.state(ws)[1].values()
            if not p.get("plugin") and p["file"].removeprefix("rules/") in SPLIT and p["status"] in ("未適用", "適用済み")]


def relinks(ws):
    """分け直しで、提案の変更先（file）と文の置き場所が合わなくなったもの: [(提案の ID, 前のファイル, 今のファイル, 決められない理由)]。
    文がほかの rules/ の 1 つのファイルにだけあれば、それが今のファイル（理由は None）。決められないもの（今のファイルは None）は、relink で決める。
    file が古いままだと、ledger.py の apply・undo・drift が文を見つけられない。移行した時点になかった提案（そのあとに出したもの、移行していないワークスペースのもの）と、
    決めたもの（relink_done.json）は見ない。"""
    rules = ws / "rules"
    _, watch, done = relink_files(ws)
    md = {str(f.relative_to(ws)): unid(f.read_text(encoding="utf-8")) for f in rules.rglob("*.md")} if rules.is_dir() else {}
    out = []
    for p in in_split(ws):
        f, i = p["file"], p["id"]
        if i in done or i not in watch:
            continue
        if p["status"] == "未適用" and not p["old"].strip():
            out.append((i, f, None, "まだ当てていない足す提案。分け直したので、足す先を決める"))
            continue
        needle = unid(p["new"] if p["status"] == "適用済み" else p["old"]).strip()  # ID を外したあとの文で探す（apply がファイルから外す）
        if not needle or needle in md.get(f, ""):
            continue
        hits = sorted(k for k, t in md.items() if k != f and needle in t)
        if len(hits) == 1:
            out.append((i, f, hits[0], None))
        else:
            out.append((i, f, None, "当てた文が、分けた先にまたがるか、書き直した" if p["status"] == "適用済み" else "置き換える文が、分けた先にまたがるか、書き直した"))
    return out


def set_file(ws, i, f):
    """台帳の提案 i の変更先を f にする（行の形は変えない）。"""
    led = ws / ".desk" / "ledger.jsonl"
    lines = [json.dumps({**r, "file": f}, ensure_ascii=False) if (r := json.loads(x) if x.strip() else {}).get("kind") == "proposal" and r.get("id") == i else x
             for x in led.read_text(encoding="utf-8").splitlines()]
    led.write_text("\n".join(lines) + "\n", encoding="utf-8")


def asks(todo):
    """決められない提案の要判断と、決め方（relink のコマンド）。"""
    out = []
    for i, a, b, why in todo:
        if b:
            continue
        how = (f"足す先を決めて migrate.py relink {i} <rules/ のファイル>（元のままでよければ {a}）" if why.startswith("まだ当てていない足す")
               else f"1 つのファイルにまとまっているなら migrate.py relink {i} <そのファイル>。分けたままにするなら migrate.py relink {i} --split"
                    "（分けたことを残す。この提案は ledger.py undo で戻せなくなり、ledger.py drift には当てた文がないとして出る。報告に書く）" if why.startswith("当てた")
               else f"置き換える文のあるファイルに migrate.py relink {i} <そのファイル>。要らなくなった提案なら ledger.py withdraw {i} --reason 分け直し")
        out.append(f"要判断: 台帳の {i} の変更先 {a}: {why}。{how}")
    return out


def relink(ws):
    """relinks の今のファイルが決まった提案の file を付け替え、決まらない提案を要判断にする。"""
    todo = relinks(ws)
    for i, a, b, _ in todo:
        if b:
            set_file(ws, i, b)
    return [f"台帳を合わせた: {i} の変更先 {a} → {b}" for i, a, b, _ in todo if b] + asks(todo)


def decide(ws, i, target):
    """エージェントが決めた、提案 i の行き先（rules/ のファイルか "split"）を台帳と relink_done.json に残す。"""
    p = ledger.state(ws)[1].get(i) or sys.exit(f"台帳に {i} がない")
    p.get("plugin") and sys.exit(f"{i} はプラグインへの提案。変更先は skills/ の {p['file']} のままで、分け直しの行き先は決めない")
    if target == "--split":
        p["status"] == "適用済み" or sys.exit(f"{i} は {p['status']}。--split は当て済みの提案だけ（まだ当てていないものは、行き先のファイルを渡すか ledger.py withdraw）")
        target = "split"
    else:
        t = (ws / target).resolve()
        t.is_relative_to((ws / "rules").resolve()) and t.suffix == ".md" or sys.exit(f"行き先は rules/ の下の .md: {target}")
        target = str(t.relative_to(ws.resolve()))
        set_file(ws, i, target)
    d, watch, done = relink_files(ws)
    d.mkdir(parents=True, exist_ok=True)  # 前の変更先も残す（台帳の file は書き換えるので）
    (d / "relink_done.json").write_text(json.dumps({**done, i: {"to": target, "from": p["file"]}}, ensure_ascii=False, indent=1), encoding="utf-8")
    return [f"決めた: {i} の行き先 {target}" + ("（分けたことを残した。この提案は undo で戻せない）" if target == "split" else "")]


def needs(ws):
    """前の版のまま残っているもの（desk-doctor が出す）。"""
    moves, edit, _, _ = plan(ws)
    return ([str(a.relative_to(ws)) for a, _ in data_moves(ws)] + [".desk/scout/（desk-crawl の .desk/crawl/ へ）"] * (ws / ".desk" / "scout").is_dir()
            + [f"rules/{f.relative_to(ws / 'rules')}" for f, _ in moves] + [str(p.relative_to(ws)) for p in edit]
            + [f"{p.relative_to(ws)}（frontmatter）" for p, _ in fronts(ws, {f for f, _ in moves})]
            + [f"台帳の {i} の変更先（{a} → {b or '要判断'}）" for i, a, b, _ in relinks(ws)] + id_needs(ws)
            + [f"rules/{s.relative_to(ws / 'rules')}（recipes/ へ）" for s, _ in (recipe_moves(ws) if RECIPES else [])])


def id_needs(ws):
    """ワークスペースの決まりの ID の残り: 外すファイルと、台帳につなぐ ID と、決められない ID。"""
    ids, new, open_ = ws_ids(ws)
    return ([f"{p.relative_to(ws)}（決まりの ID）" for p, _, _ in strip_plan(ws, ids)] + [f"台帳の {x}（決まりの ID → {f}）" for x, f in sorted(new.items())]
            + [f"台帳の {x}（決まりの ID。要判断）" for x in sorted(open_)])


def fronts(ws, skip=()):
    """frontmatter（description）のない rules/ の .md: [(ファイル, 頭に足す frontmatter か None)]。プラグインのスキルのフォルダの下（前の版の、同じパスへの上書き）なら、
    そのパスを paths にする（出る場面は前と同じ）。ほかと、frontmatter はあるが description のないものは None（何に効くか分からないので、手で書く）。
    README.md と docs-build のテンプレート（templates/ の下）は決まりでない（desk.rules と同じ）。skip はこれから移すファイル（移したあとのパスで見る）。"""
    root = ws / "rules"
    have = {p for p in root.rglob("*.md") if p.is_file() and desk.described(desk.front(p.read_text(encoding="utf-8", errors="ignore")))} if root.is_dir() else set()  # 前の版の決まりのファイル（2026-10-27 の形）
    skills = {p.parent.name for p in PLUGIN.glob("*/SKILL.md")}
    out = []
    for p in sorted(root.rglob("*.md")) if root.is_dir() else []:
        rel = p.relative_to(root)
        if p in have or p in skip or rel == Path("README.md") or "templates" in rel.parts[:-1] or not p.is_file() or not (text := p.read_text(encoding="utf-8", errors="ignore")).strip():
            continue  # 中身のないファイルは、出すものがない
        plain = len(rel.parts) > 1 and rel.parts[0] in skills and not text.startswith("---")
        out.append((p, f"---\ndescription: プラグインの {rel.as_posix()} への足しと上書き\npaths: [{rel.as_posix()}]\n---\n\n" if plain else None))
    return out


def by_hand(ws, items):
    """frontmatter を足せないファイルの要判断。"""
    return [f"要判断: {p.relative_to(ws)} に frontmatter（description）がない。何に効くかを description に、手順に付く足しなら、開いたときに出すプラグインのファイルを paths に書く"
            "（deck-practices/rules.md の「Workspace rules」）" for p, head in items if not head]


def suggest(ws, rel):
    """分けたファイルへの上書きの、項目ごとの移し先の見込み（中で指すプラグインの ID の置き場所から）。行の番号と頭の語で示す（ID はこのあと外す）。"""
    out = []
    for n, line in enumerate((ws / "rules" / rel).read_text(encoding="utf-8").splitlines(), 1):
        if WS_ID.search(line) or re.match(r"\s*[-*] ", line) and PLUGIN_ID.search(line):
            cited = [p.group(0) for p in PLUGIN_ID.finditer(WS_ID.sub("", line)) if p.group(1) in TOPICS]
            to = sorted({str(f.relative_to(PLUGIN)) for c in cited for f in defined(c)})
            why = f"指す決まり（{'・'.join(cited)}）はプラグインにもうない" if cited else "プラグインの決まりを指していない"
            head = re.sub(r"^\s*[-*]\s*", "", WS_ID.sub("", line)).strip()[:20]
            out.append(f"  {n} 行目「{head}」: {'・'.join(to) if to else why + '。中身から決める'}")
    return out


def off_topic(ws):
    """書き換えたあとも、主題の表にない接頭辞の、角括弧なしのプラグインの ID（もっと前の版や手で付けたもの）。台帳は書き換える欄だけを見る（人の言葉の欄の古い ID は、原文のまま残すもの）。
    ワークスペースの ID（ws-）は主題によらず外すので見ない。"""
    found = set()
    for t in strings(ws):
        found |= {x for x in re.findall(rf"(?<![{B}])((?:ws-)?[a-z][\w-]*?)-\d{{3}}(?![{B}])", t)
                  if not x.startswith("ws-") and x not in TOPICS and x not in ("c", "p", "q")}
    return sorted(found)


def ledger_records(ws):
    led = ws / ".desk" / "ledger.jsonl"
    return [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines() if x.strip()] if led.is_file() else []


def ws_ids(ws):
    """ワークスペースの決まりの ID の、ID → ファイルの対応。(すべての対応, 台帳にまだ残していない対応, 決められない ID → 理由)。
    書いてあるファイルが 1 つならそのファイル。どこにも書いていない（消した決まり）が、台帳の今の状態で使われていれば（指摘の今の戻し先、答えていない判断待ち、
    まだ当てていない・Issue にした提案の --replaces と前の戻し先）、その ID を書いた台帳の提案の変更先が 1 つならそこ。前の戻し先やレビューの結果にだけ残る消した決まりの ID は、
    過去の記録としてそのまま読む（つなぎ直さない）。2 つのファイルにあるもの・決められないものは要判断（relink-id で決める。決めるまで、その ID は外さない）。
    前に決めたもの（migrated の記録）はそのまま。"""
    defs = {}
    for p in texts(ws):
        for x in WS_ID.findall(p.read_text(encoding="utf-8")):
            defs.setdefault(x, set()).add(p.relative_to(ws).as_posix())
    recs = ledger_records(ws)
    done = {k: v for r in recs if r.get("kind") == "migrated" for k, v in r["ids"].items()}
    cs, ps, qs, _ = ledger.state(ws) if recs else ({}, {}, {}, [])
    now = [*(c["to"] for c in cs.values()), *(q["rule"] for q in qs.values() if q["status"] == "未回答"),
           *(x for p in ps.values() if p["status"] in ("未適用", "Issue にした") for x in [*p.get("replaces", []), *p.get("prev", {}).values()]),
           *(x for p in ps.values() if p["status"] == "未適用" and not p.get("plugin") for x in WS_ID.findall(p["new"]))]  # まだ当てていない提案が書き入れる ID（当てるときに外す）
    pend = {}  # まだ当てていない提案が書き入れる ID → その変更先（当てると作るファイルでもよい）
    for p in ps.values():
        if p["status"] == "未適用" and not p.get("plugin"):
            for x in WS_ID.findall(p["new"]):
                pend.setdefault(x, set()).add(p["file"])
    used = {x for x in now if WS_FULL.fullmatch(x)}
    made = {}  # ID → その ID を決まりにした・書き入れた台帳の提案の変更先
    for r in recs:
        if r.get("kind") == "proposal" and not r.get("plugin"):
            for x in {*([r["rule"]] if WS_FULL.fullmatch(str(r.get("rule", ""))) else []), *WS_ID.findall(r.get("new", ""))}:
                made.setdefault(x, set()).add(r["file"])
    new, open_ = {}, {}
    for x in sorted((set(defs) | used) - set(done)):
        fs = defs.get(x) or {f for f in made.get(x, ()) if (ws / f).is_file()} or pend.get(x, set())
        if len(fs) == 1:
            new[x] = next(iter(fs))
        else:
            open_[x] = f"{'・'.join(sorted(fs))} の {len(fs)} つのファイルにある" if fs else "どのファイルにも書いていない（消した決まり）"
    return {**done, **new}, new, open_


TAGS = lambda ids: re.compile(r"\[(" + "|".join(map(re.escape, sorted(ids, key=len, reverse=True))) + r")\] ?")  # 外す [ID] と、その後ろの空白 1 つ


def strip_plan(ws, ids):
    """ID を外すファイル: [(ファイル, 今の文, 外したあとの文)]。"""
    if not ids:
        return []
    pat = TAGS(ids)
    return [(p, t, n) for p in texts(ws) if (n := pat.sub("", t := p.read_text(encoding="utf-8"))) != t]


def strip_ids(ws, ids, new):
    """台帳に対応（migrated）を残し、ファイルから ID を外して、ファイルごとに「移行」の版を残す。"""
    out = []
    if new:
        ledger.write(ws, {"kind": "migrated", "ids": new})
        out += [f"台帳をつないだ: {x} → {f}" for x, f in sorted(new.items())]
    for p, t, n in strip_plan(ws, ids):
        p.write_text(n, encoding="utf-8")
        pid = ledger.revise(ws, p.relative_to(ws).as_posix(), t, n, kind="移行")
        out.append(f"決まりの ID を外した: {p.relative_to(ws)}（{len(WS_ID.findall(t)) - len(WS_ID.findall(n))} 個。版 {pid}。戻すなら ledger.py undo {pid}）")
    return out


def hand_edits(ws):
    """移行より前に、当てた提案の文を手で直したファイル（前の ledger.py drift が出したもの）を「手で直した」版にする。その前の文は分からない（base）。
    直された提案を refs に残す（--auto はそのファイルに当てない。desk-dreaming の作り直しは、当てた文のところのいまの言い回しを、ユーザーの直しとして照らす）。
    台帳に版のまだないファイルだけを見る（2 回目からは版がある）。"""
    if not (ws / ".desk" / "ledger.jsonl").is_file():
        return []
    ps, vs = ledger.state(ws)[1], ledger.versions(ws)
    done = sorted((p for p in ps.values() if p["status"] == "適用済み" and not p.get("plugin") and not p.get("full")), key=lambda p: p["seq"])
    gone = {}
    for p in done:
        text = p["new"]
        for q in (q for q in done if q["file"] == p["file"] and q["seq"] > p["seq"] and q["old"]):  # あとで同じファイルに当てた置き換え（前の drift と同じ）
            if text in q["old"]:
                text = None
                break
            text = text.replace(q["old"], q["new"])
        f = p["file"]
        if text and f not in vs and ledger.rule_file(f) and unid(text) not in unid(ledger.read(ws, f)):
            gone.setdefault(f, []).append(p["id"])
    for f, refs in sorted(gone.items()):
        ledger.revise(ws, f, "", ledger.read(ws, f), kind="手で直した", base=True, refs=refs)
    return [f"手で直した版を残した: {f}（移行より前に {'・'.join(refs)} の当てた文を手で直していた。--auto は当てず、作り直しはユーザーの直しとして照らす）" for f, refs in sorted(gone.items())]


def baselines(ws):
    """版のまだない決まりのファイルを「初めの版」にする（移したあと、作る会話の初めの戻し先が、ファイル全体をその指摘の直しとして残さないように）。"""
    if not (ws / ".desk" / "ledger.jsonl").is_file():
        return []
    files = [f for f in ledger.rule_files(ws) if f not in ledger.versions(ws) and rewrite(f) == f]  # 前の名前のまま残ったファイル（移す先がもうあった）は、寄せるまで版にしない
    ledger.drift(ws, quiet=True, record=True, only=set(files))
    return [f"初めの版を残した: {len(files)} ファイル（台帳がこれからの直しを版で追う）"] if files else []


def id_asks(ws, ids, open_):
    """ID を外すときの要判断: 決められない ID と、角括弧なしで ID を指している行。"""
    out = [f"要判断: {x} は、{why}。行き先のファイルを決めて migrate.py relink-id {x} <ファイル>（消した決まりで、つなぐファイルがなければ 戻さない）" for x, why in sorted(open_.items())]
    pat = TAGS(ids) if ids else None
    for p in [*texts(ws), *sorted((ws / "rules").rglob("*.py"))]:
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            for n, line in enumerate((pat.sub("", text) if pat and p.suffix == ".md" else text).splitlines(), 1):  # md の [ID] は外すもの（apply の前の check でも）
                for x in sorted({m for m in WS_ANY.findall(line) if m in ids}):
                    out.append(f"要判断: {p.relative_to(ws)}:{n} が {x} を指している（ID はもうない。{ids[x]} の決まりなので、言葉かパスで指し直す）")
    return out


def changed(p, ws_map):
    """書き換える ID の (前 → 今) を、5 つまで添える（check で、ID でないものを替えていないかを見られるように）。"""
    seen = set()
    if p.suffix == ".jsonl":
        ledger_lines(p, lambda v: rewrite(v, seen=seen, ws_map=ws_map))
    else:
        rewrite(p.read_text(encoding="utf-8"), seen=seen, ws_map=ws_map)
    pairs = [f"{a} → {b}" for a, b in sorted(seen)]
    return f"（{'、'.join(pairs[:5])}{f' ほか {len(pairs) - 5}' if len(pairs) > 5 else ''}）" if pairs else "（パスだけ）"


def doc_imports(text):
    """ドキュメントの点検の import を、今のモジュールに。前の版の lint はスライドとドキュメントの部品を 1 つに持っていたが、
    今のドキュメントの lint（docs.py check）からは、スライドの lint.py は読めない。ドキュメントの部品（gdoc_paras など）は doc_lint にある。"""
    text = re.sub(r"(?m)^(\s*)import lint\b(?! as)", r"\1import doc_lint as lint", text)
    return re.sub(r"(?m)^(\s*)from lint import ", r"\1from doc_lint import ", text)


def defined(rid):
    """プラグインで [rid] を書いてあるファイル。"""
    return [f for f in PLUGIN.rglob("*.md") if f"[{rid}]" in f.read_text(encoding="utf-8")]


MATERIAL = ("deck-practices/content_customer.md", "deck-practices/content_internal.md", "deck-practices/content_explain.md")  # 資料の種類ごとに開くプラグインのファイル（content.md の §1 を 2026-10-24 に分けたもの）
USED = re.compile(r"使う決まり")  # 構成案の「使う決まり」の行（hooks/rules_overlay.py の USE）
RECIPES = True  # 最後の段（rules/ → recipes/）を回すか。selftest が、前の段の結果を rules/ の中で確かめるときだけ外す
slug = lambda s: re.sub(r"\W+", "_", s.lower()).strip("_") or "recipe"  # レシピのフォルダの名前（小文字と _。和文の名前は残し、組み直しで英語の名前にする）


def recipe_moves(ws):
    """2026-10-29: 前の版の rules/ の下のファイル → recipes/ の下 [(前, 今)]。決まりの .md は recipes/<名前>/RECIPE.md（名前はファイルの名前。
    ほかのフォルダに同じ名前があれば、フォルダの名前もつなぐ）、点検の checks.py は recipes/slide_checks/・doc_checks/、テンプレートは recipes/doc_templates/templates/。
    rules/README.md は移さない（控えに残し、雛形の recipes/README.md を置く）。"""
    root = ws / "rules"
    if not root.is_dir():
        return []
    files = [p for p in sorted(root.rglob("*")) if p.is_file() and not p.name.startswith(".") and "__pycache__" not in p.parts]
    rule = lambda rel: rel.suffix == ".md" and rel != Path("README.md") and "templates" not in rel.parts[:-1]
    short = lambda rel: slug(rel.stem) if slug(rel.stem) not in ("skill", "readme", "templates", "checks") else slug("_".join(rel.with_suffix("").parts))  # よくある名前と、資源のフォルダの名前は、フォルダの名前もつなぐ
    count = Counter(short(p.relative_to(root)) for p in files if rule(p.relative_to(root)))
    out, used = [], {d.name for d in (ws / "recipes").iterdir()} if (ws / "recipes").is_dir() else set()  # 今ある recipes/ の名前とも重ねない（手で作ったレシピ・途中まで移したもの）
    for p in files:
        rel = p.relative_to(root)
        if rel == Path("README.md"):
            continue
        if "templates" in rel.parts[:-1]:
            dst = Path("doc_templates", *rel.parts[rel.parts.index("templates"):])
        elif p.name == "checks.py" and len(rel.parts) == 2:
            dst = Path({"slides-build": "slide_checks", "docs-build": "doc_checks"}.get(rel.parts[0], f"{slug(rel.parts[0])}_checks"), "checks.py")
        elif rule(rel):
            name = short(rel) if count[short(rel)] == 1 else slug("_".join(rel.with_suffix("").parts))
            while name in used:  # つないだ名前がほかの名前と重なっても、1 つのレシピに 2 つを移さない
                name += "_2"
            used.add(name)
            dst = Path(name, "RECIPE.md")
        else:
            dst = rel  # 決まりでないファイル（画像など）は同じパスに。要るレシピのフォルダへは人が移す
        out.append((p, ws / "recipes" / dst))
    return out


def recipe_front(text):
    """前の版の frontmatter（paths）を今の形に。paths の行（続きの「  - 」の行も）を消し、当たるプラグインのファイルの作業（desk.triggers）から step を書く。
    paths のなかったものは per_material: true。frontmatter のないもの・description のないものは、そのまま（desk-doctor が知らせる）。"""
    meta = desk.front(text)
    if not desk.described(meta) or "step" in meta or "per_material" in meta:
        return text
    lines = text.split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    head, drop = [], False
    for x in lines[1:end]:
        if re.match(r"paths\s*:", x):
            drop = True
            continue
        if drop and (x[:1] in (" ", "\t") or x.lstrip().startswith("- ")):
            continue
        drop = False
        head.append(x)
    globs = desk.listed(meta, "paths")
    if not globs or all(g in MATERIAL for g in globs):  # 資料の種類ごとのファイルへの足しは、その種類の資料でしか開かれなかった。資料ごとに選ぶ
        head.append("per_material: true")
    else:
        plugin = [str(f.relative_to(PLUGIN)) for f in PLUGIN.glob("*/**/*.md")]
        hit = [desk.triggers(f) for f in plugin if any(fnmatch.fnmatchcase(f, g) for g in globs)]
        step = next((s for s in desk.STEPS if hit and all(s in h for h in hit)), None)
        head += [f"step: {step}"] if step else []
    return "\n".join(["---", *head, *lines[end:]])


def recipe_texts(ws):
    """前のパスを書き換えるファイル: AGENTS.md・CLAUDE.md・.gitignore・顧客の memory.md・構成案（「使う決まり」）。レシピは移したあとに別に見る。"""
    fs = [ws / "AGENTS.md", ws / "CLAUDE.md", ws / ".gitignore", *sorted((ws / "Customers").glob("*/memory.md"))]
    fs += [p for d in ("Customers", "Internal") for p in sorted((ws / d).rglob("構成案*.md"))]
    return [p for p in fs if p.is_file()]


def to_recipes(ws, backup):
    """rules/ を recipes/ にする（recipe_moves）。先に、台帳の外の直しを「手で直した」版にしてから、台帳と本文の前のパスを書き換え、
    書き換えた決まりのファイルには「移行」の版を残す（台帳に版のないものは、あとの baselines が「初めの版」にする）。"""
    moves = recipe_moves(ws)
    if not moves and not (ws / "rules").is_dir():
        return []
    led = ws / ".desk" / "ledger.jsonl"
    if led.is_file():
        ledger.drift(ws, quiet=True, record=True)  # 書き換えの前の直しを、ユーザーの直しとして残す（移行の版に混ぜない）
    fixed = [("rules/slides-build/checks.py", "recipes/slide_checks/checks.py"), ("rules/docs-build/checks.py", "recipes/doc_checks/checks.py"),
             ("rules/docs-build/templates/", "recipes/doc_templates/templates/"), ("rules/<名前>.md", "recipes/<名前>/RECIPE.md"), ("rules/README.md", "recipes/README.md")]  # 雛形の文が指す置き場所（ファイルがなくても、本文の文を今の置き場所に）
    pairs = sorted({**dict(fixed), **{f"rules/{s.relative_to(ws / 'rules').as_posix()}": f"recipes/{d.relative_to(ws / 'recipes').as_posix()}" for s, d in moves if not d.exists()}}.items(), key=lambda x: -len(x[0]))  # 移さないもの（先がもうある）の前のパスは、ほかのファイルを指すように書き換えない
    def swap_all(v):
        for a, b in pairs:
            v = re.sub(rf"(?<![\w.-]){re.escape(a)}" + ("" if a.endswith("/") else r"(?![\w./-])"), b, v)
        return v
    out, before = [], {}
    for p in [*recipe_texts(ws), *(ws / ".desk" / "harness").glob("*.json")]:
        before[p] = p.read_text(encoding="utf-8", errors="surrogateescape")  # 壊れたバイトのある構成案も、そのバイトのまま書き戻す
        dst = backup / p.relative_to(ws)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    for src, dst in moves:
        if dst.exists():
            out.append(f"移していない（移す先がもうある。中身を寄せて前のほうを消す）: {src.relative_to(ws)} → {dst.relative_to(ws)}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        old = src.read_text(encoding="utf-8") if dst.name == "RECIPE.md" else None
        src.rename(dst)
        if old is not None:
            before[dst] = old
            dst.write_text(swap_all(recipe_front(old)), encoding="utf-8")
        out.append(f"移した: {src.relative_to(ws)} → {dst.relative_to(ws)}")
        if not (dst.name in (desk.RECIPE, "checks.py") or "templates" in dst.relative_to(ws / "recipes").parts):  # 画像などは、どのレシピのフォルダにも入っていない（hook も名前を添えない）
            out.append(f"要判断: {dst.relative_to(ws)} はレシピのフォルダの外にある。使うレシピのフォルダへ移し、RECIPE.md の中のパスを直す")
    if (readme := ws / "rules" / "README.md").is_file():
        readme.unlink()  # 控えにある。雛形の今の README を置く
        out.append("消した: rules/README.md（控えに残した。recipes/README.md は desk-init の雛形）")
    if not (ws / "recipes" / "README.md").exists() and (ws / "recipes").is_dir():
        shutil.copy2(PLUGIN / "desk-init" / "templates" / "recipes" / "README.md", ws / "recipes" / "README.md")
    for d in sorted((p for p in [ws / "rules", *(ws / "rules").rglob("*")] if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    if led.is_file() and (n := ledger_lines(led, swap_all)) != led.read_text(encoding="utf-8"):
        led.write_text(n, encoding="utf-8")
        out.append(f"書き換えた: {led.relative_to(ws)}（前の rules/ のパス）")
    for p in [*recipe_texts(ws), *(ws / ".desk" / "harness").glob("*.json")]:
        t = before[p]
        n = "".join(swap_all(x) if USED.search(x) else x for x in t.splitlines(keepends=True)) if p.name.startswith("構成案") else swap_all(t)  # 構成案は「使う決まり」の行だけ（hook が読む。ほかは過去の記録のまま）
        if p.name in ("AGENTS.md", "CLAUDE.md", ".gitignore"):  # ワークスペースのフォルダとしての rules/ も（雛形の「rules/ の決まりのファイル」・!/rules/）
            n = re.sub(r"(?<![\w./-])rules/(?![\w.<-])", "recipes/", n).replace("!/rules/", "!/recipes/")  # パスの続くもの（rules/<…>・rules/x.md）は、移したものと雛形の置き場所だけ（pairs）。ほかは下で知らせる
        if n != t:
            p.write_text(n, encoding="utf-8", errors="surrogateescape")
            out.append(f"書き換えた: {p.relative_to(ws)}（前の rules/ のパス）")
    for p in (ws / "AGENTS.md", ws / "CLAUDE.md"):  # 書き換えられなかった前のパス（どこへ移ったか分からない）は、推し量って書き換えずに知らせる
        left = [x.strip()[:80] for x in (p.read_text(encoding="utf-8", errors="replace").splitlines() if p.is_file() else []) if re.search(r"(?<![\w./-])rules/", x)]
        if left:
            out.append(f"要判断: {p.name} に前の rules/ のパスが残っている（{' / '.join(left[:3])}{f' ほか {len(left) - 3} 行' if len(left) > 3 else ''}）。今のレシピのパスに直す")
    vs = ledger.versions(ws) if led.is_file() else {}
    for p, t in before.items():  # 書き換えた決まりのファイルの版（パスは今のもの）
        rel = p.relative_to(ws).as_posix()
        if ledger.rule_file(rel) and rel in vs and p.is_file() and (n := p.read_text(encoding="utf-8")) != vs[rel][-1][3]:
            ledger.revise(ws, rel, vs[rel][-1][3], n, kind="移行")
    if (ws / "rules").exists():
        out.append(f"要判断: rules/ に移せなかったものが残っている（{'・'.join(str(x.relative_to(ws)) for x in sorted((ws / 'rules').rglob('*')) if x.is_file())[:300]}）。中身を recipes/ のレシピに寄せてから消す")
    out.append("要判断: レシピは前のファイルを 1 つずつフォルダにしただけ。目的ごとにまとめ直す（desk-recipes の SKILL.md の §5）。step は paths から決めたので、合っているかを見る")
    return out


def apply(ws):
    data = move_data(ws) + move_scout(ws)  # 台帳（.desk/ledger.jsonl）を書き換える前に、名前を今の版にする
    moves, edit, split, ws_map = plan(ws)
    # 前の名前で整理を回していた。移すもの（rules/dreaming/ のファイルか、前の名前の残る本文）があるときだけ。前の名前が何も残らなければ、登録し直したあとと見分けられない
    old_run = (ws / ".desk" / "dreaming").is_dir() and (any(src.is_relative_to(ws / "rules" / "dreaming") for src, _ in moves) or any(DREAMING.search(t) for t in strings(ws)))
    heads = fronts(ws)  # 移すものがあれば、移したあとで見直す
    ids, new, open_ = ws_ids(ws)  # 書き換えるものがなければ、今の形の ID のまま
    if not moves and not edit and not any(h for _, h in heads) and not new and not strip_plan(ws, ids) and not (RECIPES and (ws / "rules").is_dir()):
        return data + relink(ws) + by_hand(ws, heads) + id_asks(ws, ids, open_) or ["移すものはない（今の版）"]
    backup = ws / ".desk" / "migrate" / time.strftime("%Y%m%d-%H%M%S")
    n = 1
    while backup.exists():  # 同じ秒に回し直しても、前の控え（前の版の中身）を上書きしない
        n += 1
        backup = backup.with_name(f"{backup.name.split('_')[0]}_{n}")
    for p in [ws / "AGENTS.md", ws / "CLAUDE.md", ws / "rules", ws / "recipes", ws / ".desk" / "ledger.jsonl", *sorted((ws / "Customers").glob("*/memory.md"))]:
        if p.exists():
            dst = backup / p.relative_to(ws)
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst)
    out = [*data, f"控え: {backup}"]
    for src, dst in moves:
        if dst.exists():
            out.append(f"移していない（移す先がもうある。中身を寄せて前のほうを消す）: {src} → {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        out.append(f"移した: {src.relative_to(ws)} → {dst.relative_to(ws)}")
    for old, _ in MOVES:  # 空になったフォルダを、深いほうから消す
        d = ws / "rules" / old
        if not d.is_dir():
            continue
        for x in sorted((p for p in [d, *d.rglob("*")] if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(x.iterdir()):
                x.rmdir()
    checks, doc_checks = ws / "rules" / "slides-build" / "checks.py", ws / "rules" / "docs-build" / "checks.py"
    if checks.is_file() and "def doc(" in checks.read_text(encoding="utf-8") and not doc_checks.exists():  # ドキュメントの点検は docs-build が読む
        doc_checks.parent.mkdir(parents=True, exist_ok=True)
        doc_checks.write_text(doc_imports(checks.read_text(encoding="utf-8")), encoding="utf-8")
        out.append(f"写した: {checks.relative_to(ws)} → {doc_checks.relative_to(ws)}（ドキュメントの lint は doc() をこちらから読む。"
                   "こちらの import lint は import doc_lint as lint にした。それぞれ使わない関数は消してよい）")
    for p in texts(ws):
        t = p.read_text(encoding="utf-8")
        if (n := rewrite(t, ws_map=ws_map)) != t:
            p.write_text(n, encoding="utf-8")
            out.append(f"書き換えた: {p.relative_to(ws)}")
    led = ws / ".desk" / "ledger.jsonl"
    if led.is_file() and (n := ledger_lines(led, lambda v: rewrite(v, ws_map=ws_map))) != led.read_text(encoding="utf-8"):
        led.write_text(n, encoding="utf-8")
        out.append(f"書き換えた: {led.relative_to(ws)}")
    out += [f"番号を替えた（前の別々の決まりが同じ ID になるため）: {a} → {b}" for a, b in sorted(ws_map.items()) if b != rewrite(a, paths=False)]
    heads = fronts(ws)
    for p, head in heads:  # 移したあとのパスで、前の版の同じパスへの上書きに frontmatter を足す
        if head:
            p.write_text(head + p.read_text(encoding="utf-8"), encoding="utf-8")
            out.append(f"frontmatter を足した: {p.relative_to(ws)}（paths は前と同じパス。description は、何に効くかが分かるように直してよい）")
    out += by_hand(ws, heads)
    for rel, where in plan(ws)[2] if (moves or edit) and not RECIPES else []:  # 分けた件は、前の版から移すときだけ（frontmatter を足すだけのときは、もう分けてある。check と同じ）。recipes/ に移すなら、レシピは作業ごとに出るので、どのファイルへの足しかは要らない
        out += [f"要判断: rules/{rel} は、プラグインで {where} に分けた。決まりごとに、足しているプラグインの節のファイルを frontmatter の paths に足す"
                "（決まりを、そのファイルを paths に持つファイルへ移してもよい。ID はそのまま）"] + suggest(ws, rel)
    d = relink_files(ws)[0]  # 初めて移行した時点にある提案だけを見張る（そのあとに出した提案は今の版のもの。回し直しても足さない）
    if not (d / "relink.json").is_file():  # 当て済みは、いま文がそのファイルにあるもの（移行の前から文のないものは、drift の受け持ち）
        now = {p["id"] for p in in_split(ws) if p["status"] == "未適用" or p["new"].strip() and (ws / p["file"]).is_file() and p["new"].strip() in (ws / p["file"]).read_text(encoding="utf-8")}
        (d / "relink.json").write_text(json.dumps(sorted(now)), encoding="utf-8")
    out += [] if RECIPES else asks(relinks(ws))  # recipes/ に移すと、分けたファイルの提案は、前の文を丸ごと持つレシピについていく（決めることがない）
    ids, new, open_ = ws_ids(ws)  # 2026-10-27: ワークスペースの決まりの ID を外す（ほかの書き換えのあとの、今の形の ID で）
    out += hand_edits(ws) + strip_ids(ws, ids, new) + baselines(ws) + id_asks(ws, ids, open_)
    if off := off_topic(ws):
        out.append(f"要判断: 角括弧なしで書いた、もうプラグインにない前の ID がある（{'・'.join(off)}）。ids_*.json の prefixes で今の主題を見て、"
                   "その文を直すか、要らなければ消す（ID だと言い切れないので、ここでは替えない）")
    if RECIPES and ws_ids(ws)[2]:  # 決められない ID は rules/ のファイルで探す（relink-id）。決めるまで移さない
        out.append("要判断: rules/ から recipes/ への移しは、上の ID の行き先を決めてから（relink-id のあと、apply を回し直す）")
    elif RECIPES:  # 2026-10-29: 最後に rules/ を recipes/ に（前の段は rules/ の中で済ませる）
        out += to_recipes(ws, backup) + baselines(ws)
    if old_run:  # 登録はワークスペースの外（アプリ・launchd・cron）にあり、ここからは直せない
        out.append("要判断: 定期の整理を前の名前（dreaming）で登録していれば、前の登録を消して登録し直す（desk-dreaming の SKILL.md を開いてから、その schedule.md の頭。"
                   "前の登録のままだと、run.sh が見つからないか前のスキルを呼んで止まり、報告も出ない）")
    return out


def relink_id(ws, x, to):
    """ID を外すときに決められなかった ws- の ID の行き先（ワークスペースの決まりのファイルか 戻さない）を台帳に残し、その ID をファイルから外す。"""
    WS_FULL.fullmatch(x) or sys.exit(f"ワークスペースの決まりの ID（ws-<主題>-<3 桁>）を渡す: {x}")
    ids, _, open_ = ws_ids(ws)
    x in ids and sys.exit(f"{x} はもう {ids[x]} につないである")
    x in open_ or sys.exit(f"{x} は、決められない ID でない（migrate.py check で見る）")
    if to != "戻さない":
        f = (ws / to).resolve()
        f.is_file() and f.is_relative_to(ws.resolve()) and ledger.rule_file(rel := f.relative_to(ws.resolve()).as_posix()) or sys.exit(f"行き先はワークスペースの決まりのファイル（rules/<名前>.md・AGENTS.md・Customers/<顧客>/memory.md）か 戻さない: {to}")
        to = rel
    return hand_edits(ws) + strip_ids(ws, {**ids, x: to}, {x: to}) + baselines(ws) + id_asks(ws, {**ids, x: to}, {k: v for k, v in open_.items() if k != x})  # 初めの apply が、決められない ID だけで止まったときも版を残す


def selftest():
    global RECIPES
    RECIPES = False  # 前の段（2026-10-24〜27）は、rules/ の中の結果で確かめる。最後の段は selftest_recipes
    assert all(m["ids"].get(n, n) == n for m in MAPS for n in m["ids"].values())  # 今の ID は、前の ID として読んでも替わらない（何度回してもよい）
    IDS = {k: rewrite(k, paths=False) for m in MAPS[:1] for k in m["ids"]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "desk.toml").write_text("")
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("rules/deck-practices/visual.md", "`deck-practices/visual.md` に足す。\n\n- [ws-visual-001] 本文は 16pt（visual-012より優先）。\n")
        put("rules/deck-practices/SKILL.md", "- [ws-deck-practices-001] 代表の 3 枚は 4 枚にする（deck-practices-007 より優先）。\n")
        put("rules/deck-build/checks.py", "import lint  # 前の雛形のとおり\n\ndef slides(p, r):\n    pass\n\ndef doc(doc, r):\n    r.hits[\"段落\"].append(str(len(lint.gdoc_paras(doc))))\n")
        put("rules/doc-build/templates/a/doc.md", "t")
        put("rules/slides-template/SKILL.md", "mine")
        put("rules/deck-template/SKILL.md", "x")
        put("rules/deck-review/SKILL.md", "- [ws-deck-review-001] 今の形の ID\n")
        put("rules/deck-review/prompt_doc.md", "- [ws-prompt_doc-001] 文書の観点\n")
        put("rules/deck-review/prompt_slides.md", "- [ws-prompt_slides-001] スライドの観点\n")
        put("rules/slides-speaker-notes/ja.md", "- [ws-slides-speaker-notes-ja-001] 間を長く（slides-speaker-notes-ja-002 より優先）。\n")
        put("AGENTS.md", "スキル deck-build の deck-build-005 と、doc-build-010。スキルdeck-templateの手順。")
        put("rules/vids-voice/en.md", "- [ws-speaker-notes-en-001] x\n- [ws-odd-001] y\n")
        put("Customers/acme/memory.md", "- [ws-memory-001] 品番の assets-100 と template-777 は顧客の言葉のまま。[visual-777] は前の決まり\n")
        put(".desk/ledger.jsonl", json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0001", "to": "ws-visual-001", "file": "rules/deck-practices/visual.md", "rule": "visual-012"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0009", "file": "rules/a.md", "old": "", "new": "x", "rule": "sessions-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0001", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-001] 代表の 3 枚は 4 枚にする（deck-practices-007 より優先）。"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "applied", "ref": "P0001", "prev": {}}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0002", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-009] 却下した案"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "rejected", "ref": "P0002", "reason": "要らない"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0003", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-practices-010] まだ当てていない案"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0002", "to": "ws-prompt_doc-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0003", "to": "ws-prompt_slides-001"}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0004", "quote": "deck-build の visual-012 を直して", "to": "visual-012"}, ensure_ascii=False) + "\n")
        assert "visual-012 → slides-visual-012" in changed(ws / "rules" / "deck-practices" / "visual.md", ws_plan(ws)) and "assets-100" not in changed(ws / "Customers" / "acme" / "memory.md", ws_plan(ws))
        assert needs(ws)
        out = apply(ws)
        r = ws / "rules"
        body = lambda f: re.sub(r"\A---\n.*?\n---\n\n", "", f.read_text(), flags=re.S)  # 足した frontmatter のあとの、前の中身
        assert body(r / "slides-build" / "visual.md") == "`slides-build/visual.md` に足す。\n\n- 本文は 16pt（slides-visual-012より優先）。\n"  # ID を外した
        assert desk.front((r / "slides-build" / "visual.md").read_text())["paths"] == ["slides-build/visual.md"] and any(o == "frontmatter を足した: rules/slides-build/visual.md（paths は前と同じパス。description は、何に効くかが分かるように直してよい）" for o in out)
        assert not desk.front((r / "docs-build" / "templates" / "a" / "doc.md").read_text()) and any(o.startswith("要判断: rules/deck-template/SKILL.md に frontmatter") for o in out)  # テンプレートには足さない。スキルでないフォルダは手で書く
        assert "slides-visual-012" in (r / "slides-build" / "visual.md").read_text() and (r / "docs-build" / "templates" / "a" / "doc.md").is_file()
        assert (r / "slides-build" / "checks.py").is_file() and (r / "docs-build" / "checks.py").is_file() and not (r / "deck-build").exists() and not (r / "doc-build").exists()
        assert (r / "slides-build" / "checks.py").read_text().startswith("import lint ") and (r / "docs-build" / "checks.py").read_text().startswith("import doc_lint as lint ")
        (ws / "recipes" / "doc_checks").mkdir(parents=True)  # 最後の段で移す先（lint は recipes/ の下の checks.py を読む）
        shutil.copy2(r / "docs-build" / "checks.py", ws / "recipes" / "doc_checks" / "checks.py")
        run = subprocess.run([sys.executable, "-c", "import sys; sys.path[:0] = sys.argv[1:3]; import doc_lint, textlint; r = textlint.Report(); "
                              "doc_lint.workspace_checks('doc', {'body': {'content': []}}, r); print(r.hits['段落'])",
                              str(PLUGIN / "docs-build" / "scripts"), str(PLUGIN / "deck-practices" / "scripts")], cwd=ws, capture_output=True, text=True)
        assert run.returncode == 0 and "['0']" in run.stdout, run.stderr  # 写したドキュメントの点検が、ドキュメントの lint から読めて動く
        shutil.rmtree(ws / "recipes")
        assert body(r / "vids-voice" / "en.md") == "- x\n- y\n"  # 主題の表にない ID も外す
        assert not any("主題の表にない" in o and "visual-012" in o for o in out)  # 原文の中の古い ID は、主題の表にない ID として出さない
        assert body(r / "vids-voice" / "ja.md") == "- 間を長く（vids-voice-ja-002 より優先）。\n"
        assert (r / "deck-template" / "SKILL.md").is_file() and any("移していない" in o for o in out)  # 移す先にあるものは上書きしない
        assert (ws / "AGENTS.md").read_text() == f"スキル slides-build の {IDS['deck-build-005']} と、{IDS['doc-build-010']}。スキルslides-templateの手順。"  # 和文が続いても替える
        led = [json.loads(x) for x in (ws / ".desk" / "ledger.jsonl").read_text().splitlines()]
        assert led[:10] == [{"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0001", "to": "ws-slides-visual-001", "file": "rules/slides-build/visual.md", "rule": "slides-visual-012"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0009", "file": "rules/a.md", "old": "", "new": "x", "rule": "desk-dreaming-001"},  # 台帳の値がまるごと ID なら、もうない ID も接頭辞で替える
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0001", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-flow-001] " + body(r / "deck-practices" / "SKILL.md").strip().removeprefix("- ")},  # 台帳の文は、ID を外す前のまま
                       {"ts": "2026-10-01T00:00:00Z", "kind": "applied", "ref": "P0001", "prev": {}},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0002", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-flow-009] 却下した案"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "rejected", "ref": "P0002", "reason": "要らない"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "proposal", "id": "P0003", "rule": "", "file": "rules/deck-practices/SKILL.md", "old": "", "new": "- [ws-deck-flow-010] まだ当てていない案"},
                       {"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0002", "to": "ws-deck-review-002"}, {"ts": "2026-10-01T00:00:00Z", "kind": "route", "ref": "c-0003", "to": "ws-deck-review-003"},  # ぶつかる番号は替え、定義と台帳で同じ
                       {"ts": "2026-10-01T00:00:00Z", "kind": "correction", "id": "c-0004", "quote": "deck-build の visual-012 を直して", "to": "slides-visual-012"}]  # ユーザーの言葉の原文は替えない
        mig = next(x for x in led if x["kind"] == "migrated")["ids"]  # ID を外す前に、ID → ファイルの対応を台帳に残す（前の行は書き換えない）
        assert (mig["ws-slides-visual-001"], mig["ws-deck-review-002"], mig["ws-deck-review-003"], mig["ws-memory-001"]) == (
            "rules/slides-build/visual.md", "rules/deck-review/prompt_doc.md", "rules/deck-review/prompt_slides.md", "Customers/acme/memory.md")  # ぶつかる番号は替え、定義と台帳で同じ
        cs = ledger.state(ws)[0]
        assert (cs["c-0001"]["to"], cs["c-0004"]["to"]) == ("rules/slides-build/visual.md", "slides-visual-012")
        assert "rules/slides-build/visual.md" in {x["file"] for x in led if x.get("type") == "移行"}  # ファイルごとに「移行」の版
        assert body(r / "deck-review" / "SKILL.md") == "- 今の形の ID\n" and body(r / "deck-review" / "prompt_doc.md") == "- 文書の観点\n"
        assert any(o.startswith("番号を替えた") and "ws-prompt_slides-001 → ws-deck-review-003" in o for o in out)
        mem = (ws / "Customers" / "acme" / "memory.md").read_text()
        assert "assets-100" in mem and "template-777" in mem and "[slides-visual-777]" in mem  # 角括弧のない ID でないものは替えない
        assert not any("P0002" in o for o in out) and [x[0] for x in relinks(ws)] == ["P0003"]  # 却下した提案は見ない。まだ当てていない足す提案は、足す先を決める
        assert any(o.startswith("要判断: 台帳の P0003") and "migrate.py relink P0003" in o for o in out)
        assert decide(ws, "P0003", "rules/slides-build/workflow.md")[0].startswith("決めた: P0003") and relinks(ws) == []
        with open(ws / ".desk" / "ledger.jsonl", "a", encoding="utf-8") as f:  # 移行のあとに出した普通の足す提案は見ない
            f.write(json.dumps({"ts": "2026-10-25T00:00:00Z", "kind": "proposal", "id": "P0004", "rule": "", "file": "rules/slides-build/pages.md", "old": "", "new": "- [ws-slides-pages-009] 新しい案"}, ensure_ascii=False) + "\n")
        assert relinks(ws) == [] and not any("P0004" in x for x in needs(ws))
        assert any(o.startswith("要判断: rules/deck-practices/SKILL.md") for o in out) and any(IDS["deck-practices-007"].rsplit("-", 1)[0] in o or "workflow" in o for o in out)
        assert any(o.startswith("控え: ") for o in out) and list((ws / ".desk" / "migrate").glob("*/rules/deck-practices/visual.md"))
        first = next(x for x in sorted((ws / ".desk" / "migrate").iterdir()) if x.is_dir())
        put("rules/deck-build/x.md", "y")
        assert apply(ws)[0] != f"控え: {first}" and (first / "rules" / "deck-practices" / "visual.md").is_file()  # 同じ秒に回しても、前の控えを残す
        (r / "slides-build" / "x.md").unlink()
        (r / "deck-template" / "SKILL.md").unlink()
        moved = (r / "deck-practices" / "SKILL.md").read_text()  # 分け直しで、決まりを workflow.md への上書きに移したとする
        put("rules/slides-build/workflow.md", moved)
        (r / "deck-practices" / "SKILL.md").write_text("")
        assert any(x.startswith("台帳の P0001") for x in needs(ws)) and [(i, b) for i, _, b, _ in relinks(ws)] == [("P0001", "rules/slides-build/workflow.md")]
        assert apply(ws) == ["台帳を合わせた: P0001 の変更先 rules/deck-practices/SKILL.md → rules/slides-build/workflow.md"]
        assert next(json.loads(x) for x in (ws / ".desk" / "ledger.jsonl").read_text().splitlines() if '"P0001"' in x)["file"] == "rules/slides-build/workflow.md"
        put("rules/slides-build/workflow.md", "")  # 決まりを分けた先にまたがって書き直し、どこにも元の文がない
        put(".desk/ledger.jsonl", (ws / ".desk" / "ledger.jsonl").read_text().replace("rules/slides-build/workflow.md", "rules/deck-practices/SKILL.md"))
        assert apply(ws)[0].startswith("要判断: 台帳の P0001") and "--split" in apply(ws)[0] and needs(ws)  # 当てた文が分かれたら、決めるまで前の版
        try:
            decide(ws, "P0002", "--split")
            raise AssertionError("却下した提案に --split")
        except SystemExit:
            pass
        assert decide(ws, "P0001", "--split")[0].endswith("undo で戻せない）") and needs(ws) == [] and relinks(ws) == []  # 決めたら、もう出さない
        assert relink_files(ws)[2]["P0003"] == {"to": "rules/slides-build/workflow.md", "from": "rules/deck-practices/SKILL.md"}
        put("rules/slides-build/workflow.md", moved)
        assert needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]  # 2 回目は何もしない
    with tempfile.TemporaryDirectory() as tmp:  # 今の版で作ったワークスペースの、普通の足す提案は前の版にしない
        ws = Path(tmp)
        (ws / "desk.toml").write_text("")
        (ws / "rules" / "slides-build").mkdir(parents=True)
        (ws / "rules" / "slides-build" / "pages.md").write_text("---\ndescription: x\npaths: [slides-build/pages.md]\n---\n- x\n")
        (ws / ".desk").mkdir()
        (ws / ".desk" / "ledger.jsonl").write_text(json.dumps({"ts": "2026-10-25T00:00:00Z", "kind": "proposal", "id": "P0001", "rule": "", "file": "rules/slides-build/pages.md", "old": "", "new": "y"}, ensure_ascii=False) + "\n")
        assert relinks(ws) == [] and needs(ws) == []
        (ws / "rules" / "deck-practices").mkdir()  # プラグインへの提案は、分けたファイルと同じパスでも、ワークスペースの上書きから文を探さない
        (ws / "rules" / "deck-practices" / "content.md").write_text("---\ndescription: x\n---\n足す。\n")
        with open(ws / ".desk" / "ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-10-25T00:00:00Z", "kind": "proposal", "id": "P0026", "rule": "", "file": "deck-practices/content.md", "old": "プラグインの文", "new": "z", "plugin": True}, ensure_ascii=False) + "\n")
        (ws / ".desk" / "migrate").mkdir()
        (ws / ".desk" / "migrate" / "relink.json").write_text('["P0026"]')  # 直す前の版の apply が見張りに入れていた
        assert [p["id"] for p in in_split(ws)] == ["P0001"] and relinks(ws) == [] and needs(ws) == []
        (ws / ".desk" / "migrate" / "relink_done.json").write_text(json.dumps({"P0026": {"to": "deck-practices/content.md", "from": "deck-practices/content.md"}}))
        assert relinks(ws) == [] and needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]  # 手で足した回り道の行があっても壊れない
        (ws / "rules" / "customer.md").write_text("- 顧客の言葉で書く\n")  # スキルのフォルダの外。何に効くか分からない
        assert needs(ws) == ["rules/customer.md（frontmatter）"] and apply(ws)[0].startswith("要判断: rules/customer.md に frontmatter") and (ws / "rules" / "customer.md").read_text() == "- 顧客の言葉で書く\n"
        (ws / "rules" / "customer.md").unlink()
        for t in ("rules/deck-practices/content.md", "--split"):  # プラグインへの提案の変更先を、ワークスペースのファイルに付け替えない
            before = [(ws / ".desk" / x).read_text() for x in ("ledger.jsonl", "migrate/relink_done.json")]
            try:
                decide(ws, "P0026", t)
                raise AssertionError("プラグインへの提案に relink")
            except SystemExit:
                pass
            assert [(ws / ".desk" / x).read_text() for x in ("ledger.jsonl", "migrate/relink_done.json")] == before
    with tempfile.TemporaryDirectory() as tmp:  # 2026-10-25: factory.toml → desk.toml、.factory/ → .desk/、factory-* → desk-*
        ws = Path(tmp)
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("factory.toml", '[factory]\nprivate = ["x"]  # factory-kaizen が見る\n\n[drive]\nfactory = "u"   # 根元\ncustomers = ""\n\n[slides.templates]\nfactory = "t"\n  [docs.templates]\n  factory = "d"\n')
        put(".factory/ledger.jsonl", json.dumps({"ts": "2026-10-20T00:00:00Z", "kind": "correction", "id": "c-0001", "quote": "factory-kaizen で出して", "file": "rules/factory-kaizen/SKILL.md", "to": "factory-dreaming-001"}, ensure_ascii=False) + "\n")
        put(".factory/lint_runs.jsonl", "{}\n")
        put("rules/factory-kaizen/SKILL.md", "- [ws-deck-rules-001] x\n")
        put(".gitignore", "/*\n!/rules/\n!/factory.toml")  # 最後の行に改行がなくても替える
        put("AGENTS.md", "`factory.toml` の `drive.factory`。台帳は `.factory/ledger.jsonl`。スキル factory-kaizen（factory-dreaming-001）。別の道具の ~/.factory/config・${HOME}/.factory/x、自分の .factory-old。\n")
        assert workspace(ws / "Customers" / "a") == ws.resolve() and {"factory.toml", ".factory"} <= set(needs(ws))  # 前の版も見つける
        out = apply(ws)
        assert not (ws / "factory.toml").exists() and not (ws / ".factory").exists() and (ws / ".desk" / "lint_runs.jsonl").is_file() and (ws / ".desk" / "migrate" / "factory.toml").is_file()
        assert (ws / "desk.toml").read_text() == '[desk]\nprivate = ["x"]  # desk-kaizen が見る\n\n[drive]\ndesk = "u"   # 根元\ncustomers = ""\n\n[slides.templates]\nfactory = "t"\n  [docs.templates]\n  factory = "d"\n'  # テーマとテンプレートの名前は替えない（字下げした見出しも）
        assert (ws / "rules" / "desk-kaizen" / "SKILL.md").is_file() and not (ws / "rules" / "factory-kaizen").exists()
        assert (ws / ".gitignore").read_text() == "/*\n!/rules/\n!/desk.toml"  # 設定を git に入れたまま
        assert (ws / "AGENTS.md").read_text() == "`desk.toml` の `drive.desk`。台帳は `.desk/ledger.jsonl`。スキル desk-kaizen（desk-dreaming-001）。別の道具の ~/.factory/config・${HOME}/.factory/x、自分の .factory-old。\n"  # ほかのパスは替えない
        led = json.loads((ws / ".desk" / "ledger.jsonl").read_text().splitlines()[0])
        assert led["file"] == "rules/desk-kaizen/SKILL.md" and led["quote"] == "factory-kaizen で出して" and led["to"] == "desk-dreaming-001"  # 原文は替えない
        assert any(o.startswith("移した: factory.toml") for o in out) and needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]
        put("factory.toml", "[drive]\nfactory = \"v\"\n")  # desk.toml がもうあれば上書きしない
        assert any(o.startswith("移していない") for o in apply(ws)) and 'desk = "u"' in (ws / "desk.toml").read_text() and needs(ws) == ["factory.toml"]
    with tempfile.TemporaryDirectory() as tmp:  # 2026-10-25: dreaming → desk-dreaming、factory-dreaming → desk-dreaming
        ws = Path(tmp)
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("desk.toml", "")
        put("rules/dreaming/run.md", "- [ws-factory-dreaming-001] 朝に回す（factory-dreaming-001 より優先）。\n")
        put("AGENTS.md", "スキル `dreaming`（`/desk-tools:dreaming`、`../dreaming/run.md`）。記録は `.desk/dreaming/log/`（.desk/ の `dreaming/last_run`・`dreaming/backup/`）。\n")
        put(".desk/ledger.jsonl", json.dumps({"ts": "2026-10-25T00:00:00Z", "kind": "correction", "id": "c-0001", "quote": "dreaming して", "to": "ws-factory-dreaming-001", "by": "dreaming"}, ensure_ascii=False) + "\n")
        assert "rules/dreaming/run.md" in needs(ws)
        put(".desk/dreaming/last_run", "2026-10-24T20:00:00Z")
        out = apply(ws)
        assert re.sub(r"\A---\n.*?\n---\n\n", "", (ws / "rules" / "desk-dreaming" / "run.md").read_text(), flags=re.S) == "- 朝に回す（desk-dreaming-001 より優先）。\n" and not (ws / "rules" / "dreaming").exists()
        assert (ws / "AGENTS.md").read_text() == "スキル `desk-dreaming`（`/desk-tools:desk-dreaming`、`../desk-dreaming/run.md`）。記録は `.desk/dreaming/log/`（.desk/ の `dreaming/last_run`・`dreaming/backup/`）。\n"  # 記録のフォルダは替えない
        assert any(o.startswith("要判断: 定期の整理") for o in out)  # 前の名前で回していた（.desk/dreaming/ がある）
        led = json.loads((ws / ".desk" / "ledger.jsonl").read_text().splitlines()[0])
        assert (led["to"], led["quote"], led["by"]) == ("ws-desk-dreaming-001", "dreaming して", "dreaming")  # 原文と、書いた者の種類は替えない
        assert ledger.state(ws)[0]["c-0001"]["to"] == "rules/desk-dreaming/run.md"  # 台帳はファイルとして読む
        assert needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]
    with tempfile.TemporaryDirectory() as tmp:  # 2026-10-29: source-scout の上書き・名前・記録を desk-crawl に
        ws = Path(tmp)
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("desk.toml", "")
        put("rules/source-scout/SKILL.md", "---\ndescription: 読む先\npaths: [source-scout/SKILL.md]\n---\n\n- 毎朝 `scout.py plan` を回す（source-scout-002 より優先）。\n")
        put("AGENTS.md", "スキル `source-scout`（`../source-scout/scripts/scout.py`）。記録は `.desk/scout/`。\n")
        put(".desk/scout/t/sources.json", json.dumps({"sources": {
            "slack:A": {"tier": "core", "mode": "filter", "notes": [{"id": "n1", "text": "x", "helpful": 1, "harmful": 0}]},
            "gmail:label:news": {"tier": "muted", "mode": "search"}, "wiki:123": {"tier": "candidate"}}, "notes": [], "next_note": 2,
            "applied": {"2026-10-27T07:00+09:00": {"lessons": [[0, "gmail:label:news", "Skip digests"], [1, "*", "x"]], "votes": [[0, "n1", True]], "changes": []}}}))
        put(".desk/scout/t/runs.jsonl", json.dumps({"id": "2026-10-27T07:00+09:00", "until": "2026-10-27T07:00+09:00",
            "reads": [{"source": "gmail:label:news", "ok": True}], "items": [{"url": "https://x/1", "used": True, "value": 0, "seen_in": ["slack:A", "gmail:label:news"]}],
            "misses": [{"source": "slack:A", "url": "https://x/2"}], "feedback": [{"url": "https://x/1", "value": 0}]}) + "\n")
        put(".desk/scout/t/plan.json", "{}")
        put(".desk/scout/.DS_Store", "x")  # 話題のほかのファイルが残っても、移し終えたら消す
        put(".desk/scout/u/runs.jsonl", json.dumps({"id": "r", "items": [{"url": "https://u/1", "used": True, "seen_in": ["slack:A"]},
            {"url": "https://u/2", "used": True, "value": 0, "seen_in": ["slack:A"]}], "feedback": [{"url": "https://u/1/", "value": 0}]}) + "\n")
        put("recipes/news/RECIPE.md", "---\ndescription: x\n---\n\n- `scout.py plan` を回す（[source-scout-002] より優先）。記録は `.desk/scout/`。\n")
        assert "rules/source-scout/SKILL.md" in needs(ws) and any(x.startswith(".desk/scout/") for x in needs(ws))
        out = apply(ws)
        assert (ws / "rules" / "desk-crawl" / "SKILL.md").read_text() == "---\ndescription: 読む先\npaths: [desk-crawl/SKILL.md]\n---\n\n- 毎朝 `crawl.py plan` を回す（desk-crawl-002 より優先）。\n"
        assert not (ws / "rules" / "source-scout").exists() and not (ws / ".desk" / "scout").exists() and list((ws / ".desk" / "migrate").glob("scout_*/t/runs.jsonl"))
        assert (ws / "AGENTS.md").read_text() == "スキル `desk-crawl`（`../desk-crawl/scripts/crawl.py`）。記録は `.desk/crawl/`。\n"
        reg = json.loads((ws / ".desk" / "crawl" / "t" / "sources.json").read_text())
        assert {k: v["tier"] for k, v in reg["sources"].items()} == {"slack:A": "follow", "gmail-search:label:news": "candidate", "wiki:123": "candidate"}, reg
        assert [n["id"] for n in reg["sources"]["slack:A"]["notes"]] == ["n1", "n2"] and "mode" not in reg["sources"]["slack:A"] and reg["next_note"] == 3
        assert reg["applied"]["2026-10-27T07:00+09:00"]["lessons"] == [[0, "gmail-search:label:news", "Skip digests"], [1, "*", "x"]]  # 当てた控えの先も替える
        run = json.loads((ws / ".desk" / "crawl" / "t" / "runs.jsonl").read_text())
        assert run["items"][0] == {"url": "https://x/1", "used": True, "seen_in": ["slack:A", "gmail-search:label:news"]} and "misses" not in run and "feedback" not in run, run  # used は残す（使われた済みの印）
        assert not (ws / ".desk" / "crawl" / "t" / "plan.json").exists()
        assert [i["used"] for i in json.loads((ws / ".desk" / "crawl" / "u" / "runs.jsonl").read_text())["items"]] == [True, True]
        assert (ws / "recipes" / "news" / "RECIPE.md").read_text().endswith("- `crawl.py plan` を回す（[desk-crawl-002] より優先）。記録は `.desk/crawl/`。\n")  # レシピの中の名前も替える
        assert any(o.startswith("要判断: 定期の集め") for o in out) and any("wiki:123" in o for o in out), out
        assert needs(ws) == [] and apply(ws) == ["移すものはない（今の版）"]
        put(".desk/scout/v/runs.jsonl", "{broken\n")  # 読めない話題は移さずに知らせ、ほかは止めない
        put(".desk/scout/w/sources.json", "[]")
        put("CLAUDE.md", "source-scout を使う。\n")
        out = apply(ws)
        assert all(any(o.startswith(f"要判断: .desk/scout/{t}/ を読めない") for o in out) and (ws / ".desk" / "scout" / t).is_dir() for t in "vw"), out
        assert (ws / "CLAUDE.md").read_text() == "desk-crawl を使う。\n" and any(p.read_text() == "source-scout を使う。\n" for p in (ws / ".desk" / "migrate").glob("*/CLAUDE.md"))
        shutil.rmtree(ws / ".desk" / "scout")
        put(".desk/scout/t/sources.json", "{}")  # 移す先がもうあれば、上書きしない
        assert any(o.startswith("移していない") for o in apply(ws)) and (ws / ".desk" / "scout" / "t").is_dir()
    with tempfile.TemporaryDirectory() as tmp:  # 整理を回していない（.desk/dreaming/ がない）なら、登録し直しは出さない
        ws = Path(tmp)
        (ws / "desk.toml").write_text("")
        (ws / "rules" / "dreaming").mkdir(parents=True)
        (ws / "rules" / "dreaming" / "run.md").write_text("x\n")
        out = apply(ws)
        assert (ws / "rules" / "desk-dreaming" / "run.md").is_file() and not any(o.startswith("要判断: 定期の整理") for o in out)
        (ws / ".desk" / "dreaming").mkdir(parents=True)
        (ws / "rules" / "dreaming").mkdir()  # 空のフォルダだけが残る（前の名前は何も残らない）
        assert apply(ws) == ["移すものはない（今の版）"]
    with tempfile.TemporaryDirectory() as tmp:  # 2026-10-27: ワークスペースの決まりの ID を外す
        ws = Path(tmp).resolve()
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("desk.toml", "")
        fm = "---\ndescription: x\n---\n"
        put("rules/a.md", fm + "- [ws-slides-visual-001] 表は分ける。\n- [ws-deck-content-002] 結論を先に。\n[ws-deck-content-005] **まとまり**\n- 項。\n")
        put("rules/b.md", fm + "- [ws-deck-content-002] 結論を先に（写し）。\n- ws-slides-visual-001 と同じ。\n")  # 2 つのファイルにある ID と、角括弧なしの参照
        put("rules/slides-build/checks.py", "# [ws-slides-visual-001] を見る\n")
        put("Customers/acme/memory.md", "- [ws-memory-001] 敬称は様\n")
        put("rules/c.md", fm + "- [ws-slides-visual-007] 足した文。\n")
        rec = lambda **r: json.dumps({"ts": "2026-10-20T00:00:00Z", **r}, ensure_ascii=False)
        put(".desk/ledger.jsonl", "\n".join([
            rec(kind="correction", id="c-0001", deck="Customers/acme/d1", quote="表を分けて", to="ws-slides-visual-001", decided=True),
            rec(kind="correction", id="c-0002", deck="Customers/acme/d1", quote="結論", to="ws-deck-content-002"),
            rec(kind="correction", id="c-0003", deck="Customers/acme/d1", quote="消した決まり", to="ws-deck-content-003"),
            rec(kind="proposal", id="P0001", file="rules/a.md", old="", new="- [ws-deck-content-003] 消した。", rule="ws-deck-content-003"),
            rec(kind="correction", id="c-0004", deck="Customers/acme/d1", quote="どこにもない", to="ws-deck-content-004"),
            rec(kind="review", deck="Customers/acme/d1", rule="ws-memory-001", page="p1", result="直した", key="k1"),
            rec(kind="correction", id="c-0005", deck="Customers/acme/d1", quote="前の戻し先だけ", to="ws-deck-content-009"),  # 消した決まりが、前の戻し先とレビューの結果にだけ残る
            rec(kind="route", ref="c-0005", to="slides-visual-012"),
            rec(kind="review", deck="Customers/acme/d1", rule="ws-deck-content-009", page="p2", result="直した", key="k2"),
            rec(kind="proposal", id="P0002", src=[], why="試し", type="", file="rules/a.md", old="- [ws-deck-content-002] 結論を先に。", new="- [ws-deck-content-002] 結論を先に書く。", rule=""),  # 移行より前の、まだ当てていない提案
            rec(kind="proposal", id="P0003", src=[], why="試し", type="", file="rules/c.md", old="", new="- [ws-slides-visual-007] 足した文。", rule=""),  # 移行より前に当てた提案
            rec(kind="applied", ref="P0003", appended=True, prev={}),
            rec(kind="proposal", id="P0004", src=[], why="試し", type="", file="rules/b.md", old="", new="- [ws-deck-content-002] 手で消された文。", rule=""),  # 当てたあと、ユーザーが手で消した
            rec(kind="applied", ref="P0004", appended=True, prev={}),
            rec(kind="proposal", id="P0005", src=[], why="試し", type="", file="rules/c.md", old="", new="- [ws-slides-visual-020] まだ当てていない新しい決まり。", rule="ws-slides-visual-020")]) + "\n")  # 新しい ID を書き入れる、まだ当てていない提案
        assert {"rules/a.md（決まりの ID）", "台帳の ws-deck-content-002（決まりの ID。要判断）", "台帳の ws-deck-content-004（決まりの ID。要判断）"} <= set(needs(ws))
        before = {p: (ws / p).read_text() for p in ("rules/a.md", "rules/b.md", "rules/c.md", "Customers/acme/memory.md", ".desk/ledger.jsonl")}
        out = apply(ws)
        assert (ws / "rules" / "a.md").read_text() == fm + "- 表は分ける。\n- [ws-deck-content-002] 結論を先に。\n**まとまり**\n- 項。\n"  # 決められない ID は、決めるまで外さない
        assert (ws / "Customers" / "acme" / "memory.md").read_text() == "- 敬称は様\n" and "[ws-slides-visual-001]" in (ws / "rules" / "slides-build" / "checks.py").read_text()  # py は書き換えず、知らせる
        assert any("ws-deck-content-002 は、rules/a.md・rules/b.md の 2 つのファイル" in o for o in out) and any("ws-deck-content-004 は、どのファイルにも書いていない（消した決まり）" in o for o in out)
        assert not any("ws-deck-content-009" in o for o in out)  # 過去の記録だけの ID は、そのまま読む（要判断にしない）
        assert any(o.startswith("要判断: rules/b.md:5 が ws-slides-visual-001") for o in out) and any(o.startswith("要判断: rules/slides-build/checks.py:1 が ws-slides-visual-001") for o in out)
        cs, _, _, rv = ledger.state(ws)
        assert (cs["c-0001"]["to"], cs["c-0003"]["to"], rv[0]["rule"]) == ("rules/a.md", "rules/a.md", "Customers/acme/memory.md")  # 消した決まりは、書いた提案の変更先
        assert cs["c-0001"]["decided"] and cs["c-0002"]["to"] == "ws-deck-content-002"  # ユーザーが決めた印は残る。決めるまではつなぎ直さない
        lines = (ws / ".desk" / "ledger.jsonl").read_text().splitlines()
        assert lines[:15] == before[".desk/ledger.jsonl"].splitlines()  # 前の行は書き換えない
        hand = [(p, k) for p, k, _, _ in ledger.versions(ws)["rules/b.md"]]
        assert hand[0][1] == "手で直した" and ledger.state(ws)[1][hand[0][0]]["refs"] == ["P0004"] and ledger.state(ws)[1][hand[0][0]].get("base")  # 前の drift の分を、ID を外す前に残す
        assert "rules/a.md" not in {f for f, *_ in [(f,) for f in ledger.versions(ws)] if any(k == "手で直した" for _, k, _, _ in ledger.versions(ws)[f])}
        backup = next(x for x in (ws / ".desk" / "migrate").iterdir() if x.is_dir())
        assert all((backup / p).read_text() == t for p, t in before.items())  # 控えから戻せる
        again = (ws / ".desk" / "ledger.jsonl").read_text()
        assert not any(o.startswith(("台帳をつないだ", "決まりの ID を外した", "控え")) for o in apply(ws)) and (ws / ".desk" / "ledger.jsonl").read_text() == again  # 回し直しても変わらない
        try:
            relink_id(ws, "ws-deck-content-002", "rules/none.md")
            raise AssertionError("ないファイルに relink-id")
        except SystemExit:
            pass
        out = relink_id(ws, "ws-deck-content-002", "rules/a.md")
        assert "[ws-" not in (ws / "rules" / "a.md").read_text() + (ws / "rules" / "b.md").read_text() and ledger.state(ws)[0]["c-0002"]["to"] == "rules/a.md"
        assert relink_id(ws, "ws-deck-content-004", "戻さない")[0] == "台帳をつないだ: ws-deck-content-004 → 戻さない" and ledger.state(ws)[0]["c-0004"]["to"] == "戻さない"
        import contextlib, io
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ledger.main(["apply", "P0002"])  # 移行より前の提案も、ID を外した文で当たる
                assert "結論を先に書く。" in (ws / "rules" / "a.md").read_text()
                ledger.main(["undo", "P0002"])
                ledger.main(["undo", "P0003"])  # 移行より前に当てた提案も戻せる
                ledger.main(["apply", "P0005"])  # 新しい ID を書き入れる提案も、ID を外した文で当たる
                assert "- まだ当てていない新しい決まり。" in (ws / "rules" / "c.md").read_text() and "[ws-" not in (ws / "rules" / "c.md").read_text()
                ledger.main(["undo", "P0005"])
            assert (ws / "rules" / "c.md").read_text() == fm
        finally:
            os.chdir(cwd)
        assert needs(ws) == [] and ledger.drift(ws, quiet=True) == []  # ID を外したファイルは移行の版、ほかのファイル（py も）は初めの版がある
        assert {"移行", "初めの版", "手で直した"} <= {k for v in ledger.versions(ws).values() for _, k, _, _ in v}
        pid = next(p for p, kind, _, _ in ledger.versions(ws)["Customers/acme/memory.md"] if kind == "移行")
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ledger.main(["undo", pid])  # ID を外した版を戻せる
        finally:
            os.chdir(cwd)
        assert (ws / "Customers" / "acme" / "memory.md").read_text() == "- [ws-memory-001] 敬称は様\n"
    with tempfile.TemporaryDirectory() as tmp:  # 決められない ID だけが残り、初めの apply が早く返ったときも、relink-id が手で直した版と初めの版を残す
        ws = Path(tmp).resolve()
        put = lambda rel, text: ((ws / rel).parent.mkdir(parents=True, exist_ok=True), (ws / rel).write_text(text))
        put("desk.toml", "")
        fm = "---\ndescription: x\n---\n"
        put("rules/a.md", fm + "- [ws-deck-content-001] 写し。\n- 手で直した文。\n")
        put("rules/b.md", fm + "- [ws-deck-content-001] 写し。\n")
        put(".desk/ledger.jsonl", json.dumps({"ts": "2026-10-20T00:00:00Z", "kind": "proposal", "id": "P0001", "file": "rules/a.md", "old": "", "new": "- 当てたあと手で直された文。", "rule": "", "src": [], "why": "x", "type": ""}, ensure_ascii=False) + "\n"
            + json.dumps({"ts": "2026-10-20T00:00:00Z", "kind": "applied", "ref": "P0001", "appended": True, "prev": {}}) + "\n")
        out = apply(ws)
        assert all(o.startswith("要判断") for o in out) and not ledger.versions(ws)  # 早く返った（控えも版もない）
        relink_id(ws, "ws-deck-content-001", "rules/a.md")
        kinds = {f: [k for _, k, _, _ in v] for f, v in ledger.versions(ws).items()}
        assert kinds["rules/a.md"][0] == "手で直した" and "移行" in kinds["rules/a.md"] and "移行" in kinds["rules/b.md"] and ledger.drift(ws, quiet=True) == []
    with tempfile.TemporaryDirectory() as tmp:  # to-user: ワークスペースの desk.toml を個人の設定に移す
        ws, conf = Path(tmp, "ws").resolve(), Path(tmp, "home", ".desk.toml")
        (ws / ".desk" / "migrate").mkdir(parents=True)
        (ws / "desk.toml").write_text('# 頭\n[drive]\ndesk = "u"\n')
        (ws / ".desk" / "migrate" / "desk.toml").write_text("前に移したもの")
        os.environ["DESK_CONFIG"] = str(conf)
        out = to_user(ws)
        assert out[0].startswith(f"移した: desk.toml → {conf}") and not (ws / "desk.toml").exists() and desk.locate(ws) == (conf, ws) == desk.locate(tmp)
        assert desk.with_workspace('# 頭\n[drive]\ndesk = "u"\n', ws) == conf.read_text() and (ws / ".desk" / "migrate" / "desk.toml").read_text() == "前に移したもの"  # 前の控えを上書きしない
        assert to_user(ws)[0].startswith("移していない") and workspace(ws) == ws  # 2 回目は何もしない。上に desk.toml がなくても、個人の設定で見つかる
        (ws / "desk.toml").write_text("")
        assert to_user(ws)[0].startswith(f"移していない（{conf} がもうある") and (ws / "desk.toml").is_file()
        conf.unlink()
        (ws / OLD_CONF).write_text("")  # 前の版の factory.toml が残っている
        assert to_user(ws)[0].startswith("移していない（前の版") and not conf.exists()
        (ws / OLD_CONF).unlink()
        Path(tmp, "desk.toml").write_text("")  # 上に desk.toml がある: 移すと、中で開いたときにそちらが勝つ
        assert to_user(ws)[0].startswith("移していない（上の") and (ws / "desk.toml").is_file() and not conf.exists()
    RECIPES = True
    selftest_recipes()
    print("selftest ok")


def selftest_recipes():
    """2026-10-29: rules/ → recipes/。決まりはフォルダごとのレシピに、paths は step に、台帳と本文の前のパスは今のパスに。何度回してもよい。"""
    with tempfile.TemporaryDirectory() as tmp:  # 和文の名前は残し、つないだ名前がほかの名前と重なっても、1 つのレシピに 2 つを移さない
        ws = Path(tmp)
        for f in ("rules/顧客向け.md", "rules/x/顧客向け.md", "rules/a/b.md", "rules/c/b.md", "rules/a_b.md", "rules/---.md", "rules/cxo.md", "recipes/cxo/RECIPE.md", "rules/logo.png", "recipes/logo.png"):
            (ws / f).parent.mkdir(parents=True, exist_ok=True)
            (ws / f).write_text("x")
        dst = [d.relative_to(ws / "recipes").as_posix() for _, d in recipe_moves(ws)]
        assert len(set(dst)) == len(dst) and {"顧客向け/RECIPE.md", "x_顧客向け/RECIPE.md", "recipe/RECIPE.md", "cxo_2/RECIPE.md"} <= set(dst), dst  # 手で作った recipes/cxo/ とも重ねない
        (ws / "AGENTS.md").write_text("- 画像は rules/logo.png、決まりは rules/cxo.md\nrules/<名前>.md … 決まり（rules/README.md）\n")
        out = to_recipes(ws, ws / "backup")
        assert (ws / "AGENTS.md").read_text() == "- 画像は rules/logo.png、決まりは recipes/cxo_2/RECIPE.md\nrecipes/<名前>/RECIPE.md … 決まり（recipes/README.md）\n" and any("移していない" in x and "logo.png" in x for x in out)  # 移さなかったものの前のパスは書き換えない。前の雛形の置き場所は今の置き場所に
        assert any(x.startswith("要判断: AGENTS.md に前の rules/ のパスが残っている（- 画像は rules/logo.png") for x in out), out  # 書き換えなかった前のパスは知らせる
    with tempfile.TemporaryDirectory() as tmp:  # 決められない ID があれば、relink-id で決めるまで rules/ を移さない（relink-id は rules/ で ID を探す）
        ws = Path(tmp).resolve()
        (ws / "desk.toml").write_text("")
        for f in ("a.md", "b.md"):
            (ws / "rules").mkdir(exist_ok=True)
            (ws / "rules" / f).write_text("---\ndescription: x\n---\n- [ws-example-001] 残す\n")
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            out = apply(ws)
            assert (ws / "rules" / "a.md").is_file() and any("relink-id のあと" in x for x in out), out
            relink_id(ws, "ws-example-001", "rules/a.md")
            apply(ws)
        finally:
            os.chdir(cwd)
        assert not (ws / "rules").exists() and "ws-example-001" not in (ws / "recipes" / "a" / "RECIPE.md").read_text() + (ws / "recipes" / "b" / "RECIPE.md").read_text()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp).resolve()
        (ws / "desk.toml").write_text("")
        r = ws / "rules"
        files = {"slides-build/visual.md": "---\ndescription: 見た目\npaths: [slides-build/visual.md]\n---\n- 16pt\n",
                 "deck-practices/materials.md": "---\ndescription: 道具\npaths:\n  - deck-practices/materials.md\n  - deck-research/sources.md\ntargets: [slides]\n---\n- Glean\n",
                 "deck-practices/content.md": "---\ndescription: 中身\npaths: [deck-practices/content.md, slides-build/visual.md]\n---\n- 主張\n",
                 "deck-review/visual.md": "---\ndescription: レビューの見た目\npaths: [deck-review/prompt_slides.md]\n---\n- 観点\n",
                 "docs-build/templates.md": "---\ndescription: PoC の計画書\npaths: [docs-build/templates.md]\n---\n- 章立て\n",
                 "deck-practices/content_internal.md": "---\ndescription: 社内の資料\npaths: [deck-practices/content_internal.md]\n---\n- 社内\n",
                 "account_plan.md": "---\ndescription: Account Plan\naudience: [社内向け]\n---\n- 章\n",
                 "slides-build/checks.py": "def slides(p, r):\n    pass\n", "docs-build/templates/poc/doc.md": "# PoC\n", "README.md": "# rules/\n", "slides-build/logo.png": "png"}
        for f, x in files.items():
            (r / f).parent.mkdir(parents=True, exist_ok=True)
            (r / f).write_text(x)
        (ws / "AGENTS.md").write_text("- 決まりは `rules/` に置く。点検は `rules/slides-build/checks.py`。ドキュメントの点検は `rules/docs-build/checks.py`。\n")
        (ws / ".gitignore").write_text("/*\n!/rules/\n")
        deck = ws / "Customers" / "acme" / "d"
        deck.mkdir(parents=True)
        (deck / "構成案.md").write_text("- **使う決まり:** rules/account_plan.md\n- 前は rules/account_plan.md の章立てで作った。\n")
        (deck.parent / "e").mkdir()
        (deck.parent / "e" / "構成案.md").write_bytes("- **使う決まり:** rules/account_plan.md\n- 欠けた字（".encode() + b"\xbc\x89\n")  # 壊れたバイトがあっても止まらず、そのバイトのまま書き戻す
        (ws / "Customers" / "acme" / "memory.md").write_text("- 訳は rules/slides-build/visual.md の書体\n")
        led = ws / ".desk" / "ledger.jsonl"
        led.parent.mkdir()
        led.write_text(json.dumps({"ts": "2026-10-28T00:00:00Z", "kind": "correction", "id": "c-0001", "deck": "Customers/acme/d", "quote": "rules/slides-build/visual.md のとおり",
                                   "fix": "x", "to": "rules/slides-build/visual.md", "check": "レビュー", "decided": True}, ensure_ascii=False) + "\n")
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            assert any("recipes/ へ" in x for x in needs(ws))
            out = apply(ws)
        finally:
            os.chdir(cwd)
        rc = ws / "recipes"
        got = {str(p.relative_to(rc)) for p in rc.rglob("*") if p.is_file()}
        assert got == {"materials/RECIPE.md", "content/RECIPE.md", "deck_review_visual/RECIPE.md", "slides_build_visual/RECIPE.md", "account_plan/RECIPE.md",
                       "slide_checks/checks.py", "doc_templates/templates/poc/doc.md", "slides-build/logo.png", "README.md", "docs_build_templates/RECIPE.md", "content_internal/RECIPE.md"}, got  # 同じ名前（visual）は、フォルダの名前もつなぐ
        front = lambda f: desk.front((rc / f / "RECIPE.md").read_text())
        assert front("slides_build_visual")["step"] == "build" and front("materials")["step"] == "gather" and front("materials")["targets"] == ["slides"]  # どのファイルも同じ作業なら step に
        assert "step" not in front("content") and "step" not in front("deck_review_visual") and "paths" not in front("content")  # 作業がまたがるもの・レビューは書かない（資料を作るどの作業でも）
        assert front("account_plan")["per_material"] == front("content_internal")["per_material"] == "true" and not (ws / "rules").exists()  # 資料の種類ごとのファイルへの足しも、資料ごとに選ぶ  # paths のなかったものは資料ごとに選ぶ。rules/ は残らない
        assert "recipes/slide_checks/checks.py" in (ws / "AGENTS.md").read_text() and "recipes/doc_checks/checks.py" in (ws / "AGENTS.md").read_text() and "`recipes/` に置く" in (ws / "AGENTS.md").read_text() and "!/recipes/" in (ws / ".gitignore").read_text()
        assert (deck.parent / "e" / "構成案.md").read_bytes() == "- **使う決まり:** recipes/account_plan/RECIPE.md\n- 欠けた字（".encode() + b"\xbc\x89\n"
        assert (deck / "構成案.md").read_text() == "- **使う決まり:** recipes/account_plan/RECIPE.md\n- 前は rules/account_plan.md の章立てで作った。\n" and "recipes/slides_build_visual/RECIPE.md" in (ws / "Customers" / "acme" / "memory.md").read_text()
        c = ledger.state(ws)[0]["c-0001"]
        assert c["to"] == "recipes/slides_build_visual/RECIPE.md" and c["quote"] == "rules/slides-build/visual.md のとおり" and c["decided"]  # 台帳の戻し先はつながる。ユーザーの言葉はそのまま
        assert ledger.drift(ws, quiet=True) == [] and any("目的ごとにまとめ直す" in x for x in out) and "要判断: recipes/slides-build/logo.png はレシピのフォルダの外にある。使うレシピのフォルダへ移し、RECIPE.md の中のパスを直す" in out and not needs(ws)  # 書き換えたものは版になり、もう移すものはない
        assert apply(ws) == ["移すものはない（今の版）"]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    ws = workspace()
    if not ws:
        sys.exit("desk.toml も factory.toml も見つからない。ワークスペースの中で回す")
    if a in ([], ["check"]):
        moves, edit, split, ws_map = plan(ws)
        ids, new, open_ = ws_ids(ws)
        heads = fronts(ws, {s for s, _ in moves})
        data = [f"移す: {s.relative_to(ws)} → {d.relative_to(ws)}" for s, d in data_moves(ws)] + ["（台帳の書き換えは、.desk/ に移したあとの check で出る）"] * (ws / OLD_DIR).is_dir()
        data += [f"移す: {s.relative_to(ws)}/ → {d.relative_to(ws)}/（状態・種類・mode を desk-crawl の形に）" for s, d in scout_moves(ws)]
        print("\n".join(data + [f"移す: {s.relative_to(ws)} → {d.relative_to(ws)}" for s, d in moves] + [f"書き換える: {p.relative_to(ws)}{changed(p, ws_map)}" for p in edit]
                        + [f"frontmatter を足す: {p.relative_to(ws)}" for p, h in heads if h] + by_hand(ws, heads)
                        + [f"要判断（apply のあと）: rules/{k} は {v} に分けた" for k, v in split if (moves or edit) and not RECIPES]
                        + [f"台帳を合わせる: {i} の変更先 {a} → {b}" for i, a, b, _ in relinks(ws) if b] + asks(relinks(ws))
                        + [f"決まりの ID を外す: {p.relative_to(ws)}（{len(WS_ID.findall(t)) - len(WS_ID.findall(n))} 個）" for p, t, n in strip_plan(ws, ids)]
                        + [f"台帳をつなぐ: {x} → {f}" for x, f in sorted(new.items())] + id_asks(ws, ids, open_)
                        + [f"移す（recipes/ へ）: {s.relative_to(ws)} → {d.relative_to(ws)}" for s, d in recipe_moves(ws)]) or "移すものはない（今の版）")
    elif a == ["apply"]:
        print("\n".join(apply(ws)))
    elif len(a) == 3 and a[0] == "relink":
        print("\n".join(decide(ws, a[1], a[2])))
    elif len(a) == 3 and a[0] == "relink-id":
        print("\n".join(relink_id(ws, a[1], a[2])))
    elif a == ["to-user"]:
        print("\n".join(to_user(ws)))
    else:
        sys.exit(__doc__)
