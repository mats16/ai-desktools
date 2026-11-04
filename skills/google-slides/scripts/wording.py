#!/usr/bin/env python3
"""日本語の点検: 組んだ資料の保存版を読み、言い回しの指摘を場所つきで出し、直したあとに読み直して、意味の変わる恐れと、まだ判断していない指摘を数える。
文を集めるのは道具（スライドは gslides.py wording、ドキュメントは docs.py wording）で、ここは集めた文を見て、資料のフォルダの wording.json に残す。
持ち主は google-slides。google-docs は写しを持つ（tests/skills/check.py --sync）。標準ライブラリと、同じフォルダの textlint.py・yomiyasu/ だけ。
usage: wording.py <資料のフォルダ>                            今の点検の状態（wording.json）
       wording.py keep <資料のフォルダ> <ID> ... --why <理由>   言い回しの指摘（W…）を直さずに残す（その文のハッシュに結ぶ。文が変われば判断は消える）
       wording.py ask  <資料のフォルダ> <ID> ... --why <問い>   指摘か恐れをユーザーに聞く（渡すときの問いの一覧へ）
       wording.py ok   <資料のフォルダ> <ID> ... --why <理由>   意味の変わる恐れ（R…）を確かめ、変えてよいとした
       （--selftest で自己確認）
決め方（2026-11-04 の「決めたこと」）: 指摘と判断は文の中身のハッシュで結ぶ（翻訳の確認の道具が区切りごとの「無視」を、区切りが変わると消すのと同じ）。
直したあとは、前に通した文（base）と今の文を比べ、守る語（数・URL・コード・英字の語・かぎかっこの中・否定・語と助詞の組）の崩れと、yomiyasu_diff の
意味の変わる恐れを出す。恐れが残るうちは base を進めない（2 度目に直したときに 1 度目の崩れが見えなくならないように）。"""
import argparse, collections, contextlib, difflib, functools, hashlib, importlib.util, io, json, os, re, sys, time, unicodedata

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textlint  # noqa: E402

STATE = "wording.json"  # 資料のフォルダ（build/ の親）に置く。flow.py（deck-workflow）が事実として読む
MAX_ROUNDS = 2  # 書き直しの回の上限。yomiyasu の手順は「直すのは 1 回、直したら検査をもう一度、そのあとは本文を変えない」。1 回は直しの副作用の分
# [deck-lint-028] 作ったあとの日本語の点検の規則: lint の言い回しの要確認（deck-lint-027）と textlint の日本語の文の規則。指摘は文のハッシュに結び、判断（keep・ask・ok）は文が変われば消える
RULES = {**{n: "書き換え" for n in ("動詞を名詞にした語", "直訳の語", "たとえの動詞", "空疎な言い回し", "あおり")},
         textlint.SLIDE_COMMA: "区切り", "和欧間のスペース抜け": "表記", "約物の前後のスペース": "表記"}  # 点検する規則と直し方の種類
JA_WARN = ("空疎な言い回し", "あおり", "和欧間のスペース抜け", "約物の前後のスペース")  # textlint の WARN のうち日本語の文の規則（lint の要確認と同じ式）
HOW = {"書き換え": "誰が何をするかを書き直す（deck-content-065、deck-writing）。言い分・数・順が変わるなら直さずに ask",
       "区切り": "読点を外すか、語の順を変える。条件・理由・並びの読点と、外すと読み違える読点は keep",
       "表記": "表記だけを直す（語は変えない）。製品名・組織名の正式な表記（カタカナと英字を詰めて書く名前など）は keep"}
REREAD = "書き換えの読み比べ（言い分・言い切りの強さ・慣用句）"  # 守る語が崩れていなくても、意味を伴う書き換えは人が読み比べる（校正の赤字照合。専門家役のレビューで、語の突き合わせが拾えない改悪が 3 件あった）
NEG = re.compile(r"な[いくかけ](?![がりれ])|ず(?![つっ])|ぬ(?![けぐ])|ません|ぬき|不(?=[一-鿿])|非(?=[一-鿿])|無(?=[一-鿿])|未(?=[一-鿿])")  # 否定の印（少ない・危ないは同じ語が残れば数は変わらない）
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9.+#_/-]*[A-Za-z0-9+#]|[A-Za-z]")  # 英字の語（製品名・社名・コードの名前）
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
CODE = re.compile(r"`[^`]+`")
PARTICLE = re.compile(r"(?<![A-Za-z0-9.ァ-ヺー])([A-Za-z][A-Za-z0-9.+#_-]*|[ァ-ヺー]{2,}|\d+(?:\.\d+)?)\s?(?:社|さん|様|部|チーム)?\s?(が|は|に|から|より|と)")  # 語と、その後の助詞（誰が・誰に・誰と）。を・へは目的と向きで、書き直しでよく変わるので見ない


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short(*parts):
    return hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:6]


@functools.cache
def rules_version():
    """点検の結果を変えるもの（このファイル・textlint.py・yomiyasu の lint）の中身。変われば、前の結果の写しを使わない。"""
    return short(*(open(os.path.join(HERE, *p), encoding="utf-8").read() for p in (("wording.py",), ("textlint.py",), ("yomiyasu", "scripts", "yomiyasu_lint.py"))))


@functools.cache
def yomiyasu_diff():
    """yomiyasu の yomiyasu_diff.py をパスで読む（textlint.yomiyasu と同じ。中は直さない）。"""
    spec = importlib.util.spec_from_file_location("yomiyasu_diff", os.path.join(HERE, "yomiyasu", "scripts", "yomiyasu_diff.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unit(where, text, key, kind, slides=True, one_line=False, page=None, obj=None):
    """点検する 1 つの文（段落・セル・ノートの行）。key は直す前後を組にするページの名前（ページのファイル名か p<番号>。ドキュメントは doc）。"""
    return {"where": where, "page": page, "key": key, "kind": kind, "text": text, "slides": slides, "one_line": one_line, "obj": obj, "file": None, "loc": None}


def collector(report, units, key_of, kind_of=lambda kw: "本文"):
    """lint の Report の wording を、文を集める関数に差し替える。lint が言い回しを見る文（フッター・等幅・引用とコードの段落・出典の行を外したもの）と、同じ文を点検する。
    key_of(where, kw) はページの名前、kind_of(kw) は文の種類。"""
    def wording(where, text, slides=True, one_line=False, **kw):
        if textlint.wording_text(text):
            m = re.match(r"p(\d+)", where)
            units.append(unit(where, text, key_of(where, kw), kind_of(kw), slides, one_line, int(m.group(1)) if m else None, kw.get("obj")))
    report.wording = wording
    return report


KEEP = ("where", "key", "kind", "text", "slides", "one_line", "file", "loc")  # wording.json に残す文の項目（前に通した文と比べるときにも、同じ規則で見直す）


def check_unit(u):
    """1 つの文の指摘: [(規則の名前, 抜き出し, 当たった言い方)]。同じ規則の同じ言い方は 1 つにまとめる。"""
    out = list(textlint.yomi(u["text"], u.get("slides", True), u.get("one_line", False)))
    text = textlint.wording_text(u["text"])
    if text and u.get("kind") != "ノート":  # ノートは話す文なので、表記の規則（スペース・約物）と、スライドの空疎な言い回しは見ない
        inside = [m.span() for m in textlint.QUOTED.finditer(text)]
        for name in JA_WARN:
            for m in textlint.WARN[name].finditer(text):
                if not any(a <= m.start() and m.end() <= b for a, b in inside):
                    out.append((name, text[max(0, m.start() - 12):m.end() + 12].strip(), m.group()))
    return list(dict.fromkeys(out))


def finding_id(rule, unit_sha, said):
    return "W" + short(rule, unit_sha, said)


def tokens(text):
    """守る語: 種類 → 語の数え上げ。かぎかっこの中は語を数えず、中身ごと 1 つの語にする（引用の中の書き換えを、英字の語の崩れと二重に出さない）。"""
    t = unicodedata.normalize("NFKC", text)
    quotes = textlint.QUOTED.findall(t)
    rest = textlint.QUOTED.sub(" ", t)
    codes = CODE.findall(rest)
    rest = CODE.sub(" ", rest)
    urls = textlint.URL.findall(rest)
    rest = textlint.URL.sub(" ", rest)
    return {"数": collections.Counter(n.replace(",", "") for n in NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3})", "", rest))),
            "英字の語（固有名詞・コード）": collections.Counter(LATIN.findall(rest)),
            "かぎかっこの中": collections.Counter(quotes), "コード": collections.Counter(codes), "URL": collections.Counter(urls),
            "否定の数": collections.Counter({"否定": len(NEG.findall(rest))}) if NEG.search(rest) else collections.Counter(),
            "語と助詞の組（誰が・誰に）": collections.Counter(f"{a}{b}" for a, b in PARTICLE.findall(rest))}


def guard(old, new):
    """直す前後の文（1 つの組）の守る語の崩れ: [(種類, 詳しく)]。語と助詞の組は、語の数え上げが同じときだけ見る（語が変われば、ほかの種類で出ている）。"""
    a, b, out = tokens(old), tokens(new), []
    for kind in a:
        if a[kind] != b[kind]:
            if kind == "語と助詞の組（誰が・誰に）" and (a["英字の語（固有名詞・コード）"] != b["英字の語（固有名詞・コード）"] or a["数"] != b["数"]):
                continue
            lost, got = a[kind] - b[kind], b[kind] - a[kind]
            out.append((kind, "・".join(f"-{x}" for x in lost.elements()) + (" " if lost and got else "") + "・".join(f"+{x}" for x in got.elements())))
    return out


YOMI_RISK = {"number": "数", "negation": "否定の数", "quote": "かぎかっこの中", "protected": "守る語（URL・コード）", "certainty": "確度（言い切り・推量）",
             "modality_review": "できる・すべき・してよい", "modality": "できる・すべき・してよい", "subject": "主語", "hearsay": "伝聞", "request": "依頼", "sentence_type": "文の種類（事実・意見・推量・依頼）"}


def lines_of(units):
    """yomiyasu_diff に渡す文と、行の番号（1 から）→ (ページの名前, そのページの中の番号)。ページごとに見出しの行を置く。"""
    out, where, last, seen = [], {}, None, collections.Counter()
    for u in units:
        if u["key"] != last:
            out.append(f"## {u['key']}")
            last = u["key"]
        out.append(u["text"].replace("\n", " ").replace("\v", " "))
        where[len(out)] = (u["key"], seen[u["key"]])
        seen[u["key"]] += 1
    return "\n".join(out) + "\n", where


def risks(base, cur):
    """前に通した文（base）と今の文（cur）を、ページごとに組にして比べる。[{id, key, old, new, kind, detail, where, file, loc}]。
    組は difflib の並びで決め、置き換え・消した・足したの塊ごとに守る語を比べる。yomiyasu_diff の意味の変わる恐れも、同じ塊に寄せる。"""
    by = lambda us: collections.OrderedDict((k, [u for u in us if u["key"] == k]) for k in dict.fromkeys(u["key"] for u in us))
    old, new, blocks = by(base), by(cur), []
    for k in dict.fromkeys(list(old) + list(new)):
        o, n = old.get(k, []), new.get(k, [])
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [u["text"] for u in o], [u["text"] for u in n], autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            pairs = [((i, i + 1), (j, j + 1)) for i, j in zip(range(i1, i2), range(j1, j2))] if i2 - i1 == j2 - j1 else [((i1, i2), (j1, j2))]  # 同じ数なら 1 文ずつ組にする
            for (a, b), (c, d) in pairs:
                blocks.append({"key": k, "i": (a, b), "j": (c, d), "old": "\n".join(u["text"] for u in o[a:b]), "new": "\n".join(u["text"] for u in n[c:d]),
                               "at": (n[c:d] or o[a:b])[0]})
    if not blocks:
        return []
    found = collections.OrderedDict()

    def add(b, kind, detail):
        rid = "R" + short(kind, b["key"], b["old"], b["new"])
        found.setdefault(rid, {"id": rid, "key": b["key"], "old": b["old"], "new": b["new"], "kind": kind, "detail": detail,
                               "where": b["at"]["where"], "file": b["at"].get("file"), "loc": b["at"].get("loc")})
    for b in blocks:
        for kind, detail in guard(b["old"], b["new"]):
            add(b, kind, detail)
        rules = lambda text: {r for t in text.split("\n") for r, *_ in check_unit({**b["at"], "text": t}) if RULES.get(r) == "書き換え"}  # 前の文も今の文と同じ種類（ノートか）で見る
        if b["old"] and b["new"] and (gone := sorted(rules(b["old"]) - rules(b["new"]))):
            add(b, REREAD, "・".join(gone))  # 書き換えの指摘を直した（消えた）。直す前と後を読み、同じことを同じ強さで言っているかを確かめて ok
    (ot, ow), (nt, nw) = lines_of(base), lines_of(cur)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        got = yomiyasu_diff().diff(ot, nt)
    for r in got.get("meaning_risks", []):
        k, idx = nw.get(r.get("new_line")) or ow.get(r.get("old_line")) or (None, None)
        side = "j" if r.get("new_line") in nw else "i"
        b = next((b for b in blocks if b["key"] == k and b[side][0] <= idx < max(b[side][1], b[side][0] + 1)), None)
        if b:
            add(b, YOMI_RISK.get(r.get("kind"), r.get("kind", "?")), r.get("subkind") or "")
    return list(found.values())


def load(folder):
    p = os.path.join(folder, STATE)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"{p} を読めない（{e}）。消すと点検は 未実施 に戻る")
    return st if isinstance(st, dict) else {}


def save(folder, st):
    p = os.path.join(folder, STATE)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


def summarize(st):
    """最後の点検と判断から、今の状態を決める。済み は、読めない文・通らない理由・未判断の指摘・未確認の恐れがどれもないとき（聞く は残ってよく、渡すときの問いに入る）。"""
    last, dec = st.get("last") or {}, st.get("decisions", {})
    fs, rs = last.get("findings", []), last.get("risks", [])
    status = lambda x: dec.get(x["id"], {}).get("status")
    open_f = [f for f in fs if status(f) not in ("keep", "ask")]
    open_r = [r for r in rs if status(r) not in ("ok", "ask")]
    s = {"状態": "済み" if last and not (open_f or open_r or last.get("problems")) else "未完" if last else "未実施",
         "文": len(last.get("units", [])), "指摘": len(fs), "未判断": len(open_f), "残す": sum(status(f) == "keep" for f in fs),
         "聞く": sum(status(x) == "ask" for x in fs + rs), "直した": last.get("fixed", 0), "恐れ": len(rs), "未確認": len(open_r),
         "書き直し": st.get("rounds", 0), "上限": MAX_ROUNDS, "通らない理由": last.get("problems", []), "revision": last.get("revision"), "ts": last.get("ts")}
    return s, open_f, open_r


def place(x):
    return f"{x['where']}" + (f"（build/{x['file']}" + (f" {x['loc']}" if x.get("loc") else "") + "）" if x.get("file") else "（build/ にこの文がない: 直したが組んでいないか、画面で直したか、部品が足した文）")


def show(st, tool="wording"):
    s, open_f, open_r = summarize(st)
    last, dec = st.get("last") or {}, st.get("decisions", {})
    if not last:
        print("日本語の点検: 未実施（gslides.py wording <URL> か docs.py wording <URL> を build/ で回す）")
        return s
    print(f"日本語の点検: 文 {s['文']}・指摘 {s['指摘']}（未判断 {s['未判断']}・残す {s['残す']}・聞く {sum(dec.get(f['id'], {}).get('status') == 'ask' for f in last.get('findings', []))}）"
          f"・前の点検から直した {s['直した']}・意味の変わる恐れ {s['恐れ']}（未確認 {s['未確認']}）・書き直し {s['書き直し']} / {s['上限']} 回")
    for f in last.get("findings", []):
        d = dec.get(f["id"], {})
        mark = {"keep": "残す", "ask": "聞く"}.get(d.get("status"), "未判断")
        print(f"[{mark}] {f['id']} {place(f)} {f['rule']}〔{RULES.get(f['rule'], '?')}〕「{f['excerpt']}」" + (f"（{f['said']}）" if f.get("said") else "")
              + (f" ×{f['places']}" if f.get("places", 1) > 1 else "") + (f" — {d['why']}" if d.get("why") else ""))
    for r in last.get("risks", []):
        d = dec.get(r["id"], {})
        mark = {"ok": "確かめた", "ask": "聞く"}.get(d.get("status"), "未確認")
        one = lambda t: " ⏎ ".join(t.split("\n"))[:80]
        print(f"[{mark}] {r['id']} {place(r)} {r['kind']}（{r['detail']}）: 「{one(r['old'])}」→「{one(r['new'])}」" + (f" — {d['why']}" if d.get("why") else ""))
    for p in s["通らない理由"]:
        print(f"[通らない] {p}")
    if open_f and s["書き直し"] >= MAX_ROUNDS:
        print(f"書き直しが上限（{MAX_ROUNDS} 回）に達した。残る {len(open_f)} 件は書き直さず、keep（理由）か ask（問い）で閉じる（警告を消すためだけに言い換えを重ねない）")
    hint = {"書き換え": 0, "区切り": 0, "表記": 0}
    for f in open_f:
        hint[RULES.get(f["rule"], "書き換え")] += 1
    for k, n in hint.items():
        if n:
            print(f"直し方〔{k}〕{n} 件: {HOW[k]}")
    if s["状態"] == "済み":
        print("状態: 済み" + (f"（聞く {s['聞く']} 件は、渡すときの問いの一覧に入れる）" if s["聞く"] else "") + f"。保存版のリビジョン {s['revision']} で点検した")
    else:
        print(f"状態: 未完。ページの JSON（ドキュメントは doc.md）を直して組み、check で画像を見てから {tool} をもう一度回す。直さないものは "
              f"wording.py keep・ask、変えてよい恐れは wording.py ok（<資料のフォルダ> <ID> … --why …）で閉じる")
    return s


def run(folder, kind, url, revision, units, files, problems=(), tool="wording"):
    """保存版から集めた文（units。file・loc は道具が埋める）を点検し、wording.json を書き、状態を出す。済みなら True。
    files は点検したときのファイル（資料のフォルダからのパス → sha256）。flow.py が、点検のあとに変わったかを見る。problems は道具が見つけた、通らない理由。"""
    st, t0 = load(folder), time.time()
    if st.get("url") not in (None, url):  # 別の資料の記録は使わない（作り直した資料など）
        st = {}
    prev, cache = st.get("last") or {}, st.get("cache", {}) if st.get("rules") == rules_version() else {}
    for u in units:
        u["sha"] = sha(u["text"])
    hits, unreadable = collections.OrderedDict(), []
    for u in units:
        ck = f"{u['sha']}:{int(u['slides'])}{int(u['one_line'])}{u['kind'] == 'ノート'}"
        if ck not in cache:
            try:
                cache[ck] = check_unit(u)
            except Exception as e:  # noqa: BLE001  調べられない文は通さない（飛ばした文を済みにしない）
                unreadable.append(f"{u['where']}: 調べられない（{type(e).__name__}: {e}）")
                continue
        for rule, excerpt, said in cache[ck]:
            fid = finding_id(rule, u["sha"], said)
            if fid in hits:
                hits[fid]["places"] += 1
            else:
                hits[fid] = {"id": fid, "rule": rule, "excerpt": excerpt, "said": said, "unit": u["sha"], "places": 1,
                             **{k: u[k] for k in ("where", "file", "loc", "obj")}}
    base = st.get("base") or units
    try:
        rs = risks(base, units)
    except Exception as e:  # noqa: BLE001
        rs, unreadable = [], unreadable + [f"直す前と後を比べられない（{type(e).__name__}: {e}）"]
    dec = st.get("decisions", {})
    prev_open = {f["unit"] for f in prev.get("findings", []) if dec.get(f["id"], {}).get("status") not in ("keep", "ask")}
    now = {u["sha"] for u in units}
    rounds = st.get("rounds", 0) + bool(prev_open - now)  # 前に未判断の指摘があった文を書き換えた回を数える
    fixed = len({f["id"] for f in prev.get("findings", [])} - set(hits))
    last = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "revision": revision, "units": [{k: u[k] for k in KEEP + ("sha",)} for u in units],
            "findings": list(hits.values()), "risks": rs, "fixed": fixed, "problems": list(problems) + unreadable, "files": files, "seconds": None}
    st = {"version": 1, "kind": kind, "url": url, "rules": rules_version(), "rounds": rounds, "max_rounds": MAX_ROUNDS,
          "base": st.get("base") or [{k: u[k] for k in KEEP} for u in units],
          "decisions": dec, "last": last, "cache": {k: v for k, v in cache.items() if k.split(":")[0] in now}}  # 今の文の結果だけを残す（増え続けない）
    s, _, open_r = summarize(st)
    if not open_r and not unreadable:  # 恐れが残るうちは前に通した文を進めない
        st["base"] = [{k: u[k] for k in KEEP} for u in units]
    if s["状態"] == "済み":
        st["rounds"] = 0
    last["seconds"] = round(time.time() - t0, 2)
    st["summary"], _, _ = summarize(st)
    save(folder, st)
    print(f"（保存版 {url} の文 {len(units)}。{last['seconds']} 秒）")
    show(st, tool)
    return st["summary"]["状態"] == "済み"


def decide(folder, status, ids, why):
    """指摘（W…）か恐れ（R…）の判断を残す。ID は最後の点検にあるものだけ。keep は W だけ、ok は R だけ。"""
    st = load(folder)
    last = st.get("last") or sys.exit(f"{os.path.join(folder, STATE)} がない（点検は未実施）。先に gslides.py wording か docs.py wording を回す")
    known = {x["id"]: x for x in last.get("findings", []) + last.get("risks", [])}
    bad = [i for i in ids if i not in known or (status == "keep" and not i.startswith("W")) or (status == "ok" and not i.startswith("R"))]
    bad and sys.exit(f"最後の点検にない ID か、使えない判断（keep は W…、ok は R…、ask はどちらも）: {', '.join(bad)}")
    why.strip() or sys.exit("--why に理由（ask は問い）を書く")
    for i in ids:
        st.setdefault("decisions", {})[i] = {"status": status, "why": " ".join(why.split()), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    s, _, open_r = summarize(st)
    if not open_r and not (last.get("problems")):  # 恐れを確かめ終えたら、今の文を前に通した文にする（次の点検は、ここからの違いを見る）
        st["base"] = [{k: u.get(k) for k in KEEP} for u in last.get("units", [])]
    if s["状態"] == "済み":
        st["rounds"] = 0
    st["summary"], _, _ = summarize(st)
    save(folder, st)
    show(st)


def selftest():
    import tempfile
    textlint.yomiyasu()
    u = lambda key, text, **kw: unit(kw.pop("where", key), text, key, kw.pop("kind", "本文"), **kw)
    # 指摘: lint の要確認と同じ規則。かぎかっこの中・出典の行・英字だけの文は出さない。ノートは表記の規則を見ない
    assert [x[0] for x in check_unit(u("p1", "4 つの構成の比べ"))] == ["動詞を名詞にした語"]
    assert check_unit(u("p1", "顧客は「前の版の比べ」と言った")) == [] and check_unit(u("p1", "出典: 前の版の比べ")) == [] and check_unit(u("p1", "Run the build")) == []
    assert [x[0] for x in check_unit(u("p1", "2026年に始める"))] == ["和欧間のスペース抜け"] and check_unit(u("p1", "2026年に始める", kind="ノート")) == []
    assert [x[0] for x in check_unit(u("p1", "費用は、CU 時間で見積もる", one_line=True))] == [textlint.SLIDE_COMMA] and check_unit(u("p1", "費用は、CU 時間で見積もる")) == []
    # 守る語の崩れ（改悪は出し、言い回しだけを直したものは出さない）
    bad = [("検証は不要ではない", "検証は不要だ"), ("価格は月 100 円", "価格は月 120 円"), ("Databricks の Unity Catalog で管理する", "Databricks のカタログで管理する"),
           ("「書き方の取り決め」に書く", "「書き方の決まり」に書く"), ("A 社が B 社に渡す", "B 社が A 社に渡す"), ("詳しくは https://example.com/a", "詳しくは https://example.com/b"),
           ("`slides.py build` で組む", "slides.py で組む"), ("移行しない", "移行する")]
    good = [("4 つの構成の比べ", "4 つの構成を比べる"), ("前の版のファイル", "前のバージョンのファイル"), ("費用は、CU 時間で見積もる", "費用は CU 時間で見積もる"),
            ("AI がデータを語る", "AI がデータの傾向を示す"), ("2026年に始める", "2026 年に始める"), ("Spark 3.5 で動かさない", "Spark 3.5 では動かさない")]
    assert all(guard(a, b) for a, b in bad), [(a, b) for a, b in bad if not guard(a, b)]
    assert not any(guard(a, b) for a, b in good), [(a, b, guard(a, b)) for a, b in good if guard(a, b)]
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out:
        page = lambda *texts, key="p01": [u(key, t, where=f"p{i}") for i, t in enumerate(texts, 1)]
        url = "https://docs.google.com/presentation/d/x/edit"
        # 1 回目: 指摘は場所つき・未判断で、通らない
        assert not run(d, "slides", url, "r1", page("4 つの構成の比べ", "顧客は「前の版の比べ」と言った", "検証は不要ではない"), {"build/p01.json": "a"})
        st = load(d)
        (f,) = st["last"]["findings"]
        assert f["rule"] == "動詞を名詞にした語" and f["id"] == finding_id("動詞を名詞にした語", sha("4 つの構成の比べ"), "の比べ") and st["summary"]["未判断"] == 1 and st["summary"]["状態"] == "未完"
        # 同じ文で回し直しても、ID は変わらず、増えない（重複しない）。書き直しの回も数えない
        run(d, "slides", url, "r1", page("4 つの構成の比べ", "顧客は「前の版の比べ」と言った", "検証は不要ではない"), {})
        assert [x["id"] for x in load(d)["last"]["findings"]] == [f["id"]] and load(d)["rounds"] == 0
        # 直す: 指摘は消え、直したに数える。ついでに否定を反転させた改悪は、恐れとして出て、通らない
        assert not run(d, "slides", url, "r2", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要だ"), {})
        st = load(d)
        assert st["last"]["findings"] == [] and st["last"]["fixed"] == 1 and st["rounds"] == 1 and sorted(r["kind"] for r in st["last"]["risks"]) == sorted(["否定の数", REREAD])
        neg = next(r for r in st["last"]["risks"] if r["kind"] == "否定の数")
        assert neg["where"] == "p3" and neg["old"] == "検証は不要ではない"  # 続けて直した文も、1 文ずつ組にして場所を出す
        reread = next(r for r in st["last"]["risks"] if r["kind"] == REREAD)
        assert reread["where"] == "p1" and reread["detail"] == "動詞を名詞にした語"  # 書き換えの指摘を直した文は、守る語が崩れていなくても読み比べる
        decide(d, "ok", [reread["id"]], "比べる対象と強さは同じ")
        rid = neg["id"]
        # 2 度目に直すときに否定とかかわらない語を変えても、前に通した文と比べるので、恐れは消えない
        assert not run(d, "slides", url, "r3", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要だと考える"), {})
        assert "否定の数" in [r["kind"] for r in load(d)["last"]["risks"]]
        # 戻せば恐れは消え、済みになる（前に通した文が今の文になる）
        assert run(d, "slides", url, "r4", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない"), {})
        assert load(d)["summary"]["状態"] == "済み" and load(d)["rounds"] == 0
        # 残す判断は文のハッシュに結ぶ: 文が変われば判断は消え、未判断に戻る（失効）
        run(d, "slides", url, "r5", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順に戻す"), {})
        (g,) = load(d)["last"]["findings"]
        assert g["rule"] == "直訳の語"
        decide(d, "keep", [g["id"]], "製品の版（エディション）の意味")
        assert load(d)["summary"]["状態"] == "済み" and load(d)["summary"]["残す"] == 1
        run(d, "slides", url, "r6", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す"), {})
        assert load(d)["summary"]["未判断"] == 1 and load(d)["summary"]["状態"] == "未完"
        # 判断の誤り: 知らない ID、keep に R、理由なし
        for args in (("keep", ["Wzzzzzz"], "x"), ("keep", [rid], "x"), ("ask", [load(d)["last"]["findings"][0]["id"]], " ")):
            try:
                decide(d, *args)
                raise AssertionError(args)
            except SystemExit:
                pass
        decide(d, "ask", [load(d)["last"]["findings"][0]["id"]], "「版」はエディションの意味か")
        s = load(d)["summary"]
        assert s["状態"] == "済み" and s["聞く"] == 1  # 聞くは閉じた扱いで、問いの一覧に入る
        # 恐れを確かめる（ok）: 意図して数を変えたもの
        run(d, "slides", url, "r7", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す", "価格は月 120 円"), {})
        run(d, "slides", url, "r8", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す", "価格は月 100 円"), {})
        (r,) = load(d)["last"]["risks"]
        assert r["kind"] == "数" and load(d)["summary"]["状態"] == "未完"
        decide(d, "ok", [r["id"]], "出典の表 F3 の値に合わせた")
        assert load(d)["summary"]["状態"] == "済み"
        run(d, "slides", url, "r9", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す", "価格は月 100 円"), {})
        assert load(d)["last"]["risks"] == [] and load(d)["summary"]["状態"] == "済み"  # 確かめたあとは、そこからの違いだけを見る
        # 文を消しても、ページごと消しても比べられる（消えた文の守る語は恐れに出る）
        run(d, "slides", url, "r9b", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す", "価格は月 100 円") + page("仕組みを比べる", key="p09"), {})
        assert run(d, "slides", url, "r9c", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す"), {}) is False
        assert [r["kind"] for r in load(d)["last"]["risks"]] == ["数"] and not load(d)["last"]["problems"]
        decide(d, "ok", [load(d)["last"]["risks"][0]["id"]], "価格の行は 10 で聞く")
        assert load(d)["summary"]["状態"] == "済み" and len(load(d)["cache"]) == 4  # 結果の写しは今の文の分だけ
        # 道具が見つけた通らない理由（画面で直された・画像を取っていない）は、指摘がなくても通さない
        assert not run(d, "slides", url, "r10", page("4 つの構成を比べる", "顧客は「前の版の比べ」と言った", "検証は不要ではない", "前の版の手順へ戻す", "価格は月 100 円"), {}, ["組んだあとに画面で直された"])
        # 書き直しの上限: 未判断の指摘のある文を書き換え続けても、上限のあとは keep・ask で閉じるように出す（回り続けない）
        for i, t in enumerate(("仕組みの比べ", "仕組みの比べをする", "全体の仕組みの比べ")):
            run(d, "slides", url, f"s{i}", page(t, key="p02"), {})
        assert load(d)["rounds"] >= MAX_ROUNDS and "上限" in out.getvalue()
        # 別の資料の記録は使わない
        run(d, "slides", "https://docs.google.com/presentation/d/other/edit", "o1", page("仕組みを比べる", key="p02"), {})
        assert load(d)["rounds"] == 0 and load(d)["decisions"] == {} and load(d)["last"]["risks"] == []
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
        assert summarize(load(d))[0]["状態"] == "未実施"  # 回していなければ未実施（済みにしない）
        report = type("R", (), {})()
        units = []
        collector(report, units, lambda where, kw: "p01")
        report.wording("p3", "仕組みの比べ", one_line=True, obj="g1", table=True)
        report.wording("p3", "https://example.com")
        assert len(units) == 1 and units[0]["page"] == 3 and units[0]["obj"] == "g1"
    print("selftest ok")


def main(argv):
    if argv[:1] and argv[0] in ("keep", "ask", "ok"):
        ap = argparse.ArgumentParser(prog=f"wording.py {argv[0]}")
        ap.add_argument("folder"); ap.add_argument("ids", nargs="+"); ap.add_argument("--why", required=True)
        a = ap.parse_args(argv[1:])
        return decide(a.folder, argv[0], a.ids, a.why)
    if len(argv) == 1 and not argv[0].startswith("-"):
        st = load(argv[0])
        s = show(st)
        sys.exit(0 if s["状態"] == "済み" else 1)
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
