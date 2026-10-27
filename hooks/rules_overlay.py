#!/usr/bin/env python3
"""ワークスペースの決まり（rules/ の下の、frontmatter に description のある .md。探し方は skills/deck-practices/scripts/desk.py の rules）を、要る場面で続けて出す（開き忘れを防ぐ）。
- frontmatter の paths に当たるプラグインのスキルのファイル（slides-build/visual.md。* も使える）が読まれたら、そのファイルを出す（手順に付く足しと上書き）。
- 顧客の資料（Customers/ と Internal/ の下）の 構成案*.md・社内メモ_*.md・references.md が読まれたら、その顧客の Customers/<顧客>/memory.md（資料への好み。どう作るか）と、
  構成案の頭の「使う決まり」に書いた rules/ のファイル（paths のない、資料ごとに選ぶ決まり）を出す。構成案に「使う決まり」の行がなければ、選ぶ一覧（パスと description）を出す。
  資料を作り始めるとき（deck-practices/start.md が読まれたとき）にも、一覧を出す。
/desk-tools:<スキル>（Claude Code）・$desk-tools:<スキル>（Codex）で呼んだスキルは、道具を使わずに SKILL.md が入るので、プロンプトから拾って、paths が <スキル>/SKILL.md に当たるものを出す。
Claude Code は自動のコンパクションのあと、呼んだスキルの SKILL.md を付け直すので、SessionStart（compact）でそれに当たるものを出し直す（Codex はスキルも差し込みも消すので、出し直さない）。
並べて呼んだ道具の hook は同時に走り、会話の記録にまだ互いの差し込みがないので、同じターンで出したものは印のファイルで知らせ合う（pi は拡張がそのターンに足したものを覚える）。
同じ会話で出したもののうち、まだモデルに見えている（コンパクションで消えていない）ものは出し直さない。Claude Code と Codex は hook に渡る会話の記録（transcript_path）の、最後のコンパクションのあとを見る。pi は拡張が、モデルに見えている道具の結果を渡す。Codex は差し込みを記録に developer のメッセージで残し、コンパクションで消す（2026-10-25 に確かめた）。
決まりの形と出し方は skills/deck-practices/rules.md の「Workspace rules」。Claude Code と Codex は hooks.json の PostToolUse（Read・Bash・Skill。Claude Code は if で、.md に触れる Read・Bash だけ）・UserPromptSubmit・SessionStart（compact）、pi は extensions/rules.ts から呼ぶ。
usage: rules_overlay.py claude   （標準入力に Claude Code か Codex の hook の JSON）
       rules_overlay.py pi       （標準入力に {"cwd", "text", "isPath", "seen"}。isPath は text が読んだファイルのパスのとき。seen は今の文脈に残る、前に出したもの。出力は {"context": …}）
       rules_overlay.py --selftest
標準ライブラリだけ。ワークスペースが見つからない（探し方は skills/deck-practices/scripts/desk.py）か、決まりと memory.md がないときは何も出さない。"""
import fnmatch, functools, hashlib, json, os, re, shlex, shutil, stat, sys, tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # プラグインの scripts/ に __pycache__ を残さない
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "deck-practices" / "scripts"))
import desk  # noqa: E402  ワークスペースの探し方（スキルのスクリプトと同じ）

SKILLS = {p.parent.name for p in (Path(__file__).resolve().parent.parent / "skills").glob("*/SKILL.md")}
NAMES = "|".join(map(re.escape, SKILLS))  # スキルの名前のどれか（REF・COMMAND・CALL）
REF = re.compile(rf"(?<![\w-])({NAMES})/([\w./-]+\.md)")  # スキルの名前で始まるパス（前のフォルダは問わない）
MEMORY_FROM = re.compile(r"(?:^|/)(?:構成案[^/]*|社内メモ_[^/]*|references)\.md$")  # 資料を始めるときとコンパクションのあとに読むもの（組む途中に何度も開く build/ は入れない）
RULE_PATH = r"rules/[\w./-]+?\.md"  # 「使う決まり」に書く決まりのファイルのパス
USE = re.compile(r"(?m)^[ \t]*(?:[-*][ \t]*)?\**使う決まり\**[ \t]*[:：]\**(.*)$")  # 構成案の頭の「使う決まり」の行（- **使う決まり:** rules/a.md、rules/b.md）
INDEX, START, STALE = "rules/*.md", "deck-practices/start.md", "rules/（使う決まりの確かめ）"  # 選ぶ一覧の見出しのパス（ファイルではない）、資料を作り始めるときに開くファイル（ここで一覧を出す）、「使う決まり」の名前の知らせ（ファイルではない）
COMMAND = re.compile(rf"<command-name>/desk-tools:({NAMES})</command-name>")  # Claude Code の記録で、ユーザーが打った /desk-tools:<スキル>
CALL = re.compile(rf"(?:^\s*/|(?<![\w$/.-])\$)desk-tools:({NAMES})(?![\w-])", re.ASCII)  # プロンプトで呼んだスキル（Claude Code の / は頭だけ、Codex の $ はどこでも。和文は続けて書いても呼んだことになる）
PUNCT = "();<>|&`"  # コマンドの区切り
HEAD = re.compile(r'## (?:ワークスペースの決まり(?:の一覧)?|顧客の memory): ([^`"\\\n]+?\.md)(?=\\|\n|$)')  # 出したものの見出し。会話の記録では改行が \n（hook の出力の写しでは \\n）になる
CUT_BY_HOST = ("<persisted-output>", "<truncated-output>", "persist-to-disk failed", "writing it to disk failed")  # Claude Code が 1 万字を超える差し込みを、頭だけにして渡した印（ファイルに逃がした・書けずに切った）
COMPACTED = (b'"subtype":"compact_boundary"', b'"type":"compacted"')  # コンパクションの印（Claude Code・Codex の会話の記録）
LIMIT = 9000  # 1 回に差し込む字数の上限（決まりと memory の合計。切ったときの添え書きも含む）。Claude Code は 1 万字を超える差し込みをファイルに逃がし、頭の 2,000 字だけを見せる（Codex は hooks.json の additionalContextLimit で逃がさない）
NOTE = 500  # 切ったときの添え書きの字数の上限（切ったほうの字数に含める）


def workspace(cwd):
    """スクリプトが cwd で使うワークスペース（desk.locate）。cwd がその中になければ（プラグインのフォルダなど）、会話を開いたフォルダ（Claude Code の CLAUDE_PROJECT_DIR）から探したもの。
    Claude Code は会話の中で cd した先を cwd に渡すので、プラグインのフォルダへ cd したあとも、開いたワークスペースを見つける（2026-10-27 に資料を作る会話で見つけた）。
    前の版のワークスペース（factory.toml）の中では、どこへも進まない（desk.locate と同じ）。個人の設定が読めなくても止めない（スクリプトが止めて知らせる）。"""
    def find(d):
        try:
            return desk.locate(d)
        except SystemExit:
            return None
    f = find(cwd)
    if not (f and Path(cwd).resolve().is_relative_to(f[1])) and not desk.old(cwd) and (p := os.environ.get("CLAUDE_PROJECT_DIR")):
        f = find(p) or f
    return f[1] if f else None


def words(command):
    """コマンドの語。引用符の外の ; | & ( ) < > ` だけで区切る（引用符の中の空白や括弧はそのまま）。引用符が閉じていなければ、空白で切る。"""
    lex = shlex.shlex(command, posix=True, punctuation_chars=PUNCT)
    lex.whitespace_split, lex.commenters = True, ""  # # は語の中にも出る（deck#2）。コメントの語は、パスでなければ使わない
    try:
        return list(lex)
    except ValueError:
        return command.split()


def decks(ws, cwd, text, is_path=False):
    """text（読んだファイルのパスか、コマンド）に出てくる資料のファイル（Customers/ と Internal/ の下の 構成案*.md・社内メモ_*.md・references.md。
    絶対パスか、cwd からのパス。コマンドの中の cd もたどる）の実のパス。"""
    tops = [str(ws / d).lower() + "/" for d in ("Customers", "Internal")]  # macOS は大文字と小文字を区別しない
    toks, base, outer, out = [text] if is_path else words(text), str(cwd), [], []  # パスは切らない（空白のあるフォルダ）
    for i, tok in enumerate(toks):
        if all(c in PUNCT for c in tok):  # 区切り（続いたものは 1 語になる。「);」など）。サブシェルの中の cd は、閉じたら戻す
            for c in tok:
                if c == "(":
                    outer.append(base)
                elif c == ")" and outer:
                    base = outer.pop()
        elif i and toks[i - 1] == "cd" and not tok.startswith("-"):  # cd -P などは追わない（引数のない cd の次は区切りで、上で外れる）
            base = os.path.join(base, os.path.expanduser(tok))
        elif MEMORY_FROM.search(tok):
            p = os.path.realpath(os.path.join(base, os.path.expanduser(tok)))  # Path.expanduser は ~user で例外を出す
            if any(p.lower().startswith(t) and "/" in p[len(t):] for t in tops):
                out.append(p)
    return out


def memory(ws, p):
    """資料のファイル p（decks の実のパス）の顧客の memory.md。Customers/ の下でなければ None。"""
    top = str(ws / "Customers").lower() + "/"
    return ws / "Customers" / p[len(top):].split("/")[0] / "memory.md" if p.lower().startswith(top) else None


def chosen(p):
    """資料のファイル p の構成案（p が構成案ならそれ、ほかは同じフォルダのいちばん新しい 構成案*.md）の「使う決まり」に書いた rules/ のパス。
    構成案に行がなければ None（選ぶ一覧を出す）。構成案がないか、「なし」なら []。rules/ のパスのない行は、その値（空なら「（空）」）。"""
    p = Path(p)
    try:
        outline = p if p.name.startswith("構成案") else max(p.parent.glob("構成案*.md"), key=lambda x: x.stat().st_mtime, default=None)
        text = outline.read_text(encoding="utf-8") if outline else ""
    except (OSError, ValueError):  # ない（コマンドに書いただけ）、読めない、UTF-8 でない
        return []
    if not (lines := USE.findall(text)):
        return None if text else []
    line = " ".join(lines)
    names = re.findall(RULE_PATH, line)
    extra = [v for v in (x.strip("`*") for x in re.split(r"[\s、,，]+", re.sub(RULE_PATH, " ", line))) if ".md" in v or re.match(r"rules?/", v)]  # パスに読めない値（b.md、rule/b.md、rules/b）
    if names or extra:
        return names + extra
    return [] if "なし" in line else [line.strip(" \t*") or "（空）"]  # rules/ のパスのない行は、書いた値をそのまま返す（決まりのファイルにないと知らせる）


def index(ws, files):
    """資料ごとに選ぶ決まり（paths のないもの）の一覧。"""
    rows = [f"- {p.relative_to(ws)}（{'・'.join(desk.listed(m, 'targets')) or '全部'}、{'・'.join(desk.listed(m, 'audience')) or '全部'}）: {m['description']}" for p, m in files]
    return (f"## ワークスペースの決まりの一覧: {INDEX}\n\n資料ごとに選ぶ決まり（frontmatter に paths のないもの。行は「パス（作るもの、資料の種類）: いつ使うか」）。"
            "この資料に合うものを選び、構成案の頭に「- **使う決まり:** rules/a.md、rules/b.md」（合うものがなければ「なし」）と書いて、構成案を開き直す。"
            "構成案を開くたびに hook が中身を出す（deck-practices/rules.md の「Workspace rules」）。\n\n" + "\n".join(rows))


def transcript(ev):
    """hook に渡った会話の記録。Claude Code の子（agent_id がある）には親の記録が渡るので、子の記録（<親>/subagents/agent-<id>.jsonl）にする。"""
    path, agent = ev.get("transcript_path"), ev.get("agent_id")
    return str(Path(path).with_suffix("") / "subagents" / f"agent-{agent}.jsonl") if path and agent else path


def read(transcript):
    """会話の記録（bytes）。なければ b""。"""
    try:
        return Path(transcript).read_bytes()
    except (OSError, TypeError):
        return b""


def compacted(raw):
    """会話の記録（bytes）の、最後のコンパクションの印の位置。なければ -1。"""
    return max(raw.rfind(m) for m in COMPACTED)


def shown(raw):
    """会話の記録（Claude Code・Codex。bytes）の、最後のコンパクションのあとに出したもの（rules/… と Customers/…/memory.md）。記録がなければ空。"""
    lines, parent, last = {}, {}, None  # 行の id ごとの見出しを探す文と親（Claude Code は parentUuid の木。巻き戻して捨てた枝も同じファイルに残る）
    for i, x in enumerate(raw[compacted(raw) + 1:].split(b"\n")):  # 印がなければ -1 + 1 で頭から
        try:
            d = json.loads(x)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("uuid"):  # Claude Code: モデルが見るのは hook_additional_context だけ（要約・hook_success の stdout の写しは数えない。1 万字を超えるとファイルに逃がし、頭の 2 KB だけを見せる）
            a = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
            c = a.get("content") if a.get("type") == "hook_additional_context" else ""
            c = c if isinstance(c, str) else "\n".join(map(str, c or []))
            lines[d["uuid"]], parent[d["uuid"]], last = "" if any(m in c for m in CUT_BY_HOST) else c, d.get("parentUuid"), d["uuid"]
        else:  # uuid のない記録（Codex）は 1 本の列なので、行をそのまま使う（Claude Code の uuid のない行は API への写しなどで、下で外す）
            lines[i] = x.decode("utf-8", "replace")
    if last:  # Claude Code: 最後の行から親をたどった、今の枝だけ
        on, k = set(), last
        while k in parent and k not in on:
            on.add(k)
            k = parent[k]
        lines = {k: x for k, x in lines.items() if k in on}
    return set(HEAD.findall("\n".join(lines.values())))


def overlays(cwd, text, is_path=False, seen=(), key=None):
    """text（読んだパスかコマンド）に出てくるプラグインのファイルに paths が当たる決まり、資料のファイルに当たる顧客の memory.md と「使う決まり」の決まり（行がなければ選ぶ一覧）の中身。
    seen（まだ見えているもの）は出さない。key（会話の記録、ターン）があれば、同じターンにほかの hook が出したものも出さない。
    seen と key は会話の記録を読む関数でもよく、出すものがあるときだけ呼ぶ。"""
    ws = workspace(cwd)
    if not ws:
        return ""
    refs = [f"{m[1]}/{m[2]}" for m in REF.finditer(text) if "rules/" + m[1] not in text[max(0, m.start() - 6):m.end()]]  # rules/ そのものを読んだときは出さない
    docs = decks(ws, cwd, text, is_path)
    files = desk.rules(ws) if refs or docs else []  # ワークスペースの中でも、たいていの道具の呼び出しはここで終わる（rules/ も会話の記録も読まない）
    mems = list(dict.fromkeys(m for p in docs if (m := memory(ws, p)) and m.is_file()))
    picks = [chosen(p) for p in docs]
    free = [(p, m) for p, m in files if not desk.listed(m, "paths")]  # 資料ごとに選ぶ決まり
    written = {x for c in picks if c for x in c}  # 構成案の「使う決まり」に書いたもの。文字で比べる（絶対パスを書かれても落ちない）
    stale = sorted(written - {str(p.relative_to(ws)) for p, _ in files})
    hits = [p for r in refs for p, m in files if any(fnmatch.fnmatchcase(r, g) for g in desk.listed(m, "paths"))] + [p for p, _ in files if str(p.relative_to(ws)) in written]
    old = [p for r in refs if (p := ws / "rules" / r).is_file() and p not in dict(files)]  # プラグインの同じパスの、description のないファイル（前の版の上書き）。desk-migrate を回すまでも、黙って出さなくならないように
    want = {}  # 出す順: 開いたファイルに当たるもの、構成案で選んだもの、一覧（RULE_MAX のファイルが先頭なら、memory と並んでも丸ごと入る）
    for p in hits + old:
        why = "このワークスペースの決まり。description の場面で当てる" if p not in old else "frontmatter の description がない（前の版の形なら desk-migrate の apply で足す。ほかは 1 行で書く）"
        want.setdefault(p, f"## ワークスペースの決まり: {p.relative_to(ws)}\n\n{why}。プラグインと食い違うところは、こちらに従う（deck-practices/rules.md の「Workspace rules」）。\n\n{p.read_text(encoding='utf-8')}")
    if stale:  # 見出しが HEAD に合わないので、見えているものとして外さない（直すまで、構成案を開くたびに出す）
        want[ws / STALE] = (f"## 構成案の「使う決まり」の確かめ\n\n「使う決まり」の {'・'.join(stale)} は、決まりのファイルにない（名前が変わったか、消えたか、frontmatter の description がない。"
                            f"書き方は「- **使う決まり:** rules/a.md、rules/b.md」）。ワークスペースの決まりの一覧（{INDEX}）から選び直して、構成案を直す。")
    if free and (START in refs or None in picks or stale):
        want[ws / INDEX] = index(ws, free)
    if not (want or mems):
        return ""
    seen = {ws / x for x in (seen() if callable(seen) else seen)}
    mem = {p: f"## 顧客の memory: {p.relative_to(ws)}\n\nこの顧客の資料への好み（どう作るか。相手の事業や構成は profile.md）。ワークスペースの決まりとプラグインより優先する。新しいユーザーの言葉と食い違えば、そちらに従って memory を直す（deck-practices/rules.md の「Customer memory」）。\n\n{p.read_text()}"
           for p in mems if p not in seen}
    out = {p: x for p, x in want.items() if p not in seen}
    if not (mem or out):  # みな見えている（印を調べない）
        return ""
    key, mine = key() if callable(key) else key, set()
    for p in [p for p in (*mem, *out) if claimed(key, p)]:  # 同じターンにほかの hook がもう丸ごと出したものは、ここで途中まで出すことになるものも外す
        mem.pop(p, None), out.pop(p, None)
    while True:  # 組んでから、丸ごと出すものにだけ印を置く。同じターンにほかの hook がもう出したものは外して組み直す（外すと字数が空くので、丸ごと出すものは減らない）
        room = LIMIT - 2 if mem and out else LIMIT  # 決まりと memory をつなぐ改行の分
        r, m = size(out), size(mem)
        keep = min(r, max(room // 2, room - m))  # 決まりの字数。両方が長ければ半分ずつ（片方が長くても、もう片方を押し出さない）、短いほうの余りはもう片方に回す
        (rt, rw), (mt, mw) = cut(out, keep, ws), cut(mem, room - keep, ws)
        text = "\n\n".join(x for x in (rt, mt) if x)
        whole = (rw | mw) - mine
        taken = {p for p in whole if not claim(key, p)}
        mine |= whole - taken
        if not taken:
            return text
        for p in taken:
            mem.pop(p, None), out.pop(p, None)


def skill_md(names):
    """スキルの名前を、REF に当たる SKILL.md のパスにする（呼んだスキルも、読んだファイルと同じ道で出す）。このプラグインのスキル（名前だけか desk-tools: 付き）だけ。"""
    return " ".join(f"{s}/SKILL.md" for s in dict.fromkeys(n.removeprefix("desk-tools:") for n in names) if s in SKILLS)


def called(cwd, prompt, seen=(), key=None):
    """プロンプトで呼んだスキル（/desk-tools:<スキル>・$desk-tools:<スキル>）の SKILL.md に paths が当たる決まりの中身。"""
    return overlays(cwd, skill_md(CALL.findall(prompt)), seen=seen, key=key)


def invoked(raw):
    """Claude Code の会話の記録で呼んだスキル（新しい順）: Skill の呼び出しと、ユーザーが打った /desk-tools:<スキル>。道具の結果と要約に写ったものは数えない。
    自動のコンパクションのあと、Claude Code はこれらの SKILL.md を新しい順に付け直す。Codex はコンパクションでスキルの中身も消し、記録にこの形もない（空になる）。"""
    last, asked = {}, {}  # スキルごとの最後の行、まだ結果の来ていない Skill の呼び出し（id → スキル）
    for i, x in enumerate(raw.split(b"\n")):
        if b"desk-tools:" not in x and b'"Skill"' not in x and not any(k in x for k in asked):  # たいていの行は読まずに飛ばす
            continue
        try:
            d = json.loads(x)
        except ValueError:
            continue
        m = d.get("message") if isinstance(d, dict) and not d.get("isCompactSummary") else None
        c = m.get("content") if isinstance(m, dict) else None
        for b in [{"type": "text", "text": c}] if isinstance(c, str) else c if isinstance(c, list) else []:
            t = b.get("type") if isinstance(b, dict) else None
            if d.get("type") == "user" and t == "text":  # 道具の結果は tool_result なので入らない
                last.update((n, i) for n in COMMAND.findall(str(b.get("text"))))
            elif d.get("type") == "assistant" and t == "tool_use" and b.get("name") == "Skill":
                asked[str(b.get("id")).encode()] = str((b.get("input") or {}).get("skill", "")).removeprefix("desk-tools:")
            elif d.get("type") == "user" and t == "tool_result" and (n := asked.pop(str(b.get("tool_use_id")).encode(), None)) and not b.get("is_error"):
                last[n] = i  # 呼べた Skill だけ（断られた・失敗したものは SKILL.md が入っていない）
    return sorted((n for n in last if n in SKILLS), key=last.get, reverse=True)


def sha(x):
    return hashlib.sha1(str(x).encode()).hexdigest()[:16]


def spot(key):
    """key（会話の記録、ターン）の印のフォルダ。自分だけが書ける一時フォルダの下に置き、ほかの人が作ったフォルダやリンクは使わない（使えなければ None）。"""
    try:
        base = Path(tempfile.gettempdir()) / f"desk-tools-overlay-{getattr(os, 'getuid', lambda: 0)()}"  # 書ける一時フォルダがなければ、ここで OSError
        base.mkdir(mode=0o700, exist_ok=True)
        st = base.lstat()
    except OSError:
        return None
    if not stat.S_ISDIR(st.st_mode) or hasattr(os, "getuid") and (st.st_uid != os.getuid() or st.st_mode & 0o077):
        return None  # リンクか、ほかの人のフォルダか、ほかの人も書ける（/tmp に先に作られた）
    return base / sha(key[0]) / sha(key[1])


def claimed(key, p):
    """key のターンで p の印がもうあるか（ほかの hook が丸ごと出した）。調べられなければ False（出す）。"""
    try:
        return bool(key and (t := spot(key)) and (t / sha(p)).exists())
    except OSError:
        return False


def claim(key, p):
    """key のターンで p をまだ誰も出していなければ、印を置いて True。key がないか、印を置けなければ True（印なしで出す）。"""
    if not key or not (t := spot(key)):
        return True
    try:
        t.mkdir(parents=True, exist_ok=True)
        for x in t.parent.iterdir():  # 前のターンの印は要らない（今のターンのフォルダは消さない。同時に走るほかの hook が使う）
            if x != t:
                shutil.rmtree(x, ignore_errors=True)
    except OSError:  # 一時フォルダに書けない
        return True
    try:
        os.close(os.open(t / sha(p), os.O_CREAT | os.O_EXCL))
    except FileExistsError:  # ほかの hook がもう出した
        return False
    except OSError:  # 同時に消された
        pass
    return True


def size(parts):
    """parts をつないだ字数。"""
    return max(0, sum(len(x) + 2 for x in parts.values()) - 2)


def cut(parts, limit, ws):
    """parts（ファイル → 見出しから始まる中身）を limit 字まで（添え書きを含める）つなぎ、(文, 丸ごと出したファイル) を返す。
    切ったら、途中で切れたものと出せなかったもののパスを、入るだけ添える（どれを開けばよいか分かるように）。"""
    if size(parts) <= limit:
        return "\n\n".join(parts.values()), set(parts)
    out, room, items = [], limit - NOTE, [*parts.items()]
    for k, (p, x) in enumerate(items):
        if len(x) > room:  # ここで切る。見出しは HEAD に合わない形にする（出したと数えず、次に開いたときに出し直す）
            if room > x.index("\n") + 6:  # 見出しの行が丸ごと入るときだけ、途中まで出す（6 は「（途中まで）」の分）
                out.append(x.replace(": ", "（途中まで）: ", 1)[:room])
            break
        out.append(x)
        room -= len(x) + 2
    rest = [str(p.relative_to(ws)) for p, _ in items[k:]]
    notes = [f"\n\n（ここで切った。残りは {ws} の {'・'.join(rest[:n])}{f' ほか {len(rest) - n} 件' if n < len(rest) else ''} を自分で開いて読む）" for n in range(len(rest), 0, -1)]
    note = next((x for x in notes if len(x) <= NOTE), "\n\n（ここで切った。残りは、見出しのファイルとそのあとのものを自分で開いて読む）")  # 長ければ、頭から入るだけ挙げて残りは数にする
    return "\n\n".join(out) + note, {p for p, _ in items[:k]}


def main(mode):
    ev = json.load(sys.stdin)
    if mode == "pi":
        print(json.dumps({"context": overlays(ev.get("cwd", "."), ev.get("text", ""), is_path=bool(ev.get("isPath")), seen=set(HEAD.findall(ev.get("seen", ""))))}, ensure_ascii=False))
        return
    cwd, ti, event, log = ev.get("cwd", "."), ev.get("tool_input", {}), ev.get("hook_event_name", "PostToolUse"), transcript(ev)
    raw = functools.cache(lambda: read(log))  # 会話の記録は大きい（数十 MB）ので、出すものがあるときだけ、1 回だけ読む
    seen = lambda: shown(raw())
    turn = ev.get("turn_id") or ev.get("prompt_id")  # 同じターン（Codex は turn_id、Claude Code は 1 回の頼みごとの prompt_id）
    key = (lambda: (log, f"{turn}@{compacted(raw())}")) if log and turn else None  # コンパクションのあとは別の印にする（SessionStart の起きない子の会話でも）
    if event == "SessionStart":  # コンパクションのあと（hooks.json の matcher が compact）。paths のある決まりも前の版の SKILL.md の上書きもなければ、会話の記録を読まない
        ws = workspace(cwd)
        ctx = overlays(cwd, skill_md(invoked(raw()))) if ws and (any(desk.listed(m, "paths") for _, m in desk.rules(ws)) or any((ws / "rules").glob("*/SKILL.md"))) else ""  # 記録にはまだ今のコンパクションの印がない（前の部分が見える）ので、seen では外さない
    elif event == "UserPromptSubmit":
        ctx = called(cwd, ev.get("prompt", ""), seen, key)
    elif ev.get("tool_name") == "Skill":
        ctx = overlays(cwd, skill_md([str(ti.get("skill", ""))]), seen=seen, key=key)
    else:
        ctx = overlays(cwd, ti.get("file_path") or ti.get("command") or "", is_path=bool(ti.get("file_path")), seen=seen, key=key)
    if ctx:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False))


def selftest():
    os.environ["DESK_CONFIG"] = ""  # 手元の ~/.desk.toml に左右されない
    os.environ.pop("CLAUDE_PROJECT_DIR", None)
    with tempfile.TemporaryDirectory() as ws:
        (Path(ws) / "desk.toml").write_text("")
        (Path(ws) / "rules" / "deck-practices").mkdir(parents=True)
        (Path(ws) / "rules" / "slides-build").mkdir()
        fm = lambda *paths: f"---\ndescription: 試し\npaths: [{', '.join(paths)}]\n---\n"
        vis = lambda t: (Path(ws) / "rules" / "slides-build" / "visual.md").write_text(fm("slides-build/visual.md") + t)
        vis("本文は 16pt")
        (Path(ws) / "rules" / "deck-practices" / "SKILL.md").write_text(fm("deck-practices/SKILL.md") + "最初に聞くこと")
        sub = Path(ws) / "Customers" / "x"
        sub.mkdir(parents=True)
        assert "16pt" in overlays(sub, "/plug/skills/slides-build/visual.md")
        os.environ["CLAUDE_PROJECT_DIR"] = ws
        assert "16pt" in overlays("/", "/plug/skills/slides-build/visual.md")  # 会話の中でワークスペースの外（プラグインのフォルダ）へ cd したあと
        with tempfile.TemporaryDirectory() as old:
            (Path(old) / "factory.toml").write_text("")
            assert overlays(old, "/plug/skills/slides-build/visual.md") == ""  # 前の版のワークスペースの中へ cd したときは、開いたフォルダのワークスペースへも進まない
        del os.environ["CLAUDE_PROJECT_DIR"]
        assert overlays("/", "/plug/skills/slides-build/visual.md") == ""
        assert "16pt" in overlays(ws, "sed -n 1,40p slides-build/visual.md")  # Bash で読んだとき
        assert overlays(ws, f"{ws}/rules/slides-build/visual.md") == ""  # rules/ そのものを読んだときは出さない
        assert overlays(ws, "/plug/skills/deck-practices/content.md") == ""  # rules/ に同じファイルがない
        assert overlays(ws, "ls", seen=lambda: 1 / 0) == "" and "16pt" in overlays(ws, "slides-build/visual.md", seen=set)  # 出すものがなければ、会話の記録を読まない
        assert "最初に聞くこと" in overlays(ws, skill_md(["desk-tools:deck-practices"])) and overlays(ws, skill_md(["other:x"])) == overlays(ws, skill_md(["other:deck-practices"])) == ""  # ほかのプラグインの同じ名前のスキルは出さない
        assert CALL.findall("/desk-tools:slides-build と $desk-tools:deck-review、desk-tools:docs-build、$desk-tools:slides-builds") == ["slides-build", "deck-review"]  # 呼んだものだけ
        assert CALL.findall("さっきの /desk-tools:slides-build は x/$desk-tools:docs-build") == []  # 文の途中の / とパスの中は呼んでいない
        assert CALL.findall("資料を$desk-tools:slides-buildで作る") == ["slides-build"] and CALL.findall("/desk-tools:docs-buildで") == ["docs-build"]  # 和文が続いても切る
        assert "最初に聞くこと" in called(ws, "/desk-tools:deck-practices を回して") and called(ws, "$desk-tools:slides-build") == ""  # rules/ に SKILL.md のないスキル
        assert called(ws, "/desk-tools:deck-practices $desk-tools:deck-practices").count("最初に聞くこと") == 1
        assert overlays("/", "/plug/skills/slides-build/visual.md") == ""  # ワークスペースの外
        with tempfile.TemporaryDirectory() as home:  # 上に desk.toml がなければ、~/.desk.toml の workspace の rules/ を出す
            (Path(home) / "Documents" / "rules" / "slides-build").mkdir(parents=True)
            (Path(home) / "Documents" / "rules" / "slides-build" / "visual.md").write_text(fm("slides-build/visual.md") + "既定のワークスペースは 18pt")
            (Path(home) / ".desk.toml").write_text('workspace = "Documents"\n')
            os.environ["DESK_CONFIG"] = str(Path(home) / ".desk.toml")
            assert "18pt" in overlays("/", "/plug/skills/slides-build/visual.md") and "16pt" in overlays(sub, "slides-build/visual.md")  # 中で開けば、そのフォルダの desk.toml
            os.environ["CLAUDE_PROJECT_DIR"] = ws
            (Path(home) / "Documents" / "Customers").mkdir()
            assert "18pt" in overlays(Path(home) / "Documents" / "Customers", "slides-build/visual.md") and "16pt" in overlays("/", "slides-build/visual.md")  # ~/.desk.toml のワークスペースの中ならスクリプトと同じそこ、外なら開いたフォルダのもの
            del os.environ["CLAUDE_PROJECT_DIR"]
            (Path(home) / ".desk.toml").write_text("workspace = \n")
            assert overlays("/", "/plug/skills/slides-build/visual.md") == ""  # 読めない設定でも止まらない
            os.environ["CLAUDE_PROJECT_DIR"] = ws
            assert "16pt" in overlays("/", "/plug/skills/slides-build/visual.md")  # 読めない ~/.desk.toml で止まらず、開いたフォルダのワークスペースへ
            del os.environ["CLAUDE_PROJECT_DIR"]
            os.environ["DESK_CONFIG"] = ""
        deck = Path(ws) / "Customers" / "acme" / "deck_202610"
        deck.mkdir(parents=True)
        (Path(ws) / "Customers" / "acme" / "memory.md").write_text("- [ws-memory-001] 敬称は様")
        assert "敬称は様" in overlays(ws, f"{deck}/構成案.md")
        assert "敬称は様" in overlays(deck, "cat 社内メモ_経緯.md references.md")  # 資料のフォルダからの相対パス
        assert overlays(ws, f"{deck}/構成案.md references.md").count("敬称は様") == 1  # 同じ顧客は 1 回
        assert "敬称は様" in overlays(ws, f"{str(deck).replace('Customers', 'customers')}/構成案.md")
        assert overlays(ws, f"{deck}/build/pages.py") == "" and overlays(ws, f"{deck.parent}/memory.md") == ""  # 組む途中と memory そのものは出さない
        assert overlays(sub, "構成案.md") == ""  # memory.md のない顧客
        spaced = Path(ws) / "Customers" / "Acme Corp"
        (spaced / "d 1").mkdir(parents=True)
        (spaced / "memory.md").write_text("- [ws-memory-002] 略称は ACME")
        assert "ACME" in overlays(ws, f"{spaced}/d 1/構成案.md", is_path=True)  # 空白のあるフォルダは、パスを切らない
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/d 1/社内メモ_x.md'; ls")  # 引用符の中の空白
        assert "ACME" not in overlays(ws, "cat Customers/Acme Corp/d 1/構成案.md")  # 引用符がなければ別の語（シェルと同じ）
        (spaced / "資料(1)").mkdir()
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/資料(1)/構成案.md'|head")  # 引用符の中の括弧は切らない
        (spaced / "deck#2").mkdir()
        assert "ACME" in overlays(ws, "cat 'Customers/Acme Corp/deck#2/構成案.md'") and "ACME" in overlays(ws, "cd 'Customers/Acme Corp/d 1' && cat 構成案.md")  # # と cd
        assert "ACME" in overlays(ws, "(cd /tmp && ls); cd -P x; cd; cat 'Customers/Acme Corp/d 1/構成案.md'")  # サブシェル・cd -P・引数のない cd
        assert "ACME" not in overlays(ws, "cat ~nosuchuser/構成案.md") and "ACME" in overlays(ws, "cat 'Customers/Acme Corp/x/../d 1/references.md'")  # ~user で落ちない、.. を畳む
        log = Path(ws) / "t.jsonl"  # 会話の記録: 見えているものは出し直さず、コンパクションで消えたものは出し直す
        ctx = overlays(ws, f"cat '{spaced}/d 1/構成案.md' slides-build/visual.md")
        out = json.dumps({"hookSpecificOutput": {"additionalContext": ctx}}, ensure_ascii=False)  # hook の出力の写し（改行が \\n になる）
        log.write_text(json.dumps({"attachment": {"content": ctx, "stdout": out}}, ensure_ascii=False) + "\n")  # uuid のない記録（Codex の形）
        assert shown(read(log)) == {"rules/slides-build/visual.md", "Customers/Acme Corp/memory.md"} and shown(read(Path(ws) / "none.jsonl")) == shown(read(None)) == set()
        assert overlays(ws, f"cat '{spaced}/d 1/構成案.md' slides-build/visual.md", seen=shown(read(log))) == ""
        assert "16pt" in overlays(ws, "slides-build/visual.md", seen={"Customers/Acme Corp/memory.md"})  # 見えているのが別のものなら出す
        log.write_text(log.read_text() + '{"type":"system","subtype":"compact_boundary"}\n')
        assert shown(read(log)) == set() and "最初に聞くこと" in called(ws, "/desk-tools:deck-practices", shown(read(log)))
        log.write_text(log.read_text() + json.dumps({"uuid": "s1", "parentUuid": None, "isCompactSummary": True, "message": {"content": ctx}}, ensure_ascii=False) + "\n")
        assert shown(read(log)) == set()  # 要約に写った見出しは数えない
        hook = {"type": "hook_additional_context", "content": [ctx]}
        tree = [{"uuid": "u1", "parentUuid": None, "attachment": {"type": "hook_success", "stdout": out}}, {"uuid": "u2", "parentUuid": "u1", "attachment": hook},
                {"uuid": "u3", "parentUuid": "u1", "attachment": {"type": "hook_additional_context", "content": "<persisted-output>" + ctx[:2000]}},
                {"uuid": "u5", "parentUuid": "u3", "attachment": {"type": "hook_additional_context", "content": [ctx[:10000] + "\n[Hook additionalContext truncated at 10000 chars — persist-to-disk failed: x]"]}},
                {"type": "api-request-blob", "content": ctx}]  # uuid のない API への写し
        log.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in tree) + "\n")
        assert shown(read(log)) == set()  # 巻き戻して捨てた枝（u2）に出したもの、stdout と API への写し、ファイルに逃がしたもの（u3）と書けずに切ったもの（u5）は、見えていない
        log.write_text(log.read_text() + json.dumps({"uuid": "u4", "parentUuid": "u2"}) + "\n")
        assert shown(read(log)) == {"rules/slides-build/visual.md", "Customers/Acme Corp/memory.md"}  # 今の枝なら数える
        assert transcript({"transcript_path": "/p/s1.jsonl", "agent_id": "a9"}) == "/p/s1/subagents/agent-a9.jsonl" and transcript({"transcript_path": "/p/s1.jsonl"}) == "/p/s1.jsonl"
        (spaced / "memory.md").write_text("い" * (LIMIT + 10))
        both = overlays(ws, f"cat '{spaced}/d 1/構成案.md' slides-build/visual.md")
        assert "本文は 16pt" in both and "Customers/Acme Corp/memory.md を自分で開いて読む" in both  # 長い memory が決まりを押し出さない。開くファイルを示す
        assert HEAD.findall(both) == ["rules/slides-build/visual.md"] and "顧客の memory（途中まで）: Customers/Acme Corp/memory.md" in both  # 途中で切ったものは出したと数えない
        vis("あ" * (LIMIT + 10))
        both = overlays(ws, f"cat '{spaced}/d 1/構成案.md' slides-build/visual.md deck-practices/SKILL.md")
        assert len(both) <= LIMIT and both.count("ここで切った") == 2  # 両方が長ければ半分ずつ。Claude Code の 1 万字に収める（超えると頭の 2,000 字しか見えない）
        assert len(overlays(ws, "slides-build/visual.md")) <= LIMIT  # 決まりだけでも
        assert "rules/slides-build/visual.md・" in both and "rules/deck-practices/SKILL.md を自分で開いて読む" in both  # 切れたものと、そのあとで出せなかったもの
        vis("本文は 16pt")
        tempfile.tempdir = ws  # 印は selftest の中に置く
        k1, k2 = (str(log), "p1"), (str(log), "p2")
        assert "敬称は様" in overlays(deck, "構成案.md", key=k1) and overlays(deck, "references.md", key=k1) == ""  # 同じターンに並べて読んだら 1 回
        assert "16pt" in overlays(ws, "slides-build/visual.md", key=k1) and "敬称は様" in overlays(deck, "references.md", key=k2)  # ほかのものと、次のターン
        assert [x.name for x in spot(k2).parent.iterdir()] == [spot(k2).name]  # 前のターンの印は消す
        at = compacted(read(log))
        log.write_text(log.read_text() + '{"type":"system","subtype":"compact_boundary"}\n')
        assert compacted(read(log)) > at and "敬称は様" in overlays(deck, "references.md", key=(str(log), f"p2@{compacted(read(log))}"))  # コンパクションのあとは別の印（同じターンでも出し直す）
        vis("あ" * (LIMIT + 10))
        assert "ここで切った" in overlays(ws, "slides-build/visual.md", key=k2) and "ここで切った" in overlays(ws, "slides-build/visual.md", key=k2)  # 切ったものには印を置かない
        vis("う" * 5000)
        (deck.parent / "memory.md").write_text("え" * 6000)
        k4 = (str(log), "p4")
        assert "ここで切った" in overlays(deck, "cat 構成案.md slides-build/visual.md", key=k4) and "う" * 5000 in overlays(ws, "slides-build/visual.md", key=k4)  # 同じターンでほかの hook が途中までしか出さなかったものは、丸ごと出す
        k7 = (str(log), "p7")
        assert "え" * 6000 in overlays(deck, "構成案.md", key=k7)
        b = overlays(deck, "cat references.md slides-build/visual.md", key=k7)
        assert "う" * 5000 in b and "え" not in b  # ほかの hook が丸ごと出したものは、ここで途中までになるものでも外す（空いた字数で決まりを丸ごと出す）
        vis("本文は 16pt")
        (deck.parent / "memory.md").write_text("- [ws-memory-001] 敬称は様")
        k5 = (str(log), "p5")
        assert "敬称は様" in overlays(deck, "構成案.md", key=k5)
        again = overlays(deck, "cat 構成案.md slides-build/visual.md", key=k5)
        assert "16pt" in again and "敬称は様" not in again  # ほかの hook が出したものだけ外して組み直す
        rng = __import__("random").Random(0)
        for _ in range(300):  # どんな大きさの組み合わせでも、上限を超えず、丸ごと出したと数えたものは丸ごと入っている
            rp = {Path(ws) / f"r{i}": f"## ワークスペースの決まり: rules/r{i}.md\n\n" + "あ" * rng.choice([0, 300, 4400, 4600, 12000]) for i in range(rng.randint(0, 5))}
            mp = {Path(ws) / f"m{i}": f"## 顧客の memory: Customers/m{i}/memory.md\n\n" + "い" * rng.choice([0, 3000, 4500, 9500]) for i in range(rng.randint(0, 3))}
            room = LIMIT - 2 if rp and mp else LIMIT
            keep = min(size(rp), max(room // 2, room - size(mp)))
            (rt, rw), (mt, mw) = cut(rp, keep, Path(ws)), cut(mp, room - keep, Path(ws))
            assert len("\n\n".join(x for x in (rt, mt) if x)) <= LIMIT and all(rp.get(p, mp.get(p)) in rt + mt for p in rw | mw)
        odd = Path(ws) / "Customers" / 'A"B'
        (odd / "d").mkdir(parents=True)
        (odd / "memory.md").write_text("か" * (LIMIT + 10))
        long = overlays(ws, f"cat '{odd}/d/構成案.md'")
        assert len(long) <= LIMIT and 'Customers/A"B/memory.md を自分で開いて読む' in long  # HEAD に合わない名前でも、切って止まらない
        (odd / "memory.md").write_text("- 短い")
        assert "短い" in overlays(ws, f"cat '{odd}/d/構成案.md'", key=(str(log), "p6")) and overlays(ws, f"cat '{odd}/d/構成案.md'", key=(str(log), "p6")) == ""  # 印も置く
        shutil.rmtree(odd)
        many = [f"slides-build/x{i:02d}.md" for i in range(40)]
        for x in many:
            (Path(ws) / "rules" / x).write_text(fm(x) + "お" * 300)
        cut40 = overlays(ws, " ".join(many))
        assert len(cut40) <= LIMIT and "ほか" in cut40 and "ここで切った" in cut40  # 添え書きも上限に入れる（長ければ数にする）
        for x in many:
            (Path(ws) / "rules" / x).unlink()
        uid = getattr(os, "getuid", lambda: 0)()
        (Path(ws) / "t2").mkdir()
        (Path(ws) / "t2" / f"desk-tools-overlay-{uid}").write_text("")  # 置き場の名前がファイル
        (Path(ws) / "t3").mkdir()
        (Path(ws) / "t3" / f"desk-tools-overlay-{uid}").symlink_to(Path(ws) / "Customers")  # 置き場がリンク（ほかの人が仕掛けた）
        (Path(ws) / "t4" / f"desk-tools-overlay-{uid}").mkdir(parents=True)
        (Path(ws) / "t4" / f"desk-tools-overlay-{uid}").chmod(0o777)  # ほかの人も書ける
        def no_tmp():
            raise FileNotFoundError("No usable temporary directory found")
        gettemp = tempfile.gettempdir
        for bad in ("desk.toml", "t2", "t3", "t4", ""):  # 印を置けない（ファイルの下にフォルダは作れない、ほか。"" は書ける一時フォルダがない）
            tempfile.tempdir, tempfile.gettempdir = str(Path(ws) / bad), gettemp if bad else no_tmp
            assert "16pt" in overlays(ws, "slides-build/visual.md", key=(str(log), "p3")) and "16pt" in overlays(ws, "slides-build/visual.md", key=(str(log), "p3"))  # 止まらず、印なしで出す
        tempfile.gettempdir = gettemp
        assert sorted(x.name for x in (Path(ws) / "Customers").iterdir()) == ["Acme Corp", "acme", "x"]  # リンクの先は消さない
        tempfile.tempdir = ws
        log.write_text('{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Skill","input":{"skill":"desk-tools:slides-build"}}]}}\n'
                       '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"Launching skill: desk-tools:slides-build"}]}}\n'
                       '{"type":"user","message":{"content":"<command-name>/desk-tools:deck-practices</command-name>"}}\n'
                       '{"type":"user","message":{"content":"<command-name>/other:deck-review</command-name> \\"skill\\":\\"desk-tools:docs-build\\""}}\n'
                       '{"type":"user","message":{"content":[{"type":"tool_result","content":"<command-name>/desk-tools:docs-build</command-name>"}]}}\n'
                       '{"type":"user","isCompactSummary":true,"message":{"content":"<command-name>/desk-tools:docs-build</command-name>"}}\n'
                       '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t2","name":"Skill","input":{"skill":"desk-tools:docs-build"}}]}}\n'
                       '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","is_error":true,"content":"denied"}]}}\n')
        assert invoked(read(log)) == ["deck-practices", "slides-build"] and invoked(b"") == []  # 新しい順。ほかのプラグイン、文字列の中の写し、道具の結果、要約、断られた Skill は数えない
        again = overlays(ws, skill_md(invoked(read(log))))
        assert "最初に聞くこと" in again and "16pt" not in again  # 付け直される SKILL.md の上書きだけ（slides-build は rules/ に SKILL.md がない）
        r = Path(ws) / "rules"
        (r / "diagram_extra.md").write_text(fm("slides-build/pages.md", "slides-build/diagrams.md") + "矢印は太く")
        (r / "all_slides.md").write_text(fm("slides-build/*") + "スライド全部")
        (r / "slides-build" / "api.md").write_text("前の形（frontmatter がない）")
        assert "矢印は太く" in overlays(ws, "/plug/skills/slides-build/diagrams.md") and "矢印は太く" in overlays(ws, "slides-build/pages.md")  # 1 つのファイルから、分けた両方を指す
        assert "スライド全部" in called(ws, "/desk-tools:slides-build") and "スライド全部" not in called(ws, "/desk-tools:docs-build")  # * で、そのスキルのどのファイルにも
        legacy = overlays(ws, "slides-build/api.md")
        assert "前の形" in legacy and "desk-migrate" in legacy  # 前の版の同じパスの上書き（frontmatter がない）は、desk-migrate を回すまで前と同じに出す
        assert "前の形" not in overlays(ws, "slides-build/pages.md")  # ほかのパスには出さない
        (r / "customer.md").write_text("---\ndescription: 顧客向けの資料\naudience: [顧客向け]\n---\n- 顧客の言葉で書く")
        (r / "update.md").write_text("---\ndescription: 製品のアップデートをまとめるとき\ntargets: [slides]\n---\n- 効くものだけ選ぶ")
        start = overlays(ws, "/plug/skills/deck-practices/start.md")
        assert "の一覧: rules/*.md" in start and "rules/customer.md（全部、顧客向け）: 顧客向けの資料" in start and "rules/update.md（slides、全部）" in start
        assert "diagram_extra" not in start and "顧客の言葉で書く" not in start and HEAD.findall(start) == [INDEX]  # paths のあるものは一覧に入れず、中身も出さない
        assert overlays(ws, "/plug/skills/deck-practices/start.md", seen={INDEX}) == ""  # 見えている一覧は出し直さない
        outline = deck / "構成案.md"
        outline.write_text("# 構成案\n\n- **資料の種類:** 顧客向け\n")
        first = overlays(ws, str(outline), is_path=True)
        assert "の一覧: rules/*.md" in first and "敬称は様" in first  # 「使う決まり」がまだない構成案は、memory と一覧
        outline.write_text("# 構成案\n\n- **使う決まり:** rules/customer.md、rules/update.md\n")
        picked = overlays(ws, str(outline), is_path=True)
        assert "顧客の言葉で書く" in picked and "効くものだけ選ぶ" in picked and "の一覧" not in picked and "敬称は様" in picked
        assert HEAD.findall(picked) == ["rules/customer.md", "rules/update.md", "Customers/acme/memory.md"]
        assert "効くものだけ選ぶ" in overlays(deck, "cat references.md") and overlays(ws, str(outline), is_path=True, seen=set(HEAD.findall(picked))) == ""  # 同じフォルダの構成案から
        outline.write_text("- 使う決まり：なし\n")
        assert "の一覧" not in (none := overlays(ws, str(outline), is_path=True)) and "顧客の言葉" not in none and "敬称は様" in none
        mem_file, big = Path(ws) / "Customers" / "acme" / "memory.md", "---\ndescription: 大きい\n---\n"
        keep_mem = mem_file.read_text()
        mem_file.write_text("め" * 6000)
        (r / "big.md").write_text(big + "き" * (desk.RULE_MAX - len(big)))
        (r / "mid.md").write_text(big + "ま" * 1000)
        outline.write_text("- **使う決まり:** rules/big.md、rules/mid.md\n")
        full = overlays(ws, str(outline), is_path=True)
        assert "き" * (desk.RULE_MAX - len(big)) in full and HEAD.findall(full)[0] == "rules/big.md" and "rules/mid.md" in full and len(full) <= LIMIT  # 上限の大きさのファイルは、ほかのファイルと長い memory が並んでも丸ごと出す（入りきらないものは添え書きで挙げる）
        for i in range(30):
            (r / f"free{i:02}.md").write_text(f"---\ndescription: {'い' * 60}\n---\n- x")
        head = fm("deck-review/prompt_slides.md")
        (r / "bigp.md").write_text(head + "ぱ" * (desk.RULE_MAX - len(head)))
        outline.write_text("# 構成案\n")
        both = overlays(ws, f"cat {shlex.quote(str(outline))} /plug/skills/deck-review/prompt_slides.md")
        assert HEAD.findall(both)[0] == "rules/bigp.md" and "ぱ" * (desk.RULE_MAX - len(head)) in both and len(both) <= LIMIT  # 一覧が長くても、開いたファイルに当たる決まりを先に丸ごと出す
        mem_file.write_text(keep_mem)
        outline.write_text("- **使う決まり:** rules/mid.md、rules/nope.md\n")
        gone = overlays(ws, str(outline), is_path=True)
        assert "rules/nope.md は、決まりのファイルにない" in gone and "ま" * 1000 in gone and HEAD.findall(gone)[:2] == ["rules/mid.md", INDEX]  # 書いた名前の決まりがなければ、選び直す一覧を出す
        again = overlays(ws, str(outline), is_path=True, seen=set(HEAD.findall(gone)))
        assert "rules/nope.md は、決まりのファイルにない" in again and "の一覧:" not in again  # 一覧が見えていても、直すまで知らせは出す
        for line, word in (("- **使う決まり:** customer.md", "customer.md は"), ("- **使う決まり:**", "（空） は"), ("- **使う決まり:** rules/mid.md、b.md、rule/c.md", "b.md・rule/c.md は"), ("- 使う決まり: /Users/x/決まり.md", "/Users/x/決まり.md は")):
            outline.write_text(line + "\n")
            assert word in overlays(ws, str(outline), is_path=True), line  # rules/ のパスのない行は、「なし」と同じにしない
        for x in [*r.glob("free*.md"), r / "bigp.md", r / "big.md", r / "mid.md"]:
            x.unlink()
        internal = Path(ws) / "Internal" / "lt_202610"
        internal.mkdir(parents=True)
        (internal / "構成案.md").write_text("- 使う決まり: rules/update.md\n")
        assert "効くものだけ選ぶ" in (inside := overlays(internal, "sed -n 1,20p 構成案.md")) and "memory" not in inside  # 社内向けの資料にも。memory はない
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1] if sys.argv[1:] else "claude"))
