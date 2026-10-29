#!/usr/bin/env python3
"""定期に回す集めの作業で、どの先をいつ読むかを決め、回ごとに学ぶ（../SKILL.md）。話題（読む領域）ごとに、読む先の台帳と回の記録を
ワークスペースの .desk/crawl/<topic>/ に置く。何を選ぶか・何を書くか（関心・目的・分類）は使う側が持ち、ここには持たない。標準ライブラリだけ。
usage:
  crawl.py plan <topic> [--hours 24 | --since <ISO>] [--until <ISO>] [--explore 3]
                      今回読む先を組（子に 1 つずつ渡す単位）に分けて出す。先ごとの始まり（前に読んだ所から。取れなかった先は取れた所から）、
                      間隔で今回は読まない先、覚え書き、探索する候補、ユーザーに聞くことも出す。plan.json に残す
  crawl.py more <topic> <先の id>...   その回の中で追加に読む先（1 回に 3 つまで）を plan.json に組として足し、組の番号を出す
  crawl.py prompt <topic> <組の番号> --goal <目的の文>   その組の子への依頼文（../prompt_collect.md を埋めたもの）を出す
  crawl.py feeds <topic> [--out <file>]   kind が feed の先（RSS・Atom）を読み、子の返事と同じ形の JSON を出す
  crawl.py merge <topic> <子の返事.json>... --out <run.json>   子の返事を 1 つの回の記録の下書きにまとめる（同じ URL は 1 つにし、
                      どの先で見えたかを足す。前の回までに使われた項目には dup、題の似たものには similar を付ける）。候補の一覧を出す
  crawl.py record <topic> <run.json> [--published <出力の md>...] [--missed <取りこぼし.json>...]   回を記録する。出力のどれかに
                      URL があった項目を「使われた」にし（出力を渡さなければ、前に記録した印のまま）、取りこぼしを足す。覚え書きの足しと票、候補から follow への引き上げを当てて出す
  crawl.py report <topic> [<回の id>]   まとめの md に貼る「## 情報源」の節を出す（既定は最後の回）。直近 10 回とその前の 10 回の比べも出す
  crawl.py sources <topic> [--json]     台帳と成績の表を出す（人が読む）。--json は、ほかの話題に写す JSON（follow の先と覚え書き）
  crawl.py set <topic> <先の id> key=value...   台帳を直す（tier・name・group・pinned・url・why・created、note=<覚え書き>）
  crawl.py set <topic> --from <file.json>        台帳に読む先をまとめて足す（[{"id": …, "tier": …}, …]。sources --json の出力も読む）
  crawl.py --selftest
先の id は <kind>:<ref>。流れは <サービス>:<ref>、検索は <サービス>-search:<語>、開かれた形式は feed・web（slack:C0123456789、
slack-search:japaneast、gmail-search:label:product-news、feed:https://…/feed.xml、web:https://…、web-search:<語>、confluence:<ページ>）。"""
import difflib, html, ipaddress, json, math, re, statistics, sys, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deck-practices" / "scripts"))
import desk  # noqa: E402  ワークスペースの探し方

PROMPT = Path(__file__).resolve().parents[1] / "prompt_collect.md"
GAMMA = 0.93       # 1 回ごとに前の回の重みに掛ける数（半分になるのは約 10 回、平日の 2 週）。読む先の中身は時期で変わるので、古い回ほど軽くする
PROMOTE = 2.0      # 候補が、重みを掛けて合わせたこの数の項目で使われたら follow に上げる（自動。報告に書く）
# ponytail: 段の境目は仮の値。実際の記録が 20 回たまったら、report の比べ（取りこぼしが増えずに読む先が減るか）を見て決め直す
EVERY = ((0.5, 1), (0.25, 2), (0.0, 4))  # 1 日あたりの値打ちが、follow の先の中ほど（中央値）の何倍以上なら、何回に 1 回読むか
MIN_READS = 5     # この回数読むまでは間を空けない（1 回の空振りで 4 回に 1 回にしない）。中ほども、この回数読んだ先だけで出す
MUST_READ = timedelta(days=6)  # 前に読んでからこれを超えたら、間隔によらず読む（取り戻せる CATCHUP に収め、遅れても読み落とさない）
DROP_READS, DROP_USED = 10, 0.5  # 4 回に 1 回の follow で、最後の DROP_READS 回の読みで使われたのが DROP_USED 件未満なら、外すかを聞く（自動では外さない）
COOL = 10          # 探索して何も使われなかった候補は、この回数のあいだ探索しない（ほかの回で使われたものがあれば休ませない）
NEW_DAYS, NEW_MAX = 14, 3  # 作られてこの日数のうちの、まだ読んでいない先は、ほかの候補より先に探索する（1 回に NEW_MAX まで）
CATCHUP = timedelta(days=7)  # 前に読んだ所から取り戻す、いちばん古い始まり
MORE_MAX = 3       # その回の中で追加に読む先の数
NOTES_MAX = 5      # 子に渡す覚え書きの数（先ごと・話題ごと）。全部渡すと、回すほど依頼文が重くなる
NOTE_STALE = 30    # この回数のあいだ効いた票の付かない覚え書きは、子に渡さない（消さない。sources で見える）
SITE_MIN = 2       # 使われた項目の出典（public_url）に、この回数出た、読む先にないサイトを挙げる
TREND = 10         # report が比べる回の数（直近と、その前）
GROUP_MAX = 10     # 1 つの組（子 1 つ）に入れる先の数
TIERS = ("follow", "candidate", "dropped")
RESERVED = {"explore", "feed", "more"}  # plan と more が作る組の名前
APPLIED_KEEP = 30  # 台帳に残す「当てた覚え書きと票」の控えの回数
KEYS = {"tier", "name", "group", "pinned", "url", "why", "created"}
OLD = "scout"      # 前の名前（source-scout）の記録のフォルダ（.desk/scout/）
TRACKING = re.compile(r"^(utm_\w+|gclid|fbclid|mc_[ce]id|ref_src|trk)$")  # ref は版や枝を指すことがある（GitHub）ので外さない
URL = re.compile(r"https?://[^\s<>{}|\"'`（）「」『』【】、。，]+")
URL_TAIL = ".,;:!?*_~"  # md の文末と強調の記号（「https://x/1.」「**https://x/1**」）。URL の末尾に来ない


def md_urls(text):
    """md の中の URL。末尾の記号と、対になっていない閉じ括弧（[名前](URL) の「)」）を外す。Foo_(bar) のような対の括弧は残す。"""
    out = set()
    for u in URL.findall(text):
        while True:
            v = u.rstrip(URL_TAIL)
            for o, c in ("()", "[]"):
                if v.endswith(c) and v.count(c) > v.count(o):
                    v = v[:-1]
            if v == u:
                break
            u = v
        out.add(canon(u))
    return out
ROOT = None  # selftest がワークスペースの代わりに使う


def now():
    return datetime.now().astimezone()


def when(s):
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.astimezone()


def folder(topic):
    if not re.fullmatch(r"[\w-]+", topic):
        sys.exit(f"話題の名前は英数字と - だけ（{topic}）")
    root = ROOT or ((f := desk.locate()) and f[1]) or sys.exit(desk.missing())
    if (old := Path(root) / ".desk" / OLD).exists():  # 黙って記録が 2 か所に分かれないよう、前の名前の記録があれば止める
        sys.exit(f"前の名前（source-scout）の記録 {old} がある。状態の名前（core → follow、muted → candidate か dropped）と種類の名前"
                 f"（gmail → gmail-search、wiki → confluence などサービスの名前）が変わったので、そのままでは読めない。写してから消すか、要らなければ消す")
    return Path(root) / ".desk" / "crawl" / topic


def read_json(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def read_input(path, as_json=True):
    """引数で渡されたファイル（子の返事・回の記録・出力の md・取りこぼし・台帳に足す先）を読む。読めなければ理由を出して止める。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text) if as_json else text
    except (OSError, ValueError) as e:  # ない・読めない・UTF-8 でない・JSON でない
        sys.exit(f"{path} を読めない: {e}")


def registry(topic):
    return read_json(folder(topic) / "sources.json", {"sources": {}, "notes": [], "next_note": 1})


def runs(topic):
    p = folder(topic) / "runs.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    return sorted(rows, key=run_time)


def run_time(r):
    """回の並べ順。until（なければ id）を時刻として比べる（時差の違う文字列を文字の順に並べない）。"""
    return when(r.get("until") or r["id"])


def kind(sid):
    return sid.split(":", 1)[0]


def canon(url):
    """同じ項目の URL を 1 つにそろえる。追跡の引数・#・末尾の / を外し、ホストを小文字にする（Slack の thread_ts などほかの引数は残す）。"""
    p = urllib.parse.urlsplit(url.strip())
    slack = p.netloc.lower().endswith(".slack.com")  # Slack のリンクの cid（チャンネル）はパスと同じなので外す
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k) and not (slack and k == "cid")]
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", urllib.parse.urlencode(sorted(q)), ""))


def norm_title(t):
    return " ".join(re.sub(r"[\W_]+", " ", (t or "").lower()).split())


def keys(item):
    return {canon(u) for u in [item.get("url"), *item.get("urls", [])] if u}


def published(rows):
    """前の回までに使われた項目: URL → (回の id, 題)。"""
    out = {}
    for r in rows:
        for i in r.get("items", []):
            if i.get("used"):
                for k in keys(i):
                    out.setdefault(k, (r["id"], i.get("title", "")))
    return out


def true_misses(run):
    """その回の取りこぼし（使う側が record --missed で返したもの）のうち、候補になかったもの（候補にあって選ばれなかったものは、選ぶ側の判断で、読む先の取りこぼしではない）。"""
    seen = {k for i in run.get("items", []) for k in keys(i)}
    return [m for m in run.get("misses", []) if not keys(m) & seen]


def credits(run):
    """その回に使われた項目の手柄を、見えた先で割って配る。そこでしか見えなかった項目は 1、2 つの先で見えたら 0.5 ずつ。
    読むのをやめたら失う項目の数を見るため（ほかの先でも拾えるものは、読む理由が弱い）。取りこぼしも、元の先が分かれば 1 を付ける。
    使われた項目だけで数えると、読む量を減らす向きにしか学ばないため。"""
    c = defaultdict(float)
    for i in run.get("items", []):
        if not i.get("used"):
            continue
        srcs = sorted(set(i.get("seen_in", [])) | ({i["origin"]} if i.get("origin") else set()))
        for s in srcs:
            c[s] += 1 / len(srcs)
    for m in true_misses(run):
        if m.get("source"):
            c[m["source"]] += 1
    return c


def days(rd, run):
    """その読みが覆った日数。読みの since・until、なければ回の since・until。分からなければ 1 日。"""
    a, b = rd.get("since") or run.get("since"), rd.get("until") or run.get("until")
    return max((when(b) - when(a)).total_seconds() / 86400, 1 / 24) if a and b else 1.0


def stats(rows):
    """先ごとの成績。新しい回ほど重い（GAMMA）。n: 読んだ回、w: 手柄のあった回（1 回の手柄は 1 まで）、c: 手柄の和、
    rate: 1 日あたりの手柄（間を空けた先が、まとめて読んだ回だけ高く出ないよう、読んだ日数で割る）、hist: 読みごとの手柄、
    hot: 最後に手柄の付いた回、pointed: 最後にほかの先から指された回。"""
    st = defaultdict(lambda: {"n": 0.0, "w": 0.0, "c": 0.0, "rd": 0.0, "rate": None, "reads": 0, "used": 0.0, "hist": [], "last_read": None,
                              "last_used": "", "until": None, "fails": 0, "gap": None, "mean": 0.5, "found": defaultdict(int), "created": "",
                              "name": "", "zero_explore": None, "hot": None, "pointed": None})
    T = len(rows)
    for t, r in enumerate(rows):
        g = GAMMA ** (T - 1 - t)
        cr = credits(r)
        for rd in r.get("reads", []):
            s = st[rd["source"]]
            s["name"] = rd.get("name") or s["name"]
            if not rd.get("ok", True):
                s["fails"] += 1
                s["gap"] = s["gap"] or rd.get("since") or r.get("since")  # 取れなかった期間の始まり。取れるまで残す
                continue
            v = cr.get(rd["source"], 0)
            s["fails"], s["gap"] = 0, None
            s["n"] += g
            s["w"] += g * min(1.0, v)
            s["rd"] += g * days(rd, r)
            s["reads"] += 1
            s["hist"].append(v)
            s["last_read"] = t
            u = rd.get("until") or r.get("until")
            if u and (not s["until"] or when(u) > when(s["until"])):
                s["until"] = u
            if rd.get("explore") and not v:
                s["zero_explore"] = t
        for sid, v in cr.items():
            s = st[sid]
            s["c"] += g * v
            s["used"] += v
            s["last_used"] = max(s["last_used"], r["id"][:10])
            s["hot"] = t
        for d in r.get("discovered", []):
            s = st[d["source"]]
            s["name"] = s["name"] or d.get("name", "")
            s["found"][d.get("via", "")] += 1
            s["created"] = d.get("created") or s["created"]
            s["pointed"] = t
    for s in st.values():
        s["mean"] = (s["w"] + 1) / (s["n"] + 2)
        s["rate"] = s["c"] / s["rd"] if s["rd"] else None
    return st


def tier(reg, sid):
    return reg["sources"].get(sid, {}).get("tier", "candidate")


def name(reg, st, sid):
    return reg["sources"].get(sid, {}).get("name") or st[sid]["name"] or sid


def middle(reg, st):
    """follow の先の 1 日あたりの値打ちの中ほど（中央値）。話題の大きさによらず、間隔を同じ決まりで出すため。"""
    xs = [st[s]["rate"] for s, e in reg["sources"].items() if e.get("tier") == "follow" and st[s]["rate"] is not None and st[s]["reads"] >= MIN_READS]
    return statistics.median(xs) if xs else 0.0


def every(reg, st, sid, T, med):
    """follow の先を何回に 1 回読むか、とその理由。"""
    s = st[sid]
    if reg["sources"].get(sid, {}).get("pinned"):
        return 1, "固定"
    if T - 1 in (s["hot"], s["pointed"]):
        return 1, "前の回で使われたか、指された"
    if s["rate"] is None or s["reads"] < MIN_READS or not med:
        return 1, ""  # まだ数えられない（読んだ回が少ない、どの先にも手柄がない）
    n = next(n for k, n in EVERY if s["rate"] >= k * med)
    return n, f"1 日あたり {s['rate']:.2f} 件（follow の中ほど {med:.2f}）"


def gap(n):
    return "毎回" if n == 1 else f"{n} 回に 1 回"


def due(s, T, n, until):
    """間隔が来たか。取れなかった先と、前に読んでから MUST_READ を超えた先は、間隔によらず読む。"""
    if n == 1 or s["last_read"] is None or s["fails"] or not s["until"]:
        return True
    return T - s["last_read"] >= n or until - when(s["until"]) >= MUST_READ


def choose(reg, rows, explore=3, until=None):
    """今回読む先。follow は間隔の来たもの。候補は、前の回で手柄の付いた先（取りこぼしの元、転送の元）、新しい先、
    見込みの上限（UCB）の高い順に explore まで。dropped は読まない。返す: 成績、follow ごとの (間隔, 理由, 読むか)、探索する候補。"""
    st, T = stats(rows), len(rows)
    until = until or now()
    known = set(reg["sources"]) | set(st)
    med = middle(reg, st)
    follow = {}
    for s in sorted(x for x in known if tier(reg, x) == "follow"):
        n, why = every(reg, st, s, T, med)
        follow[s] = (n, why, due(st[s], T, n, until))
    cands = [s for s in known if tier(reg, s) == "candidate"
             and not (st[s]["zero_explore"] is not None and T - 1 - st[s]["zero_explore"] < COOL and st[s]["c"] < 0.5)]

    def fresh(s):
        c = st[s]["created"] or reg["sources"].get(s, {}).get("created", "")
        return bool(c) and st[s]["reads"] == 0 and (until.date() - datetime.fromisoformat(c).date()).days <= NEW_DAYS

    hot = sorted((s for s in cands if st[s]["hot"] == T - 1), key=lambda s: (-st[s]["c"], s))[:explore]
    new = sorted((s for s in cands if s not in hot and fresh(s)), key=lambda s: (st[s]["created"] or "", s), reverse=True)[:max(0, min(NEW_MAX, explore - len(hot)))]
    # ponytail: UCB1 に見つけた回数を少し足しただけの見込み。候補が数百を超えて外れが目立てば、話題の近さ（製品名の一致）を足す
    ucb = lambda s: st[s]["mean"] + math.sqrt(2 * math.log(T + 2) / (st[s]["n"] + 1)) + 0.05 * min(5, sum(st[s]["found"].values()))
    rest = sorted((s for s in cands if s not in hot and s not in new), key=lambda s: (-ucb(s), s))[:max(0, explore - len(hot) - len(new))]
    return st, follow, hot + new + rest


def window(a):
    until = (when(a["until"]) if a.get("until") else now()).replace(second=0, microsecond=0)  # 分にそろえる（plan.json は分までで書く）
    since = when(a["since"]) if a.get("since") else until - timedelta(hours=float(a.get("hours", 24)))
    return since.replace(second=0, microsecond=0), until


def start(since, until, s):
    """先ごとの始まり。前の回で取れなかったなら、その期間の始まりから取り戻す（CATCHUP まで）。前に読んだ所（until）が期間の始まりより前のときも
    （間隔で読まなかった回のあと）、そこから。"""
    if s.get("gap"):
        b = when(s["gap"])
    elif s.get("until"):
        b = when(s["until"])
    else:
        b = since
    return max(min(since, b), until - CATCHUP)


def suggestions(reg, st, T):
    out, med = [], middle(reg, st)
    for sid, s in st.items():
        t, e = tier(reg, sid), reg["sources"].get(sid, {})
        last = sum(s["hist"][-DROP_READS:])
        if (t == "follow" and not e.get("pinned") and len(s["hist"]) >= DROP_READS and last < DROP_USED
                and every(reg, st, sid, T, med)[0] == EVERY[-1][1]):
            out.append(f"{sid} {name(reg, st, sid)}: {EVERY[-1][1]} 回に 1 回にしても、最後の {DROP_READS} 回の読みで使われたのは {last:.1f} 件。"
                       f"外すか（`set {sid} tier=dropped`）、毎回読むか（`set {sid} pinned=true`。聞かなくなる）を聞く")
        if s["fails"] >= 2:
            out.append(f"{sid} {name(reg, st, sid)}: {s['fails']} 回続けて取れていない（道具・権限を確かめる）")
    owners = [(f"{sid} の覚え書き", e.get("notes", [])) for sid, e in reg["sources"].items()] + [("話題の覚え書き", reg.get("notes", []))]
    for owner, notes in owners:
        for n in notes:
            if n.get("harmful", 0) >= n.get("helpful", 0) + 2:
                out.append(f"{owner} {n['id']}（+{n.get('helpful', 0)}/-{n['harmful']}）: 外すかを聞く「{n['text'][:60]}」")
    return out


def notes_of(reg, sid, rows=()):
    """子に渡す覚え書き: 票の多い順に NOTES_MAX まで。NOTE_STALE 回のあいだ効いた票の付かないもの（足した日か、最後に効いた日から数える）は渡さない。"""
    ns = reg["sources"].get(sid, {}).get("notes", []) if sid != "*" else reg.get("notes", [])
    times = [run_time(r) for r in rows]
    live = [n for n in ns if sum(t > when(n.get("last") or n.get("added") or "1970-01-01") for t in times) < NOTE_STALE]
    return sorted(live, key=lambda n: -(n.get("helpful", 0) - n.get("harmful", 0)))[:NOTES_MAX]


def entry(reg, st, rows, sid, since, until, why=""):
    e = reg["sources"].get(sid, {})
    return {"id": sid, "name": name(reg, st, sid), "since": start(since, until, st[sid]).isoformat(timespec="minutes"), "why": why,
            "url": e.get("url", ""), "notes": [f"{n['id']}: {n['text']}" for n in notes_of(reg, sid, rows)]}


def plan(topic, a):
    reg, rows = registry(topic), runs(topic)
    since, until = window(a)
    st, follow, explore = choose(reg, rows, int(a.get("explore", 3)), until)
    groups, every_of = defaultdict(list), {}
    for sid, (n, why, go) in follow.items():  # feed は group を書いても子に渡さない（feeds で取る）
        if go:
            groups["feed" if kind(sid) == "feed" else reg["sources"][sid].get("group") or kind(sid)].append(entry(reg, st, rows, sid, since, until))
            every_of[sid] = gap(n) + (f"（{why}）" if why else "")
    for sid in explore:  # 探索する先も、feed は feeds で取る
        s = st[sid]
        why = ("前の回で手柄が付いた（取りこぼしか転送の元）" if s["hot"] == len(rows) - 1 else
               f"新しい先（{s['created']} 作成）" if s["created"] and not s["reads"] else
               f"見つけた {sum(s['found'].values())} 回・使われた {s['used']:.1f}・読んだ {s['reads']} 回")
        groups["feed" if kind(sid) == "feed" else "explore"].append(entry(reg, st, rows, sid, since, until, why))
    out = []
    for g in sorted(groups, key=lambda g: (g == "explore", g == "feed", g)):
        xs = groups[g]
        for i in range(0, len(xs), GROUP_MAX):
            out.append({"name": g if len(xs) <= GROUP_MAX else f"{g}-{i // GROUP_MAX + 1}", "sources": xs[i:i + GROUP_MAX], "explore": g == "explore", "feed": g == "feed"})
    p = {"topic": topic, "since": since.isoformat(timespec="minutes"), "until": until.isoformat(timespec="minutes"), "groups": out,
         "explore_ids": explore, "more_ids": [], "notes": [f"{n['id']}: {n['text']}" for n in notes_of(reg, "*", rows)]}
    write_json(folder(topic) / "plan.json", p)
    print(f"# {topic} の読み方（{p['since']} 〜 {p['until']}。記録 {len(rows)} 回）\n")
    if not reg["sources"]:
        print("台帳が空。読む先を `set <topic> --from <file.json>` で足してから、もう一度 plan を回す。\n")
    print("## 組（feed は `feeds` で取る。ほかは 1 組を 1 つの子に、`prompt <topic> <番号> --goal …` の依頼文で渡す）\n")
    for i, g in enumerate(out, 1):
        print(f"### {i}. {g['name']}（{len(g['sources'])}）")
        for e in g["sources"]:
            s = st[e["id"]]
            score = f"読んだ {s['reads']}・使われた {s['used']:.1f}" if s["reads"] or s["used"] else "まだ読んでいない"
            late = "（取り戻す）" if when(e["since"]) < since else ""
            print(f"- {e['id']} {e['name']}｜{e['since'][5:16].replace('T', ' ')} から{late}｜{score}｜{e['why'] or every_of.get(e['id'], '')}")
        print()
    skip = [(sid, n, why) for sid, (n, why, go) in follow.items() if not go]
    print("## 今回は読まない follow（間隔。次に読む回に、前に読んだ所から取り戻す）\n")
    print("\n".join(f"- {sid} {name(reg, st, sid)}: {n} 回に 1 回（{why}）" for sid, n, why in skip) if skip else "- なし")
    sg = suggestions(reg, st, len(rows))
    print("\n## ユーザーに聞くこと（報告の「聞くこと」に入れる）\n")
    print("\n".join(f"- {x}" for x in sg) if sg else "- なし")
    print("\n## 話題の覚え書き（上ほど効いた）\n")
    print("\n".join(f"- {x}" for x in p["notes"]) if p["notes"] else "- なし")


def more(topic, ids):
    """その回の中で追加に読む先を、plan.json に組として足す。探索として数える（何も使われなければ休ませる）。"""
    p = read_json(folder(topic) / "plan.json", None) or sys.exit("plan.json がない。先に plan を回す")
    reg, rows = registry(topic), runs(topic)
    for sid in ids:
        if not is_sid(sid):
            sys.exit(f"先の id は <kind>:<ref>: {sid}")
        if kind(sid) == "feed":
            sys.exit(f"feed は追加に読まない（探索の枠で選ばれたら feeds で取る）: {sid}")
        if tier(reg, sid) == "dropped":
            sys.exit(f"外した先（dropped）は読まない: {sid}")
    have = {e["id"] for g in p["groups"] for e in g["sources"]}
    new = [s for s in dict.fromkeys(ids) if s not in have]
    if not new:
        sys.exit("どれも今回の plan にある")
    if len(p.get("more_ids", [])) + len(new) > MORE_MAX:
        sys.exit(f"追加に読むのは 1 回に {MORE_MAX} つまで（もう {len(p.get('more_ids', []))} つ）")
    st = stats(rows)
    since, until = when(p["since"]), when(p["until"])
    p["groups"].append({"name": "more", "sources": [entry(reg, st, rows, s, since, until, "追加に読む（今日の項目に関わる）") for s in new],
                        "explore": True, "feed": False, "more": True})
    p["explore_ids"] = p.get("explore_ids", []) + new
    p["more_ids"] = p.get("more_ids", []) + new
    write_json(folder(topic) / "plan.json", p)
    print(f"組 {len(p['groups'])}（more）に {len(new)} つ足した。`prompt {topic} {len(p['groups'])} --goal …` の依頼文で子に渡し、"
          f"返事を足して merge し直す（前の返事も全部渡す）")


def prompt(topic, n, goal):
    p = read_json(folder(topic) / "plan.json", None) or sys.exit("plan.json がない。先に plan を回す")
    if not (1 <= n <= len(p["groups"])):
        sys.exit(f"組は 1〜{len(p['groups'])}")
    if not goal.strip():
        sys.exit("--goal（プロンプトの目的・聞き手・分類の文）がない")
    g = p["groups"][n - 1]
    if g.get("feed"):
        sys.exit("feed の組は子に渡さない。feeds で取る")
    lines = []
    for e in g["sources"]:
        lines.append(f"- `{e['id']}` {e['name']} — read from {e['since']}" + (f"; {e['url']}" if e["url"] else "")
                     + (f"; why now: {e['why']}" if e["why"] else ""))
        lines += [f"  - note {x}" for x in e["notes"]]
    text = PROMPT.read_text(encoding="utf-8")
    fill = {"topic": topic, "skill": str(PROMPT.parent / "SKILL.md"), "goal": goal.strip(), "since": p["since"], "until": p["until"], "group": g["name"], "sources": "\n".join(lines),
            "notes": "\n".join(f"- {x}" for x in p["notes"]) or "- (none)",
            "explore": ("This group explores: also report whether each source is worth reading every run, and what to look for in it (as lessons)."
                        if g["explore"] else "These are the regular sources.")}
    if left := sorted(set(re.findall(r"\{([a-z_]+)\}", text)) - set(fill)):
        sys.exit(f"埋め残し: {left}")
    print(re.sub(r"\{([a-z_]+)\}", lambda m: fill[m.group(1)], text))  # 1 回で埋める。差し込んだ文（覚え書き・目的）の中の {…} は埋めない


def parse_feed(xml, since):
    """RSS の item と Atom の entry を (日時, 題, URL, 要約) にする。日付しかないフィード（00:00）があるので、since の日の始まり（UTC）から取る。"""
    root, out = ET.fromstring(xml), []
    day = since.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    def date(text, parse):
        """読めない日付の項目は捨てる（1 つの項目でフィード全体を落とさない）。時差のない日付（-0000 など）は UTC とみなす。"""
        try:
            d = parse(text.strip()) if text else None
        except (TypeError, ValueError):
            return None
        return d.replace(tzinfo=timezone.utc) if d and not d.tzinfo else d

    for i in root.iter():
        if i.tag.rsplit("}", 1)[-1] != "item":
            continue  # RSS 2.0 の item と、RSS 1.0（RDF）の名前空間つきの item
        f = lambda n: next((c.text or "" for c in i if c.tag.rsplit("}", 1)[-1] == n), "")
        d = date(f("pubDate"), parsedate_to_datetime) or date(f("date"), datetime.fromisoformat)  # RSS 1.0 は dc:date
        out.append((d, f("title"), f("link").strip(), f("description")))
    for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
        d = e.findtext("a:published", namespaces=ns) or e.findtext("a:updated", namespaces=ns)
        link = next((l.get("href") for l in e.findall("a:link", ns) if l.get("rel", "alternate") == "alternate"), "")
        out.append((date(d, datetime.fromisoformat), e.findtext("a:title", namespaces=ns) or "", link, e.findtext("a:summary", namespaces=ns) or ""))
    clean = lambda s: " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())[:300]
    got, titles = [], set()
    for d, t, u, s in out:  # 同じ項目が別の URL で 2 回出るフィードがある（製品のページと全体のページ）。題で 1 つにする
        if d and d >= day and u and norm_title(clean(t)) not in titles:
            titles.add(norm_title(clean(t)))
            got.append((d, clean(t), u, clean(s)))
    return got


def unsafe_feed(url):
    """開かないフィードの URL なら理由を返す: http・https でない、手元の名前、手元・社内の IP アドレス。
    ponytail: 名前を引いた先の IP は見ない（DNS で社内に向く名前は通る）。要れば socket.getaddrinfo で引いて同じに見る"""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https"):
        return "http・https の URL ではない"
    host = (p.hostname or "").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return "手元・社内の名前の URL は開かない"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return ""
    return "" if ip.is_global else "手元・社内の IP アドレスの URL は開かない"


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """転送先にも unsafe_feed を当てる（公開の URL から 127.0.0.1 などへ 302 で送られても、つなぐ前に止める）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if why := unsafe_feed(newurl):
            raise urllib.error.URLError(f"転送先を開かない（{why}）: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SafeRedirect)


def feeds(topic, out=None):
    reg, rows = registry(topic), runs(topic)
    p = read_json(folder(topic) / "plan.json", None) or sys.exit("plan.json がない。先に plan を回す")
    since, until = when(p["since"]), when(p["until"])
    st = stats(rows)
    res = {"reads": [], "candidates": []}
    for sid in [x["id"] for g in p["groups"] if g.get("feed") for x in g["sources"]]:  # plan が選んだ feed だけ（間隔の来た follow と、探索に選ばれた候補）
        e = reg["sources"].get(sid, {})
        url = sid.split(":", 1)[1]
        if why := unsafe_feed(url):  # 先の id は子の返事（読んだページ）からも入るので、開く前に確かめる
            res["reads"].append({"source": sid, "name": e.get("name", ""), "ok": False, "error": why})
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with OPENER.open(req, timeout=60) as r:
                got = parse_feed(r.read(), start(since, until, st[sid]))
        except Exception as x:  # 1 つのフィードが落ちても、ほかは取る。取れなかった先は次の回に取り戻す
            res["reads"].append({"source": sid, "name": e.get("name", ""), "ok": False, "error": str(x)[:200]})
            continue
        res["reads"].append({"source": sid, "name": e.get("name", ""), "ok": True, "until": until.isoformat(timespec="minutes"), "scanned": len(got), "picked": len(got)})
        for d, t, u, s in sorted(got):
            ahead = d > until
            res["candidates"].append({"title": t, "url": u, "summary": s, "published": d.isoformat(timespec="minutes"), "seen_in": [sid],
                                      **({"note": "日付が先。ページが公開されているかを確かめる"} if ahead else {})})
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
        print(f"{out}: フィード {len(res['reads'])}（取れなかった {sum(not r['ok'] for r in res['reads'])}）、項目 {len(res['candidates'])}")
    else:
        print(text)


def merge(topic, files, out):
    p = read_json(folder(topic) / "plan.json", {})
    rid = p.get("until") or now().isoformat(timespec="minutes")  # 回の id は期間の終わり。plan し直せば別の回、plan せずにまとめ直せば同じ回
    pub = published([r for r in runs(topic) if r["id"] != rid])  # 同じ回をまとめ直したとき、その回で使われた項目を「使われた済み」にしない
    old = [(norm_title(t), rid, t) for _, (rid, t) in pub.items() if t]
    run = {"id": rid, "since": p.get("since"), "until": p.get("until"),
           "reads": [], "items": [], "discovered": [], "misses": [], "lessons": [], "votes": []}
    explore, extra = set(p.get("explore_ids", [])), set(p.get("more_ids", []))
    starts = {e["id"]: e["since"] for g in p.get("groups", []) for e in g["sources"]}  # 子が since を書かなくても、取れなかった期間の始まりを残す
    by = {}
    for f in files:
        d = read_input(f)
        if isinstance(d, dict) and ("items" in d or "id" in d):
            sys.exit(f"{f} は回の記録（merge の出力）で、子の返事ではない。子の返事と feeds の出力だけを渡す")
        if not isinstance(d, dict) or not all(isinstance(d.get(k, []), list) and all(isinstance(x, dict) for x in d.get(k, []))
                                              for k in ("reads", "candidates", "discovered", "lessons", "votes")):
            sys.exit(f"{f} は子の返事の形でない（../prompt_collect.md の Return。各項目はオブジェクトのリスト）")
        if errs := check({"id": f, **{k: d.get(k, []) for k in ("reads", "discovered", "lessons", "votes")},
                          "items": d.get("candidates", [])}):  # 回の記録と同じ確かめ（使う前に止める）
            sys.exit(f"{f} の形が違う:\n- " + "\n- ".join(errs))
        for rd in d.get("reads", []):
            run["reads"].append({**({"since": starts[rd["source"]]} if rd.get("source") in starts else {}), **rd,
                                 **({"explore": True} if rd.get("source") in explore else {}),
                                 **({"more": True} if rd.get("source") in extra else {})})
        for k in ("discovered", "lessons", "votes"):  # 取りこぼしは子から取らない。使う側が record --missed で返すものだけにする（読み方の外れは覚え書きの票で返る）
            run[k] += d.get(k, [])
        for c in d.get("candidates", []):
            hits = []
            for k in keys(c):  # 候補の URL のどれかで当たった前の項目を、全部集める（別名で 2 つの項目がつながることがある）
                if k in by and all(by[k] is not h for h in hits):
                    hits.append(by[k])
            if not hits:
                hit = {**c, "seen_in": sorted(set(c.get("seen_in", [])))}
                run["items"].append(hit)
            else:  # 同じ項目: 見えた先と別の URL を足す。いちばん元の投稿（origin）は、先に出た項目のものを残す
                hit = hits[0]
                for other in [*hits[1:], c]:
                    hit["seen_in"] = sorted(set(hit["seen_in"]) | set(other.get("seen_in", [])))
                    hit["urls"] = sorted((set(hit.get("urls", [])) | {other.get("url")} | set(other.get("urls", []))) - {hit.get("url"), None})
                    if other.get("origin") and not hit.get("origin"):
                        hit["origin"] = other["origin"]
                run["items"] = [i for i in run["items"] if all(i is not h for h in hits[1:])]
            for k in keys(hit):
                by[k] = hit
    got = {rd["source"] for rd in run["reads"]}
    for sid, since in starts.items():  # plan にあって返事のない先（子が落ちた組、feeds を回さなかった）は、取れなかったとして次の回に読み直す
        if sid not in got:
            run["reads"].append({"source": sid, "ok": False, "since": since, "error": "返事がない（子が落ちたか、組を渡さなかった）",
                                 **({"explore": True} if sid in explore else {}), **({"more": True} if sid in extra else {})})
    for i in run["items"]:
        if d := next((pub[k] for k in keys(i) if k in pub), None):
            i["dup"] = d[0][:10]
            continue
        t = norm_title(i.get("title"))
        sm, best = difflib.SequenceMatcher(None, t), (0, "", "")
        for o, r, ot in old:  # 使われた題の数だけ比べるので、上限の見積もり（quick_ratio）で外れを先に落とす
            sm.set_seq1(o)
            if sm.real_quick_ratio() >= 0.85 and sm.quick_ratio() >= 0.85 and (x := sm.ratio()) > best[0]:
                best = (x, r, ot)
        if t and best[0] >= 0.85:
            i["similar"] = f"{best[1][:10]}「{best[2]}」"
    write_json(Path(out), run)
    print(f"{out}: 読んだ先 {len(run['reads'])}（取れなかった {sum(not r.get('ok', True) for r in run['reads'])}）、候補 {len(run['items'])}、"
          f"見つけた先 {len(run['discovered'])}、覚え書き {len(run['lessons'])}\n")
    for n, i in enumerate(run["items"], 1):
        flag = f"［使われた済み {i['dup']}］" if i.get("dup") else (f"［似ている: {i['similar']}］" if i.get("similar") else "")
        print(f"{n}. {flag}{i.get('title', '')}｜{i.get('url', '')}｜{len(i['seen_in'])} 先: {', '.join(i['seen_in'])}")


def add_note(reg, sid, text, day):
    """覚え書きを足す。ほとんど同じ文がすでにあれば、足さずに helpful を 1 増やす（同じ学びを何度も書いて膨らませない）。"""
    if sid == "*":
        ns = reg.setdefault("notes", [])
    else:
        ns = reg["sources"].setdefault(sid, {"tier": "candidate", "added": day, "why": "覚え書きから"}).setdefault("notes", [])
    t = norm_title(text)
    for n in ns:
        if difflib.SequenceMatcher(None, t, norm_title(n["text"])).ratio() >= 0.9:
            n["helpful"], n["last"] = n.get("helpful", 0) + 1, day
            return f"{sid} の覚え書き {n['id']} と同じ（helpful +1）"
    nid = f"n{reg.get('next_note', 1)}"
    reg["next_note"] = reg.get("next_note", 1) + 1
    ns.append({"id": nid, "text": text.strip(), "added": day, "helpful": 0, "harmful": 0})
    return f"{sid} に覚え書き {nid} を足した"


def vote(reg, nid, good, day):
    for n in reg.get("notes", []) + [n for e in reg["sources"].values() for n in e.get("notes", [])]:
        if n["id"] == nid:
            n["helpful" if good else "harmful"] = n.get("helpful" if good else "harmful", 0) + 1
            if good:
                n["last"] = day  # 効いた日。NOTE_STALE はここから数える
            return True
    return False


def bad_date(v, day_only=False):
    """読めない日付か（plan が毎回読むので、記録に入れる前に止める）。"""
    try:
        (datetime.fromisoformat(v).date() if day_only else datetime.fromisoformat(v))
        return day_only and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)
    except (TypeError, ValueError):
        return True


def is_sid(v):
    return isinstance(v, str) and re.fullmatch(r"[\w.-]+:.+", v) is not None


def check(run):
    """回の記録の形。runs.jsonl に入るものは全部ここで確かめる（plan・report・sources が毎回読むので、壊れた行を入れない）。"""
    if not isinstance(run, dict):
        return ["回の記録は JSON のオブジェクト"]
    errs = []
    if not isinstance(run.get("id"), str) or not run["id"]:
        errs.append("id（回の名前。merge が期間の終わりを入れる）がない")
    for k in ("since", "until"):
        if run.get(k) and bad_date(run[k]):
            errs.append(f"{k} は ISO の日時: {run[k]}")
    lists = ("reads", "items", "discovered", "misses", "lessons", "votes", "changes")
    for k in lists:
        if not isinstance(run.get(k, []), list) or not all(isinstance(x, str if k == "changes" else dict) for x in run.get(k, [])):
            errs.append(f"{k} は{'文' if k == 'changes' else 'オブジェクト'}のリスト")
    if errs:
        return errs
    for r in run.get("reads", []):
        if not is_sid(r.get("source")):
            errs.append(f"reads の source は <kind>:<ref>: {r}")
        if not isinstance(r.get("name", ""), str):
            errs.append(f"reads の name は文字列: {r}")
        for k in ("since", "until"):
            if r.get(k) and bad_date(r[k]):
                errs.append(f"reads の {k} は ISO の日時: {r}")
    for i in run.get("items", []):
        if not isinstance(i.get("url"), str) or not i["url"] or not all(isinstance(u, str) for u in i.get("urls", [])):
            errs.append(f"items の url（と urls）は URL の文字列: {i.get('title')}")
        if not isinstance(i.get("public_url", ""), str) or not isinstance(i.get("title", ""), str):
            errs.append(f"items の public_url と title は文字列: {i.get('title')}")
        seen = i.get("seen_in", [])
        if not isinstance(seen, list) or not all(is_sid(x) for x in seen) or (i.get("origin") and not is_sid(i["origin"])):
            errs.append(f"items の seen_in・origin は <kind>:<ref>: {i.get('title')}")
        elif not seen and not i.get("origin"):
            errs.append(f"items に seen_in（見えた先）がない: {i.get('title')}")
    for d in run.get("discovered", []):
        if not is_sid(d.get("source")):
            errs.append(f"discovered の source は <kind>:<ref>: {d}")
        if not isinstance(d.get("name", ""), str):
            errs.append(f"discovered の name は文字列: {d}")
        if d.get("created") and bad_date(d["created"], day_only=True):
            errs.append(f"discovered の created は YYYY-MM-DD: {d}")
    for m in run.get("misses", []):
        if not isinstance(m.get("url"), str) or not m["url"] or not all(isinstance(u, str) for u in m.get("urls", [])):
            errs.append(f"misses の url は URL の文字列: {m}")
        if m.get("source") and not is_sid(m["source"]):
            errs.append(f"misses の source は <kind>:<ref>: {m}")
    for l in run.get("lessons", []):
        if not isinstance(l.get("text"), str) or not l["text"].strip() or not (l.get("source", "*") == "*" or is_sid(l["source"])):
            errs.append(f"lessons は source（<kind>:<ref> か *）と text: {l}")
    for v in run.get("votes", []):
        if not isinstance(v.get("note"), str) or not isinstance(v.get("helpful", True), bool):
            errs.append(f"votes は note（覚え書きの id）と helpful（true・false）: {v}")
    return errs


def add_misses(run, ms):
    """取りこぼしを足す。同じ URL は 1 つにする。"""
    url = lambda m: canon(m["url"]) if isinstance(m, dict) and isinstance(m.get("url"), str) else None  # 形の違うものも足し、check で止める
    have = {url(m) for m in run.get("misses", [])} - {None}
    for m in ms:
        if url(m) is None or url(m) not in have:
            run.setdefault("misses", []).append(m)
            have.add(url(m))


def sites(reg, rows):
    """使われた項目の出典（public_url）のサイトのうち、まだ読む先にないもの: [(件数, ホスト)]。読む先の id と url のホスト（dropped も）は外す。"""
    host = lambda u: (urllib.parse.urlsplit(u).hostname or "").lower().removeprefix("www.")
    known = {host(x) for sid, e in reg["sources"].items() for x in (sid.split(":", 1)[1], e.get("url", "")) if x.startswith("http")}
    n = Counter(host(i["public_url"]) for r in rows for i in r.get("items", [])
                if i.get("used") and str(i.get("public_url", "")).startswith("http"))
    return sorted(((c, h) for h, c in n.items() if h and h not in known and c >= SITE_MIN), key=lambda x: (-x[0], x[1]))


def record(topic, path, outputs=(), missed=()):
    run = read_input(path)
    old = runs(topic)
    prev = next((r for r in old if r["id"] == run.get("id")), None) if isinstance(run, dict) else None
    if isinstance(run, dict):
        if prev:  # 同じ回を記録し直しても、前に足した取りこぼしは残す
            add_misses(run, prev.get("misses", []))
        for f in missed:
            ms = read_input(f)
            if not isinstance(ms, list) or not all(isinstance(m, dict) for m in ms):
                sys.exit(f"{f} は取りこぼしのオブジェクトのリスト（[{{\"url\": …, \"source\": \"<kind>:<ref>（分かれば）\", \"why\": …}}, …]）")
            add_misses(run, ms)
    if errs := check(run):  # 形を確かめてから印を付ける（壊れた記録で落ちない）
        sys.exit("記録の形が違う:\n- " + "\n- ".join(errs))
    if outputs:
        urls = set().union(*(md_urls(read_input(f, as_json=False)) for f in outputs))
    else:  # 出力を渡さずに記録し直す（取りこぼしだけ足す）ときは、前に使われたとした項目をそのまま残す
        urls = {k for i in (prev or {}).get("items", []) if i.get("used") for k in keys(i)}
    for i in run.get("items", []):
        i["used"] = bool(keys(i) & urls) or (not outputs and not prev and bool(i.get("used")))
    reg = registry(topic)
    rows = [r for r in old if r["id"] != run["id"]]  # 同じ回を回し直したら置き換える
    # 回ごとに当てた覚え書きと票は、台帳に残す（同じ回を記録し直しても当て直さない。台帳を先に書くので、途中で落ちても当てた分と食い違わない）
    applied = reg.setdefault("applied", {}).setdefault(run["id"], {"lessons": [], "votes": [], "changes": []})
    day = run["id"][:10]
    kept = list(dict.fromkeys(applied.setdefault("changes", []) + run.get("changes", [])))  # 前に当てた直しは、記録に残す
    changes = []
    for n, l in enumerate(run.get("lessons", [])):  # 回の中の位置も鍵にする（2 つの子が同じ票を返したら 2 票）
        k = [n, l.get("source", "*"), l["text"]]
        if k not in applied["lessons"]:
            changes.append(add_note(reg, k[1], k[2], day))
            applied["lessons"].append(k)
    for n, v in enumerate(run.get("votes", [])):
        k = [n, v["note"], bool(v.get("helpful", True))]
        if k in applied["votes"]:
            continue
        applied["votes"].append(k)
        if not vote(reg, v["note"], v.get("helpful", True), day):
            changes.append(f"覚え書き {v['note']} がない（票を捨てた）")
    rows_all = sorted(rows + [run], key=run_time)
    st = stats(rows_all)
    for sid, s in st.items():
        if tier(reg, sid) != "candidate" or s["c"] < PROMOTE:
            continue
        if since := reg["sources"].get(sid, {}).get("tier_since"):  # 候補に下げた先は、下げたあとの手柄だけで数える（すぐ follow に戻さない）
            s = stats(sorted((r for r in rows_all if run_time(r) > when(since)), key=run_time))[sid]
            if s["c"] < PROMOTE:
                continue
        e = reg["sources"].setdefault(sid, {"added": day})
        e.update(tier="follow", tier_since=run.get("until") or now().isoformat(timespec="minutes"), name=e.get("name") or s["name"], why=f"{day} に引き上げた（使われた {s['used']:.1f} 件）")
        changes.append(f"{sid} {s['name']} を follow に上げた（候補のうちに使われた項目 {s['used']:.1f} 件）")
    run["changes"] = applied["changes"] = kept + [c for c in changes if c not in kept]
    for old_id in sorted(reg["applied"])[:-APPLIED_KEEP]:  # 記録し直すのは直近の回だけなので、古い回の控えは捨てる
        del reg["applied"][old_id]
    write_json(folder(topic) / "sources.json", reg)
    p = folder(topic) / "runs.jsonl"
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_all), encoding="utf-8")
    tmp.replace(p)
    used = sum(1 for i in run.get("items", []) if i.get("used"))
    print(f"{p} に {run['id']} を記録した: 読んだ先 {len(run.get('reads', []))}、候補 {len(run.get('items', []))}、使われた {used}、"
          f"取りこぼし {len(true_misses(run))}、見つけた先 {len(run.get('discovered', []))}")
    if outputs and not used:
        print("注意: --published の出力に、候補の URL が 1 つもなかった（出力に元の URL を書いたかを確かめる）")
    print("\n".join(f"- {c}" for c in changes) or "- 台帳の直しなし")
    for c, h in sites(reg, rows_all):
        print(f"- 読む先にないサイト: {h}（使われた項目の出典に {c} 回）。更新の流れ（blog・release notes）なら feed を探して "
              f"`set {topic} feed:<URL> tier=candidate`、資料（docs）なら `set {topic} web:https://{h} tier=dropped` で、もう出さない")
    for x in suggestions(reg, st, len(rows_all)):
        print(f"- 聞く: {x}")


def trend(rows):
    """直近 TREND 回と、その前の TREND 回の、1 回あたりの読んだ先・使われた項目・取りこぼし・探索と追加読みから使われた項目。"""
    def per(rs):
        if not rs:
            return None
        def one(r):
            ex = {rd["source"] for rd in r.get("reads", []) if rd.get("explore")}
            return (sum(rd.get("ok", True) for rd in r.get("reads", [])), sum(bool(i.get("used")) for i in r.get("items", [])),
                    len(true_misses(r)), sum(v for s, v in credits(r).items() if s in ex))
        xs = [one(r) for r in rs]
        return [sum(x[k] for x in xs) / len(xs) for k in range(4)]
    a, b = per(rows[-TREND:]), per(rows[-2 * TREND:-TREND])
    if not a:
        return ""
    label = ("読んだ先", "使われた項目", "取りこぼし", "探索と追加読みから使われた")
    vs = lambda k: f"{a[k]:.1f}" + (f"（{b[k]:.1f}）" if b else "")
    return (f"- 直近 {min(TREND, len(rows))} 回の 1 回あたり" + ("（かっこはその前の回）" if b else "") + ": "
            + "、".join(f"{label[k]} {vs(k)}" for k in range(4)))


def report(topic, rid=None):
    reg, rows = registry(topic), runs(topic)
    run = next((r for r in rows if r["id"] == rid), None) if rid else (rows[-1] if rows else None)
    if not run:
        sys.exit("回の記録がない")
    st = stats(rows)
    nm = lambda sid: name(reg, st, sid)
    link = lambda sid: f"[{nm(sid)}]({reg['sources'][sid]['url']})" if reg["sources"].get(sid, {}).get("url") else nm(sid)
    ok = [r for r in run.get("reads", []) if r.get("ok", True)]
    out = ["## 情報源", "", "- 読んだもの:" + ("" if any(not r.get("explore") for r in ok) else " なし")]
    by = defaultdict(list)
    for r in ok:
        by[(kind(r["source"]), bool(r.get("explore")))].append(r)
    for (k, ex), rs in sorted(by.items()):
        if not ex:
            out.append(f"  - {k} {len(rs)} 件（見た {sum(r.get('scanned', 0) for r in rs)} 件 → 拾った {sum(r.get('picked', 0) for r in rs)} 件）")
    exp = [r for r in ok if r.get("explore")]
    out.append("- 探索と追加読みの先:" + ("" if exp else " なし"))
    cr = credits(run)
    out += [f"  - {link(r['source'])}{'（追加）' if r.get('more') else ''}: 見た {r.get('scanned', 0)} 件、使われた {cr.get(r['source'], 0):.1f} 件" for r in exp]
    bad = [r for r in run.get("reads", []) if not r.get("ok", True)]
    out.append("- 取れなかった先:" + ("" if bad else " なし"))
    out += [f"  - {nm(r['source'])}: {r.get('error', '理由は未記入')}（次の回で取り戻す）" for r in bad]
    ms = true_misses(run)
    out.append("- 取りこぼし:" + ("" if ms else " なし"))
    out += [f"  - {m.get('title') or m['url']}（{nm(m['source']) if m.get('source') else '元の先は分からない'}）" for m in ms]
    top = sorted(((v, s) for s, v in cr.items() if v), reverse=True)
    out.append("- 使われた項目の元: " + ("、".join(f"{link(s)} {v:.1f}" for v, s in top[:10]) if top else "なし"))
    out.append("- 情報源の直し:" + ("" if run.get("changes") else " なし"))
    out += [f"  - {c}" for c in run.get("changes", [])]
    if t := trend(rows[:rows.index(run) + 1]):
        out.append(t)
    print("\n".join(out) + "\n")


def sources(topic, as_json=False):
    reg, rows = registry(topic), runs(topic)
    st = stats(rows)
    if as_json:  # ほかの話題に写す形（set --from が読む）。成績は写さない。新しい話題の記録で測り直すため
        top = [n["text"] for n in notes_of(reg, "*", rows)]
        out = [{"id": "*", "notes": top}] if top else []
        for sid, e in sorted(reg["sources"].items()):
            if e.get("tier") == "follow":
                ns = [n["text"] for n in notes_of(reg, sid, rows)]
                out.append({"id": sid, "tier": "follow", **{k: e[k] for k in ("name", "group", "url") if e.get(k)}, **({"notes": ns} if ns else {})})
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    T, med = len(rows), middle(reg, st)
    ids = sorted(set(reg["sources"]) | set(st), key=lambda s: (TIERS.index(tier(reg, s)), -st[s]["c"], s))
    print(f"# {topic} の読む先（記録 {T} 回）\n")
    print("| tier | id | 名前 | 読んだ | 使われた | 1 日あたり | 間隔 | 最後に使われた | 見つけた | 覚え書き（渡す / 全部） |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for s in ids:
        x, e = st[s], reg["sources"].get(s, {})
        pin = "（固定）" if e.get("pinned") else ""
        n = gap(every(reg, st, s, T, med)[0]) if tier(reg, s) == "follow" else "-"
        rate = f"{x['rate']:.2f}" if x["rate"] is not None else "-"
        print(f"| {tier(reg, s)}{pin} | {s} | {name(reg, st, s)} | {x['reads']} | {x['used']:.1f} | {rate} | {n} | {x['last_used'] or '-'} | "
              f"{sum(x['found'].values())} | {len(notes_of(reg, s, rows))} / {len(e.get('notes', []))} |")


def set_(topic, a):
    reg = registry(topic)
    day = now().date().isoformat()
    if a[:1] == ["--from"]:
        rows = read_input(a[1])
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            sys.exit(f"{a[1]} は先のオブジェクトのリスト（[{{\"id\": \"slack:C…\", \"tier\": \"follow\"}}, …]）")
    else:
        if bad := [x for x in a[1:] if "=" not in x]:
            sys.exit(f"key=value の形でない: {bad}")
        if dup := sorted(k for k, n in Counter(x.split("=", 1)[0] for x in a[1:]).items() if n > 1):
            sys.exit(f"同じ項目を 2 回渡した（1 つだけ渡す）: {dup}")
        rows = [{"id": a[0] if a else "", **dict(x.split("=", 1) for x in a[1:])}]
    for r in rows:  # 全部の行を確かめてから書く（途中で止めても、台帳は半分だけ直らない）
        if r.get("id") == "*" and set(r) <= {"id", "note", "notes"}:
            pass  # 話題の覚え書きだけの行（sources --json の頭）
        elif not is_sid(r.get("id")):
            sys.exit(f"先の id は <kind>:<ref>: {r}")
        if bad := set(r) - KEYS - {"id", "note", "notes"}:
            sys.exit(f"直せない項目: {sorted(bad)}（{sorted(KEYS)} と note）")
        if bad := [k for k in KEYS - {"pinned"} if k in r and not isinstance(r[k], str)] + (["pinned"] if not isinstance(r.get("pinned", ""), (str, bool)) else []):
            sys.exit(f"{sorted(bad)} は文字列（pinned は true・false でもよい）: {r.get('id')}")
        if not isinstance(r.get("note", ""), str):
            sys.exit(f"note は文: {r.get('id')}")
        if r.get("tier", "follow") not in TIERS:
            sys.exit(f"tier は {TIERS}")
        if r.get("created") and bad_date(r["created"], day_only=True):
            sys.exit(f"created は YYYY-MM-DD（{r['id']}: {r['created']}）")
        if r.get("group") in RESERVED:
            sys.exit(f"group に {sorted(RESERVED)} は使えない（plan が使う組の名前）")
        if not isinstance(r.get("notes", []), list) or not all(isinstance(t, str) or isinstance(t, dict) and isinstance(t.get("text"), str) for t in r.get("notes", [])):
            sys.exit(f"notes は文か {{\"text\": …}} のリスト: {r['id']}")
    for r in rows:
        sid = r.pop("id")
        note = r.pop("note", None)
        notes = r.pop("notes", [])
        if sid != "*":
            if "pinned" in r:
                r["pinned"] = r["pinned"] in (True, "true", "1", "yes")
            e = reg["sources"].setdefault(sid, {"tier": "candidate", "added": day})
            if r.get("tier") and r["tier"] != e.get("tier"):
                r["tier_since"] = now().isoformat(timespec="minutes")  # 下げたり上げたりした時。record は、候補に下げたあとの回の手柄だけで follow に戻す
            e.update(r)
        for t in ([note] if note else []) + notes:
            print(add_note(reg, sid, t if isinstance(t, str) else t["text"], day))
    write_json(folder(topic) / "sources.json", reg)
    print(f"{folder(topic) / 'sources.json'}: {len(rows)} 件を直した（読む先は全部で {len(reg['sources'])}）")


def selftest():
    import tempfile
    global ROOT
    assert canon("https://Ex.com/a/?utm_source=x&b=2#top") == "https://ex.com/a?b=2"
    assert canon("https://x.slack.com/archives/C1/p2?thread_ts=1.2") == "https://x.slack.com/archives/C1/p2?thread_ts=1.2"
    run = {"id": "r", "items": [{"url": "https://a", "used": True, "seen_in": ["s:1"]},
                                {"url": "https://b", "used": True, "seen_in": ["s:1", "s:2"]}, {"url": "https://c", "seen_in": ["s:3"]}],
           "misses": [{"url": "https://m", "source": "s:4"}, {"url": "https://c", "source": "s:5"}, {"url": "https://n"}]}
    assert credits(run) == {"s:1": 1.5, "s:2": 0.5, "s:4": 1.0}, credits(run)  # 候補にあって選ばれなかった項目は、取りこぼしに数えない
    assert [m["url"] for m in true_misses(run)] == ["https://m", "https://n"]
    # 1 日あたり: 4 日分をまとめて読んで 1 件の先と、毎日読んで 4 回に 1 件の先は、同じ値打ち
    daily = [{"id": f"d{k}", "until": f"2026-11-{k + 1:02d}T07:00+09:00", "since": f"2026-11-{k:02d}T07:00+09:00" if k else "2026-10-31T07:00+09:00",
              "reads": [{"source": "s:D", "ok": True}] + ([{"source": "s:W", "ok": True, "since": f"2026-10-{28 + k:02d}T07:00+09:00" if k < 4 else
                                                           f"2026-11-{k - 3:02d}T07:00+09:00"}] if k % 4 == 3 else []),
              "items": [{"url": f"https://d/{k}", "used": k % 4 == 3, "seen_in": ["s:D"]}, {"url": f"https://w/{k}", "used": k % 4 == 3, "seen_in": ["s:W"]}]}
             for k in range(8)]
    sd = stats(daily)
    assert abs(sd["s:D"]["rate"] - sd["s:W"]["rate"]) < 0.05, (sd["s:D"]["rate"], sd["s:W"]["rate"])  # 差は新しい回ほど重い分だけ（1 回あたりなら 4 倍違う）
    x = b"""<rss><channel><item><title>A &amp; B</title><link>https://f/a</link><pubDate>Mon, 26 Oct 2026 00:00:00 GMT</pubDate>
            <description>&lt;p&gt;hi&lt;/p&gt;</description></item><item><title>old</title><link>https://f/o</link>
            <pubDate>Thu, 22 Oct 2026 00:00:00 GMT</pubDate></item><item><title>A &amp; B</title><link>https://f/a2</link>
            <pubDate>Mon, 26 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
    got = parse_feed(x, when("2026-10-26T07:00+09:00"))  # 10/25 22:00 UTC → 10/25 の日の始まりから
    assert [(t, u, s) for _, t, u, s in got] == [("A & B", "https://f/a", "hi")], got
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>E</title><link href="https://f/e"/>
               <updated>2026-10-26T01:00:00Z</updated></entry></feed>"""
    assert [u for _, _, u, _ in parse_feed(atom, when("2026-10-26T07:00+09:00"))] == ["https://f/e"]
    odd = b"""<rss><channel><item><title>z</title><link>https://f/z</link><pubDate>Mon, 26 Oct 2026 01:00:00 -0000</pubDate></item>
              <item><title>bad</title><link>https://f/b</link><pubDate>not a date</pubDate></item></channel></rss>"""
    assert [u for _, _, u, _ in parse_feed(odd, when("2026-10-26T07:00+09:00"))] == ["https://f/z"]  # 時差のない日付は UTC、読めない日付の項目だけ捨てる
    rdf = b"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
              <item><title>R</title><link>https://f/r</link><dc:date>2026-10-26T02:00:00+00:00</dc:date></item></rdf:RDF>"""
    assert [u for _, _, u, _ in parse_feed(rdf, when("2026-10-26T07:00+09:00"))] == ["https://f/r"]  # RSS 1.0（RDF）の item と dc:date
    try:
        opts(["--goal"], {"goal"})
        raise AssertionError("値のない --goal で止まらない")
    except SystemExit:
        pass
    assert opts(["r.json", "--published", "a.md", "b.md", "--missed", "m.json", "--published", "c.md"], {"published", "missed"}, {"published", "missed"}) == (
        {"published": ["a.md", "b.md", "c.md"], "missed": ["m.json"]}, ["r.json"])
    try:
        opts(["--goal", "a", "--goal", "b"], {"goal"})
        raise AssertionError("2 回の --goal で止まらない")
    except SystemExit:
        pass
    with tempfile.TemporaryDirectory() as d:
        ROOT = d
        q = _quiet
        q(set_, "t", ["slack:A", "tier=follow", "name=team-announce", "note=Skip questions starting with QQ"])
        q(set_, "t", ["slack:B", "tier=follow", "name=quiet", "pinned=false"])
        q(set_, "t", ["slack:M", "name=old"])
        q(set_, "t", ["slack:A", "note=Link replies as p{ts}?thread_ts={parent}"])
        for bad in (["slack:X", "group=explore"], ["slack:X", "group=more"], ["slack:X", "name=a", "name=b"], ["slack:X", "created=Oct 24"], ["slack:X", "tier", "follow"],
                    ["slack:X", "tier=core"], ["slack:X", "mode=filter"], ["--from", str(Path(d) / "none.json")]):
            try:
                q(set_, "t", bad)
                raise AssertionError(f"止まらない: {bad}")
            except SystemExit:
                pass
        reg = registry("t")
        assert reg["sources"]["slack:A"]["notes"][0]["id"] == "n1" and reg["sources"]["slack:B"]["pinned"] is False
        # 1 回目: plan → 子の返事 2 つ → merge → record（出力に載った URL だけ使われた）
        out = q(plan, "t", {"since": "2026-10-25T07:00+09:00", "until": "2026-10-26T07:00+09:00"})
        p = read_json(folder("t") / "plan.json", {})
        assert [g["name"] for g in p["groups"]] == ["slack", "explore"] and [e["id"] for e in p["groups"][1]["sources"]] == ["slack:M"], p
        brief = q(prompt, "t", 1, "Product updates for SAs, not {sources}")
        assert "team-announce" in out and "n1: Skip questions" in brief and "p{ts}?thread_ts={parent}" in brief and "not {sources}" in brief, brief
        c1 = {"reads": [{"source": "slack:A", "ok": True, "scanned": 10, "picked": 2}, {"source": "slack:B", "ok": False, "error": "timeout"}],
              "candidates": [{"title": "Genie is GA", "url": "https://x/1?utm_source=s", "seen_in": ["slack:A"], "origin": "slack:N",
                              "public_url": "https://www.blog.example.com/genie"},
                             {"title": "Chat", "url": "https://x/2", "seen_in": ["slack:A"]}],
              "discovered": [{"source": "slack:N", "name": "new-preview", "via": "forward", "created": "2026-10-24"}],
              "lessons": [{"source": "*", "text": "Forwarded posts carry no body; open the original"}]}
        c2 = {"reads": [{"source": "slack:M", "ok": True, "scanned": 3, "picked": 0}], "misses": [{"source": "slack:M", "url": "https://x/forward"}],
              "candidates": [{"title": "Genie is GA!", "url": "https://x/1", "seen_in": ["slack:M"]}]}
        for i, c in enumerate((c1, c2)):
            (Path(d) / f"c{i}.json").write_text(json.dumps(c))
        q(merge, "t", [str(Path(d) / "c0.json"), str(Path(d) / "c1.json")], str(Path(d) / "run.json"))
        r = json.loads((Path(d) / "run.json").read_text())
        assert r["id"] == "2026-10-26T07:00+09:00", r["id"]  # 回の id は期間の終わり（同じ日の 2 回目の回が 1 回目を置き換えない）
        assert len(r["items"]) == 2 and r["items"][0]["seen_in"] == ["slack:A", "slack:M"] and r["reads"][2].get("explore"), r
        assert r["reads"][1]["since"] == "2026-10-25T07:00+09:00", r["reads"][1]  # 子が since を書かなくても、plan の始まりを残す
        assert r["misses"] == [], r["misses"]  # 子が misses を返しても、回の取りこぼしにしない
        (Path(d) / "d.md").write_text("- 出典（https://x/1）。\n")  # 全角の括弧と句点の前の URL も使われたと読む
        q(record, "t", str(Path(d) / "run.json"), [str(Path(d) / "d.md")])
        again = q(merge, "t", [str(Path(d) / "c0.json"), str(Path(d) / "c1.json")], str(Path(d) / "run1b.json"))
        assert "使われた済み" not in again, again  # 同じ回をまとめ直しても、その回で使われた項目は「使われた済み」にしない
        rows = runs("t")
        assert [i.get("used") for i in rows[0]["items"]] == [True, False]
        st = stats(rows)
        assert abs(st["slack:N"]["c"] - 1 / 3) < 1e-9 and st["slack:B"]["fails"] == 1 and st["slack:B"]["until"] is None
        # 2 回目: 取れなかった slack:B は前の期間から取り戻し、前の回で手柄の付いた候補（slack:M・slack:N）を先に探索する
        q(plan, "t", {"since": "2026-10-26T07:00+09:00", "until": "2026-10-27T07:00+09:00"})
        p = read_json(folder("t") / "plan.json", {})
        b = next(e for g in p["groups"] for e in g["sources"] if e["id"] == "slack:B")
        assert b["since"] == "2026-10-25T07:00+09:00", b  # 取れなかった前の期間から
        ex = [e["id"] for g in p["groups"] if g["explore"] for e in g["sources"]]
        assert ex[:2] == ["slack:M", "slack:N"], ex
        q(set_, "t", ["slack:M", "tier=dropped"])
        q(plan, "t", {"since": "2026-10-26T07:00+09:00", "until": "2026-10-27T07:00+09:00"})
        assert "slack:M" not in json.dumps(read_json(folder("t") / "plan.json", {})["groups"])  # 外した先は読まない
        q(set_, "t", ["feed:https://f/feed.xml", "tier=candidate", "name=blog"])
        q(plan, "t", {"since": "2026-10-26T07:00+09:00", "until": "2026-10-27T07:00+09:00", "explore": "5"})
        p2 = read_json(folder("t") / "plan.json", {})
        fg = [e["id"] for g in p2["groups"] if g.get("feed") for e in g["sources"]]
        assert fg == ["feed:https://f/feed.xml"] and "feed:https://f/feed.xml" in p2["explore_ids"], p2  # 候補の feed は探索の枠で選び、feeds で取る
        assert all(kind(e["id"]) != "feed" for g in p2["groups"] if g["explore"] for e in g["sources"])
        # 追加に読む: 組を足し、子の依頼文を出せる。feed・外した先・4 つ目は止める
        out = q(more, "t", ["slack:Q"])
        p3 = read_json(folder("t") / "plan.json", {})
        assert p3["groups"][-1]["more"] and "slack:Q" in p3["explore_ids"] and "slack:Q" in q(prompt, "t", len(p3["groups"]), "g"), out
        for bad in (["feed:https://f/x.xml"], ["slack:M"], ["slack:R", "slack:S", "slack:U"], ["slack:Q"]):
            try:
                q(more, "t", bad)
                raise AssertionError(f"止まらない: {bad}")
            except SystemExit:
                pass
        (Path(d) / "cq.json").write_text(json.dumps({"reads": [{"source": "slack:Q", "ok": True}]}))
        q(merge, "t", [str(Path(d) / "cq.json")], str(Path(d) / "runq.json"))
        assert next(r for r in json.loads((Path(d) / "runq.json").read_text())["reads"] if r["source"] == "slack:Q").get("more")
        q(plan, "t", {"since": "2026-10-26T07:00+09:00", "until": "2026-10-27T07:00+09:00"})
        # 同じ話を 2 回使ったら、候補の slack:N は follow に上がる。前に使われた URL は dup になる
        c3 = {"reads": [{"source": "slack:N", "ok": True, "scanned": 4, "picked": 2}],
              "candidates": [{"title": "Lakebase PrPr", "url": "https://x/3", "seen_in": ["slack:N"], "public_url": "https://blog.example.com/lb"},
                             {"title": "Apps OBO", "url": "https://x/4", "seen_in": ["slack:N"]},
                             {"title": "Genie is GA", "url": "https://x/1", "seen_in": ["slack:N"]}],
              "lessons": [{"source": "*", "text": "Forwarded posts carry no body - open the original."}],
              "votes": [{"note": "n1", "helpful": False}, {"note": "n1", "helpful": False}]}  # 2 つの子が同じ票を返した
        (Path(d) / "c3.json").write_text(json.dumps(c3))
        out = q(merge, "t", [str(Path(d) / "c3.json")], str(Path(d) / "run2.json"))
        assert "［使われた済み 2026-10-26］Genie is GA" in out, out
        (Path(d) / "d2.md").write_text("**https://x/3**.\n")
        (Path(d) / "d3.md").write_text("[OBO](https://x/4)\n")  # 2 つの案件の出力。どちらかにあれば使われた
        out = q(record, "t", str(Path(d) / "run2.json"), [str(Path(d) / "d2.md"), str(Path(d) / "d3.md")])
        reg = registry("t")
        assert reg["sources"]["slack:N"]["tier"] == "follow" and "follow に上げた" in out, out
        assert "読む先にないサイト: blog.example.com（使われた項目の出典に 2 回）" in out, out  # www. の有無はそろえる
        assert reg["notes"][0]["helpful"] == 1 and reg["sources"]["slack:A"]["notes"][0]["harmful"] == 2  # 同じ学びは足さずに数え、票は子ごとに数える
        before = json.dumps(registry("t")["notes"])
        q(record, "t", str(Path(d) / "run2.json"), [str(Path(d) / "d2.md"), str(Path(d) / "d3.md")])  # 同じ回をもう一度記録しても、覚え書きの票は増えない
        assert json.dumps(registry("t")["notes"]) == before and len(runs("t")) == 2
        lines = (folder("t") / "runs.jsonl").read_text().splitlines()
        (folder("t") / "runs.jsonl").write_text(lines[0] + "\n")  # 台帳を書いたあと、回の記録を書く前に落ちた
        q(record, "t", str(Path(d) / "run2.json"), [str(Path(d) / "d2.md"), str(Path(d) / "d3.md")])
        assert json.dumps(registry("t")["notes"]) == before and len(runs("t")) == 2  # 記録し直しても、当てた覚え書きと票を二重に当てない
        q(set_, "t", ["web:https://blog.example.com", "tier=dropped"])
        assert not sites(registry("t"), runs("t"))  # 資料のサイトは dropped にすれば、もう出さない
        rep = q(report, "t")
        assert "- 探索と追加読みの先:\n  - new-preview: 見た 4 件、使われた 2.0 件" in rep and "follow に上げた" in rep and "直近 2 回の 1 回あたり" in rep, rep
        assert "slack:N" in q(sources, "t")
        # 取りこぼし: 使う側が別の所で知った項目は、元の先の手柄になり、元が候補なら次の回に先に試す。記録し直しても残る
        (Path(d) / "m.json").write_text(json.dumps([{"url": "https://y/9", "source": "slack:Z", "why": "別の会議で聞いた"}]))
        (Path(d) / "m2.json").write_text(json.dumps([{"url": "https://y/7", "why": "別の案件"}]))
        out = q(record, "t", str(Path(d) / "run2.json"), [], [str(Path(d) / "m.json"), str(Path(d) / "m2.json")])  # 出力を渡さず、2 つの案件の取りこぼしだけ足す
        assert "取りこぼし 2" in out and "使われた 2" in out, out  # 前に使われたとした項目は残す
        q(record, "t", str(Path(d) / "run2.json"), [str(Path(d) / "d2.md"), str(Path(d) / "d3.md")])
        assert [m["url"] for m in runs("t")[-1]["misses"]] == ["https://y/9", "https://y/7"]
        (Path(d) / "m_bad.json").write_text(json.dumps([{"url": "https://y/8", "urls": [5]}]))
        try:
            q(record, "t", str(Path(d) / "run2.json"), [], [str(Path(d) / "m_bad.json")])  # 形の違う取りこぼしは、記録に入れる前に止める
            raise AssertionError("形の違う取りこぼしで止まらない")
        except SystemExit:
            pass
        q(plan, "t", {"since": "2026-10-27T07:00+09:00", "until": "2026-10-28T07:00+09:00"})
        assert read_json(folder("t") / "plan.json", {})["explore_ids"][0] == "slack:Z"
        assert "- 取りこぼし:\n  - https://y/9（slack:Z）" in q(report, "t")
        # 写す: follow の先と覚え書きを、ほかの話題に写す（成績は写さない）
        (Path(d) / "export.json").write_text(q(sources, "t", True))
        q(set_, "t2", ["--from", str(Path(d) / "export.json")])
        r2 = registry("t2")
        assert sorted(r2["sources"]) == ["slack:A", "slack:B", "slack:N"] and r2["sources"]["slack:A"]["tier"] == "follow" and r2["notes"], r2
        assert not runs("t2") and len(r2["sources"]["slack:A"]["notes"]) == 2
        # 間隔: 値打ちの低い follow は 4 回に 1 回。前に読んでから 6 日を超えたら読む。4 回に 1 回のまま使われなければ、外すかを聞く（pinned は聞かない）
        rows = runs("t")
        for k in range(20):
            rows.append({"id": f"2026-11-{k + 1:02d}", "until": f"2026-11-{k + 1:02d}T07:00+09:00", "since": f"2026-11-{k:02d}T07:00+09:00" if k else
                         "2026-10-31T07:00+09:00", "reads": [{"source": "slack:B", "ok": True}, {"source": "slack:A", "ok": True}, {"source": "slack:N", "ok": True}],
                         "items": [{"url": f"https://z/{k}", "used": True, "seen_in": ["slack:A"]}, {"url": f"https://z/n{k}", "used": True, "seen_in": ["slack:N"]}]})
        reg = registry("t")
        st, T = stats(rows), len(rows)
        assert every(reg, st, "slack:B", T, middle(reg, st))[0] == 4 and every(reg, st, "slack:A", T, middle(reg, st))[0] == 1
        last = when(st["slack:B"]["until"])
        assert not due(st["slack:B"], T, 4, last + timedelta(days=1)) and due(st["slack:B"], T, 4, last + timedelta(days=6))
        sg = suggestions(reg, st, T)
        assert any(x.startswith("slack:B") and "外すか" in x for x in sg), sg
        reg["sources"]["slack:B"]["pinned"] = True
        assert not any(x.startswith("slack:B") for x in suggestions(reg, st, T)) and every(reg, st, "slack:B", T, middle(reg, st))[0] == 1
        reg["sources"]["slack:B"]["pinned"] = False
        _, fl, _ = choose(reg, rows, 3, last + timedelta(days=1))
        assert fl["slack:B"][:1] == (4,) and not fl["slack:B"][2] and fl["slack:A"][2], fl
        rows2 = rows + [{"id": "2026-11-21b", "until": "2026-11-21T08:00+09:00", "discovered": [{"source": "slack:B", "via": "mention"}]}]
        assert every(reg, stats(rows2), "slack:B", len(rows2), middle(reg, stats(rows2)))[0] == 1  # 指された次の回は毎回に戻す
        # 覚え書き: 子に渡すのは NOTES_MAX まで。NOTE_STALE 回のあいだ効かなかったものは渡さない
        reg = registry("t")
        for k in range(7):
            add_note(reg, "slack:N", f"note number {k} about {'xyz' * k}", "2026-10-27")
        assert len(notes_of(reg, "slack:N", rows)) == NOTES_MAX
        vote(reg, reg["sources"]["slack:N"]["notes"][-1]["id"], True, "2099-01-01")
        assert [n["id"] for n in notes_of(reg, "slack:N", rows + [{"id": f"s{k}", "until": f"2027-01-{k + 1:02d}T07:00+09:00"} for k in range(NOTE_STALE)])] == [
            reg["sources"]["slack:N"]["notes"][-1]["id"]]
        # 探索して何も使われなかった候補は COOL 回のあいだ選ばない
        cool = rows + [{"id": "z", "until": "2026-12-01T07:00+09:00", "reads": [{"source": "slack:P", "ok": True, "explore": True}]}]
        assert "slack:P" not in choose(registry("t"), cool, 3, when("2026-12-01T08:00+09:00"))[2]
        assert "slack:P" in choose(registry("t"), cool + [{"id": f"y{k}", "until": f"2026-12-{k + 2:02d}T07:00+09:00"} for k in range(COOL)], 3,
                                   when("2026-12-20T07:00+09:00"))[2]
        assert check({"id": "x", "items": [{"title": "t"}]}) and not check(rows[0])
        q(set_, "u", ["feed:file:///etc/hosts", "tier=follow"])
        q(plan, "u", {})
        q(feeds, "u", str(Path(d) / "f.json"))
        got = json.loads((Path(d) / "f.json").read_text())
        assert got["reads"][0]["ok"] is False and not got["candidates"], got  # http・https でないフィードは開かない
        assert check({"id": "x", "discovered": [{"source": "slack:Z", "created": "Oct 24"}]}) and check({"id": "x", "since": "yesterday"})
        assert md_urls("[a](https://w/Foo_(bar)) と [b](https://x/2)。 https://x/3]") == {canon("https://w/Foo_(bar)"), canon("https://x/2"), canon("https://x/3")}
        assert canon("https://github.com/o/r/blob/x?ref=v1") != canon("https://github.com/o/r/blob/x?ref=v2")  # ref は版を指すので残す
        assert canon("https://w.slack.com/archives/C1/p2?cid=C1") == canon("https://w.slack.com/archives/C1/p2")
        (Path(d) / "list.json").write_text("[1, 2]")
        try:
            q(record, "t", str(Path(d) / "list.json"), [str(Path(d) / "d.md")])  # --published があっても、形を先に確かめる
            raise AssertionError("形の違う記録で止まらない")
        except SystemExit:
            pass
        # 候補に下げた先は、下げたあとの手柄が PROMOTE に届くまで follow に戻さない
        q(set_, "t", ["slack:N", "tier=candidate"])
        later = {"id": "2099-01-01T07:00+09:00", "until": "2099-01-01T07:00+09:00", "reads": [{"source": "slack:A", "ok": True}]}
        (Path(d) / "later.json").write_text(json.dumps(later))
        q(record, "t", str(Path(d) / "later.json"))
        assert registry("t")["sources"]["slack:N"]["tier"] == "candidate"
        q(set_, "t", ["slack:N", "tier=follow"])
        for broken in ({"lessons": [{"source": "*"}]}, {"votes": [{"note": "n1", "helpful": "no"}]}, {"items": [{"url": "https://x", "seen_in": ["nokind"]}]},
                       {"reads": "slack:A"}, {"misses": [{"source": "slack:A"}]}, {"reads": [{"source": "slack:A", "name": 5}]},
                       {"discovered": [{"source": "slack:A", "name": ["x"]}]}, {"items": [{"url": "https://x", "seen_in": ["a:b"], "public_url": 5}]}, {"items": [{"url": "https://x", "seen_in": ["a:b"], "title": 5}]}):
            assert check({"id": "x", **broken}), broken  # plan が毎回読む記録に、壊れた行を入れない
        for rows_ in ({"id": "slack:Z"}, [{"tier": "follow"}], [{"id": "feed"}], [{"id": "*", "tier": "follow"}], [{"id": "slack:Z", "notes": "one"}],
                      [{"id": "slack:Z", "group": 5}], [{"id": "slack:Z", "url": 5}], [{"id": "slack:Z", "note": 5}], [{"id": "slack:Z", "pinned": 1}]):
            (Path(d) / "bad.json").write_text(json.dumps(rows_))
            try:
                q(set_, "t", ["--from", str(Path(d) / "bad.json")])
                raise AssertionError(f"止まらない: {rows_}")
            except SystemExit:
                pass
        for bad_child in ('{"candidates": ["x"]}', '{"candidates": [{"title": "x", "url": 5, "seen_in": ["slack:C1"]}]}',
                          '{"reads": [{"source": ["a"], "ok": true}]}', '{"candidates": [{"url": "https://x/9", "seen_in": "slack:C1"}]}'):
            (Path(d) / "child_bad.json").write_text(bad_child)
            try:
                q(merge, "t", [str(Path(d) / "child_bad.json")], str(Path(d) / "x.json"))
                raise AssertionError(f"形の違う子の返事で止まらない: {bad_child}")
            except SystemExit:
                pass
        alias = {"candidates": [{"title": "A", "url": "https://n/a", "seen_in": ["slack:A"]}, {"title": "B", "url": "https://n/b", "seen_in": ["slack:B"]},
                                {"title": "A", "url": "https://n/a", "urls": ["https://n/b"], "seen_in": ["slack:M"]}]}
        (Path(d) / "alias.json").write_text(json.dumps(alias))
        q(merge, "t", [str(Path(d) / "alias.json")], str(Path(d) / "alias_run.json"))
        alias_run = json.loads((Path(d) / "alias_run.json").read_text())
        items = alias_run["items"]
        planned = {e["id"]: e["since"] for g in read_json(folder("t") / "plan.json", {})["groups"] for e in g["sources"]}
        assert planned and {r["source"]: (r["ok"], r["since"]) for r in alias_run["reads"]} == {k: (False, v) for k, v in planned.items()}  # 返事のない先は取れなかった読み
        assert len(items) == 1 and items[0]["seen_in"] == ["slack:A", "slack:B", "slack:M"], items  # 別名でつながった 2 項目は 1 つに
        try:
            q(merge, "t", [str(Path(d) / "alias_run.json")], str(Path(d) / "x.json"))  # 前の回の記録を子の返事として取り込まない
            raise AssertionError("回の記録を子の返事として取り込んだ")
        except SystemExit:
            pass
        req = urllib.request.Request("https://example.com/feed.xml")
        try:
            SafeRedirect().redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/x")
            raise AssertionError("手元への転送で止まらない")
        except urllib.error.URLError:
            pass
        mixed = [{"id": "a", "until": "2026-10-26T07:00+09:00"}, {"id": "b", "until": "2026-10-25T23:30+00:00"}]
        assert [r["id"] for r in sorted(mixed, key=run_time)] == ["a", "b"]  # 時差が違っても時刻の順
        assert unsafe_feed("http://169.254.169.254/x") and unsafe_feed("http://localhost/f") and unsafe_feed("http://10.0.0.1/f")
        assert not unsafe_feed("https://example.com/feed.xml")
        fresh_reg = {"sources": {"slack:F": {"tier": "candidate", "created": "2026-12-01"}}, "notes": []}
        assert choose(fresh_reg, [], 0, when("2026-12-02T07:00+09:00"))[2] == []  # --explore 0 なら新しい先も読まない
        assert choose(fresh_reg, [], 3, when("2026-12-02T07:00+09:00"))[2] == ["slack:F"]
        (Path(d) / ".desk" / OLD).mkdir(parents=True)
        try:
            folder("t")
            raise AssertionError("前の名前の記録があっても止まらない")
        except SystemExit:
            pass
    text = PROMPT.read_text(encoding="utf-8")
    one = [{"id": "o", "until": "2026-11-01T07:00+09:00", "reads": [{"source": "s:A", "ok": True}, {"source": "s:B", "ok": True}],
            "items": [{"url": "https://o/1", "used": True, "seen_in": ["s:A"]}]}]
    r1 = {"sources": {"s:A": {"tier": "follow"}, "s:B": {"tier": "follow"}}}
    assert every(r1, stats(one), "s:B", 1, middle(r1, stats(one)))[0] == 1  # 1 回の空振りでは間を空けない
    assert set(re.findall(r"\{([a-z_]+)\}", text)) == {"topic", "skill", "goal", "since", "until", "group", "sources", "notes", "explore"}, text
    ROOT = None
    print("selftest ok")


def _quiet(f, *a):
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        f(*a)
    return buf.getvalue()


def opts(a, names, multi=()):
    """--名前 値 を取り出す。multi の名前は、次の -- までの値をすべて取る（--published a.md b.md）。"""
    out, rest, i = {}, [], 0
    while i < len(a):
        if a[i].startswith("--") and a[i][2:] in names:
            k, j = a[i][2:], i + 1
            while j < len(a) and not a[j].startswith("--") and (k in multi or j == i + 1):
                j += 1
            if j == i + 1:
                sys.exit(f"{a[i]} の値がない\n{__doc__}")
            if k in out and k not in multi:  # 2 回目の値で 1 回目を黙って捨てない
                sys.exit(f"{a[i]} を 2 回渡した（1 つだけ渡す）\n{__doc__}")
            out[k] = out.get(k, []) + a[i + 1:j] if k in multi else a[i + 1]  # 同じ旗を繰り返しても、前の値を捨てない
            i = j
        else:
            rest.append(a[i])
            i += 1
    return out, rest


def main():
    a = sys.argv[1:]
    if a == ["--selftest"]:
        return selftest()
    if len(a) < 2:
        sys.exit(__doc__)
    cmd, topic, rest = a[0], a[1], a[2:]
    flags = {"plan": {"hours", "since", "until", "explore"}, "more": set(), "prompt": {"goal"}, "feeds": {"out"}, "merge": {"out"},
             "record": {"published", "missed"}, "report": set(), "sources": set(), "set": {"from"}}
    arity = {"plan": (0, 0), "more": (1, MORE_MAX), "prompt": (1, 1), "feeds": (0, 0), "merge": (1, 99), "record": (1, 1), "report": (0, 1),
             "sources": (0, 0), "set": (0, 99)}
    if cmd not in flags:
        sys.exit(__doc__)
    as_json = cmd == "sources" and "--json" in rest
    o, r = opts([x for x in rest if not (as_json and x == "--json")], flags[cmd], {"published", "missed"})  # 引数の数は、ここで 1 か所で確かめる
    if not arity[cmd][0] <= len(r) <= arity[cmd][1]:
        sys.exit(f"{cmd} の引数の数が違う\n{__doc__}")
    if cmd == "plan":
        if not (re.fullmatch(r"\d+(\.\d+)?", o.get("hours", "24")) and o.get("explore", "3").isdigit()) or any(
                bad_date(o[k]) for k in ("since", "until") if k in o):
            sys.exit(f"--hours・--explore は数、--since・--until は ISO の日時\n{__doc__}")
        return plan(topic, o)
    if cmd == "more":
        return more(topic, r)
    if cmd == "prompt":
        if not r[0].isdigit():
            sys.exit(f"組の番号がない\n{__doc__}")
        return prompt(topic, int(r[0]), o.get("goal", ""))
    if cmd == "feeds":
        return feeds(topic, o.get("out"))
    if cmd == "merge":
        return merge(topic, r, o.get("out") or sys.exit("--out <run.json> がない"))
    if cmd == "record":
        return record(topic, r[0], o.get("published", []), o.get("missed", []))
    if cmd == "report":
        return report(topic, r[0] if r else None)
    if cmd == "sources":
        return sources(topic, as_json)
    return set_(topic, ["--from", o["from"]] if "from" in o else r)


if __name__ == "__main__":
    main()
