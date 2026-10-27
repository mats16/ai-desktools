#!/usr/bin/env python3
"""決まりの台帳。修正の指示（指摘）、決まりの変更の提案・適用・却下、判断待ち、レビューの結果、ワークスペースの決まりのファイルの版を、ワークスペースの .desk/ledger.jsonl に 1 件 1 行で足していく。
プラグインの決まりの本文には ID（slides-visual-<番号> を角括弧で囲む。接頭辞は何についての決まりか〔TOPICS〕で、置き場所が変わっても変えない）と短い理由だけを書き、日付・原文・どの資料か・ユーザーが決めたかは、ここに ID でつなぐ。
ワークスペースの決まり（AGENTS.md・rules/・顧客の memory.md）には ID を書かない。指摘はファイルにつなぎ、ファイルが変わるたびに版（P-ID。前と後の全文と、取り込んだ指摘）を残す。
決まりの置き場所と戻し方は ../rules.md。ワークスペース（探し方は desk.py）で回す。標準ライブラリだけ。
usage:
  ledger.py add --deck <資料のフォルダ> --quote <ユーザーの言葉> [--fix <直した箇所>] [--to <決まりの ID・ファイル・未・戻さない>] [--check lint|レビュー|なし] [--session <会話 ID>] [--at <言われた時刻（UTC）>] [--decided] [--plan AI|人] [--once]
                                                   --plan は構成の見逃し（方針のレビューのあとに、聞き手・問い・主張・順序を変えた指摘。値はその資料の方針のレビュー）
                                                   --at は会話の記録からあとで拾ったときの発言の時刻（再発の数に使う。既定は書いた時刻）
                                                   --once は前の形の構成案から取り込むときだけ（同じ資料・言葉・会話がもうあれば足さない）
                                                   作る会話が --to にワークスペースの決まりのファイルを書いたら、そのファイルが最後の版から変わっていれば版を残す（route も）
  ledger.py route <c-ID> <戻し先>                 指摘の戻し先を決める・変える
  ledger.py plan <c-ID> AI|人|なし                 台帳にある指摘に、構成の見逃しの印をあとから付ける（なしは付け間違いを外す）
  ledger.py list [--deck <フォルダ>] [--open] [--to <戻し先>] [--odd] [--since <時刻>]   指摘の一覧（--open は戻し先が「未」のものだけ。--odd は決まりに結び付かない前の書き方の戻し先。--since はその時刻から〔同じ秒も〕書いた・戻し先が変わったもの。当てた提案がつないだものは除く）
  ledger.py why <決まりの ID かファイル>           その決まりの出典（指摘・日付・原文、再発か）と、資料・顧客の数、ユーザーが決めたか、レビューの結果。ファイルなら版の並びも
  ledger.py rules                                  決まりごとの数（指摘・再発・資料・顧客・レビューの結果）と、週ごとの取りこぼしと構成の見逃し
  ledger.py candidates                             決まりごとの次の一手（下ろす・書き直す・条件を足す・写しを消す・上書きを見直す）と、その決まりへの前の提案
  ledger.py effects                                文を変えた決まりごとに、変わる前と後に作った資料での指摘の数と見立て（効いた・変わらない・害が出た・指摘なし・まだ分からない、混ざっている）
  ledger.py next <接頭辞>                          プラグインの次の決まりの ID（接頭辞は TOPICS の主題）
  ledger.py where <決まりの ID>                    プラグインの決まりが書いてある場所（[ID] のファイルと行）
  ledger.py topics                                 決まりの ID の主題の一覧
  ledger.py propose --file <ワークスペースのファイル> (--new <新しい文> [--old <今の文>] | --rewrite <新しい全文のファイル>) --why <要点> [--src c-1,c-2] [--changes c-1:足した,…] [--kind <種類>] [--rec 適用|様子見|却下 [--rec-why <理由>]] [--auto]
  ledger.py propose --plugin --file <skills/ からのパス> --new <新しい文> [--old <今の文>] [--rule <ID>] --why <要点> [--src c-1,c-2] [--replaces <ワークスペースのファイル>,…] [--kind <種類>] [--rec …]
                                                   --rewrite はファイルの全体を作り直す（今の全文から、そのファイルの文へ。desk-dreaming の作り直し）
                                                   --changes は取り込んだ指摘ごとの変化（足した・まとめた・消した・書き換えた）
                                                   --rec は出した側の推奨（ユーザーは「推奨どおり」と例外だけを返せる）
                                                   --auto は会話を出典にしない片付け（重なり・古い記述）で、箇条書きの項目を丸ごと消すだけのものを、出してすぐ当てる。当ててよいかはここで見る
                                                   --plugin は変更先がプラグイン（--file は skills/ からのパス）。当てず、desk-kaizen で Issue にする
                                                   --replaces は、その Issue の直しが届いたら写しを消すワークスペースのファイル（上書きなど。出典の指摘の戻し先は書かなくてよい）
  ledger.py pending [--status 却下|適用済み|戻した|取り下げ|Issue にした|all]   提案と差分（既定は未適用。却下は理由も）
  ledger.py apply <P-ID ...|all>                   提案を当てる（今の文がそのまま 1 か所にあるときだけ。プラグインへの提案は当てない）
  ledger.py sent <P-ID> --issue <URL> [--rule <ID>]   プラグインへの提案を Issue にした（出典の指摘をその決まりにつなぐ。--rule は Issue で提案と違う ID にしたとき）
  ledger.py reject <P-ID> --reason <理由>           ユーザーが却下した（desk-dreaming は同じ趣旨の提案をもう出さない）。Issue にしたものが断られたときも（出典の指摘は前の戻し先に戻る）
  ledger.py withdraw <P-ID か Q-ID> --reason <理由>   出した側が取り下げる（書き間違いの出し直しなど。却下には数えない）
  ledger.py undo <P-ID>                            当てた提案（版）を逆向きに当てて戻す
  ledger.py drift [--record]                       最後の版から変わった決まりのファイル（手で直したか、作る会話が戻し先を書かずに直した。ユーザーが直したものとして扱う）。--record は「手で直した」版にする
  ledger.py ask --q <ユーザーに聞くこと> [--rule <ID かファイル>] [--src c-1,c-2] [--rec <推奨の答え>]   判断待ち
  ledger.py answer <Q-ID> --a <ユーザーの言葉>      判断待ちへの答え
  ledger.py questions [--all]                      判断待ち（--all は答えたものと取り下げたものも）
  ledger.py review --deck <資料のフォルダ> --table <指摘の表のファイル>   deck-review の指摘の表から、決まりの列のある行の結果を取り込む（同じ行は 2 度数えず、ラウンドをまたぐ同じ行はあとのラウンドの結果）
  ledger.py --selftest
台帳の原文には顧客のことが入る。.desk/ から外（Issue・チャット）に写さない。
add と review は、そのときのハーネス（プラグインと、ワークスペースの AGENTS.md・rules/）の指紋も残す。指紋ごとの決まりの文の控えは .desk/harness/<指紋>.json（effects が読む）。
desk-migrate がワークスペースの決まりの ID を外したときの、ID → ファイルの対応は migrated の記録に残し、前の記録の ID はそのファイルとして読む（台帳の前の行は書き換えない）。"""
import argparse, difflib, hashlib, json, os, re, sys, tempfile, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import desk  # ワークスペースの探し方

try:
    import fcntl
except ImportError:  # ponytail: Windows では鍵をかけない。同時に書く会話があれば番号が重なりうる
    fcntl = None

PLUGIN = Path(__file__).resolve().parents[2]  # プラグインの skills/
ID = r"(?!ws-)[a-z][\w-]*?-\d{3}"  # プラグインの決まりの ID（slides-visual-012）
ANY_ID = r"(?:ws-)?[a-z][\w-]*?-\d{3}"  # 前の版のワークスペースの ID（ws-slides-visual-003）も含めた、ID の形
RULE_ID = re.compile(rf"\[({ID})\]")
FILE = r"[^\s,、「」|\[\]](?:[^,、「」|\[\]\n]*?[^\s,、「」|\[\]])?\.(?:md|py)"  # レビューの表の「決まり」の列に書く、ワークスペースかプラグインのファイル（顧客のフォルダの名前に空白があってよい）
KEY = re.compile(rf"{ID}|lint:.+|{FILE}")  # レビューの表の「決まり」の列に書くもの（lint の規則は名前で lint:<名前>）
CITE = re.compile(rf"(?<![\w-])\[?({ID}|{FILE})\]?\s*「([^」]*)」")  # 決まりの列の ID・ファイルに添えた、その決まりの文から写した語句（slides-visual-013「単語や文節の途中で折り返さない」）
RESULTS = ("直した", "残した（誤り）", "残した", "聞く")
NO_RULE = ("未", "戻さない")  # 決まりにつないでいない戻し先
TWICE = 2  # 2 本以上の資料・2 社以上の顧客に出たら、たまたまでないとみなす（desk-dreaming の prompt_propose.md の c、run.md の 4i・5）
AUTO = ("重なり", "古い記述")  # 会話を出典にしない片付け。--auto で、出してすぐ当てる（desk-dreaming/run.md の 3d）
RECS = ("適用", "様子見", "却下")
TOPICS = {  # 決まりの ID の主題（何についての決まりか）。ID は一度付けたら、ファイルを分けても移しても変えない（../rules.md の "Rule IDs"）
    "deck-flow": "1〜11 の工程と、どの工程でも守ること", "deck-agents": "子の起こし方と待ち方", "deck-content": "構成案と言葉",
    "deck-sources": "材料の集め方と出典の台帳", "deck-drive": "Drive への置き方", "deck-rules": "ワークスペースの決まりと、修正の指示の戻し方",
    "deck-review": "返す前のレビューと、その観点", "deck-comments": "コメントから直す", "deck-profile": "顧客の profile", "deck-research": "調べ直し",
    "deck-lint": "スライドとドキュメントで共通の lint", "deck-google": "Google の API・認証・上限", "deck-brand": "書体・字幅・著作権表示",
    "slides-flow": "6〜8 の工程と、確かめの 3 層", "slides-command": "組むコマンドと、組むときのふるまい", "slides-pages": "ページの JSON の書き方",
    "slides-component": "部品の寸法と描き方", "slides-visual": "スライドの見た目", "slides-theme": "テーマとテンプレート", "slides-image": "画像・ロゴ・アイコン",
    "slides-api": "Slides API の落とし穴", "slides-legacy": "pages.py と pptx の古いデッキ", "slides-reuse": "社内のデッキの流用", "slides-lint": "スライドの lint と画像での測り",
    "docs-write": "doc.md の書き方と組み方", "docs-visual": "ドキュメントの見た目", "docs-lint": "ドキュメントの lint", "docs-api": "Docs API の落とし穴",
    "vids-voice": "動画の読み上げの台本（スピーカーノート）", "vids-voice-ja": "日本語の読み上げの台本", "vids-voice-en": "英語の読み上げの台本",
    "vids-video": "動画を作る・差し替える", "desk-dreaming": "定期の整理", "source-scout": "定期の見張りで読む先を管理し、学ぶ"}
PLAN_RULE = "deck-flow-004"  # 構成案の AI レビューの頼み方。これを見直すかの判断待ちに答えたら、構成の見逃しをその答えのあとから数え直す
AGENTS_MAX = 20000  # ワークスペースの AGENTS.md のバイト数の上限（desk-dreaming/run.md の 4h。Codex は 32 KiB で切り、Claude Code は毎回すべて読む）
HARNESS = ("skills", "hooks", "extensions")  # 指紋に入れるプラグインのフォルダ（リポジトリの根元から）
OVERRIDE = re.compile(r"[（(]([^（）()\n]*?)\s*より優先")  # ワークスペースの決まりの「…（slides-visual-012 より優先）」。括弧の中の ID を全部取る
PLUGIN_ID = re.compile(r"(?<![\w-])(?!ws-)[a-z][\w-]*?-\d{3}")
BRACKETED = re.compile(rf"\[({ANY_ID})\]")  # ワークスペースのファイルに書かない、角括弧の ID
CHANGES = ("足した", "まとめた", "消した", "書き換えた")  # 版が取り込んだ指摘ごとの変化（--changes）
VERSIONS = ("その場で戻した", "手で直した", "初めの版", "移行")  # 台帳が書く版だけの提案（人に出す提案でない。「前の提案」に出さない）


def workspace():
    """ワークスペース（探し方は desk.py）。"""
    return f[1] if (f := desk.locate()) else sys.exit(desk.missing())


def path(ws):
    return ws / ".desk" / "ledger.jsonl"


def records(ws):
    p = path(ws)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def write(ws, rec, number=None):
    """1 行足す。number=("correction", "c-", 4) なら、鍵をかけたまま次の番号を rec["id"] にする（同時に書く会話で番号が重ならないように）。"""
    p = path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **rec}
    with p.open("a", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        if number:
            kind, head, width = number
            rec = {**rec, "id": f"{head}{sum(r['kind'] == kind for r in records(ws)) + 1:0{width}d}"}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def utc(s):
    """--at を ts と同じ UTC の形にする（文字のまま ts と比べるので）。時差のない時刻は UTC とみなす（sessions.py の時刻は UTC）。"""
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"--at は ISO 8601 の時刻（2026-10-12T09:30 など。時差がなければ UTC）: {s}")
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def when(c):
    return c.get("at") or c.get("date") or c["ts"]


def by(c):
    """誰が書いたか。作る会話（session）、あとで会話の記録から拾った dreaming（--at）、前の形からの取り込み（import）。
    by のない前の記録は、日付だけ（本文から移した出典）なら取り込み、--at があれば dreaming。前の --once の取り込みは見分けられず、作る会話に入る。"""
    if "by" in c:
        return c["by"]
    if "at" in c:
        return "dreaming"
    return "import" if "date" in c else "session"


def introduces(p):
    """提案が決まりの ID を新しく書き入れるか。今ある決まりを書き直す提案は、決まりを作らない。"""
    tag = f"[{p['rule']}]"
    return bool(p["rule"]) and tag in p["new"] and tag not in p["old"]


def linked(to, ws=None):
    """戻し先が決まりの ID・ファイル（後ろに（）の注を付けてよい）・未・戻さない のどれか 1 つか。ID とファイルを並べた戻し先は、決まりに結び付かない
    （why と、ユーザーが決めた決まりの守りが効かない）。前の記録にある並べた形は、auto_ok が読み、list --odd が出す（desk-dreaming/run.md の 3c で付け直す）。"""
    real = re.fullmatch(r"(.+?\.\w+)(?:（([^）]*)）)?", to)  # ワークスペースかプラグインに実際にあるフォルダの中のファイルなら、名前に・や（）があってもよい（Customers/アクメ・ジャパン/memory.md）
    exists = lambda b, f: (b / f).is_file() or (b / f).parent != b and (b / f).parent.is_dir() and re.fullmatch(r"[^\s・、,（#]+\.\w+", Path(f).name)  # ファイルがあるか、根元でないフォルダの中の、ふつうの名前のファイル
    if ws and real and any(exists(b, real.group(1)) for b in (ws, PLUGIN)) and not re.search(rf"(?:^|[^\w/.-]){ANY_ID}(?:[^\w/.-]|$)", real.group(1) + "（" + (real.group(2) or "") + "）"):
        return True
    path = re.fullmatch(r"([^・、,（#]+\.\w+)(?:（([^）]*)）)?", to)  # パスには空白が入ってよい（Customers/Acme Corp/memory.md）。ID を並べたもの・ファイルを 2 つ並べたものは除く
    alone = rf"(?:^|[^\w/.-]){ANY_ID}(?:[^\w/.-]|$)"  # パスの区切り（/）の中でない ID（ws-a-003:rules/a.md・rules/a.md ws-a-003）。Customers/client-001/memory.md は通す
    one = path and not re.search(alone, path.group(1)) and sum(bool(re.search(r"\.\w+$", x)) for x in path.group(1).split()) == 1
    return bool(re.fullmatch(ID, to) or to in NO_RULE or one and not re.search(rf"(?<![\w-]){ANY_ID}(?![\w-])", path.group(2) or ""))


def to_arg(s):
    """add と route の --to。決まりに結び付かない書き方は止める。"""
    if linked(s, (f := desk.locate()) and f[1]):
        return s
    raise argparse.ArgumentTypeError(f"戻し先はプラグインの決まりの ID・ファイル・未・戻さない のどれか 1 つ: {s}（ワークスペースの決まりは ID でなく、そのファイル〔rules/<名前>.md・"
                                     "AGENTS.md・Customers/<顧客>/memory.md〕にする。ID とファイルを並べると決まりに結び付かない。"
                                     "点検に下ろした決まりも、その決まりの ID かファイルにする。その資料だけの直しは 戻さない にし、理由は --fix に書く）")


def key(to):
    """数える単位。ファイルの戻し先は、頭の ./ と後ろの（）の注を外したパス。"""
    return re.sub(r"^\./|（[^）]*）$", "", to) if re.search(r"\.\w+(?:（[^）]*）)?$", to) else to


def rule_file(f):
    """台帳が版を残すワークスペースの決まりのファイルか（AGENTS.md、rules/ の .md と .py〔README.md と docs-build のテンプレートは除く〕、顧客の memory.md）。"""
    p = Path(f)
    return (f == "AGENTS.md" or p.parts[:1] == ("rules",) and p.suffix in (".md", ".py") and p.name != "README.md" and "templates" not in p.parts
            or len(p.parts) == 3 and p.parts[0] == "Customers" and p.name == "memory.md")


def rule_files(ws):
    """今あるワークスペースの決まりのファイル（ワークスペースからのパス）。"""
    fs = [ws / "AGENTS.md", *(ws / "rules").rglob("*"), *(ws / "Customers").glob("*/memory.md")]
    return sorted(r for f in fs if f.is_file() and rule_file(r := f.relative_to(ws).as_posix()))


def ws_rules_arg(s):
    """--replaces はワークスペースの決まりのファイルを , でつないだもの。"""
    fs = [key(x) for x in s.split(",") if x]
    if not fs or not all(map(rule_file, fs)):
        raise argparse.ArgumentTypeError(f"ワークスペースの決まりのファイルを , でつなぐ（rules/slides-build/visual.md,AGENTS.md など）: {s}")
    return fs


def rule_arg(s):
    """--rule はプラグインの決まりの ID の形だけ（崩れた ID は next の番号を数えられない）。"""
    if not re.fullmatch(ID, s):
        raise argparse.ArgumentTypeError(f"プラグインの決まりの ID の形でない（slides-visual-012 など。ワークスペースの決まりに ID は付けない）: {s}")
    return s


def subject_arg(s):
    """ask の --rule。プラグインの決まりの ID か、ワークスペースの決まりのファイル。"""
    if re.fullmatch(ID, s) or rule_file(key(s)):
        return key(s)
    raise argparse.ArgumentTypeError(f"プラグインの決まりの ID か、ワークスペースの決まりのファイル（rules/<名前>.md など）: {s}")


def changes_arg(s):
    """--changes は c-ID:変化 を , でつないだもの（変化は CHANGES）。"""
    pairs = [x.split(":", 1) for x in s.split(",") if x]
    if not pairs or not all(len(x) == 2 and re.fullmatch(r"c-\w+", x[0]) and x[1] in CHANGES for x in pairs):
        raise argparse.ArgumentTypeError(f"c-ID:変化 を , でつなぐ（変化は {'・'.join(CHANGES)}。c-0012:足した,c-0007:まとめた など）: {s}")
    return dict(pairs)


def state(ws):
    """台帳を読み直して、いまの指摘（戻し先は最後の route）、提案と判断待ち（状態は最後の出来事）、レビューの結果にする。
    指摘の recur（再発）は、初めてつないだプラグインの決まりの ID（first。ファイルは数えない）が、言われたときにあったか。つないだ時刻ではなく、言われた時刻で見る。
    台帳の提案で作った決まり（ID を書き入れた提案を Issue にした時から、断られた時まで）は、その間に言われたか（作り直したら、どの間でもよい）。台帳で作っていなければ、前からある。
    あとで別の決まりに移しても（大元に上げたときなど）first は変えない。未・戻さない・ファイルに戻したら決め直す。
    desk-migrate が外したワークスペースの決まりの ID（migrated の記録）は、そのファイルとして読む。"""
    cs, ps, qs, rv = {}, {}, {}, {}
    life, made = {}, {}  # 台帳の提案で作った決まりの ID → あった間 [[できた時刻, なくなった時刻か None], …]・いまの決まりを作った提案
    recs = records(ws)
    alias = {k: v for r in recs if r["kind"] == "migrated" for k, v in r["ids"].items()}  # 前の版のワークスペースの ID → ファイル
    name = lambda x: key(alias.get(x, x))
    unid = (lambda t, pat=re.compile(r"\[(?:" + "|".join(map(re.escape, alias)) + r")\] ?"): pat.sub("", t)) if alias else (lambda t: t)  # desk-migrate がファイルから外した [ID]（台帳の前の行は書き換えない）

    def link(c, to):
        if not re.fullmatch(ID, to):  # 未・戻さない・ファイル（1 つのファイルには別々の決まりが入るので、再発を数えない）
            c.pop("first", None)
        elif "first" not in c:
            c["first"] = to

    for n, r in enumerate(recs):
        k = r["kind"]
        if k == "correction":
            cs[r["id"]] = {**r, "to": name(r["to"])}
            link(cs[r["id"]], cs[r["id"]]["to"])
        elif k == "route" and r["ref"] in cs:
            c = cs[r["ref"]]
            if name(r["to"]) != c["to"]:  # routed は、戻し先を人か会話が変えた時刻。当てた提案が出典をつなぐ（close。via）のは、その版が取り込んだので新しい入力にしない
                c.update(to=name(r["to"]), **({} if "via" in r else {"routed": r["ts"]}))
            link(c, c["to"])
        elif k == "plan" and r["ref"] in cs:
            if r["plan"] == "なし":
                cs[r["ref"]].pop("plan", None)
            else:
                cs[r["ref"]]["plan"] = r["plan"]
        elif k == "proposal":
            rule = "" if re.fullmatch(r"ws-.+", r["rule"]) else r["rule"]  # 前の版のワークスペースの ID は、変更先のファイルで数える
            ps[r["id"]] = {**r, "file": key(r["file"]), "rule": rule, "status": "未適用", "proposed": rule,  # proposed は提案の文に書いた ID（Issue で替えたら rule が替わる）
                           **({} if r.get("plugin") or r.get("full") else {"old": unid(r["old"]), "new": unid(r["new"])}),  # 移行より前の提案も、今のファイルと同じ文で当てる・戻す（全体の版は、そのときの全文のまま）
                           **({"replaces": [name(x) for x in r["replaces"]]} if r.get("replaces") else {})}
        elif k in ("applied", "rejected", "withdrawn", "undone", "sent") and r["ref"] in ps:
            p = ps[r["ref"]]
            intro = introduces(p)  # Issue で別の ID にしたときも、もとの提案の文で見る
            p.update(status={"applied": "適用済み", "rejected": "却下", "withdrawn": "取り下げ", "undone": "戻した", "sent": "Issue にした"}[k], seq=n,
                     **{x: r[x] for x in ("appended", "reason", "pr", "rule") if x in r}, **({"prev": {c: name(t) for c, t in r["prev"].items()}} if "prev" in r else {}))
            if k in ("applied", "sent") and intro and p["rule"] not in made:
                life.setdefault(p["rule"], []).append([r["ts"], None])
                made[p["rule"]] = p["id"]
            elif k in ("undone", "rejected", "withdrawn") and made.get(p["rule"]) == p["id"]:  # 作った決まりがなくなった
                life[p["rule"]][-1][1] = r["ts"]
                del made[p["rule"]]
        elif k == "question":
            qs[r["id"]] = {**r, "rule": name(r["rule"]), "status": "未回答"}
        elif k in ("answered", "withdrawn") and r["ref"] in qs:
            qs[r["ref"]].update(status="回答済み" if k == "answered" else "取り下げ", **{x: r[x] for x in ("a", "reason") if x in r},
                                **({"answered": r["ts"]} if k == "answered" else {}))
        elif k == "review":
            rv[r["key"]] = {**r, "rule": name(r["rule"])}  # 同じ行は、あとで取り込んだ結果にする
    for c in cs.values():
        if "first" not in c:
            continue
        t, f = when(c), c["first"]
        if "date" in c and "at" not in c:  # 前の形から移した、決まりを作った出典（日付だけ）
            c["recur"] = False
        else:
            c["recur"] = any(start < t and (end is None or t < end) for start, end in life[f]) if f in life else True
    return cs, ps, qs, list(rv.values())


def rel(ws, p):
    p = (Path.cwd() / Path(p).expanduser()).resolve()  # 絶対パスなら cwd は効かない
    return str(p.relative_to(ws)) if p.is_relative_to(ws) else str(p)


def versions(ws):
    """ワークスペースの決まりのファイル → 版の並び [(P-ID, 種類, 時刻, その版の全文)]。当てた・戻した出来事ごと。
    全文は、版の提案（full）の前と後の文か、当てた・戻した出来事に残した after。全文の分からない前の記録は並びに入れない。"""
    ps, out = {}, {}
    for r in records(ws):
        if r["kind"] == "proposal":
            ps[r["id"]] = r
        elif r["kind"] in ("applied", "undone") and (p := ps.get(r["ref"])) and not p.get("plugin"):
            text = r.get("after", (p["new"] if r["kind"] == "applied" else p["old"]) if p.get("full") else None)
            if text is not None:
                out.setdefault(key(p["file"]), []).append((p["id"], p.get("type", "") if r["kind"] == "applied" else "戻した", r["ts"], text))
    return out


def read(ws, f):
    return (ws / f).read_text(encoding="utf-8") if (ws / f).is_file() else ""


def revise(ws, f, old, new, src=(), kind="その場で戻した", base=False, **extra):
    """f の版を 1 つ残す。前と後の全文を持つ提案（full）を書き、当てたことにする（その P-ID が版の ID）。
    base は、台帳が初めて見たファイルの版（前の文が分からない。old は空にしておくが、undo はしない）。"""
    p = write(ws, {"kind": "proposal", "file": f, "old": old, "new": new, "rule": "", "why": kind, "src": list(src), "type": kind, "full": True,
                   **({"base": True} if base else {}), **extra}, ("proposal", "P", 4))
    write(ws, {"kind": "applied", "ref": p["id"], "prev": {}})
    return p["id"]


def record(ws, to, src):
    """作る会話がその場で決まりのファイルに戻したあと（add・route の --to がワークスペースの決まりのファイル）。最後の版から変わっていれば版を残す。
    台帳に版のないファイルは、この指摘より前の直しと分けられないので「初めの版」にする（指摘はつなぐが、ファイル全体をその指摘の直しとはしない。undo しない）。"""
    f = key(to)
    if not rule_file(f) or not (ws / f).resolve().is_relative_to(ws):
        return None
    vs, now = versions(ws).get(f), read(ws, f)
    if now != (old := vs[-1][3] if vs else ""):
        pid = revise(ws, f, old, now, src, kind="その場で戻した" if vs else "初めの版", base=not vs)
        print(f"{f} の版を残した: {pid}")
        return pid
    return None


def add(ws, a):
    deck = rel(ws, a.deck)
    same = a.once and next((c for c in state(ws)[0].values() if (c["deck"], c["quote"], c["session"]) == (deck, a.quote, a.session or "")), None)
    if same:  # 前の形の構成案の同じ行を、次の回でまた取り込んだとき。足し直さず、前の ID を返す（会話をまたぐくり返しは --once なしで足す）
        print(same["id"])
        return
    rec = write(ws, {"kind": "correction", "deck": deck, "quote": a.quote, "fix": a.fix or "", "to": key(a.to), "check": a.check,
                     "session": a.session or "", "decided": a.decided, "by": "import" if a.once else "dreaming" if a.at else "session",
                     **({"at": utc(a.at)} if a.at else {}), **({"plan": a.plan} if a.plan else {}),
                     **({} if a.once or a.at else {"fp": fingerprint(ws)})}, ("correction", "c-", 4))  # あとで拾った指摘は、言われたときのハーネスが分からない
    print(rec["id"])
    if not a.once and not a.at:  # 作る会話がその場で戻した（あとで拾った指摘は、そのときの直しが分からない）
        record(ws, a.to, [rec["id"]])


def show(c):
    d = " ユーザーが決めた" if c.get("decided") else ""
    d += "（再発）" if c.get("recur") else ""
    d += f"（構成の見逃し: {c['plan']}）" if c.get("plan") else ""
    return f"{c['id']} {when(c)[:10]} {c['deck'] or c.get('where') or '-'}「{c['quote'] or c.get('note', '')}」→ {c.get('fix') or '-'} [戻し先: {c['to']}][確かめ: {c.get('check', 'なし')}]{d}"


def customers(decks):
    return {d.split("/")[1] for d in decks if d.startswith("Customers/")}


def count(rows):
    """件数と、それが出た資料の数（desk-dreaming は資料の数で決める）。"""
    return f"{len(rows)}（資料 {len({r['deck'] for r in rows} - {''})}）"


def why(ws, rid):
    """その決まり（プラグインの ID か、ワークスペースのファイル）の指摘・数・レビューの結果。ファイルなら版の並び（どの版がどの指摘を取り込んだか）も。"""
    if re.fullmatch(r"ws-[a-z][\w-]*?-\d{3}", rid):  # desk-migrate が外したワークスペースの ID は、つないだファイルとして見る（つないでいなければ、前の記録の ID のまま）
        to = next((r["ids"][rid] for r in records(ws) if r["kind"] == "migrated" and rid in r["ids"]), rid)
        if to in NO_RULE:  # 消した決まりで、つなぐファイルがなかった。その ID につないだ指摘だけを出す
            mine = {r.get("id") or r.get("ref") for r in records(ws) if r["kind"] in ("correction", "route") and r["to"] == rid}
            cs = [c for c in state(ws)[0].values() if c["id"] in mine and c["to"] == to]  # あとでほかへつなぎ直したものは除く
            print(f"（{rid} は {to} にした決まり。その ID につないだ指摘 {len(cs)} 件）")
            for c in cs:
                print(show(c))
            return cs
        rid = to
        print(f"（{rid} として見る）")
    elif not (re.fullmatch(ID, rid) or rid.startswith("lint:")):  # ファイルは、ワークスペースからのパスか、今のフォルダからのパス
        rid = key(rid) if (ws / key(rid)).is_file() else key(rel(ws, rid))
    all_cs, ps, _, rv = state(ws)
    cs = [c for c in all_cs.values() if c["to"] == rid]
    for c in cs:
        print(show(c))
    decks = {c["deck"] for c in cs if c["deck"]}
    print(f"== {rid}: 指摘 {len(cs)} 件（再発 {count([c for c in cs if c.get('recur')])}）・資料 {len(decks)} 本・顧客 {len(customers(decks))} 社・"
          f"ユーザーが決めた: {'あり' if any(c.get('decided') for c in cs) else 'なし'}")
    mine = [r for r in rv if r["rule"] == rid]
    if mine:
        print("   レビュー: " + "・".join(f"{k} {count([r for r in mine if r['result'] == k])}" for k in RESULTS if any(r["result"] == k for r in mine)))
        for q in sorted({r["phrase"] for r in mine if r.get("phrase")}):  # ファイルにつないだ行は、写した語句でどの項目かを見る
            print(f"     「{q}」: " + "・".join(f"{k} {n}" for k in RESULTS if (n := sum(r["result"] == k for r in mine if r.get("phrase") == q))))
    for pid, kind, ts, _ in versions(ws).get(rid, []):
        p = ps[pid]
        took = "・".join(f"{c} {v}" for c, v in p.get("changes", {}).items()) or ",".join(p["src"]) or "-"
        refs = f"、移行より前に手で直した提案: {','.join(p['refs'])}（当てた文は pending --status all）" if p.get("refs") else ""
        print(f"   版 {pid} {ts[:10]} {kind or p['why']}（{p['status']}、指摘: {took}{refs}）")
    return cs


def tally(ws):
    """決まりごとの数。再発と「直した」が続くなら、文の決まりでは止まっていない。「残した（誤り）」が多いなら、決まりの書き方が外れている。"""
    cs, _, _, rv = state(ws)
    rows = {}
    row = lambda k: rows.setdefault(k, {"指摘": [], "再発": [], "decks": set(), "決めた": False, **{x: [] for x in RESULTS}})
    for c in cs.values():
        if c["to"] not in NO_RULE:  # state が戻し先を数える単位（key）にしてある
            x = row(c["to"])
            x["指摘"].append(c)
            if c.get("recur"):
                x["再発"].append(c)
            x["決めた"] |= bool(c.get("decided"))
            x["decks"].add(c["deck"])
    for r in rv:
        if r["rule"] in NO_RULE:  # 消した決まりの前の ID を 戻さない にした行
            continue
        x = row(r["rule"])
        x[r["result"]].append(r)
        x["decks"].add(r["deck"])
    signals = ("再発", *RESULTS)
    return {k: {**x, "顧客": len(customers(x["decks"])), "資料ごと": {f: len({r["deck"] for r in x[f]} - {""}) for f in signals}} for k, x in rows.items()}


def summary(ws):
    rows = tally(ws)
    out = sorted(rows.items(), key=lambda kv: (-len(kv[1]["再発"]) - len(kv[1]["直した"]), -len(kv[1]["残した（誤り）"]), kv[0]))
    print("再発とレビューの結果は「件数（出た資料の数）」。資料・顧客は、指摘かレビューの出た資料の数")
    print("決まり\t指摘\t再発\t資料\t顧客\t" + "\t".join(RESULTS) + "\tユーザーが決めた")
    for k, x in out:
        print("\t".join(map(str, [k, len(x["指摘"]), count(x["再発"]), len(x["decks"] - {""}), x["顧客"],
                                   *(count(x[r]) for r in RESULTS), "あり" if x["決めた"] else ""])))
    weekly(ws)
    cs, _, qs, _ = state(ws)
    misses = [c for c in cs.values() if c.get("plan")]
    by_mode = lambda xs: "・".join(f"{m} {count([c for c in xs if c['plan'] == m])}" for m in ("AI", "人"))
    print("\n構成の見逃し: " + by_mode(misses))
    done = [q for q in qs.values() if q["rule"] == PLAN_RULE and q.get("answered")]
    if done:  # 頼み方を見直すかに答えたあとは、そのあとに言われた見逃しで決める
        q = max(done, key=lambda q: q["answered"])
        print(f"  {q['id']} の答え（{q['answered']}）のあと: " + by_mode([c for c in misses if when(c) > q["answered"]]))
    return {k: {**x, "指摘": len(x["指摘"]), **{f: len(x[f]) for f in ("再発", *RESULTS)}} for k, x in rows.items()}


def weekly(ws, weeks=8):
    """週ごとに、誰が指摘を書いたか。desk-dreaming が拾った分が取りこぼし（作る会話が台帳に書かなかった）。コンパクションの前に拾う hook を入れるかの材料。
    構成の見逃しは、方針のレビュー（AI・人）ごとの件数。構成案のレビューの頼み方を変えたあとに減ったかを見る。"""
    n = {}
    for c in state(ws)[0].values():
        y, w, _ = datetime.fromisoformat(when(c)[:10]).isocalendar()
        x = n.setdefault(f"{y}-W{w:02d}", Counter())
        x[by(c)] += 1
        if c.get("plan"):
            x["plan:" + c["plan"]] += 1
    if n:
        print("\n週\t作る会話\tdreaming（取りこぼし）\t取り込み\t取りこぼしの割合\t構成の見逃し（AI・人）")
    for k in sorted(n)[-weeks:]:
        x = n[k]
        print(f"{k}\t{x['session']}\t{x['dreaming']}\t{x['import']}\t{x['dreaming'] / max(1, x['session'] + x['dreaming']):.0%}\t{x['plan:AI']}・{x['plan:人']}")
    return n


def texts(roots, skip=()):
    files = [f for r in roots if r.exists() for f in ([r] if r.is_file() else r.rglob("*"))
             if f.suffix in (".md", ".py") and f.is_file() and f.resolve() not in skip]
    return [f.read_text(encoding="utf-8", errors="ignore") for f in files]


def candidates(ws, plugin=PLUGIN):
    """決まりごとの次の一手。境目はここで決め、desk-dreaming は趣旨（その人の好みか、顧客の事情か）と提案の文だけを考える。
    ワークスペースの決まりはファイルごとに数える。「上げる」（2 社以上）はファイルでは出さない（一般的な決まりのファイルには、どの顧客の指摘もつながる）。
    desk-dreaming が作り直すときに、指摘ごとの顧客の数を見て決める（run.md の 4i）。"""
    _, ps, _, _ = state(ws)
    plug = "\n".join(texts([plugin], {Path(__file__).resolve()}))
    mine = {f: read(ws, f) for f in rule_files(ws) if f.endswith(".md")}  # ワークスペースの決まりと顧客の memory
    sent = [p for p in ps.values() if p["status"] == "Issue にした"]
    promoted = [(t, p) for p in sent for t in {*p.get("prev", {}).values(), *p.get("replaces", [])} if t in mine]  # Issue の直しが届いたら写しを消すワークスペースのファイル（出典の指摘の前の戻し先と --replaces）と、その提案
    out = []
    for k, x in tally(ws).items():
        if not (k.startswith("lint:") or k in mine or f"[{k}]" in plug or re.search(r"\.\w+$", k) and (plugin / k).is_file()):
            continue  # 消した・移した決まりとファイル（写しを消したあとも、レビューの結果はもとの ID に残る）
        d, layer = x["資料ごと"], "ワークスペース" if k in mine else "lint" if k.startswith("lint:") else "プラグイン"
        if max(d["再発"], d["直した"]) >= TWICE:
            out.append(("下ろす", k, f"{layer}。再発 {d['再発']} 本・直した {d['直した']} 本の資料（文の決まりでは止まっていない。点検か作る手順に）"))
        if d["残した（誤り）"] >= TWICE:
            out.append(("書き直す", k, f"{layer}。残した（誤り）{d['残した（誤り）']} 本の資料（拾う範囲が外れている。消す・緩めるは判断待ち）"))
        if d["聞く"] >= TWICE:
            out.append(("条件を足す", k, f"{layer}。聞く {d['聞く']} 本の資料（決まりからは決めきれない）"))
    gone = {}  # Issue の直しが入っているプラグインに届き、ワークスペースに写しが残っているファイル → その提案
    for t, p in promoted:
        if landed(p, plugin) and copied(p, mine[t]):
            gone.setdefault(t, []).append(p)
    for w, p in sorted((w, p) for w, xs in gone.items() for p in xs):
        out.append(("写しを消す", w, f"{p['rule']} がプラグインに入った（{p['id']}、{p.get('pr', '')}）。届いた文と同じ項目を消す"))
    for w, text in mine.items():
        for base in (b for clause in OVERRIDE.findall(text) for b in PLUGIN_ID.findall(clause) if b not in {p["rule"] for p in gone.get(w, [])}):
            if f"[{base}]" in plug:
                out.append(("上書きを見直す", base, f"{w} が上書きしている（プラグインの決まりが合っていない合図。その人の好みなら、そのまま）"))
            else:
                out.append(("古い上書き", w, f"上書きしている {base} がプラグインにない（入れ直して消えたか、ID が変わった）"))
    last = {p["rule"] or p["file"]: p for p in sorted(ps.values(), key=lambda p: p["id"]) if p["type"] not in VERSIONS}  # 決まりかファイルごとに、いちばん新しい提案（台帳が書く版は除く）
    print("次の一手\t決まり\t根拠\t前の提案")
    for act, k, why in out:
        p = last.get(k) or next((p for t, p in promoted if t == k), None)
        before = f"{p['id']} {p['status']}{'（' + p['reason'] + '）' if p.get('reason') else ''}" if p else "-"
        print(f"{act}\t{k}\t{why}\t{before}")
    return out


def landed(p, plugin):
    """プラグインへの提案の文（Issue で ID を替えたなら、替えた ID にした文）が、入っているプラグインの行き先のファイルにあるか。
    ID だけでは見ない（今ある決まりを書き直す提案は、ID が前からある）。Issue で文を変えたら届いたとは分からないので、写しを消す案を出さない（重なりは desk-dreaming/run.md の 4e で見る）。"""
    tag = f"[{p['proposed']}]"
    want = [x.replace(tag, f"[{p['rule']}]").strip() for x in p["new"].splitlines() if p["proposed"] and tag in x]
    f = plugin / p["file"]
    return bool(want) and f.is_file() and all(x in f.read_text(encoding="utf-8") for x in want)


def plain(t):
    """項目の文の比べ方。行の頭の箇条書きの印と [ID] を外し、flat にする（ワークスペースの写しには ID がない）。"""
    return flat(re.sub(rf"(?m)^\s*(?:[-*+]|\d+[.)])\s+|\[{ANY_ID}\]", "", t))


def copied(p, text):
    """上げた提案の文（[ID] を除いた項目）が、ワークスペースのファイルの文にまだあるか。文を変えて上げたものは見つけられない（4e の重なりで見る）。"""
    tag = f"[{p['proposed']}]"
    want = [plain(x) for x in p["new"].splitlines() if p["proposed"] and tag in x]
    return bool(want) and any(w and w in plain(text) for w in want)


def next_id(ws, prefix):
    found = texts([PLUGIN], {Path(__file__).resolve(), (PLUGIN / "desk-migrate" / "scripts" / "migrate.py").resolve()})  # selftest の試しの ID は数えない
    num = re.compile(rf"{re.escape(prefix)}-(\d{{3}})")
    ids = [m.group(1) for t in found for m in RULE_ID.finditer(t)]
    ids += [r.get("rule", "") for r in records(ws) if r["kind"] in ("proposal", "sent")]  # 提案だけで、まだ当てていない ID と、Issue で替えた ID も使ったものにする
    used = [int(m.group(1)) for x in ids if (m := num.fullmatch(x))]
    return f"{prefix}-{max(used, default=0) + 1:03d}"


def known(prefix):
    """新しい ID を出してよい接頭辞か（TOPICS の主題）。打ち間違いと主題の増えすぎを止める。"""
    return prefix in TOPICS


def where(rid):
    """プラグインで [rid] が書いてあるファイルと行（skills/ から）。"""
    out = []
    for f in sorted(PLUGIN.rglob("*")):
        if f.suffix in (".md", ".py") and f.is_file() and f.resolve() != Path(__file__).resolve():
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if f"[{rid}]" in line:
                    out.append(f"{f.relative_to(PLUGIN)}:{n}")
    return out


def target(ws, f):
    p = (ws / f).resolve()
    if not p.is_relative_to(ws) or p.is_relative_to(PLUGIN):
        sys.exit(f"変更先はワークスペースの中のファイルだけ（プラグインは desk-kaizen で Issue にする）: {f}")
    return p


def propose(ws, a):
    a.replaces and not a.plugin and sys.exit("--replaces はプラグインへの提案（--plugin）だけ")
    a.rule and not a.plugin and sys.exit("--rule はプラグインへの提案（--plugin）だけ（ワークスペースの決まりに ID は付けない。数える単位はファイル）")
    (a.new is None) != (a.rewrite is None) or sys.exit("--new か --rewrite のどちらか 1 つ")
    full = a.rewrite is not None
    if a.plugin:  # 当てないので、skills/ の中を指していることだけ見る
        full and sys.exit("--rewrite はワークスペースのファイルだけ")
        (PLUGIN / a.file).resolve().is_relative_to(PLUGIN) or sys.exit(f"--plugin の --file は skills/ からのパス（slides-build/visual.md など）: {a.file}")
        file = a.file
    else:
        file = target(ws, a.file).relative_to(ws).as_posix()
    if full:  # ファイルの全体を作り直す（desk-dreaming）。今の全文から、渡したファイルの全文へ
        a.old and sys.exit("--rewrite に --old は付けない（今の全文を前の文にする）")
        a.auto and sys.exit("--rewrite は --auto にしない（作り直しは人が見る）")
        Path(a.rewrite).is_file() or sys.exit(f"--rewrite のファイルがない: {a.rewrite}（作り直した全文を先に書く）")
        a.old, a.new = read(ws, file), Path(a.rewrite).read_text(encoding="utf-8")
    a.rec_why and not a.rec and sys.exit("--rec-why は --rec と一緒に付ける")
    auto = a.auto and auto_ok(ws, a)
    rec = write(ws, {"kind": "proposal", "file": file, "old": a.old or "", "new": a.new, "rule": a.rule or "", "why": a.why,
                     "src": [x for x in (a.src or "").split(",") if x], "type": a.kind or "", **({"plugin": True} if a.plugin else {}),
                     **({"full": True} if full else {}), **({"changes": a.changes} if a.changes else {}),
                     **({"replaces": a.replaces} if a.replaces else {}), **({"rec": a.rec, "rec_why": a.rec_why or ""} if a.rec else {}),
                     **({"auto": True} if a.auto else {})}, ("proposal", "P", 4))
    if not auto:
        print(rec["id"])
        return
    f, text, out = auto
    try:
        print(rec["id"])
        apply(ws, [rec["id"]])
    except BaseException:  # 確かめたあとでファイルが変わった・書けなかった。人の見ていない提案を、未適用のまま残さない
        try:
            if f.exists() and f.read_text(encoding="utf-8") == out:  # ファイルに書いたあとで止まったなら、消した行を戻す
                f.write_text(text, encoding="utf-8")
        finally:
            write(ws, {"kind": "withdrawn", "ref": rec["id"], "reason": "--auto で当てられなかった"})
        raise


ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s")  # 箇条書きの項目の頭の行


def auto_ok(ws, a):
    """--auto で当ててよいか。会話の指摘を出典にせず、AGENTS.md・rules/ の .md で、箇条書きの項目を丸ごと（字下げした続きの行も）消すだけで
    （見出し・前置き・空行・ほかの項目の一部は 1 行も消さない）、消す項目の文がプラグインか AGENTS.md にもあるもの（ほかの rules/ のファイルは出る場面が違うので数えない）。
    ユーザーが決めた指摘・答えた判断待ち・「手で直した」版・まだ版にしていない直しのあるファイルは止める（ID がないので、どの項目かを見分けられない）。
    ユーザーが戻した・却下した提案が消そうとした項目も止める。人を通さずに新しい文が決まりに入らないようにする（desk-dreaming-001）。
    --new には前か後ろの行を残す（undo の目印。空の --new は戻せない）。よければ (ファイル, 前の文, 当てたあとの文) を返す。"""
    def no(why):
        sys.exit(f"--auto にできない（{why}）。--auto を外して提案にする")
    a.kind in AUTO or no(f"種類が {'・'.join(AUTO)} でない")
    a.src and no("出典が会話の指摘")
    a.plugin and no("プラグインへの提案")
    a.old or no("--old がない。足す提案は人が見る")
    a.new.strip() or no("--new が空。戻せるように、前か後ろの行を --old と --new の両方に入れる")
    "ユーザーが決めた" in a.old and no("ユーザーが決めたと書いた文")
    f = target(ws, a.file)
    name = f.relative_to(ws).as_posix()
    name == "AGENTS.md" or f.is_relative_to(ws / "rules") and f.suffix == ".md" or no("変更先が AGENTS.md・rules/ の .md でない")
    text = read(ws, name)
    text.count(a.old) == 1 or no(f"今の文が {a.file} に 1 か所でない")
    out = text.replace(a.old, a.new)
    out != text or no("消す行がない")
    out.count(a.new) == 1 or no(f"--new が当てたあとの {a.file} に 1 か所でない（undo の目印にならない）")
    src, dst = text.split("\n"), out.split("\n")
    left, rows = iter(text.splitlines()), iter(src)  # \n のほかの改行の字で行をつながせない
    all(x in left for x in out.splitlines()) and all(x in rows for x in dst) or no("行を消すだけでない（書き換える・行の途中で切る・行がつながる）。書き換える提案は人が見る")
    kept, i = set(), 0
    for j, x in enumerate(src):  # 残る行（前から順に当てる）
        if i < len(dst) and dst[i] == x:
            kept.add(j)
            i += 1
    gone = set(range(len(src))) - kept
    depth = lambda x: len(x) - len(x.lstrip())
    spans = {}  # 項目の頭の行 → その項目の行（字下げした続きの行と、中の箇条書き）
    for h, x in enumerate(src):
        if ITEM.match(x):
            k = h + 1
            while k < len(src) and src[k].strip() and depth(src[k]) > depth(x):
                k += 1
            spans[h] = set(range(h, k))
    heads = [h for h in spans if h in gone and not any(p != h and h in s and p not in gone for p, s in spans.items())]  # 消す項目（中の項目だけを消すのは、上の項目の書き換え）
    whole = set().union(*(spans[h] for h in heads)) if heads else set()
    gone and whole == gone or no("箇条書きの項目を丸ごと消すだけでない（見出し・前置き・空行・項目の一部だけを消す）。下の決まりの効く範囲や項目の中身が変わるので人が見る")
    items = [plain("\n".join(src[k] for k in sorted(spans[h]))) for h in heads]
    elsewhere = plain("\n".join(texts([PLUGIN], {Path(__file__).resolve()}))) + "\n" + ("" if name == "AGENTS.md" else plain(read(ws, "AGENTS.md")))
    lone = [x for x in items if not x or x not in elsewhere]
    lone and no("消す項目の文が、プラグインにも AGENTS.md にもない（ほかの rules/ のファイルに残るだけでは、出る場面が変わる）")
    cs, ps, qs, _ = state(ws)
    any(c.get("decided") and c["to"] == name for c in cs.values()) and no(f"ユーザーが決めた指摘が {name} につながっている")
    any(q["status"] == "回答済み" and q["rule"] == name for q in qs.values()) and no(f"答えた判断待ちが {name} のこと")
    any(kind == "手で直した" for _, kind, _, _ in versions(ws).get(name, [])) and no(f"{name} には手で直した版がある")
    name in drift(ws, quiet=True) and no(f"{name} に、まだ版にしていない直しがある（ledger.py drift --record で版にする）")
    for q in ps.values():  # ユーザーが戻した・却下した提案が消そうとした項目は、残すと決めたものとみなす
        if q["status"] in ("戻した", "却下") and q["file"] == name and any(x in plain(q["old"]) and x not in plain(q["new"]) for x in items):
            no(f"ユーザーが戻した・却下した {q['id']} が消そうとした項目")
    return f, text, out


def diff(p):
    return "".join(difflib.unified_diff((p["old"] + "\n").splitlines(True) if p["old"] else [], (p["new"] + "\n").splitlines(True), p["file"], p["file"]))


def pending(ws, status="未適用"):
    out = [p for p in state(ws)[1].values() if status in ("all", p["status"])]
    for p in out:
        why = f"、理由: {p['reason']}" if p.get("reason") else ""
        where = f"プラグインの skills/{p['file']}" if p.get("plugin") else p["file"]
        pr = f"、{p['pr']}" if p.get("pr") else ""
        rec = (f"、推奨: {p['rec']}" + (f"（{p['rec_why']}）" if p.get("rec_why") else "")) if p.get("rec") else ""
        rec += "、出してすぐ当てた" if p.get("auto") else ""
        rec += ("、指摘ごと: " + "・".join(f"{c} {v}" for c, v in p["changes"].items())) if p.get("changes") else ""
        print(f"### {p['id']} {p['why']}（{p['status']}、{p['type'] or '-'}、{where}{'、' + p['rule'] if p['rule'] else ''}、出典 {','.join(p['src']) or '-'}{why}{pr}{rec}）\n{diff(p)}")
    return out


def apply(ws, ids):
    """提案を当てる。先に、どの提案も手元で当てて確かめ、1 つでも止まれば、どのファイルも書かない（途中で止まって、決まりが 2 か所に残ったり、どこからも消えたりしないように）。
    同じファイルへの提案は、並べた順に、前の提案を当てた文へ当てる。当てた出来事には、そのあとのファイルの全文（after）を残す（版の並び）。
    当てる前に、まだ版にしていない直しのあるファイルは「手で直した」版にする（当てた版に混ぜない）。"""
    ps = state(ws)[1]
    ids = [i for i, p in ps.items() if p["status"] == "未適用" and not p.get("plugin")] if ids == ["all"] else ids
    drift(ws, quiet=True, record=True, only={ps[i]["file"] for i in ids if i in ps and not ps[i].get("plugin")})
    after, todo = {}, []  # ファイル → 当てたあとの文（まだ書かない）・(当てる提案, その提案を当てたあとのファイルの全文)
    for i in ids:
        p = ps.get(i) or sys.exit(f"提案がない: {i}")
        if p["status"] != "未適用":
            sys.exit(f"{i} は {p['status']}")
        if p.get("plugin"):
            print(f"{i}: プラグインへの提案なので当てない（desk-kaizen で Issue にし、ledger.py sent {i} --issue <URL> で残す）")
            continue
        f = target(ws, p["file"])
        text = after[f] if f in after else f.read_text(encoding="utf-8") if f.exists() else ""
        if p.get("full"):  # ファイルの全体を作り直す提案は、今の全文が提案のときのままのときだけ
            if text != p["old"]:
                sys.exit(f"{i}: {p['file']} が作り直しの提案のあとで変わった（どの提案もまだ当てていない）。今の全文から作り直して出し直す")
            text = p["new"]
        elif p["old"]:
            if text.count(p["old"]) != 1:
                sys.exit(f"{i}: 今の文が {p['file']} に {text.count(p['old'])} か所ある（1 か所のときだけ当てる。どの提案もまだ当てていない）。提案のあとで変わったので、合わせた文を見せて聞く")
            text = text.replace(p["old"], p["new"])
        else:
            text = text + ("" if not text or text.endswith("\n") else "\n") + p["new"] + "\n"
        after[f] = text
        todo.append((p, text))
    for f, text in after.items():
        if bad := gate(ws, f, f.read_text(encoding="utf-8") if f.exists() else "", text):
            who = ",".join(p["id"] for p, _ in todo if target(ws, p["file"]) == f)
            sys.exit(f"{who}: 当てない（" + "。".join(bad) + "。どの提案もまだ当てていない）。理由に合わせて直した提案を 1 回だけ出し直す（withdraw のあと propose）。それでも止まれば報告に書く")
    written = []  # (ファイル, 前の文か None)。書く途中で止まったら（書けない・空きがない）、書いた分を戻す
    try:
        for f, text in after.items():
            f.parent.mkdir(parents=True, exist_ok=True)
            written.append((f, f.read_text(encoding="utf-8") if f.exists() else None))
            f.write_text(text, encoding="utf-8")
    except BaseException:
        for f, prev in written:
            f.write_text(prev, encoding="utf-8") if prev is not None else f.unlink(missing_ok=True)
        raise
    for p, text in todo:
        close(ws, p, "applied", appended=not p["old"] and not p.get("full"), **({} if p.get("full") else {"after": text}))  # 全文の提案は new がそのまま版
        print(f"{p['id']}: {p['file']} に当てた")


def gate(ws, f, before, after):
    """当てたあとの文の検査。止める理由の一覧（Harness² が、直した候補のハーネスを検査し、通らなければ理由を添えて 1 回だけ出し直させるのにならう）。
    AGENTS.md と rules/ の決まりのファイルを上限より大きくしない（小さくする提案は通す）。
    rules/ の決まりのファイルは、frontmatter の description をなくさない（新しいファイルにも書く。ないと hook が出さない。前の版の frontmatter のないファイルを直すときは見ない）。
    ワークスペースのファイルに [ID] を新しく書き入れない（ID はプラグインの決まりだけ。プラグインの決まりを指すときは角括弧なし）。"""
    bad, n = [], len(after.encode())
    if f == ws / "AGENTS.md" and n > AGENTS_MAX and n > len(before.encode()):
        bad.append(f"AGENTS.md が {n:,} バイトになる（{AGENTS_MAX:,} まで。作るときだけ要るものは rules/ の決まりのファイルへ）")
    rel = f.relative_to(ws)
    if rel.parts[0] == "rules" and f.suffix == ".md" and rel != Path("rules/README.md") and "templates" not in rel.parts[1:-1]:
        if after.strip() and not desk.described(desk.front(after)) and (desk.described(desk.front(before)) or not before.strip()):
            bad.append(f"{rel} の頭に frontmatter の description がない（ないと hook が出さない。deck-practices/rules.md の「Workspace rules」）")
        if len(after) > desk.RULE_MAX and len(after) > len(before):
            bad.append(f"{rel} が {len(after):,} 字になる（{desk.RULE_MAX:,} 字まで。場面ごとのファイルに分ける）")
    if new := sorted(set(BRACKETED.findall(after)) - set(BRACKETED.findall(before))):
        bad.append(f"{rel} に [{new[0]}] を書く（ワークスペースの決まりに ID は付けない。" + ("[ws-…] は消す）" if new[0].startswith("ws-") else f"プラグインの決まりを指すときは角括弧なしで {new[0]} のように書く）"))
    return bad


def close(ws, p, kind, **extra):
    """提案を当てた・Issue にした出来事を書き、出典の指摘をその決まりにつなぐ。戻すときのために、前の戻し先を残す。"""
    cs = state(ws)[0]
    write(ws, {"kind": kind, "ref": p["id"], "prev": {c: cs[c]["to"] for c in p["src"] if c in cs}, **extra})
    for c in p["src"]:
        write(ws, {"kind": "route", "ref": c, "to": p["rule"] or p["file"], "via": p["id"]})


def reopen(ws, p):
    """close でつないだ出典の指摘を、前の戻し先に戻す（あとで別の決まりに移したものは、そのまま）。"""
    cs = state(ws)[0]
    for c, to in p.get("prev", {}).items():
        if cs.get(c, {}).get("to") == (p["rule"] or p["file"]):
            write(ws, {"kind": "route", "ref": c, "to": to})


def undo(ws, i):
    p = state(ws)[1].get(i) or sys.exit(f"提案がない: {i}")
    if p.get("base"):
        sys.exit(f"{i} は戻せない（台帳が初めて見たときの版で、その前の文が分からない。戻すなら snapshot.sh restore か手で）")
    if p["status"] != "適用済み" or not p["new"] and not p.get("full"):  # 全体の版は空の文でも戻せる（ファイルの中身が空と分かる）
        sys.exit(f"{i} は戻せない（{p['status']}。消す提案は、前後の行も old と new に入れて出す）")
    f = target(ws, p["file"])
    drift(ws, quiet=True, record=True, only={p["file"]})  # 戻す前の、まだ版にしていない直しを「手で直した」版にする
    text = read(ws, p["file"])
    new = p["new"] + "\n" if p.get("appended") else p["new"]
    if text.count(new) != 1 or p.get("full") and text != new:
        sys.exit(f"{i}: 当てた文が {p['file']} に {text.count(new)} か所ある{'（全体を作り直した版は、そのあとファイルが変わると戻せない）' if p.get('full') else ''}。"
                 "手で直されたので、snapshot.sh restore か手で戻す")
    back = text.replace(new, p["old"], 1)  # 前にあった文に戻すので、gate は見ない（AGENTS.md を縮めた提案や、desk-migrate が ID を外した版も戻せるように）
    f.write_text(back, encoding="utf-8")
    write(ws, {"kind": "undone", "ref": i, "after": back})
    reopen(ws, p)
    print(f"{i}: 戻した")


def drift(ws, quiet=False, record=False, only=None):
    """台帳の最後の版から変わった決まりのファイル（版のないファイルは、空から変わったものとする）。手で直したか、作る会話が戻し先を書かずに直したもの。
    見分けられないので、どちらもユーザーが直したものとして扱い、覆さない。record なら「手で直した」版にする（desk-dreaming の 2、apply と undo の前）。only は見るファイル。
    版のまだないファイル（台帳が版を残す前からあるもの）は「初めの版」にする。そのときまでの直しは見分けられない（前の drift も、当てた提案のあとの直ししか見ていなかった）。"""
    vs, out = versions(ws), []
    for f in sorted(x for x in set(rule_files(ws)) | set(vs) if rule_file(x) and (only is None or x in only)):
        last, now = vs[f][-1][3] if f in vs else "", read(ws, f)
        if now != last:
            out.append(f)
            kind = "手で直した" if f in vs else "初めの版"
            pid = revise(ws, f, last, now, kind=kind, base=f not in vs) if record else None
            if not quiet:
                what = (f"最後の版（{vs[f][-1][0]}）から変わった（手で直したか、戻し先を書かずに直した。ユーザーが直したものとして扱い、覆さない）" if f in vs
                        else "版がまだない（台帳が版を残す前からある）")
                print(f"{f}: {what}" + (f"。{kind.removesuffix('版')}版にした: {pid}" if pid else ""))
    return out


def questions(ws, everything=False):
    out = [q for q in state(ws)[2].values() if everything or q["status"] == "未回答"]
    for q in out:
        tail = ""
        if q.get("a"):
            tail = f" → 「{q['a']}」（{q['answered']}）"
        elif q.get("reason"):
            tail = f"（{q['reason']}）"
        elif q.get("rec"):
            tail = f" 推奨: {q['rec']}"
        print(f"{q['id']} [{q['status']}] {q['q']}（{q['rule'] or '-'}、出典 {','.join(q['src']) or '-'}）{tail}")
    return out


def result_of(cell):
    if cell.startswith("残した（誤り"):
        return "残した（誤り）"
    return next((k for k in ("直した", "聞く", "残した") if cell.startswith(k)), None)


def flat(s):
    return re.sub(r"\]\([^)]*\)|[\s*`「」『』（）()\[\]、。・]", "", s)  # 太字の印や句読点、リンク先の違いで外れないように


def rule_texts():
    """プラグインの決まりの ID → その決まりの文（同じ行の次の [ID] まで。行の最初の決まりは行の頭から、最後の決まりは続く字下げの行も）を flat にしたもの。
    行の頭に立つ決まり（[deck-content-001] **どの種類でも**）は、空行までの ID のない行も。箇条書きの決まりには、隣の ID のない項目をつなげない（その項の語句を近くの ID に付けたら止める）。
    [ID] は決まりを書いたところにだけ付け、ほかから指すときは角括弧を付けない（rules.md の「Rule IDs」）。"""
    out = {}
    for t in texts([PLUGIN], {Path(__file__).resolve()}):
        bodies(t, out)
    return out


def bodies(t, out, own=None):
    """1 つのファイルの文 t から、rule_texts の決まりの ID → 文を out に足す。own に list を渡すと、行ごとの持ち主の決まりの ID の集合も入れる。"""
    lines = t.splitlines()
    own = [] if own is None else own
    own[:] = [set() for _ in lines]
    for i, l in enumerate(lines):
        ms = list(RULE_ID.finditer(l))
        for j, (m, n) in enumerate(zip(ms, ms[1:] + [None])):
            body = l[m.end() if j else 0:n.start() if n else None]  # 行の頭から: 1. 話の筋: [ID] …・MID = "…"  # [ID]
            own[i].add(m.group(1))
            if not n:
                group = l.lstrip().startswith("[")
                for k, x in enumerate(lines[i + 1:], i + 1):
                    if RULE_ID.search(x):
                        if group and not x.lstrip().startswith("["):  # まとまりの中の箇条書きの決まりは飛ばす。次に行の頭に立つ決まりで終わる
                            continue
                        break
                    if not (x.startswith((" ", "\t")) or group and x.strip()):
                        break
                    body += x
                    own[k].add(m.group(1))
            out[m.group(1)] = out.get(m.group(1), "") + "\n" + flat(body)
    return out


def review(ws, deck, table):
    """deck-review の指摘の表（1 件 1 行。`p3 | 出所 | 観点 | 重さ | 何が | 案 | 結果 | 決まり`）から、決まりの列のある行を取り込む。
    資料の文は残さず、同じ行を見分けるハッシュだけにする。ラウンドをまたいで同じ行があれば、表の後ろ（あとのラウンド）の結果にする。
    決まりの列の ID・ファイルに「」で添えた語句が、その ID の決まりの文・そのファイルにないときは、その ID・ファイルだけ取り込まずに知らせる（付け違い）。
    ファイル（ワークスペースの決まりのファイルか、ID のないプラグインのファイル）は、写した語句も残す（why でどの項目かを見る）。"""
    deck, last = rel(ws, deck), {r["key"]: r["result"] for r in state(ws)[3]}
    rows, skip, wrong, bare, known = {}, 0, [], set(), rule_texts()
    def text_of(k):  # ID の決まりの文か、ファイルの文（ワークスペース、なければプラグイン）。見つからなければ None
        if re.fullmatch(ID, k):
            return known.get(k)
        f = next((b / key(k) for b in (ws, PLUGIN) if (b / key(k)).is_file() and (b / key(k)).resolve().is_relative_to(b.resolve())), None)
        return plain(f.read_text(encoding="utf-8", errors="ignore")) if f else None
    for line in Path(table).read_text(encoding="utf-8").splitlines():
        cells = [x.strip() for x in re.sub(r"^[-*]\s+", "", line.strip()).strip("|").split("|")]
        if len(cells) < 8 or not re.match(r"p\d|全体", cells[0]):
            continue
        res = result_of(cells[-2])
        if not res:
            skip += 1
            continue
        cited, bad = CITE.findall(cells[-1]), set()  # 同じ ID に語句を 2 つ添えたら、どちらも確かめる
        for k, q in cited:
            t = text_of(k) or ""
            if not (flat(q) and flat(q) in t):  # 空や記号だけの語句も、写していないものとして知らせる
                bad.add(k)
                wrong.append(f"{cells[0]} {k}「{q}」は、{'その決まりの文にない' if t else 'その ID の決まり・そのファイルが見つからない'}")
        for w in re.findall(rf"(?<![\w-])ws-[a-z][\w-]*?-\d{{3}}", cells[-1]):  # 前の版のワークスペースの ID
            wrong.append(f"{cells[0]} {w} は、ワークスペースの決まりの ID（今は ID を付けない。そのファイルと語句にする）")
        keys = []
        for k in (x.strip(" []") for x in re.split(r"[,、]", CITE.sub(r"\1", cells[-1]))):
            if not KEY.fullmatch(k) or k in bad:
                continue
            if not k.startswith("lint:") and text_of(k) is None:
                wrong.append(f"{cells[0]} {k} は、その ID の決まり・そのファイルが見つからない")
                continue
            keys.append(key(k))
        phrases = {key(c): q for c, q in cited if c not in bad}
        if not keys:
            skip += 1
            continue
        for k in keys:
            hk = hashlib.sha1(f"{deck}|{cells[0]}|{cells[4]}|{k}".encode()).hexdigest()[:12]
            if k.startswith("lint:") or k in phrases:  # ラウンドをまたぐ同じ行は、あとのラウンドの書き方で数える
                bare.discard(hk)
            else:
                bare.add(hk)
            rows.pop(hk, None)  # あとの行を後ろに置き直す
            q = "" if re.fullmatch(ID, k) else phrases.get(k, "")
            rows[hk] = {"kind": "review", "deck": deck, "rule": k, "page": cells[0], "from": cells[1], "result": res, "key": hk, **({"phrase": q} if q else {})}
    new = [r for hk, r in rows.items() if last.get(hk) != r["result"]]
    fp = fingerprint(ws)
    if not any(r["kind"] == "harness" and (r["deck"], r["fp"]) == (deck, fp) for r in records(ws)):  # 決まりの列のある行がなくても、この資料をこのハーネスで作ったと残す（effects の分母）
        write(ws, {"kind": "harness", "deck": deck, "fp": fp})
    for r in new:
        write(ws, {**r, "fp": fp})
    print(f"取り込んだ {len(new)} 件（決まりか結果のない行 {skip}、取り込み済み {len(rows) - len(new)}）")
    for w in wrong:
        print(f"取り込まなかった: {w}（付け違い。当たる決まりを引き直すか、- にする）")
    if bare:
        print(f"決まりの文の語句のない ID・ファイルが {len(bare)} 件（決まりの列は <ID かファイル>「<決まりの文から写した語句>」。deck-review の指摘の表）")
    return len(new)


def sha8(text):
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def fingerprint(ws, plugin=PLUGIN):
    """いまのハーネスの指紋（<プラグインの 8 字>-<ワークスペースの 8 字>）。プラグインは HARNESS のフォルダ、ワークスペースは AGENTS.md と rules/ の中身から。
    初めて見る指紋なら、プラグインの決まりの ID ごとに書いてあるファイルと文のハッシュを、ワークスペースの決まりのファイルごとに全文のハッシュを、
    .desk/harness/<指紋>.json に控える（effects が、どの資料をどの文・どの版で作ったかを見る。v は控えの形。2 からファイルごと）。
    ponytail: 控えは指紋が変わるたびに 1 つ増える（数十 KB）。重くなったら、どの資料からも指されない控えを消す"""
    root = plugin.parent
    def files(roots):  # __pycache__ と点で始まるもの（.DS_Store）は、動かすだけで変わるので入れない
        return sorted(f for r in roots if r.exists() for f in ([r] if r.is_file() else r.rglob("*"))
                      if f.is_file() and not any(x.startswith((".", "__pycache__")) for x in f.relative_to(r.parent).parts))
    def digest(fs, base):
        h = hashlib.sha1()
        for f in fs:
            h.update(f"{f.relative_to(base)}\0".encode() + f.read_bytes() + b"\0")
        return h.hexdigest()[:8]
    mine, theirs = files([root / d for d in HARNESS]), files([ws / "AGENTS.md", ws / "rules"])
    fp = f"{digest(mine, root)}-{digest(theirs, ws)}"
    snap = ws / ".desk" / "harness" / f"{fp}.json"
    if not snap.exists():
        skip = {Path(__file__).resolve(), (plugin / "desk-migrate" / "scripts" / "migrate.py").resolve()}  # selftest の試しの ID
        rules = {}
        for f in mine:
            if f.suffix in (".md", ".py") and f.resolve() not in skip:
                for rid, body in bodies(f.read_text(encoding="utf-8", errors="ignore"), {}).items():
                    rules[rid] = [str(f.relative_to(root)), sha8(body.replace(rid, ""))]  # 自分の ID は入れない（ID だけ変えても、同じ文のまま）
        for f in theirs:
            if rule_file(r := f.relative_to(ws).as_posix()):
                rules[r] = [r, sha8(f.read_text(encoding="utf-8", errors="ignore"))]
        snap.parent.mkdir(parents=True, exist_ok=True)
        part = snap.with_name(f"{snap.name}.{os.getpid()}.part")  # 書き終えてから置き換える（途中で止まっても、壊れた控えを残さない。同時に書く会話とも混ざらない）
        part.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "v": 2, "rules": rules}, ensure_ascii=False), encoding="utf-8")
        os.replace(part, snap)
    return fp


def effects(ws, plugin=PLUGIN):
    """文を変えた決まりごとに、変わる前と後に作った資料の数と、指摘（指摘と、レビューの「直した」）と、誤りか聞く（レビューの「残した（誤り）」「聞く」）の出た資料の数。
    当てた・入ったことは、効いた証拠ではない（Harness² の振り返り: 採用されたのは成果物がよく見えたからで、どの直しが効いたかではない）。
    資料は、台帳に初めて出たとき（指摘・レビュー）の指紋で作ったとみなし、そのときの記録に指紋がなければ数えない。前と後は、いまの文のハッシュがその指紋の控えにあるか。
    その決まりを作るきっかけの資料（再発でない指摘のある資料）は前に数える。同じファイルのほかの決まりも同じときに変わっていれば、混ざっている（どちらが効いたか分けられない）。
    ワークスペースの決まりはファイルごとに、全文のハッシュ（版）で前と後を分ける。きっかけの資料は、いまの版が取り込んだ指摘（版の src）の資料。
    ファイルごとの控え（v 2）のない指紋で作った資料は、ファイルの比べに入れない（ID ごとの控えしかなく、どの版で作ったか分からない）。指紋のない前の記録は数えない。"""
    cs, ps, _, rv = state(ws)
    vs = versions(ws)
    form = {}  # 指紋 → 控えの形（v。2 からファイルごとの控えがある）
    def load(fp):  # 読めない控えは、ないものとする（その指紋で作った資料は数えない）
        try:
            doc = json.loads((ws / ".desk" / "harness" / f"{fp}.json").read_text(encoding="utf-8"))
            form[fp] = doc.get("v", 1)
            return doc["rules"]
        except (OSError, ValueError, KeyError):
            return None
    first = {}  # 資料 → (台帳に初めて出た時刻, そのときの指紋か None)
    for r in records(ws):
        if r.get("deck") and r["kind"] in ("correction", "review", "harness"):
            t = when(r) if r["kind"] == "correction" else r["ts"]  # あとで拾った指摘は、言われた時刻
            if r["deck"] not in first or t < first[r["deck"]][0]:
                first[r["deck"]] = (t, r.get("fp"))
    snaps = {fp: s for fp in {fp for _, fp in first.values() if fp} if (s := load(fp)) is not None}
    first = {d: x for d, x in first.items() if x[1] in snaps}  # 初めの記録に指紋がない資料（あとで拾った指摘・前の記録）は、どの版で作ったか分からないので数えない
    now = load(fingerprint(ws, plugin)) or {}
    last = {p["rule"] or p["file"]: p for p in sorted(ps.values(), key=lambda p: p["id"]) if p["type"] not in VERSIONS}
    rate = lambda xs, side: len(xs & side) / len(side) if side else 0
    out = []
    for rid, (file, h) in sorted(now.items()):
        whole = not re.fullmatch(ID, rid)  # ワークスペースの決まりのファイル
        pool = {d: x for d, x in first.items() if not whole or form[x[1]] >= 2}
        if all(snaps[fp].get(rid, [None, None])[1] == h for _, fp in pool.values()):
            continue  # 数える資料はみないまの文で作った（文が変わっていない。きっかけの指摘があっても「前」を作らない）
        if whole:
            src = {c for pid, _, _, text in vs.get(rid, []) if sha8(text) == h for c in ps[pid]["src"]}
            taught = {c["deck"] for i, c in cs.items() if i in src} & set(pool)
        else:
            taught = {c["deck"] for c in cs.values() if c["to"] == rid and not c.get("recur")} & set(pool)
        after = {d for d, (_, fp) in pool.items() if snaps[fp].get(rid, [None, None])[1] == h} - taught
        before = set(pool) - after
        sig = {c["deck"] for c in cs.values() if c["to"] == rid and (whole or c.get("recur") or c["deck"] not in after)}  # ファイルは再発を数えないので、後の資料の指摘も合図
        sig |= {r["deck"] for r in rv if r["rule"] == rid and r["result"] == "直した"}
        mis = {r["deck"] for r in rv if r["rule"] == rid and r["result"] in ("残した（誤り）", "聞く")}
        if len(after) < TWICE:
            verdict = "まだ分からない"
        elif not (sig | mis) & (before | after):
            verdict = "指摘なし（前も後も出ていないので、効いたかは分からない）"  # 守られているだけのこともある（rules.md の "Verifying rules"）。下ろす案にしない
        elif rate(mis, after) > rate(mis, before):
            verdict = "害が出た（誤りか聞くが増えた）"
        elif rate(sig, after) > rate(sig, before) and len(sig & after) >= TWICE:  # 指摘の出た資料の割合が増えた（後の 1 本だけなら揺れのうち）
            verdict = "害が出た（指摘が増えた）"
        elif rate(sig, after) < rate(sig, before):
            verdict = "効いた"
        else:
            verdict = "変わらない"
        old = [pool[d] for d in before if snaps[pool[d][1]].get(rid, [None, None])[1] != h]  # いまの文でない版で作った資料（きっかけの資料は、もういまの文のことがある）
        if after and old and not whole:  # 変わり目の前後の控えで、同じファイルのほかの決まりが変わったか（ファイルごとの比べは、ファイルがまるごと 1 つ）
            b = snaps[max(old, key=lambda x: x[0])[1]]
            a = snaps[min((pool[d] for d in after), key=lambda x: x[0])[1]]
            also = sorted(k for k in set(a) | set(b) if k != rid and file in (a.get(k, [""])[0], b.get(k, [""])[0]) and a.get(k) != b.get(k))
            if also:
                verdict += f"・混ざっている（同じファイルの {', '.join(also[:3])}{' ほか' if len(also) > 3 else ''} も同じときに変わった）"
        out.append((rid, file, (len(before), len(sig & before), len(mis & before)), (len(after), len(sig & after), len(mis & after)), verdict))
    print("前・後は「資料・指摘の出た資料・誤りか聞くの出た資料」。資料は台帳に初めて出たときのハーネスで分ける（1 本ずつの比べなので、1 本の差は揺れのうち）")
    print("決まり\tファイル\t前\t後\t見立て\t前の提案")
    for rid, file, b, a, verdict in out:
        p = last.get(rid)
        print(f"{rid}\t{file}\t{'・'.join(map(str, b))}\t{'・'.join(map(str, a))}\t{verdict}\t{p['id'] + ' ' + p['status'] if p else '-'}")
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--deck", required=True); s.add_argument("--quote", required=True); s.add_argument("--fix")
    s.add_argument("--to", default="未", type=to_arg); s.add_argument("--check", default="なし"); s.add_argument("--session"); s.add_argument("--at"); s.add_argument("--decided", action="store_true"); s.add_argument("--plan", choices=("AI", "人")); s.add_argument("--once", action="store_true")
    s = sub.add_parser("route"); s.add_argument("id"); s.add_argument("to", type=to_arg)
    s = sub.add_parser("plan"); s.add_argument("id"); s.add_argument("mode", choices=("AI", "人", "なし"))
    s = sub.add_parser("list"); s.add_argument("--deck"); s.add_argument("--open", action="store_true"); s.add_argument("--to"); s.add_argument("--odd", action="store_true"); s.add_argument("--since", type=utc)
    s = sub.add_parser("why"); s.add_argument("id")
    sub.add_parser("rules")
    sub.add_parser("candidates")
    sub.add_parser("effects")
    s = sub.add_parser("next"); s.add_argument("prefix")
    s = sub.add_parser("where"); s.add_argument("id")
    sub.add_parser("topics")
    s = sub.add_parser("propose")
    s.add_argument("--file", required=True); s.add_argument("--new"); s.add_argument("--old"); s.add_argument("--rewrite"); s.add_argument("--rule", type=rule_arg)
    s.add_argument("--why", required=True); s.add_argument("--src"); s.add_argument("--changes", type=changes_arg); s.add_argument("--kind"); s.add_argument("--plugin", action="store_true"); s.add_argument("--replaces", type=ws_rules_arg)
    s.add_argument("--rec", choices=RECS); s.add_argument("--rec-why"); s.add_argument("--auto", action="store_true")
    s = sub.add_parser("pending"); s.add_argument("--status", default="未適用")
    s = sub.add_parser("apply"); s.add_argument("ids", nargs="+")
    s = sub.add_parser("reject"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("withdraw"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("undo"); s.add_argument("id")
    s = sub.add_parser("drift"); s.add_argument("--record", action="store_true")
    s = sub.add_parser("sent"); s.add_argument("id"); s.add_argument("--issue", dest="pr", required=True); s.add_argument("--rule", type=rule_arg)
    s = sub.add_parser("ask"); s.add_argument("--q", required=True); s.add_argument("--rule", type=subject_arg); s.add_argument("--src"); s.add_argument("--rec")
    s = sub.add_parser("answer"); s.add_argument("id"); s.add_argument("--a", required=True)
    s = sub.add_parser("questions"); s.add_argument("--all", action="store_true")
    s = sub.add_parser("review"); s.add_argument("--deck", required=True); s.add_argument("--table", required=True)
    a = ap.parse_args(argv)
    ws = workspace()
    if a.cmd == "add":
        add(ws, a)
    elif a.cmd == "route":
        state(ws)[0].get(a.id) or sys.exit(f"指摘がない: {a.id}")
        write(ws, {"kind": "route", "ref": a.id, "to": key(a.to)})
        record(ws, a.to, [a.id])
    elif a.cmd == "plan":
        state(ws)[0].get(a.id) or sys.exit(f"指摘がない: {a.id}")
        write(ws, {"kind": "plan", "ref": a.id, "plan": a.mode})
    elif a.cmd == "list":
        deck = rel(ws, a.deck) if a.deck else None
        for c in state(ws)[0].values():
            if ((not deck or c["deck"] == deck) and (not a.open or c["to"] == "未") and (not a.to or c["to"] == key(a.to)) and (not a.odd or not linked(c["to"], ws))
                    and (not a.since or max(c["ts"], c.get("routed", "")) >= a.since)):  # 時刻は秒まで。前回の終わりと同じ秒に書いた指摘も拾う
                print(show(c))
    elif a.cmd == "why":
        why(ws, a.id)
    elif a.cmd == "rules":
        summary(ws)
    elif a.cmd == "candidates":
        candidates(ws)
    elif a.cmd == "effects":
        effects(ws)
    elif a.cmd == "next":
        a.prefix.startswith("ws-") and sys.exit("ワークスペースの決まりには ID を付けない。指摘の戻し先は、そのファイル（--to rules/<名前>.md・AGENTS.md・Customers/<顧客>/memory.md）")
        known(a.prefix) or sys.exit(f"主題の表にない接頭辞: {a.prefix}。TOPICS（ledger.py topics）から選ぶ。新しい主題が要るなら、先に TOPICS に足す（../rules.md の「Rule IDs」）")
        print(next_id(ws, a.prefix))
    elif a.cmd == "where":
        print("\n".join(where(a.id)) or f"{a.id} はプラグインのどこにもない（消した決まりなら why で経緯を見る。ワークスペースの決まりは ID でなくファイル）")
    elif a.cmd == "topics":
        print("\n".join(f"{k}\t{v}" for k, v in TOPICS.items()))
    elif a.cmd == "propose":
        propose(ws, a)
    elif a.cmd == "pending":
        pending(ws, a.status)
    elif a.cmd == "apply":
        apply(ws, a.ids)
    elif a.cmd in ("reject", "withdraw", "sent"):
        _, ps, qs, _ = state(ws)
        p = ps.get(a.id) or (qs.get(a.id) if a.cmd == "withdraw" else None) or sys.exit(f"提案がない: {a.id}")
        sent = p["status"] == "Issue にした"  # Issue が断られた・取り下げたときは閉じられる
        p["status"] in ("未適用", "未回答") or (sent and a.cmd != "sent") or sys.exit(f"{a.id} は {p['status']}")
        if a.cmd == "sent":
            p.get("plugin") or sys.exit(f"{a.id} はワークスペースへの提案。apply で当てる")
            renamed = {"rule": a.rule} if a.rule else {}  # Issue で提案と違う ID にした
            close(ws, {**p, **renamed}, "sent", pr=a.pr, **renamed)
        else:
            write(ws, {"kind": {"reject": "rejected", "withdraw": "withdrawn"}[a.cmd], "ref": a.id, "reason": a.reason})
            if sent:
                reopen(ws, p)
    elif a.cmd == "ask":
        print(write(ws, {"kind": "question", "q": a.q, "rule": a.rule or "", "src": [x for x in (a.src or "").split(",") if x], **({"rec": a.rec} if a.rec else {})}, ("question", "Q", 4))["id"])
    elif a.cmd == "answer":
        q = state(ws)[2].get(a.id) or sys.exit(f"判断待ちがない: {a.id}")
        q["status"] == "未回答" or sys.exit(f"{a.id} は {q['status']}")
        write(ws, {"kind": "answered", "ref": a.id, "a": a.a})
    elif a.cmd == "questions":
        questions(ws, a.all)
    elif a.cmd == "review":
        review(ws, a.deck, a.table)
    elif a.cmd == "undo":
        undo(ws, a.id)
    elif a.cmd == "drift":
        drift(ws, record=a.record)


def selftest_topics():
    """プラグインのどの [ID] も、TOPICS の主題を使い、1 つのファイルにだけ書く（ファイルを分けたり、新しい決まりを足したりしたときに、表から外れた ID を止める）。"""
    bad, seen = [], {}
    for f in sorted(PLUGIN.rglob("*")):
        if f.suffix in (".md", ".py") and f.is_file() and "desk-migrate" not in f.parts and "templates" not in f.parts and f.resolve() != Path(__file__).resolve():
            for m in RULE_ID.finditer(f.read_text(encoding="utf-8")):
                rid = m.group(1)
                if rid.rsplit("-", 1)[0] not in TOPICS:
                    bad.append(f"主題の表にない {f.relative_to(PLUGIN)}: {rid}")
                if rid in seen and seen[rid] != f:
                    bad.append(f"2 か所に書いた {rid}: {seen[rid].relative_to(PLUGIN)}・{f.relative_to(PLUGIN)}（角括弧の ID は書いてある場所。ほかは角括弧なしで指す）")
                seen.setdefault(rid, f)
    assert not bad, "; ".join(bad)
    assert known("slides-visual") and not known("ws-slides-visual") and not known("visual") and not known("slides-visuals")
    assert where("slides-visual-012")[0].startswith("slides-build/visual.md:") and where("ws-none-001") == []
    assert not RULE_ID.search("[ws-slides-visual-001]") and RULE_ID.search("[slides-visual-012]")  # ワークスペースの ID は決まりの ID として読まない


def fails(main_args, code=None):
    """main(main_args) が止まる（SystemExit）。code を渡せば、その終了コード。"""
    import contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main(main_args)
    except SystemExit as e:
        assert code is None or e.code == code, (main_args, e.code)
        return str(e)
    raise AssertionError(f"通した: {main_args}")


def selftest():
    import contextlib, io, os
    selftest_topics()
    quiet = lambda *a: contextlib.redirect_stdout(io.StringIO())
    fm = "---\ndescription: 試し\n---\n"  # 新しい決まりのファイルの頭（ないと gate が止める）
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d).resolve()
        (ws / "desk.toml").write_text("")
        (ws / "Customers" / "acme" / "deck_202610").mkdir(parents=True)
        (ws / "rules" / "slides-build").mkdir(parents=True)
        v = ws / "rules" / "slides-build" / "visual.md"
        V = "rules/slides-build/visual.md"
        v.write_text("`slides-build/visual.md` に足す。\n\n- 本文は 16pt。\n")  # 前の版の frontmatter のないファイル（足す提案は止めない）
        cwd = os.getcwd()
        os.chdir(ws / "Customers" / "acme" / "deck_202610")
        try:
            with quiet():
                main(["add", "--deck", ".", "--quote", "表は 2 枚に分けて", "--fix", "p4"])
                main(["add", "--deck", ".", "--quote", "このページの数字を直して", "--to", "戻さない"])
            from concurrent.futures import ThreadPoolExecutor  # 同時に足しても番号が重ならない
            with ThreadPoolExecutor(8) as ex:
                ids = list(ex.map(lambda i: write(ws, {"kind": "note"}, ("note", "n-", 2))["id"], range(16)))
            assert len(set(ids)) == 16
            cs = state(ws)[0]
            assert cs["c-0001"]["deck"] == "Customers/acme/deck_202610" and cs["c-0001"]["to"] == "未"
            assert next_id(ws, "nothing") == "nothing-001" and next_id(ws, "slides-visual") != "slides-visual-001"  # プラグインの ID も数える
            assert "ID を付けない" in fails(["next", "ws-slides-visual"]) and "--rule はプラグインへの提案" in fails(["propose", "--file", V, "--new", "x", "--rule", "slides-visual-099", "--why", "y"])
            fails(["add", "--deck", ".", "--quote", "x", "--to", "ws-slides-visual-001"], 2)  # ワークスペースの ID は戻し先にしない
            # 足す提案を当て、出典の指摘をファイルにつなぐ。当てる前に、台帳に版のないファイルは「初めの版」にする
            with quiet():
                main(["propose", "--file", "./" + V, "--new", "- 収まらない表は 2 枚に分ける。", "--why", "表の分け方", "--src", "c-0001"])
                assert len(pending(ws)) == 1 and state(ws)[1]["P0001"]["file"] == V  # 変更先はワークスペースからのパスにそろえる
                main(["apply", "all"])
            assert "収まらない表" in v.read_text() and state(ws)[0]["c-0001"]["to"] == V and "routed" not in state(ws)[0]["c-0001"]  # 当てた提案がつないだのは新しい入力でない
            assert [x[1] for x in versions(ws)[V]] == ["初めの版", ""] and versions(ws)[V][-1][3] == v.read_text()  # 版のなかったファイルは初めの版。当てた出来事に全文を残す
            with quiet():
                assert len(why(ws, "../../../" + V)) == 1 and drift(ws) == []
            # 置き換える提案。今の文が変わっていたら当てない
            with quiet():
                main(["propose", "--file", V, "--old", "本文は 16pt。", "--new", "本文は 18pt。", "--why", "大きさ"])
                main(["propose", "--file", V, "--old", "ない文", "--new", "x", "--why", "合わない"])
                main(["apply", "P0003"])
            assert "18pt" in v.read_text()
            assert "0 か所" in fails(["apply", "P0004"])
            with quiet():
                main(["reject", "P0004", "--reason", "いらない"])
                main(["propose", "--file", V, "--new", "x", "--why", "書き間違い"])
                main(["withdraw", "P0005", "--reason", "出し直す"])
                main(["undo", "P0003"])
            assert "16pt" in v.read_text() and state(ws)[1]["P0004"]["status"] == "却下" and versions(ws)[V][-1][1] == "戻した"
            with quiet():
                assert [p["id"] for p in pending(ws, "却下")] == ["P0004"] and [p["id"] for p in pending(ws, "取り下げ")] == ["P0005"]
            # 手で直したら drift に出る。--record で「手で直した」版にすると、もう出ない
            v.write_text(v.read_text().replace("2 枚に分ける", "分ける"))
            with quiet():
                assert drift(ws) == [V]
                main(["drift", "--record"])
                assert drift(ws) == [] and versions(ws)[V][-1][1] == "手で直した" and "分ける" in versions(ws)[V][-1][3]
            # その場で戻す: 作る会話がファイルを直してから戻し先を書くと、版が残る（取り込んだ指摘はその c-ID）。変えていなければ残さない
            v.write_text(v.read_text() + "- 図は左から右。\n")
            with quiet():
                main(["add", "--deck", ".", "--quote", "図は左から", "--to", V])
            c = next(c for c in state(ws)[0].values() if c["quote"] == "図は左から")
            last = versions(ws)[V][-1]
            assert last[1] == "その場で戻した" and state(ws)[1][last[0]]["src"] == [c["id"]] and "図は左から右" in last[3]
            n = len(versions(ws)[V])
            with quiet():
                main(["add", "--deck", ".", "--quote", "同じことをまた", "--to", V])
                main(["route", c["id"], V])
            assert len(versions(ws)[V]) == n
            (ws / "rules" / "gone.md").write_text("- 消す。\n")  # 中身を空にした全体の版も戻せる
            with quiet():
                main(["drift", "--record"])
            (ws / "rules" / "gone.md").write_text("")
            with quiet():
                main(["drift", "--record"])
                main(["undo", versions(ws)["rules/gone.md"][-1][0]])
            assert (ws / "rules" / "gone.md").read_text() == "- 消す。\n"
            (ws / "rules" / "gone.md").unlink()
            with quiet():
                main(["drift", "--record"])
            (ws / "rules" / "new.md").write_text(fm + "- 新しいファイル。\n")  # 作る会話が新しく作ったファイル（空からの版）
            with quiet():
                main(["route", c["id"], "rules/new.md"])
            first = versions(ws)["rules/new.md"][-1]
            assert first[3] == fm + "- 新しいファイル。\n" and first[1] == "初めの版" and state(ws)[1][first[0]]["src"] == [c["id"]]  # 前の文が分からないので、その指摘の直しとはしない
            assert "前の文が分からない" in fails(["undo", first[0]]) and (ws / "rules" / "new.md").read_text() == fm + "- 新しいファイル。\n"  # 空にして戻さない
            with contextlib.redirect_stdout(io.StringIO()) as out:
                why(ws, "rules/new.md")
            assert "版 P" in out.getvalue() and c["id"] in out.getvalue()
            with contextlib.redirect_stdout(io.StringIO()) as out:  # --since は同じ秒に書いたものも出す（前回の終わりと同じ秒の指摘を落とさない）
                main(["list", "--since", c["ts"]])
            assert "図は左から" in out.getvalue()
            with quiet():  # あとで拾った指摘（--at）は、そのときの直しが分からないので版を残さない
                v.write_text(v.read_text() + "- あとで拾った。\n")
                main(["add", "--deck", ".", "--quote", "拾った", "--to", V, "--at", "2000-01-01T00:00"])
                assert drift(ws) == [V]
                main(["drift", "--record"])
            # 戻すと、出典の指摘の戻し先も前に戻る
            with quiet():
                main(["add", "--deck", ".", "--quote", "見出しは短く"])
                cy = next(c["id"] for c in state(ws)[0].values() if c["quote"] == "見出しは短く")
                main(["propose", "--file", "rules/y.md", "--new", fm + "- 見出しは短く。", "--why", "短く", "--src", cy])
                py = list(state(ws)[1])[-1]
                main(["apply", py])
            assert state(ws)[0][cy]["to"] == "rules/y.md"
            with quiet():
                main(["undo", py])
            assert state(ws)[0][cy]["to"] == "未" and (ws / "rules" / "y.md").read_text() == ""
            # 全体の作り直し（--rewrite）。今の全文が変わっていたら当てない。指摘ごとの変化を残す
            (ws / "new_y.md").write_text(fm + "- 見出しは 1 行。\n")
            (ws / "rules" / "y.md").write_text(fm + "- 見出しは短く。\n")
            with quiet():
                main(["drift", "--record"])
                main(["propose", "--file", "rules/y.md", "--rewrite", str(ws / "new_y.md"), "--why", "作り直す", "--kind", "作り直し", "--src", cy, "--changes", f"{cy}:書き換えた"])
                pr = list(state(ws)[1])[-1]
            p = state(ws)[1][pr]
            assert p["full"] and p["old"] == fm + "- 見出しは短く。\n" and p["changes"] == {cy: "書き換えた"}
            with contextlib.redirect_stdout(io.StringIO()) as out:
                pending(ws)
            assert f"指摘ごと: {cy} 書き換えた" in out.getvalue()
            (ws / "rules" / "y.md").write_text(fm + "- 見出しは短く。\n- 足した。\n")
            assert "作り直しの提案のあとで変わった" in fails(["apply", pr])
            (ws / "rules" / "y.md").write_text(fm + "- 見出しは短く。\n")
            with quiet():
                main(["apply", pr])
            assert (ws / "rules" / "y.md").read_text() == fm + "- 見出しは 1 行。\n" and versions(ws)["rules/y.md"][-1][3] == fm + "- 見出しは 1 行。\n"
            routed = state(ws)[0][cy]["routed"]  # 戻し先が同じなら、つなぎ直しても routed は変えない（当てた提案の close が出典を同じファイルにつなぐ。list --since に出し直さない）
            write(ws, {"ts": "2999-01-01T00:00:00Z", "kind": "route", "ref": cy, "to": "rules/y.md"})
            assert state(ws)[0][cy]["routed"] == routed and state(ws)[0][cy]["to"] == "rules/y.md"
            with quiet():
                main(["undo", pr])
            assert (ws / "rules" / "y.md").read_text() == fm + "- 見出しは短く。\n"
            assert "--rewrite のファイルがない" in fails(["propose", "--file", "rules/y.md", "--rewrite", str(ws / "none.md"), "--why", "y"])
            for argv in (["propose", "--file", "rules/y.md", "--rewrite", str(ws / "new_y.md"), "--old", "x", "--why", "y"],
                         ["propose", "--file", "rules/y.md", "--why", "y"], ["propose", "--file", "rules/y.md", "--new", "x", "--rewrite", str(ws / "new_y.md"), "--why", "y"],
                         ["propose", "--file", "rules/y.md", "--new", "x", "--why", "y", "--changes", "c-1:直した"]):
                fails(argv)
            # 前の形の取り込み（--once）は足し直さない。ほかの会話のくり返しは別の 1 件にする
            with quiet():
                main(["add", "--deck", ".", "--quote", "古い行", "--once"])
                main(["add", "--deck", ".", "--quote", "古い行", "--once"])
                main(["add", "--deck", ".", "--quote", "見出しは短く", "--session", "s2", "--decided"])
            cs = state(ws)[0].values()
            assert sum(c["quote"] == "古い行" for c in cs) == 1 and sum(c["quote"] == "見出しは短く" for c in cs) == 2
            cid = lambda q: next(c["id"] for c in state(ws)[0].values() if c["quote"] == q)
            pid = lambda w: next(p["id"] for p in state(ws)[1].values() if p["why"] == w)
            # 再発: プラグインの決まりは前からある。決まりを作った指摘（Issue にした提案の出典）と、ファイルにつないだ指摘は数えない
            with quiet():
                main(["add", "--deck", ".", "--quote", "出典は 1 行に", "--to", "slides-visual-012"])
                main(["add", "--deck", ".", "--quote", "表は分けて（別の会話）", "--at", "2000-01-01T09:00+09:00"])
            assert state(ws)[0][cid("出典は 1 行に")]["recur"] is True and state(ws)[0][cid("表は分けて（別の会話）")]["at"] == "2000-01-01T00:00:00Z"  # --at は UTC にそろえる
            fails(["add", "--deck", ".", "--quote", "x", "--at", "きのう"])
            # プラグインへの提案は当てず、Issue にしたか却下で閉じる。Issue にしたら出典の指摘をつなぎ、断られたら前の戻し先に戻す
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-099] 表は分ける。", "--rule", "slides-visual-099", "--why", "上げる", "--kind", "プラグインに上げる", "--src", cid("表は分けて（別の会話）")])
                main(["propose", "--plugin", "--file", "deck-practices/content.md", "--new", "x", "--why", "上げる 2"])
                main(["propose", "--file", "rules/w.md", "--new", fm + "- 1 つ", "--why", "足す"])
                main(["apply", pid("上げる"), pid("足す")])  # 並びにプラグインへの提案があっても、残りは当てる
                main(["apply", "all"])
            ps = state(ws)[1]
            assert [ps[pid(w)]["status"] for w in ("上げる", "上げる 2", "足す")] == ["未適用", "未適用", "適用済み"]
            for argv in (["sent", pid("足す"), "--issue", "u"], ["propose", "--plugin", "--file", "../../x.md", "--new", "x", "--why", "y"]):
                fails(argv)
            with quiet():
                main(["sent", pid("上げる"), "--issue", "https://github.com/o/r/issues/1"])
                main(["reject", pid("上げる 2"), "--reason", "この人だけの好み"])
                assert [p["id"] for p in pending(ws, "Issue にした")] == [pid("上げる")]
            c = state(ws)[0][cid("表は分けて（別の会話）")]
            assert c["to"] == "slides-visual-099" and c["recur"] is False  # Issue にした決まりを作った指摘で、再発ではない
            fails(["sent", pid("上げる"), "--issue", "u"])
            with quiet():
                main(["reject", pid("上げる"), "--reason", "入れずに閉じられた"])
            assert state(ws)[1][pid("上げる")]["status"] == "却下" and state(ws)[0][cid("表は分けて（別の会話）")]["to"] == "未"
            # 決まりができた時刻は、その ID を書き入れた提案だけで決める。今ある決まりの書き直しは作らず、断られたら消す。Issue で ID を変えたら追う
            with quiet():
                main(["add", "--deck", ".", "--quote", "既存の決まりなのに", "--at", "2000-01-01T00:00"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-050] a", "--new", "- [slides-visual-050] b", "--rule", "slides-visual-050", "--why", "書き直す", "--src", cid("既存の決まりなのに")])
                main(["sent", pid("書き直す"), "--issue", "u"])
            assert state(ws)[0][cid("既存の決まりなのに")]["recur"] is True  # slides-visual-050 は前からプラグインにある
            with quiet():  # Issue にする → 断られる → その間に言われる → 出し直して Issue にする。時刻を離すため、出来事の行は ts を書いて足す
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-201] u", "--rule", "slides-visual-201", "--why", "作って断られる"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-201] u", "--rule", "slides-visual-201", "--why", "出し直す"])
                write(ws, {"ts": "2001-01-01T00:00:00Z", "kind": "sent", "ref": pid("作って断られる"), "prev": {}})
                write(ws, {"ts": "2002-01-01T00:00:00Z", "kind": "rejected", "ref": pid("作って断られる")})
                main(["add", "--deck", ".", "--quote", "断られたあとに言われた", "--at", "2003-01-01T00:00"])
                write(ws, {"ts": "2004-01-01T00:00:00Z", "kind": "sent", "ref": pid("出し直す"), "prev": {}})
                write(ws, {"ts": "2004-01-01T00:00:00Z", "kind": "route", "ref": cid("断られたあとに言われた"), "to": "slides-visual-201"})
            assert state(ws)[0][cid("断られたあとに言われた")]["recur"] is False  # 出し直した決まりの出典で、断られる前の決まりの再発ではない
            with quiet():  # 前の決まりがあった間に言われ、出し直したあとでつないだものは再発。同じ分の中でも秒で比べる
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-202] v", "--rule", "slides-visual-202", "--why", "v を作る"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-202] v", "--rule", "slides-visual-202", "--why", "v を作り直す"])
                write(ws, {"ts": "2005-01-01T09:30:20Z", "kind": "sent", "ref": pid("v を作る"), "prev": {}})
                main(["add", "--deck", ".", "--quote", "前の v のあいだに", "--at", "2005-01-02T00:00"])
                main(["add", "--deck", ".", "--quote", "同じ分のあとの秒", "--at", "2005-01-01T09:30:45.123Z"])
                main(["add", "--deck", ".", "--quote", "同じ分の前の秒", "--at", "2005-01-01T09:30:05Z"])
                write(ws, {"ts": "2005-01-03T00:00:00Z", "kind": "rejected", "ref": pid("v を作る")})
                write(ws, {"ts": "2005-01-04T00:00:00Z", "kind": "sent", "ref": pid("v を作り直す"), "prev": {}})
                for q in ("前の v のあいだに", "同じ分のあとの秒", "同じ分の前の秒"):
                    main(["route", cid(q), "slides-visual-202"])
            cs = state(ws)[0]
            assert [cs[cid(q)]["recur"] for q in ("前の v のあいだに", "同じ分のあとの秒", "同じ分の前の秒")] == [True, True, False]
            with quiet():
                main(["add", "--deck", ".", "--quote", "ID が変わる", "--at", "2000-01-01T00:00"])
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-060] x", "--rule", "slides-visual-060", "--why", "ID を変える", "--src", cid("ID が変わる")])
                main(["sent", pid("ID を変える"), "--issue", "u", "--rule", "slides-visual-061"])
            c = state(ws)[0][cid("ID が変わる")]
            assert (c["to"], c["recur"], state(ws)[1][pid("ID を変える")]["rule"]) == ("slides-visual-061", False, "slides-visual-061")
            with quiet():  # Issue で替えた ID も、次の ID の取り置きに入る
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [zz-900] x", "--rule", "zz-900", "--why", "zz"])
                main(["sent", pid("zz"), "--issue", "u", "--rule", "zz-901"])
            assert next_id(ws, "zz") == "zz-902"
            # 戻さない・ファイルにしたら、前の決まりの再発を持ち越さない。ファイルにつないだ指摘は再発に数えない（1 つのファイルに別々の決まりが入る）
            with quiet():
                main(["add", "--deck", ".", "--quote", "つなぎ違い", "--to", "slides-visual-012"])
                main(["route", cid("つなぎ違い"), "戻さない"])
                main(["route", cid("つなぎ違い"), "slides-visual-013"])
            assert state(ws)[0][cid("つなぎ違い")]["first"] == "slides-visual-013"
            with quiet():
                for q in ("敬称は様", "ロゴは右上"):
                    main(["add", "--deck", ".", "--quote", q, "--to", "Customers/acme/memory.md"])
                main(["add", "--deck", ".", "--quote", "プラグインのファイルへ", "--to", "deck-practices/content.md"])
            cs = state(ws)[0]
            assert not any(cs[cid(q)].get("recur") for q in ("敬称は様", "ロゴは右上", "プラグインのファイルへ"))
            # 前の形から移した出典（日付だけ）は、プラグインの決まりを作ったもので再発でない。そのあと言われたものは再発
            write(ws, {"kind": "correction", "id": "c-m001", "deck": "", "where": "前の本文", "note": "移した", "quote": "", "date": "2026-10-07", "to": "deck-content-002"})
            with quiet():
                main(["add", "--deck", ".", "--quote", "移したあとに", "--to", "deck-content-002"])
            cs = state(ws)[0]
            assert (cs["c-m001"]["recur"], cs[cid("移したあとに")]["recur"]) == (False, True)
            # desk-migrate が外したワークスペースの ID は、そのファイルとして読む（台帳の前の行は書き換えない）
            write(ws, {"kind": "correction", "id": "c-old1", "deck": "Customers/acme/deck_202610", "quote": "前の ID", "fix": "", "to": "ws-slides-visual-001", "check": "なし", "session": "", "decided": True, "by": "session"})
            write(ws, {"kind": "review", "deck": "Customers/acme/deck_202610", "rule": "ws-slides-visual-001", "page": "p1", "from": "画像", "result": "直した", "key": "old-k"})
            write(ws, {"kind": "question", "id": "Q0900", "q": "前の問い", "rule": "ws-slides-visual-001", "src": []})
            assert state(ws)[0]["c-old1"]["to"] == "ws-slides-visual-001"
            write(ws, {"kind": "migrated", "ids": {"ws-slides-visual-001": V}})
            cs, _, qs, rv = state(ws)
            assert cs["c-old1"]["to"] == V and next(r for r in rv if r["key"] == "old-k")["rule"] == V and qs["Q0900"]["rule"] == V and "first" not in cs["c-old1"]
            with quiet():
                assert "c-old1" in [c["id"] for c in why(ws, "ws-slides-visual-001")]  # 前の ID でも、つないだファイルとして引ける
            write(ws, {"kind": "correction", "id": "c-old2", "deck": "Customers/acme/deck_202610", "quote": "消した決まり", "fix": "", "to": "ws-deck-content-009", "check": "なし", "session": "", "decided": False, "by": "session"})
            write(ws, {"kind": "review", "deck": "Customers/acme/deck_202610", "rule": "ws-deck-content-009", "page": "p1", "from": "画像", "result": "直した", "key": "old-k2"})
            write(ws, {"kind": "correction", "id": "c-old3", "deck": "Customers/acme/deck_202610", "quote": "あとでほかへ", "fix": "", "to": "ws-deck-content-009", "check": "なし", "session": "", "decided": False, "by": "session"})
            write(ws, {"kind": "route", "ref": "c-old3", "to": V})  # 決まりをまとめて、ほかのファイルへつなぎ直した
            write(ws, {"kind": "migrated", "ids": {"ws-deck-content-009": "戻さない"}})
            with quiet():
                assert [c["id"] for c in why(ws, "ws-deck-content-009")] == ["c-old2"] and "戻さない" not in summary(ws)  # ほかの 戻さない の指摘を混ぜない
            # 崩れた ID は --rule で止め、台帳に前からあっても next は数えられる
            for argv in (["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "x", "--why", "y", "--rule", "visual-new"], ["ask", "--q", "x", "--rule", "ws visual 1"],
                         ["ask", "--q", "x", "--rule", "ws-slides-visual-001"]):
                fails(argv)
            write(ws, {"kind": "proposal", "id": "P9999", "file": "rules/x.md", "old": "", "new": "x", "rule": "visual-new", "why": "前の台帳", "src": [], "type": ""})
            assert next_id(ws, "slides-visual").startswith("slides-visual-")
            # 判断待ち: 答えたものは、もう未回答に出ない。ファイルのことも聞ける
            with quiet():
                main(["ask", "--q", "見出しは 1 行か 2 行か", "--rule", "./" + V, "--src", "c-0007"])
                main(["ask", "--q", "書き間違い"])
                q1, q2 = sorted(q for q in state(ws)[2] if q != "Q0900")[:2]
                main(["answer", q1, "--a", "1 行にする"])
                main(["withdraw", q2, "--reason", "出し直す"])
                main(["withdraw", "Q0900", "--reason", "試し"])
                assert questions(ws) == [] and [q["status"] for q in questions(ws, True)] == ["取り下げ", "回答済み", "取り下げ"] and state(ws)[2][q1]["rule"] == V
            # 推奨: 提案と判断待ちに残し、一覧に出す
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main(["propose", "--file", "rules/r.md", "--new", "x", "--why", "推奨", "--rec", "様子見", "--rec-why", "1 本の資料だけ"])
                main(["ask", "--q", "残すか", "--rec", "残す"])
                pending(ws)
                questions(ws)
            assert "推奨: 様子見（1 本の資料だけ）" in out.getvalue() and "推奨: 残す" in out.getvalue(), out.getvalue()
            # 戻し先: 決まりに結び付かない書き方は止める
            assert not any(map(linked, ("rules/a.md ws-a-003", "戻さない（この資料だけ）", "rules/a.md#ws-a-003", "ws-a-003 rules/a.md", "この資料", "rules/a.md（ws-a-003 に足す）", "rules/a.md rules/b.md", "ws-a-003:rules/a.md", "ws-a-003→rules/a.md", "ws-slides-visual-004／rules/slides-build/visual.md", "ws-a-003")))
            assert all(map(linked, ("desk.toml", "rules/a.md（見出しの下）", "Customers/Acme Corp/memory.md", "Internal/plan_202610/構成案.md", "Customers/client-001/memory.md", "slides-visual-012")))
            for bad in ("rules/a.md ws-a-003", "rules/x.md ws-x-001・rules/slides-build/checks.py", "ws-a-001・ws-a-002", "この資料"):
                fails(["add", "--deck", ".", "--quote", "x", "--to", bad], 2)
            selftest_auto(ws, quiet)
            selftest_review(ws, quiet)
            # プラグインのファイルは変更先にしない
            try:
                target(ws, str(PLUGIN / "skills" / "slides-build" / "visual.md"))
                raise AssertionError("プラグインを変更先にした")
            except SystemExit:
                pass
        finally:
            os.chdir(cwd)
    selftest_candidates(quiet)
    selftest_effects(quiet)
    print("selftest ok")


def selftest_auto(ws, quiet):
    """--auto: 会話を出典にしない片付けで、箇条書きの項目を丸ごと消すだけ・消す文がプラグインか AGENTS.md にもあるものを、出してすぐ当てる。ほかは台帳に書かずに止める。"""
    a, A = ws / "rules" / "a.md", "rules/a.md"
    (ws / "AGENTS.md").write_text("- 本文は 16pt。\n- 表は分ける。続きの行。\n", encoding="utf-8")  # 同じ文がどの会話にも出る AGENTS.md にある
    with quiet():  # 台帳の提案で作ったファイル（手で作ったファイルは「手で直した」版になり、--auto にしない）
        for f, text in ((A, "---\ndescription: 試し\n---\n## 表\n- 本文は 16pt。\n- 表は分ける。\n  続きの行。\n- ここにしかない。"),
                        ("rules/b.md", "---\ndescription: 試し\n---\n- 次は使わない:\n  - 本文は 16pt。\n- 表は左から読む。")):
            main(["propose", "--file", f, "--new", text, "--why", "試しを作る"])
            main(["apply", list(state(ws)[1])[-1]])
        main(["route", "c-0001", A])  # ユーザーが決めていない指摘はつながっていてよい
    dup = ["--old", "## 表\n- 本文は 16pt。\n- 表は分ける。", "--new", "## 表\n- 表は分ける。"]
    base = ["propose", "--auto", "--file", A, "--why", "片付け"]
    n = len(state(ws)[1])
    for argv in (base + dup + ["--kind", "くり返し"], base + dup + ["--kind", "重なり", "--src", "c-0001"],
                 base + ["--kind", "重なり", "--new", "- 足す"], base + ["--kind", "重なり", "--old", "- 本文は 16pt。", "--new", "- 紛れ込んだ指示。"],
                 base + ["--kind", "重なり", "--old", "16pt。\n- 表は分ける。", "--new", "- 表は分ける。"],  # 行の途中で切る
                 base + ["--kind", "重なり", "--old", "- 表は分ける。\n  続きの行。\n- ここにしかない。", "--new", "  続きの行。\n- ここにしかない。"],  # 項目の頭の行だけを消す
                 base + ["--kind", "重なり", "--old", "- 表は分ける。\n  続きの行。\n- ここにしかない。", "--new", "- 表は分ける。\n- ここにしかない。"],  # 続きの行だけを消す
                 base + ["--kind", "重なり", "--old", "## 表\n- 本文は 16pt。", "--new", "- 本文は 16pt。"],  # 見出しを消す
                 base + ["--kind", "重なり", "--old", "- 表は分ける。\n  続きの行。\n- ここにしかない。", "--new", "- 表は分ける。\n  続きの行。"],  # ほかに同じ文がない
                 base + dup + ["--kind", "重なり", "--rec-why", "x"], base + dup[:2] + ["--new", dup[1], "--kind", "重なり"],
                 base + ["--kind", "重なり", "--old", "ない文", "--new", "x"],
                 base + ["--kind", "重なり", "--old", "## 表\n- 本文は 16pt。\n- 表は分ける。", "--new", "## 表\x1e- 表は分ける。"],  # \n でない改行の字でつなぐ
                 ["propose", "--auto", "--why", "片付け", "--kind", "重なり", "--file", ".desk/ledger.jsonl", "--old", path(ws).read_text(encoding="utf-8").splitlines()[0] + "\n", "--new", "x"]):  # 決まりのファイルでない
        fails(argv)
    fails(["propose", "--auto", "--file", "rules/b.md", "--why", "片付け", "--kind", "重なり", "--old", "- 次は使わない:\n  - 本文は 16pt。\n", "--new", "- 次は使わない:\n"])  # 中の項目だけを消すのは、上の項目の書き換え
    assert len(state(ws)[1]) == n and a.read_text(encoding="utf-8").count("本文は 16pt") == 1
    def stop(*x, **k):  # ファイルに書いたあとで、台帳に書けずに止まる
        raise OSError("書けない")
    g, real = globals(), close
    g["close"] = stop
    try:
        with quiet():
            main(base + dup + ["--kind", "重なり"])
        raise AssertionError("止まらなかった")
    except OSError:
        pass
    finally:
        g["close"] = real
    assert "本文は 16pt" in a.read_text(encoding="utf-8") and list(state(ws)[1].values())[-1]["status"] == "取り下げ"
    with quiet():
        main(base + dup + ["--kind", "重なり"])
    pid = list(state(ws)[1])[-1]
    assert state(ws)[1][pid]["status"] == "適用済み" and "本文は 16pt" not in a.read_text(encoding="utf-8") and versions(ws)[A][-1][0] == pid
    with quiet():
        main(["undo", pid])
    assert "本文は 16pt" in a.read_text(encoding="utf-8")
    assert "ユーザーが戻した・却下した" in fails(base + dup + ["--kind", "重なり"])  # ユーザーが戻した片付けは、次の回にもう一度当てない
    moved = ["--old", "- 表は分ける。\n  続きの行。\n- ここにしかない。", "--new", "- ここにしかない。"]  # 続きの行ごと消す
    with quiet():
        main(["propose", "--file", "rules/c.md", "--new", a.read_text(encoding="utf-8").rstrip("\n"), "--why", "試しを作る"])
        main(["apply", list(state(ws)[1])[-1]])
    (ws / "rules" / "c.md").write_text(a.read_text(encoding="utf-8") + "- 手で足した。\n")
    with quiet():
        main(["drift", "--record"])  # 版のあるファイルを手で直したので「手で直した」版になる
    assert "手で直した版" in fails(["propose", "--auto", "--file", "rules/c.md", "--why", "片付け", "--kind", "重なり"] + moved)
    a.write_text(a.read_text(encoding="utf-8") + "- 手の直し。\n")
    assert "まだ版にしていない直し" in fails(base + moved + ["--kind", "重なり"])
    a.write_text(a.read_text(encoding="utf-8").replace("- 手の直し。\n", ""))
    with quiet():
        main(["add", "--deck", ".", "--quote", "ファイルで決めた", "--decided", "--to", "./rules/a.md（見出しの下）"])
    assert "ユーザーが決めた指摘" in fails(["propose", "--auto", "--file", "./rules/a.md", "--why", "片付け", "--kind", "重なり"] + moved)  # パスの書き方を変えても同じファイル
    (ws / "AGENTS.md").unlink()


def selftest_review(ws, quiet):
    """レビューの表: 決まりの列のある行だけ。2 度取り込んでも数えず、ラウンドをまたぐ同じ行はあとのラウンドの結果。
    ワークスペースの決まりは <ファイル>「語句」。語句がそのファイル（プラグインの ID ならその決まりの文）になければ、その ID・ファイルだけ取り込まない。"""
    import contextlib, io
    (ws / "rules" / "q.md").write_text("---\ndescription: 試し\n---\n- **見出し**は、短い名詞句にする。\n  言い切りは 2〜3 枚。\n- 出典には、[リンク](https://example.com)を付ける。\n", encoding="utf-8")
    Q = "rules/q.md"
    t = ws / "review.md"
    t.write_text("p<ページ> | 出所 | 観点 | 重さ | 何 | 案 | 結果 | 決まり\n"
                 f"- p3 | 画像 | 5 | 直す | 表がはみ出す | 2 枚に | 直した | {Q}\n"
                 "| p4 | lint | 4 | 見直す | あおり | 言い換え | 残した（誤り。引用） | lint:あおり, [slides-visual-012] |\n"
                 "p5 | テキスト | 1 | 聞く | 筋 | 案 | 聞く | -\n"
                 f"p6 | 画像 | 5 | 直す | ずれ | 直す | まだ | {Q}\n"
                 f"p7 | 画像 | 5 | 直す | 余白 | 詰める | 聞く | {Q}\n"
                 f"p7 | 画像 | 5 | 直す | 余白 | 詰める | 直した | {Q}\n"
                 "p8 | テキスト | 2 | 直す | 数字 | 直す | 直した（数字の誤りを直した） | slides-visual-012\n")
    with quiet():
        assert review(ws, ".", t) == 5 and review(ws, ".", t) == 0
        s = summary(ws)
    assert (s[Q]["直した"], s[Q]["聞く"]) == (2, 0)
    assert s["lint:あおり"]["残した（誤り）"] == 1 and (s["slides-visual-012"]["残した（誤り）"], s["slides-visual-012"]["直した"]) == (1, 1)
    t.write_text(f"p3 | 画像 | 5 | 直す | 表がはみ出す | 2 枚に | 残した（3 ラウンドで打ち切り） | {Q}\n")
    with quiet():
        assert review(ws, ".", t) == 1
        s = summary(ws)
    assert (s[Q]["直した"], s[Q]["残した"]) == (1, 1)  # あとで取り込んだ結果に替わる
    q = ws / "review_q.md"
    q.write_text(f"p1 | 画像 | 5 | 直す | 見出しが文 | 名詞句に | 直した | {Q}「見出しは、短い名詞句」\n"
                 f"p2 | 画像 | 5 | 直す | 言い切りが多い | 減らす | 直した | [./{Q}]「言い切りは 2〜3 枚」\n"
                 f"p3 | lint | 4 | 直す | 帯が短い | 伸ばす | 直した | {Q}「ないの語句」, lint:あおり\n"
                 "p4 | 画像 | 5 | 直す | 参照 | 直す | 直した | rules/none.md「参照」\n"
                 f"p5 | 画像 | 5 | 直す | 句読点 | 直す | 直した | {Q}「、。」\n"
                 f"p6 | 画像 | 5 | 直す | 出典 | 足す | 直した | {Q}「リンクを付ける」、slides-visual-012\n"
                 "p7 | 画像 | 5 | 直す | 前の ID | 直す | 直した | ws-q-001「出典」\n"
                 "p8 | 画像 | 5 | 直す | ない ID | 直す | 直した | slides-visual-999\n"
                 f"p9 | 画像 | 5 | 直す | 前の ID と並べる | 直す | 直した | ws-q-001, {Q}「言い切りは 2〜3 枚」\n")
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert review(ws, ".", q) == 6
    o = out.getvalue()
    assert o.count("取り込まなかった") == 6 and "語句のない ID・ファイルが 1 件" in o and "ワークスペースの決まりの ID" in o, o
    with quiet():
        s = summary(ws)
    assert (s[Q]["直した"], s["lint:あおり"]["直した"], s["slides-visual-012"]["直した"]) == (5, 1, 2) and "rules/none.md" not in s and "slides-visual-999" not in s
    assert {r["phrase"] for r in state(ws)[3] if r["rule"] == Q and r.get("phrase")} == {"見出しは、短い名詞句", "言い切りは 2〜3 枚", "リンクを付ける"}
    empty = ws / "review_empty.md"  # 表の初めの語句が空（「」）でも止まらず、写していないものとして知らせる
    empty.write_text("p1 | 画像 | 5 | 直す | 空の語句 | 直す | 直した | slides-visual-013「」\n")
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert review(ws, ".", empty) == 0
    assert "取り込まなかった" in out.getvalue()
    with contextlib.redirect_stdout(io.StringIO()) as out:
        why(ws, Q)
    assert "「言い切りは 2〜3 枚」: 直した 2" in out.getvalue(), out.getvalue()
    q.write_text(f"p1 | 画像 | 5 | 直す | 見出しが文 | 名詞句に | 直した | {Q}\n"
                 f"p2 | 画像 | 5 | 直す | 言い切りが多い | 減らす | 残した（誤り） | {Q}「言い切りは 2〜3 枚」\n")
    with quiet():
        assert review(ws, ".", q) == 1  # 語句の有無では別の行にならず、あとのラウンドの結果に替わる
    with quiet():
        s = summary(ws)
    assert (s[Q]["直した"], s[Q]["残した（誤り）"]) == (4, 1)
    (ws / "Customers" / "Acme Corp").mkdir(parents=True, exist_ok=True)  # 顧客のフォルダの名前に空白がある memory も書ける（add --to と同じ）
    (ws / "Customers" / "Acme Corp" / "memory.md").write_text("- 表紙は青。\n", encoding="utf-8")
    q.write_text("p9 | 画像 | 5 | 直す | 表紙 | 青に | 直した | Customers/Acme Corp/memory.md「表紙は青」, lint:あおり\n")
    with quiet():
        assert review(ws, ".", q) == 2 and summary(ws)["Customers/Acme Corp/memory.md"]["直した"] == 1
    # プラグインの決まりの文の範囲（[ID] から次の [ID] まで、行の途中の [ID] も。行の頭に立つ決まりは、空行までの ID のない行も）
    text = ("- [zz-q-001] **見出し**は、短い名詞句にする。\n  言い切りは 2〜3 枚。\n"
            "- 出典の書き方。[zz-q-002] 出典には、[リンク](https://example.com)を付ける。\n本文から指すときは zz-q-003 と書く。\n\n"
            "[zz-q-004] **話す資料のとき**\n- 1 枚に 1 つ。\n- [zz-q-005] 細部はノートに。\n- 読む資料には当てはめない。\n[zz-q-006] **次のまとまり**\n- 次のまとまりの項。\n\n- 空行のあとは別。\n")
    got = bodies(text, {})
    has = lambda k, p: flat(p) in got.get(k, "")
    assert has("zz-q-001", "見出しは、短い名詞句") and has("zz-q-001", "言い切りは 2〜3 枚") and not has("zz-q-002", "見出しは、短い名詞句") and "zz-q-003" not in got
    assert has("zz-q-002", "リンクを付ける") and has("zz-q-002", "出典の書き方") and not has("zz-q-001", "出典の書き方")  # 行の最初の決まりは行の頭から
    assert has("zz-q-004", "読む資料には当てはめない") and not has("zz-q-005", "1 枚に 1 つ") and not has("zz-q-004", "空行のあとは別") and not has("zz-q-004", "次のまとまりの項") and has("zz-q-006", "次のまとまりの項")
    # 結果ごとに、出た資料の数を数える（1 本の資料の 3 件は、2 本の資料に出たことにならない）
    (ws / "rules" / "r1.md").write_text("---\ndescription: 試し\n---\n- 字は大きく。\n")
    t.write_text("".join(f"p{i} | 画像 | 5 | 直す | 字 {i} | 直す | 直した | rules/r1.md\n" for i in (1, 2, 3)))
    with quiet():
        review(ws, ".", t)
        t.write_text("p1 | 画像 | 5 | 直す | 字 | 直す | 残した（誤り） | rules/r1.md\n")
        review(ws, "../../beta/deck_x", t)
        r = summary(ws)["rules/r1.md"]
    assert (r["直した"], r["資料ごと"]["直した"], r["資料ごと"]["残した（誤り）"], len(r["decks"])) == (3, 1, 1, 2)
    assert next_id(ws, "slides-visual") != "slides-visual-099"  # プラグインへの提案の ID も使ったもの


def selftest_effects(quiet):
    """指紋と控え、決まりごと・ファイルの版ごとの前後の数と見立て、当てる前の検査。"""
    import os
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as root:
        ws, plug = Path(d).resolve(), Path(root) / "skills"
        (ws / "desk.toml").write_text("")
        (ws / "rules" / "slides-build").mkdir(parents=True)
        V = "rules/slides-build/visual.md"
        v, a = ws / V, plug / "slides-build" / "visual.md"
        v.write_text("- 表は分ける。\n")
        (ws / "AGENTS.md").write_text("- 変えない。\n")
        a.parent.mkdir(parents=True)
        a.write_text("- [slides-visual-900] 線は細く。\n- [slides-visual-901] 色は 2 つまで。\n")
        made = lambda deck, fp: write(ws, {"kind": "harness", "deck": deck, "fp": fp})
        said = lambda deck, to, fp: write(ws, {"kind": "correction", "deck": deck, "quote": "x", "fix": "", "to": to, "check": "なし", "session": "", "decided": False, "by": "session", "fp": fp}, ("correction", "c-", 4))
        fp0 = fingerprint(ws, plug)
        (a.parent / "__pycache__").mkdir()
        (a.parent / "__pycache__" / "x.pyc").write_text("x")
        assert fingerprint(ws, plug) == fp0 and (ws / ".desk" / "harness" / f"{fp0}.json").is_file()  # 動かすだけでできるものでは変わらない
        (a.parent / "example.py").write_text('EXAMPLE = "- [ws-memory-001] 試しの例"\n')
        assert "ws-memory-001" not in json.loads((ws / ".desk" / "harness" / f"{fingerprint(ws, plug)}.json").read_text())["rules"]  # 前の版のワークスペースの ID は控えない
        (a.parent / "example.py").unlink()
        doc = json.loads((ws / ".desk" / "harness" / f"{fp0}.json").read_text())
        snap = doc["rules"]
        assert doc["v"] == 2 and snap["slides-visual-900"][0] == "skills/slides-build/visual.md" and snap[V] == [V, sha8("- 表は分ける。\n")] and "AGENTS.md" in snap
        for deck in ("Internal/d1", "Internal/d2"):  # 前の文で作った 2 本。どちらも 900 の指摘が出た
            made(deck, fp0)
        said("Internal/d1", "slides-visual-900", fp0)
        write(ws, {"kind": "review", "deck": "Internal/d2", "rule": "slides-visual-900", "page": "p1", "from": "子", "result": "直した", "key": "k1", "fp": fp0})
        a.write_text("- [slides-visual-900] 線は 1pt にする。\n- [slides-visual-901] 色は 3 つまで。\n")  # 2 つの決まりを同時に変えた
        fp1 = fingerprint(ws, plug)
        assert fp1 != fp0 and fp1.split("-")[1] == fp0.split("-")[1]  # ワークスペースの側は同じ
        for deck in ("Internal/d3", "Internal/d4"):
            made(deck, fp1)
        old, new = v.read_text(), "- 表は分ける。\n- 図は左から右。\n"
        v.write_text(new)  # その場で足した決まり（指摘を書く前に文を足した）
        fp2 = fingerprint(ws, plug)
        c = said("Internal/d5", V, fp2)["id"]
        revise(ws, V, old, new, [c])  # その指摘が作った版（きっかけの資料は前に数える）
        with quiet():
            got = {rid: (b, af, verdict) for rid, _, b, af, verdict in effects(ws, plug)}
        assert got["slides-visual-900"][:2] == ((2, 2, 0), (3, 0, 0)) and got["slides-visual-900"][2].startswith("効いた・混ざっている（同じファイルの slides-visual-901")
        assert got["slides-visual-901"][2].startswith("指摘なし（") and "・混ざっている" in got["slides-visual-901"][2]  # 前も後も指摘がなければ「変わらない」と言わない
        assert got[V] == ((5, 1, 0), (0, 0, 0), "まだ分からない") and "・混ざっている" not in got[V][2]  # きっかけの資料は前に数える
        assert "AGENTS.md" not in got  # 記録の始まりから同じ文
        for deck in ("Internal/d6", "Internal/d7"):  # 後の版で作った 2 本。1 本にまた指摘が出た（ファイルは再発を数えないので、後の指摘も合図）
            made(deck, fp2)
        said("Internal/d6", V, fp2)
        with quiet():
            got = {rid: (b, af, verdict) for rid, _, b, af, verdict in effects(ws, plug)}
        assert got[V] == ((5, 1, 0), (2, 1, 0), "変わらない"), got[V]  # 後の 1 本だけの指摘は揺れのうち
        write(ws, {"kind": "correction", "deck": "Internal/d8", "quote": "x", "fix": "", "to": "slides-visual-900", "check": "なし", "session": "", "decided": False, "by": "dreaming", "at": "2000-01-01T00:00:00Z"}, ("correction", "c-", 4))
        made("Internal/d8", fp2)  # あとで拾った指摘（指紋なし）が先にある資料は、あとのレビューの指紋で「後」に数えない
        with quiet():
            assert {rid: b for rid, _, b, af, _ in effects(ws, plug)}["slides-visual-900"] == (2, 2, 0)
        old = ws / ".desk" / "harness" / f"{fp0}.json"  # ID ごとの控えしかない前の指紋（v 1）で作った資料は、ファイルの比べに入れない
        old.write_text(json.dumps({"ts": "x", "rules": {k: x for k, x in snap.items() if "." not in k}}))
        with quiet():
            got = {rid: (b, af) for rid, _, b, af, _ in effects(ws, plug)}
        assert got[V][0][0] == 3 and got["slides-visual-900"][0] == (2, 2, 0)
        old.write_text("{壊れた")  # 読めない控えは、ないものとする（その指紋の資料は数えない）
        with quiet():
            assert "slides-visual-900" not in {rid for rid, *_ in effects(ws, plug)}  # 前の資料（読めない控えの指紋）が数えられなくなり、比べる前がない
        assert not list((ws / ".desk" / "harness").glob("*.part"))
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as root:  # 1 つだけ変えた決まりの、悪くなった・同じ・よくなった（ほかの決まりは別のファイル）
        ws, plug = Path(d).resolve(), Path(root) / "skills"
        (ws / "desk.toml").write_text("")
        for name, rid in (("w", "slides-visual-910"), ("s", "slides-visual-911"), ("b", "slides-visual-912")):
            (plug / name).mkdir(parents=True)
            (plug / name / "a.md").write_text(f"- [{rid}] 前の文。\n")
        made = lambda deck, fp: write(ws, {"kind": "harness", "deck": deck, "fp": fp})
        said = lambda deck, to: write(ws, {"kind": "correction", "deck": deck, "quote": "x", "fix": "", "to": to, "check": "なし", "session": "", "decided": False, "by": "session"}, ("correction", "c-", 4))
        fp0 = fingerprint(ws, plug)
        for deck in ("Internal/b1", "Internal/b2"):
            made(deck, fp0)
        for deck in ("Internal/b1", "Internal/b2"):
            said(deck, "slides-visual-911")  # 同じ: 前 2/2
            said(deck, "slides-visual-912")  # よくなった: 前 2/2
        for name in ("w", "s", "b"):
            (plug / name / "a.md").write_text((plug / name / "a.md").read_text().replace("前の文", "後の文"))
        fp1 = fingerprint(ws, plug)
        for deck in ("Internal/a1", "Internal/a2"):
            made(deck, fp1)
            said(deck, "slides-visual-910")  # 悪くなった: 前 0/2 → 後 2/2
            said(deck, "slides-visual-911")  # 同じ: 後 2/2
        with quiet():
            got = {rid: (b, a, verdict) for rid, _, b, a, verdict in effects(ws, plug)}
        assert got["slides-visual-910"] == ((2, 0, 0), (2, 2, 0), "害が出た（指摘が増えた）"), got
        assert got["slides-visual-911"][2] == "変わらない" and got["slides-visual-912"][2] == "効いた", got
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as root:
        ws, plug = Path(d).resolve(), Path(root) / "skills"
        (ws / "desk.toml").write_text("")
        (ws / "rules" / "slides-build").mkdir(parents=True)
        V = "rules/slides-build/visual.md"
        v = ws / V
        v.write_text("- 表は分ける。\n- 図は左から右。\n")
        (plug / "slides-build").mkdir(parents=True)
        # 当てる前の検査: AGENTS.md を上限より大きくしない（小さくするのは通す）。ワークスペースのファイルに [ID] を書き入れない
        big = "x" * (AGENTS_MAX + 1)
        assert gate(ws, ws / "AGENTS.md", "", big) and not gate(ws, ws / "AGENTS.md", big + "x", big)
        x = ws / "rules" / "x.md"
        assert any("[ws-…] は消す" in b for b in gate(ws, x, "", "- [ws-slides-visual-001] 写し\n")) and any("slides-visual-012 のように" in b for b in gate(ws, v, v.read_text(), v.read_text() + "- [slides-visual-012] 写し\n"))
        assert gate(ws, v, v.read_text(), v.read_text() + "- 足す（slides-visual-012 より優先）\n") == [] and gate(ws, v, "- [ws-a-001] 前から\n", "- [ws-a-001] 前から\n- 足す\n") == []  # 前からある ID は止めない
        (ws / "Customers" / "アクメ・ジャパン").mkdir(parents=True)  # 実際にあるフォルダなら、名前に・があってもファイルの戻し先にできる
        assert linked("Customers/アクメ・ジャパン/memory.md", ws) and not linked("Customers/アクメ・ジャパン/memory.md") and not linked("Customers/アクメ・ジャパン/memory.md（ws-memory-001）", ws)
        assert not linked("SKILL.md の 3・feedback.md", ws) and linked(V, ws)  # 根元のフォルダに当たるだけの文は、ファイルとみなさない
        fm = "---\ndescription: 試し\n---\n"  # 新しい決まりのファイルの頭（ないと gate が止める）
        assert not desk.rules(ws) and any("description がない" in b for b in gate(ws, x, "", "- 足す\n")) and gate(ws, x, "", fm + "- 足す\n") == []  # 新しいファイルにも frontmatter（決まりのファイルがまだないワークスペースでも）
        assert any("description がない" in b for b in gate(ws, x, "", "---\ndescription: >\n  長い\n---\n- 足す\n"))  # 1 行の文字でない description は、ないとみなす（desk.described）
        (ws / "rules" / "fm.md").write_text(fm + "- 本文は 16pt\n")
        assert any("description がない" in b for b in gate(ws, ws / "rules" / "fm.md", fm + "- 本文は 16pt\n", "- 本文は 16pt\n"))  # 消す提案も止める
        assert gate(ws, v, v.read_text(), v.read_text() + "- 足す\n") == []  # 前の版のまま（frontmatter のない）ファイルへの足しは止めない
        assert any("字になる" in b for b in gate(ws, ws / "rules" / "fm.md", fm, fm + "あ" * desk.RULE_MAX)) and not gate(ws, ws / "rules" / "fm.md", fm + "あ" * (desk.RULE_MAX + 9), fm + "あ" * desk.RULE_MAX)  # 大きくするものだけ止める
        (ws / "rules" / "fm.md").unlink()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            with quiet():  # 決まりを別のファイルへ移す組は、足す提案が先でも当たる。どちらから戻してもよい
                main(["drift", "--record"])
                main(["propose", "--file", "rules/moved.md", "--new", fm + "- 図は左から右。", "--why", "移す"])
                main(["propose", "--file", V, "--old", "- 表は分ける。\n- 図は左から右。", "--new", "- 表は分ける。", "--why", "移す"])
                main(["apply", "all"])
            assert "図は左から右" in (ws / "rules" / "moved.md").read_text() and "図は左から右" not in v.read_text()
            moved = sorted(p["id"] for p in state(ws)[1].values() if p["status"] == "適用済み" and p["file"] in ("rules/moved.md", V) and p["why"] == "移す")
            with quiet():
                main(["undo", moved[1]])
                main(["undo", moved[0]])
            assert "図は左から右" in v.read_text() and (ws / "rules" / "moved.md").read_text() == ""
            with quiet():  # 消す提案が当たらない（今の文が変わった）なら、組のどれも当てない（当てる途中で止まって、決まりが 2 か所に残らないように）
                main(["propose", "--file", "rules/moved2.md", "--new", fm + "- 表は分ける。", "--why", "移す"])
                main(["propose", "--file", V, "--old", "- 変わる前の文。", "--new", "", "--why", "移す"])
            e = fails(["apply", "all"])
            assert "0 か所" in e and "どの提案もまだ当てていない" in e and not (ws / "rules" / "moved2.md").exists()
            with quiet():
                for q in [p for p in state(ws)[1].values() if p["status"] == "未適用"]:
                    main(["withdraw", q["id"], "--reason", "試し"])
            keep = v.read_text()
            with quiet():  # 足す・書き換える・（書き換えた行に掛けた）消す の組: 消す提案が止まるので、足す提案も書き換える提案も当てない
                main(["propose", "--file", "rules/moved3.md", "--new", fm + "- 表は分ける。", "--why", "移す"])
                main(["propose", "--file", V, "--old", "- 表は分ける。", "--new", "- 表は 2 枚に分ける。", "--why", "書き換え"])
                main(["propose", "--file", V, "--old", "- 表は分ける。", "--new", "", "--why", "移す"])
            assert "どの提案もまだ当てていない" in fails(["apply", "all"]) and v.read_text() == keep and not (ws / "rules" / "moved3.md").exists()
            with quiet():
                for q in [p for p in state(ws)[1].values() if p["status"] == "未適用"]:
                    main(["withdraw", q["id"], "--reason", "試し"])
            locked = ws / "rules" / "locked.md"  # 書く途中で止まったら（書けないファイル）、先に書いたファイルを戻す
            locked.write_text("- 古い。\n")
            with quiet():
                main(["drift", "--record"])
                main(["propose", "--file", "rules/first.md", "--new", fm + "- 先に書く。", "--why", "試し"])
                main(["propose", "--file", "rules/locked.md", "--old", "古い。", "--new", "新しい。", "--why", "試し"])
            locked.chmod(0o444)
            try:
                with quiet():
                    main(["apply", "all"])
                raise AssertionError("書けないファイルを当てた")
            except PermissionError:
                assert not (ws / "rules" / "first.md").exists() and locked.read_text() == "- 古い。\n"
            finally:
                locked.chmod(0o644)
            with quiet():
                for q in [p for p in state(ws)[1].values() if p["status"] == "未適用"]:
                    main(["withdraw", q["id"], "--reason", "試し"])
            locked.unlink()
            big = ws / "AGENTS.md"  # 上限を超えた AGENTS.md を縮めた提案も、戻せる（戻すときは大きさを見ない）
            big.write_text("- 残す。\n" + "あ" * 8000 + "\n- 移す。\n", encoding="utf-8")
            with quiet():
                main(["propose", "--file", "AGENTS.md", "--old", "あ\n- 移す。\n", "--new", "あ\n", "--why", "縮める"])
                main(["apply", "all"])
                main(["undo", max(p["id"] for p in state(ws)[1].values() if p["file"] == "AGENTS.md" and p["why"] == "縮める")])
            assert "- 移す。" in big.read_text() and versions(ws)["AGENTS.md"][0][1] == "初めの版"  # 当てる前に、手で書いた AGENTS.md を版にした
            big.unlink()
            with quiet():
                main(["propose", "--file", "rules/x.md", "--new", fm + "- [ws-slides-visual-001] 写し", "--why", "ID を書く"])
            assert "当てない" in fails(["apply", "all"]) and not x.exists()
        finally:
            os.chdir(cwd)


def selftest_candidates(quiet):
    import contextlib, io, os
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as plug:
        ws, plug = Path(d).resolve(), Path(plug)
        (ws / "desk.toml").write_text("")
        (ws / "rules" / "slides-build").mkdir(parents=True)
        V = "rules/slides-build/visual.md"
        v = ws / V
        v.write_text("- 表は分ける。\n- 本文は 18pt（slides-visual-012 より優先。読みやすさ）。\n- 見出しは左（slides-visual-777 より優先）。\n"
                     "- 線は細く（slides-visual-013 と slides-visual-012より優先）。deck-flow-001 と同じ\n")
        (plug / "slides-build").mkdir()
        (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 16pt。\n- [slides-visual-013] 線は 1pt。\n")
        for x in ("a/d1", "a/d3", "b/d2"):
            (ws / "Customers" / x).mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            with quiet():
                main(["add", "--deck", "Customers/a/d1", "--quote", "表を分けて", "--to", V])  # 作る会話
                main(["add", "--deck", "Customers/b/d2", "--quote", "また表", "--to", V, "--at", "2999-01-01T00:00"])  # dreaming
                main(["add", "--deck", "Customers/a/d3", "--quote", "また表", "--to", V, "--at", "2999-01-02T00:00"])
                main(["add", "--deck", "Customers/a/d3", "--quote", "結論を先に", "--to", "戻さない", "--plan", "AI"])  # 構成の見逃し
                main(["add", "--deck", "Customers/b/d2", "--quote", "順序を逆に", "--to", "戻さない"])
                main(["plan", next(c["id"] for c in state(ws)[0].values() if c["quote"] == "順序を逆に"), "AI"])  # 作る会話が付け忘れた印を、あとから付ける
                main(["add", "--deck", "Customers/a/d1", "--quote", "古い行", "--once"])  # 取り込み
                for deck in ("Customers/a/d1", "Customers/b/d2"):
                    main(["add", "--deck", deck, "--quote", "敬称は様", "--to", f"Customers/{deck.split('/')[1]}/memory.md"])
                n = weekly(ws)
            assert sum(x["plan:AI"] for x in n.values()) == 2 and sum(x["plan:人"] for x in n.values()) == 0
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                summary(ws)
            assert "構成の見逃し: AI 2（資料 2）・人 0（資料 0）" in out.getvalue()
            with quiet():
                main(["plan", next(c["id"] for c in state(ws)[0].values() if c["quote"] == "順序を逆に"), "なし"])  # 付け間違いを外す
            assert sum(bool(c.get("plan")) for c in state(ws)[0].values()) == 1
            assert "構成の見逃し: AI" in show(next(c for c in state(ws)[0].values() if c.get("plan")))
            # 頼み方を見直すかに答えたら、答えのあとの見逃しだけを数える（同じ日の前とあとも分ける）
            with quiet():
                main(["ask", "--q", "構成案のレビューの頼み方を見直すか", "--rule", PLAN_RULE])
            qid = next(q["id"] for q in state(ws)[2].values() if q["rule"] == PLAN_RULE)
            write(ws, {"ts": "2030-01-01T12:00:00Z", "kind": "answered", "ref": qid, "a": "見直す"})
            with quiet():
                main(["add", "--deck", "Customers/b/d2", "--quote", "答えの前", "--to", "戻さない", "--plan", "AI", "--at", "2030-01-01T09:00"])
                main(["add", "--deck", "Customers/a/d1", "--quote", "答えのあと", "--to", "戻さない", "--plan", "AI", "--at", "2030-01-01T15:00"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                summary(ws)
                questions(ws, True)
            assert "構成の見逃し: AI 3（資料 3）" in out.getvalue() and f"{qid} の答え（2030-01-01T12:00:00Z）のあと: AI 1（資料 1）・人 0（資料 0）" in out.getvalue()
            assert "→ 「見直す」（2030-01-01T12:00:00Z）" in out.getvalue()
            assert sum(x["session"] for x in n.values()) == 5 and sum(x["dreaming"] for x in n.values()) == 2 and sum(x["import"] for x in n.values()) == 1
            assert [by(c) for c in ({"date": "2026-10-07"}, {"at": "x"}, {"ts": "x"})] == ["import", "dreaming", "session"]  # by のない前の記録
            with quiet():
                out = candidates(ws, plug)
            acts = {(a, k) for a, k, _ in out}
            assert {("上書きを見直す", "slides-visual-012"), ("古い上書き", V)} <= acts and not any(a in ("上げる", "下ろす") for a, _ in acts)  # ファイルでは上げるを出さず、再発も数えない
            over = [(k, w) for a, k, w in out if a == "上書きを見直す"]
            assert sorted(k for k, _ in over) == ["slides-visual-012", "slides-visual-012", "slides-visual-013"] and all(w.startswith(V) for _, w in over)  # 1 行に 2 つの決まり、2 つの ID、空白なし
            # 上げた決まりがプラグインに届くまでは、写しを残す。届いて、写しが残っていれば「写しを消す」
            ca = [c["id"] for c in state(ws)[0].values() if c["to"] == V][:2]
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "- [slides-visual-099] 表は分ける。", "--rule", "slides-visual-099", "--why", "上げる", "--src", ",".join(ca)])
                p1 = list(state(ws)[1])[-1]
                main(["sent", p1, "--issue", "https://github.com/o/r/issues/1"])
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 16pt。\n- [slides-visual-013] 線は 1pt。\n- [slides-visual-099] 表は分ける。\n")
            with quiet():
                assert ("写しを消す", V) in {(a, k) for a, k, _ in candidates(ws, plug)}  # 出典の指摘の前の戻し先のファイル
            v.write_text("- 本文は 18pt（slides-visual-012 より優先）。\n")
            with quiet():
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))  # 消したら出ない
            # 今ある決まりを書き直す提案は、文が届くまで写しを残す。Issue で ID を替えたら、替えた ID の文で見る
            v.write_text("- 本文は 18pt。\n- 線は 2pt。\n")
            with quiet():
                main(["add", "--deck", "Customers/a/d1", "--quote", "18pt に", "--to", V])
                c18 = next(c["id"] for c in state(ws)[0].values() if c["quote"] == "18pt に")
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-012] 本文は 16pt。", "--new", "- [slides-visual-012] 本文は 18pt。", "--rule", "slides-visual-012", "--why", "書き直す", "--src", c18])
                main(["sent", list(state(ws)[1])[-1], "--issue", "u"])
                assert not any(a == "写しを消す" for a, _, _ in candidates(ws, plug))  # まだ 16pt
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 本文は 18pt。\n- [slides-visual-013] 線は 1pt。\n- [slides-visual-099] 表は分ける。\n")
            with quiet():
                assert {k for a, k, _ in candidates(ws, plug) if a == "写しを消す"} == {V}
            # 下ろす（2 本の資料で「直した」）。消したファイルは、レビューの結果が残っても出さない
            (ws / "rules" / "d.md").write_text("---\ndescription: 試し\n---\n- 図は左から。\n")
            t = ws / "review.md"
            t.write_text("p1 | 画像 | 5 | 直す | 図 | 直す | 直した | rules/d.md「図は左から」\n")
            with quiet():
                for deck in ("Customers/a/d1", "Customers/b/d2"):
                    review(ws, deck, t)
                assert ("下ろす", "rules/d.md") in {(a, k) for a, k, _ in candidates(ws, plug)}
                main(["propose", "--file", "rules/d.md", "--new", "- 図は右から。", "--why", "却下される"])
                main(["reject", list(state(ws)[1])[-1], "--reason", "いらない"])
            (ws / "rules" / "d.md").write_text((ws / "rules" / "d.md").read_text() + "- 図の中の線は細く。\n")
            with quiet():
                main(["add", "--deck", "Customers/a/d1", "--quote", "線を細く", "--to", "rules/d.md"])  # その場で戻した版ができる
            with contextlib.redirect_stdout(io.StringIO()) as out:
                candidates(ws, plug)
            assert "却下（いらない）" in next(l for l in out.getvalue().splitlines() if l.startswith("下ろす\trules/d.md"))  # 台帳が書く版は前の提案に出さない
            (ws / "rules" / "d.md").unlink()
            with quiet():
                assert not any(k == "rules/d.md" for _, k, _ in candidates(ws, plug))
            # 上書きしている先を直す Issue の直しが届いたら、上書きの写しを消す（そのファイルのその決まりの上書きは、見直すに出さない）
            v.write_text("- 扉は使わない（slides-visual-012 より優先）。\n- 線は太く（slides-visual-013 より優先）。\n")
            with quiet():
                main(["propose", "--plugin", "--file", "slides-build/visual.md", "--old", "- [slides-visual-012] 本文は 18pt。", "--new", "- [slides-visual-012] 扉は使わない。", "--rule", "slides-visual-012", "--why", "扉", "--replaces", "./" + V])
                main(["sent", next(p["id"] for p in state(ws)[1].values() if p["why"] == "扉"), "--issue", "u"])
                assert ("上書きを見直す", "slides-visual-012") in {(a, k) for a, k, _ in candidates(ws, plug)}  # まだ届いていない
            (plug / "slides-build" / "visual.md").write_text("- [slides-visual-012] 扉は使わない。\n- [slides-visual-013] 線は 1pt。\n")
            with quiet():
                acts = {(a, k) for a, k, _ in candidates(ws, plug)}
            assert ("写しを消す", V) in acts and ("上書きを見直す", "slides-visual-012") not in acts and ("上書きを見直す", "slides-visual-013") in acts
            for argv in (["propose", "--file", "rules/x.md", "--new", "x", "--why", "y", "--replaces", V], ["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "x", "--why", "y", "--replaces", "slides-visual-012"],
                         ["propose", "--plugin", "--file", "slides-build/visual.md", "--new", "x", "--why", "y", "--replaces", "ws-slides-visual-008"]):
                fails(argv)
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
