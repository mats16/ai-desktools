#!/usr/bin/env python3
"""スライドとドキュメントで同じ lint の部品: 本文の表記の決まり（HARD・WARN）、色のコントラスト、出典の表の照合、指摘の入れ物（Report）、
ワークスペースの点検（recipes/ の下の checks.py）、要確認の記録（.desk/lint_runs.jsonl）。スライドは slides-build の lint.py、
ドキュメントは docs-build の doc_lint.py が読む。標準ライブラリだけ。
usage: python3 textlint.py --stats   要確認の残り方（規則ごと。desk-dreaming/run.md の 5）
       python3 textlint.py --selftest"""
import copy, functools, hashlib, json, os, re, sys, time, unicodedata
from collections import defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi  # noqa: E402
from brand import FONT, MONO_DEFAULT  # noqa: E402

JA = r"぀-ゟァ-ヺー-ヿ㐀-鿿"  # かなと漢字（中黒「・」と全角の記号は含めない）

HARD = {
    "絵文字": re.compile("[\U0001F300-\U0001FAFF☀-⛿✅✨❌⭐️]"),
    "長いダッシュ": re.compile("[—―](?!$)|(?<!^)[—―]"),  # 「—」だけのセル（該当なし）は数えない
    "置き換え忘れ": re.compile(r"TODO|FIXME|XXX|lorem|ipsum|〇〇|○○|ここに.{0,6}(入|書)|\[insert", re.I),
    "差し替えの仮ページ": re.compile(r"差し替え："),  # 札の残り。人には Drive の URL で渡し、差し替える人はいない（2026-10-07）
}
WARN = {
    "空疎な言い回し": re.compile(r"(を|の)(実現|加速|最適化|効率化|高度化|強化|推進|促進|変革|最大化)(する|します|。|$)"
                          r"|革新的|次世代の|シームレス|ゲームチェンジ|新たな価値|可能性を広げ|解き放|圧倒的|劇的に|飛躍的"),
    "あおり": re.compile(r"乗り遅れ|取り残さ|このままでは|待ったなし|手遅れ"),
    "英語の大文字ラベル": re.compile(r"^(?![0-9A-F]{6}$)[A-Z][A-Z0-9 &/\-]{3,}$"),  # 6 桁の色の値（F9F7F4 など）は数えない
    "和欧間のスペース抜け": re.compile(rf"[{JA}][A-Za-z0-9]|[A-Za-z0-9][{JA}]"),
    "約物の前後のスペース": re.compile(r" [、。，．）」』]|[（「『] "),
    "要確認・TBD": re.compile(r"要確認|TBD"),
    "社外秘の表示": re.compile(r"Internal Only|Internal Use|Confidential|社外秘|社内限り", re.I),
}
# [deck-lint-027] 言い回しの要確認は、yomiyasu の lint の規則のうち、資料 53 本で当たりの多かったものだけ（2026-11-01。deck-content-065、deck-writing）。
# 外したもの: 読点（pause_comma。本文の文の読点にも出て空振りが多い。スライドの見出しと 1 行の箇条は slide_comma が見る）、空疎な語（slop_vocabulary。「台帳」にも出る。WARN の空疎な言い回しで見る）、
# 「〜ではなく」（negative_parallelism。比べるページでは普通）、カタカナ語、Markdown の書式（太字・箇条の多さ。ページの JSON には当たらない）
SLIDE_COMMA = "見出しと箇条の間の読点"
YOMI = {"renyo_noun": "動詞を名詞にした語", "calque": "直訳の語", "translated_term": "直訳の語", "metaphor_verb": "たとえの動詞", "slide_comma": SLIDE_COMMA}  # slide_comma は doc_type が slides のときだけ出る
YOMI_NAMES = list(dict.fromkeys(YOMI.values()))


@functools.cache
def yomiyasu():
    """yomiyasu の yomiyasu_lint.py をパスで読む（git subtree で 2.5.0 を取り込んだもの。中は直さず、git subtree pull で入れ替える）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("yomiyasu_lint", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yomiyasu", "scripts", "yomiyasu_lint.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NUM = re.compile(r"\d[\d,.]*\s?(%|％|倍|億|万|兆|円|ドル|USD|ms|TB|GB|PB|K\b|M\b)|[$＄]\s?\d")  # 統計らしい数字だけ（「2 時間」「3 社」は数えない）
URL = re.compile(r"https?://\S+")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


NO_LINK = "出典の行にリンクがない"
# [deck-lint-026] ページの数字は出典の表にあるものだけ。足すときは先に表へ足す（deck-content-064、deck-writing）。表は refs.py が資料のフォルダから読む
NOT_IN_FACTS = "出典の表にない数字"
HEAD_PERIOD, BULLET_PERIOD = "見出しの句点", "箇条書きの句点の混在"  # deck-writing の content.md の 6。名前は Docs の規則と同じ（Docs は見出しのスタイル、箇条書きのリストごと）
# [deck-lint-023] 見出しは短い名詞句。言い切りは判断を頼むページと数字の結論のページの 2〜3 枚だけ（deck-content-041 と content の 6（deck-writing）、docs-visual-002（deck-design））
HEAD_POLITE = "見出しが「ください・します」で終わる"
POLITE_END = re.compile(r"(ください|します|しましょう)$")
FONT_NG = f"書体が {FONT} でない"  # スライドはテンプレートの書体（deck_font）と比べる。Google Fonts にない書体は、API が受け付けても黙って別の書体で描かれる（api.md）。英数字だけの MONO（コード）は通す
MONO_NG = f"等幅の {MONO_DEFAULT} に和文"  # 名前は既定の書体のまま（台帳と lint_runs.jsonl が名前で数える）。テーマの mono なら指摘にその名前を出す。MONO に和文の字形はなく、Google が別の書体で描く。和文は FONT にする（slides.py の mono_reqs。slides-visual-014、deck-design）
HARD_NAMES = set(HARD) | {HEAD_PERIOD, HEAD_POLITE, FONT_NG, MONO_NG}  # スライドとドキュメントで同じ要修正（それぞれの lint が足す）


def load_facts(folder=".."):
    """資料のフォルダ（build/ の親）の出典の表の文字（同じフォルダの refs.py の facts_text）。slides.py lint・docs.py check が build/ で呼び、
    lint_slides・lint_gdoc の facts に渡す。refs.py はパスで読む（build/ に同じ名前のファイルがあっても取り違えない）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("refs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "refs.py"))
    refs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refs)
    return refs.facts_text(folder)


DIGITS = re.compile(r"\d+(?:\.\d+)?")
NUMBER = re.compile(r"(?<![A-Za-z\d.])" + DIGITS.pattern)  # 表の数の読み方。英字の後ろ（v2、H100）と、小数点の後ろ（1.2.3 の 3）は数えない


def not_in_facts(texts, facts):
    """texts の統計らしい数字（NUM。NO_SOURCE と同じもの）のうち、数の字が出典の表の文字 facts（refs.py の facts_text）にないもの。全角と桁区切りはそろえて、数の字だけを比べる。
    丸めた値は、ページの書き方のまま表の「言うこと」に書く（deck-sources-007。表 3.24 倍だけならページの 3.2 倍は出す）。
    ponytail: 単位と意味（15% と 15 社、範囲の下の値、NUM が数えない数）は見ない。それは照合の子の 2 回目（deck-review/prompt_sources.md の "Pages"）が見る"""
    norm = lambda t: re.sub(r"(?<=\d),(?=\d{3})", "", unicodedata.normalize("NFKC", t))
    bare = lambda d: d.rstrip("0").rstrip(".") if "." in d else d  # 小数の終わりの 0 は見ない（bars は桁をそろえて 40 を 40.0 と書く）
    have, out = {bare(d) for d in NUMBER.findall(norm(facts or ""))}, []
    for t in texts:
        t, end = norm(URL.sub("", t)), 0
        for m in NUM.finditer(t):
            if m.start() < end:  # 前の数の続き（$12M の 2M）
                continue
            n = DIGITS.match(t, m.start() + re.search(r"\d", m.group()).start())  # NUM の $ の形は 1 字だけを取るので、数の終わりまで読む
            end = n.end()
            if bare(n.group()) not in have and (shown := t[m.start():max(m.end(), n.end())].strip()) not in out:
                out.append(shown)
    return out


def facts_hit(where, miss, facts):
    """出典の表にない数字の指摘の 1 行（スライドはページ、ドキュメントは段落の場所）。"""
    return f"{where}: 「" + "」「".join(miss[:4]) + "」" + ("（出典の表がない）" if not facts else "。先に出典の表へ足すか、表の値にする")


class Report:
    """指摘の入れ物。hard は記録（log_run）に残さない要修正の名前、estimate は見積もりから出す指摘の名前（スライドの lint.py と docs-build の doc_lint.py が足す）。"""
    hard, estimate = HARD_NAMES, frozenset()

    def __init__(self):
        self.hits = defaultdict(list)
        self.extra_hard = set()  # ワークスペースの点検（checks.py の HARD）の要修正の名前（workspace_checks が足す）
        self.where = lambda hit: ""  # 指摘の後ろに付ける、作ったものの中の場所（slides.py lint が JSON のページの部品の場所を引く）

    def scan(self, where, text, rules):
        text = URL.sub("", text).strip()
        for name, rx in rules.items():
            m = rx.search(text)
            if m:
                self.hits[name].append(f"{where}: 「{text[max(0, m.start() - 12):m.end() + 12].strip()}」")

    def wording(self, where, text, slides=True, one_line=False):
        """yomiyasu の lint（yomiyasu/ に subtree で取り込んだもの）の候補のうち、YOMI の規則だけを要確認に足す（deck-lint-027）。
        見出しと箇条の間の読点は、1 行に収まる段落（one_line。スライドの lint が折り返しの見込みで決める）だけ。本文の文の読点は残してよいため。"""
        text = re.sub(r"\s+", " ", URL.sub("", text)).strip()  # 段落の中の改行（\v）も 1 行の指摘にする
        if not re.search(f"[{JA}]", text) or re.match(r"(出典|Sources?)\s*[:：]", text, re.I):  # 出典の行は元の題を写すので見ない
            return
        for f in yomiyasu().lint_text(text, doc_type="slides" if slides else None)["findings"]:
            if (name := YOMI.get(f["rule"])) and (one_line or name != SLIDE_COMMA):
                m = re.search(r"当たった言い方: (.+?)）の候補|直訳「(.+?)」", f["message"])  # translated_term だけ「英語の直訳「版」（version）」の形
                said = (m and (m.group(1) or m.group(2)) or "").strip("「」")
                at = text.find(said.split("、")[0].strip("「」")) if said else -1
                self.hits[name].append(f"{where}: 「{text[max(0, at - 12):at + len(said) + 12].strip() if at >= 0 else text[:30]}」" + (f"（{said}）" if said else ""))

    def show(self, names, title):
        n, est = sum(len(self.hits[k]) for k in names), sum(len(self.hits[k]) for k in names if k in self.estimate)
        print(f"\n== {title}: {n}" + (f"（うち見積もり {est}。画像で確定する）" if est else "") + " ==")
        for k in names:
            for line in self.hits[k][:6]:
                print(f"[{k}] {line}" + self.where(line) + ("（見積もり）" if k in self.estimate else ""))
            if len(self.hits[k]) > 6:
                print(f"[{k}] ほか {len(self.hits[k]) - 6} 件")
        return n


def workspace_checks(kind, data, r):
    """ワークスペースの点検。recipes/ の下の checks.py（そのレシピのフォルダに置く。テンプレートの templates/ の下は見ない）のうち、
    スライドは slides(p, r)、ドキュメントは doc(doc, r) を持つものを、パスの順に呼ぶ（修正の指示から育てる、そのワークスペースだけの点検。desk-feedback/routing.md の「Workspace rules」）。
    足された指摘のうち、そのファイルの HARD にある名前は要修正、ほかは要確認。"""
    import importlib.util
    try:
        root = gapi.workspace() / "recipes"
    except SystemExit:  # ワークスペースがない
        return 0
    n = 0
    for path in sorted(root.rglob("checks.py")) if root.is_dir() else []:
        if "templates" in path.relative_to(root).parts[1:] or not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("workspace_checks", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except ModuleNotFoundError as e:  # 前の雛形の、頭で import lint（スライドだけ）・import doc_lint（ドキュメントだけ）する点検は、ほかの lint では飛ばす
            if e.name == {"slides": "doc_lint", "doc": "lint"}[kind]:
                continue
            raise
        if not (fn := getattr(mod, kind, None)):
            continue
        before = {k: len(v) for k, v in r.hits.items()}
        fn(data, r)
        view = copy.copy(r)  # このファイルが足した指摘だけ（前のファイルと同じ名前に足しても）
        view.hits = defaultdict(list, {k: v[before.get(k, 0):] for k, v in r.hits.items() if len(v) > before.get(k, 0)})
        hard = [k for k in view.hits if k in getattr(mod, "HARD", ())]
        r.extra_hard |= set(hard)
        n += view.show(hard, f"要修正（ワークスペースの点検 {path}）")
        view.show([k for k in view.hits if k not in hard], f"要確認（ワークスペースの点検 {path.parent.relative_to(root.parent)}）")
    return n


def log_path():
    """要確認の記録。ワークスペースの .desk/ に置く（プラグインのフォルダは入れ直すと消える）。
    ponytail: 足すだけで消さない（1 回 1 行）。重くなったら古い行を落とす"""
    return str(gapi.workspace() / ".desk" / "lint_runs.jsonl")


def log_run(r, deck, path=None):
    """要確認を 1 行で残す（--stats が、組み直しても残った指摘を規則ごとに数える。desk-dreaming/run.md の 5）。要修正（r.hard と点検の HARD）は残さない。
    資料の文は残さず、場所（p3・段落 12）を除いた指摘のハッシュだけにする（ページが増えても同じ指摘と分かる）。"""
    warn = {k: sorted({hashlib.sha1(re.sub(r"^(p\d+|段落 \d+)", "", h).encode()).hexdigest()[:8] for h in v})
            for k, v in r.hits.items() if v and k not in r.hard}
    if os.environ.get("DESK_VERIFY"):  # desk-kaizen の検証で組んだ仮の資料は数えない
        return
    path = path or log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deck": deck, "warn": warn}, ensure_ascii=False) + "\n")


def stats(path=None):
    """規則ごとに、出た指摘の数と、その資料の最後の確認まで残った数。残ったものが、残す理由のある指摘か外れかは、ここからは分からない。"""
    runs, path = defaultdict(list), path or log_path()
    for line in open(path, encoding="utf-8") if os.path.exists(path) else []:
        d = json.loads(line)
        runs[d["deck"]].append(d["warn"])
    rows = defaultdict(lambda: [set(), 0, 0])  # 資料、出た、残った
    for deck, ws in runs.items():
        for k in {k for w in ws for k in w}:
            seen = {h for w in ws for h in w.get(k, [])}
            rows[k][0].add(deck)
            rows[k][1] += len(seen)
            rows[k][2] += len(seen & set(ws[-1].get(k, [])))
    out = sorted(((k, len(a), b, c) for k, (a, b, c) in rows.items()), key=lambda x: (-x[3] / x[2], -x[2]))
    print(f"確認 {sum(map(len, runs.values()))} 回・資料 {len(runs)} 本\n規則\t資料\t出た\t残った（最後の確認まで）")
    for x in out:
        print("\t".join(map(str, x)))
    return out


def selftest():
    import contextlib, io, tempfile
    from pathlib import Path
    assert abs(contrast("FFFFFF", "000000") - 21) < 0.01
    assert abs(contrast("7D8E95", "F5F7F8") - 3.16) < 0.02
    assert WARN["和欧間のスペース抜け"].search("2026年") and not WARN["和欧間のスペース抜け"].search("2026 年")
    assert WARN["空疎な言い回し"].search("業務効率化を実現する") and not WARN["空疎な言い回し"].search("実現の条件")
    assert HARD["絵文字"].search("完了 ✅") and not HARD["絵文字"].search("○ × △")
    assert HARD["長いダッシュ"].search("— 売っていない") and not HARD["長いダッシュ"].search("—")
    assert not WARN["和欧間のスペース抜け"].search("Apps・Lakebase")
    assert WARN["英語の大文字ラベル"].search("KEY POINTS") and not WARN["英語の大文字ラベル"].search("F9F7F4")  # 色の値はラベルでない
    assert HARD["差し替えの仮ページ"].search("差し替え：紹介資料 p.10") and "差し替えの仮ページ" not in WARN
    w = Report()  # 言い回し（yomiyasu）: 名前は YOMI の名前。見出しの読点はスライドだけ。英字だけの文と、残す読点（条件）は出さない
    for t in ("4 つの構成の比べ", "前の版のファイルを書き換える", "Run the build"):
        w.wording("p1", t)
    for t in ("費用は、コンピュートの CU 時間で見積もる", "急ぎなら、電話で連絡する"):
        w.wording("p1", t, one_line=True)
    w.wording("p3", "監査ログは、すべての操作を記録し、あとから誰が何をしたかを追えるようにする。保存の期間は 1 年")  # 折り返す本文の読点は出さない
    w.wording("p4", "結果を受け取る。\v今回の比べをする", one_line=True)
    w.wording("段落 1", "費用は、コンピュートの CU 時間で見積もる", slides=False)
    w.wording("p2", "出典: 前の版の仕組みの比べ（https://example.com）")
    assert {k: len(v) for k, v in w.hits.items() if v} == {"動詞を名詞にした語": 2, "直訳の語": 1, SLIDE_COMMA: 1}, dict(w.hits)
    assert "\v" not in w.hits["動詞を名詞にした語"][1] and w.hits["動詞を名詞にした語"][1].startswith("p4: ")
    assert w.hits["動詞を名詞にした語"][0] == "p1: 「4 つの構成の比べ」（の比べ）" and "（版）" in w.hits["直訳の語"][0]
    # 記録と集計: ページがずれても同じ指摘は同じもの。最後の確認で消えたものは残ったに数えない。要修正は記録しない
    with tempfile.TemporaryDirectory() as tmp:
        log, a, b = os.path.join(tmp, "runs.jsonl"), Report(), Report()
        a.hits["あおり"] += ["p3: 「このままでは」", "p5: 「乗り遅れ」"]
        a.hits["絵文字"] += ["p2: 「✅」"]
        b.hits["あおり"] += ["p4: 「このままでは」"]
        log_run(a, "d1", log), log_run(b, "d1", log), log_run(b, "d2", log)
        with contextlib.redirect_stdout(io.StringIO()):
            assert stats(log) == [("あおり", 2, 3, 2)]
    with tempfile.TemporaryDirectory() as tmp:  # load_facts はプラグインの refs.py をパスで読む
        Path(tmp, "構成案.md").write_text("## 出典の表\n\n| ID | 言うこと | 種類 | 出典 | 確認 |\n|---|---|---|---|---|\n| F1 | 40% | 数字 | S1 | 済 |\n")
        assert load_facts(tmp) == "40%" and load_facts(os.path.join(tmp, "nothing")) is None  # 資料のフォルダの出典の表を読み、構成案も台帳もなければ None
    assert not_in_facts(["売上は 1,200 億円", "３．２倍", "12%"], "1200 億円、3.2 倍") == ["12%"]  # 桁区切り・全角はそろえ、表にない値だけを出す
    assert not_in_facts(["40.0 %", "0.60 ドル", "100 件", "3.2 倍"], "40%、0.6 ドル、100.0 件、3.24 倍") == ["3.2 倍"]  # 小数の終わりの 0 は見ない。丸めた値は出す
    # ワークスペースの点検: HARD の名前だけ要修正になる。recipes/ の下のどのレシピのフォルダの checks.py も、持っている関数（slides・doc）だけ
    with tempfile.TemporaryDirectory() as ws, contextlib.chdir(ws), contextlib.redirect_stdout(io.StringIO()):
        Path(ws, "desk.toml").write_text("")
        Path(ws, "recipes", "brand").mkdir(parents=True)
        Path(ws, "recipes", "brand", "checks.py").write_text(
            'HARD = {"禁止の語"}\ndef slides(p, r):\n    r.hits["禁止の語"].append("p1")\n    r.hits["気になる語"].append("p2")\n')
        gapi.find_config.cache_clear()
        r = Report()
        assert workspace_checks("slides", {}, r) == 1 and r.hits["気になる語"] and workspace_checks("doc", {}, Report()) == 0
        Path(ws, "recipes", "group", "proposal").mkdir(parents=True)
        Path(ws, "recipes", "group", "proposal", "checks.py").write_text('HARD = {"文書の語"}\ndef doc(doc, r):\n    r.hits["文書の語"].append("段落 1")\n')
        Path(ws, "recipes", "brand", "checks.py").write_text('def doc(doc, r):\n    r.hits["社名"].append("段落 2")\n    r.hits["文書の語"].append("段落 3")\n')  # 同じ名前に、HARD にしないファイルが先に足しても
        Path(ws, "recipes", "slide_checks").mkdir()
        Path(ws, "recipes", "slide_checks", "checks.py").write_text("import lint\ndef slides(p, r):\n    pass\n")  # 前の雛形の、頭で import するスライドの点検は、ドキュメントの lint では飛ばす
        Path(ws, "recipes", "proposal", "templates", "t").mkdir(parents=True)
        Path(ws, "recipes", "proposal", "templates", "t", "checks.py").write_text("raise SystemExit('テンプレートの中は読まない')\n")
        assert workspace_checks("doc", {}, r := Report()) == 1 and r.hits["社名"] and r.hits["文書の語"] and r.extra_hard == {"文書の語"} and r.hits["文書の語"] == ["段落 3", "段落 1"]  # HARD はそのファイルの名前だけ（数えるのは、そのファイルが足したものだけ）
    gapi.find_config.cache_clear()
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if a == ["--stats"]:
        stats()
        sys.exit(0)
    sys.exit(__doc__)
