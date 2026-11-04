#!/usr/bin/env python3
"""ワークスペースと設定のファイルの探し方。スキルのスクリプトが、ここだけで探す（標準ライブラリだけ）。
1. 今いるフォルダから上へ desk.toml を探す。見つかれば、そのフォルダがワークスペースで、その desk.toml だけを読む（workspace を書いても読まない）。
2. なければ個人の設定（DESK_CONFIG のパス、なければ ~/.desk.toml）を読み、その workspace をワークスペースにする（資料・recipes/・.desk/ はそこに置く）。
   上に前のバージョンの factory.toml があれば、2 に進まない（移す前のワークスペースの中で、別のワークスペースに書かない）。workspace が前のバージョンのワークスペースなら止める。
3. どちらもなければ None（呼ぶ側が止めて desk-init を案内する）。
2 つを混ぜない（sandbox の desk.toml に書き忘れた [drive] が ~/.desk.toml から入ると、本番の Drive に書くため）。
DESK_CONFIG を空にすると 2 を飛ばす（selftest と開発の worktree。~/.desk.toml の本番のワークスペースに戻らない）。
ワークスペースの決まり（レシピ。recipes/ の下の <名前>/RECIPE.md で、frontmatter に description のあるもの）の探し方と、どの作業のものか（kind・triggers）も、ここに置く（rules・front）。
レシピは、作る会話が作業に入るときに自分で開く（2026-11-04 に hook をやめた。desk-feedback の routing.md の「Workspace rules」）。開くものは desk.py recipes が出す。
usage: desk.py                      ワークスペースのパスを出す（なければ exit 1）
       desk.py recipes [<資料のフォルダ>]  レシピの一覧を、いつ開くものかで分けて出す。資料のフォルダ（か、その中のファイル）を渡すと、
                                    その資料で開くもの（構成案の「使う決まり」のレシピと、顧客の memory.md）も出す
       desk.py --selftest"""
import fnmatch, json, os, re, sys, tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:  # desk-dreaming の snapshot.sh は素の python3 で回る。上へたどって見つかるとき（1）は、TOML を読まないので 3.11 より前でも動かす
    tomllib = None

NAME, OLD = "desk.toml", "factory.toml"  # OLD は 2026-10-25 より前の設定の名前（desk-migrate で移す）
RULE_MAX = 3800  # 決まりの 1 ファイルの字数の上限。作る会話は、作業に入るたびに当たるレシピを 1 本ずつ全文で開くので、1 本を短く保ち、もっと狭い目的で分ける（desk-feedback の routing.md の「Workspace rules」。2026-10-27 に hook の差し込みの上限から決めた値を、hook をやめたあとも保つ）
TARGETS, AUDIENCES = ("slides", "docs", "vids"), ("顧客向け", "社内向け", "コミュニティ向け")  # frontmatter の targets・audience の値（audience は deck-content-039 の資料の種類）
RECIPES, RECIPE = "recipes", "RECIPE.md"  # ワークスペースの決まりのフォルダと、決まりを書くファイル（recipes/<名前>/RECIPE.md。2026-10-29 に rules/<名前>.md から替えた）
AGENTS_TEMPLATE = ("決まりの優先", "基本方針", "いい資料の考え方", "資料を作る・直すとき", "修正の指示", "調べもの", "社外秘と顧客の情報", "書き方", "フォルダの置き方")  # 2026-10-31 までの desk-init の AGENTS.md の節（## か ###。題を書き替えた写しにも残る）
# スキルのあいだで同じ中身を持つスクリプト → 持ち主のスキル（2026-11-02 に lib/ をやめた）。直すのは持ち主だけで、ほかのスキルの scripts/ の同じ名前のファイルは写し
# （tests/skills/check.py --sync が写し、同じ中身かを見る）。ledger.py は決まりの ID を持ち主のファイルでだけ数え、前の台帳の ../lib/<名前>.py を持ち主のファイルとして読む
SHARED = {"desk.py": "desk-init", "gapi.py": "build-slides", "brand.py": "build-slides", "textlint.py": "build-slides", "sheet.py": "build-slides",
          "notes.py": "build-slides", "wording.py": "build-slides", "ledger.py": "desk-feedback", "refs.py": "deck-workflow", "doctor.py": "desk-init"}
COPIES = {"desk-migrate/templates/drive_folders.md": "desk-init/templates/drive_folders.md",  # スクリプトでない写し（<スキル>/<パス> → 持ち主。フォルダなら中のファイルをみな）
          "desk-migrate/templates/recipes/README.md": "desk-init/templates/recipes/README.md",
          "build-docs/assets/gcp": "build-slides/assets/gcp"}  # build-docs の assets/README.md は自分のもの（build-slides の台帳を名前で指す）
STEPS = ("gather", "build")  # frontmatter の step の値。書かなければ、資料を作るどの作業でも開く（per_material: true は、資料ごとに選ぶ）
TRIGGERS = {  # プラグインのファイル（<スキル>/<ファイル>）→ そのファイルの作業（その作業で開くレシピの種類）。make は step のないもの（資料を作るどの作業でも）。
    # 作る会話はこの表を読まない（スキルの md が、その作業でレシピを開くように書く）。ledger.py の --auto（消す項目が、その作業のファイルのどれにもあるか）と、migrate.py（前の paths を step にする）と、desk-dreaming の sessions.py（make のファイルを開いた会話を、作り方の表を開いたと数える）が使う
    "gather": ("deck-workflow/materials.md", "deck-workflow/start.md", "deck-workflow/research.md", "customer-profile/*", "desk-crawl/*", "desk-research/*"),
    "build": ("build-slides/*", "build-docs/*", "build-vids/*", "deck-design/slides.md", "deck-design/docs.md", "deck-workflow/slides_steps.md", "deck-workflow/prompt_pages.md", "deck-workflow/reuse.md"),
    "make": ("deck-workflow/*", "deck-writing/*", "deck-design/*", "deck-review/*", "desk-feedback/SKILL.md", "desk-feedback/routing.md", "build-slides/*", "build-docs/*", "build-vids/*")}


def loads(text, where):
    """TOML を読む。desk.py が TOML を読むのはここだけ。読めなければ止める（止めるのは SystemExit だけ。import のときに読む brand.py・doctor.py は、これだけを受けて続ける）。"""
    if not tomllib:
        sys.exit(f"{where}: 読むには Python 3.11 以上が要る（今は {sys.version.split()[0]}）")
    try:
        return tomllib.loads(text)
    except ValueError as e:  # TOMLDecodeError
        sys.exit(f"{where}: 読めない（{e}）")


def user_config():
    """個人の設定のパス（DESK_CONFIG、なければ ~/.desk.toml）。DESK_CONFIG が空なら None。"""
    p = os.environ.get("DESK_CONFIG", "~/.desk.toml")
    return Path(os.path.expanduser(p)) if p else None  # Path.expanduser は ~user で例外を出す


def pointed():
    """(個人の設定のファイル, その workspace のパス)。フォルダがあるかは見ない（desk-init が、まだないフォルダを指す設定でも確かめる）。ファイルがなければ None。読めないときは止める。"""
    if not ((p := user_config()) and p.is_file()):
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:  # 読めない、UTF-8 でない
        sys.exit(f"{p}: 読めない（{e}）")
    w = loads(text, p).get("workspace")
    if not isinstance(w, str) or not w.strip():
        sys.exit(f'{p} に workspace（資料を置くフォルダ）がない。頭（最初の表の前）に workspace = "~/Documents" のように手で書く')
    try:
        return p, (p.parent / os.path.expanduser(w)).resolve()  # 相対のパスは設定のファイルのフォルダから
    except (OSError, RuntimeError) as e:  # リンクの輪など
        sys.exit(f"{p} の workspace（{w}）をたどれない: {e}")


def user():
    """(個人の設定のファイル, その workspace)。ファイルがなければ None。読めない・workspace がない・そのフォルダがない・前のバージョンのワークスペースのときは止める（黙ってほかへ移らない）。"""
    if not (f := pointed()):
        return None
    p, ws = f
    if not ws.is_dir():
        sys.exit(f"{p} の workspace（{ws}）のフォルダがない。作るか、正しいパスに直す")
    if o := old(ws):  # 外から開いても、移す前のワークスペースに書かない（記録が .factory/ と .desk/ に分かれる）
        sys.exit(f"{p} の workspace（{ws}）は、前のバージョンのワークスペース（{o}/factory.toml）。先に {o} で desk-migrate の apply を回し、"
                 f"できた desk.toml の値を {p} に寄せてから、その desk.toml を .desk/migrate/ に移す（desk-migrate の SKILL.md の「Move the settings to `~/.desk.toml`」の 2）")
    return f


def local(start="."):
    """start から上へたどって最初の desk.toml: (desk.toml, そのフォルダ)。なければ None。前のバージョンのワークスペース（factory.toml）に先に着いたら、
    その上の desk.toml へは進まない（新しいワークスペースの中に置いた、移す前のワークスペースで、外側に書かない）。"""
    d = Path(start).resolve()
    for x in (d, *d.parents):
        if (x / NAME).is_file():
            return x / NAME, x
        if (x / OLD).is_file():
            return None
    return None


def copied(f):
    """プラグインのファイル f が、ほかのスキルの持つ写しか（SHARED の名前で持ち主でないスキルの scripts/ にあるもの、scripts/yomiyasu/ の下）。決まりの ID は数えない。"""
    f = Path(f)
    if "yomiyasu" in f.parts[:-1] and "scripts" in f.parts[:-1] or any(f"/{k}/" in f"/{f.as_posix()}/" for k in COPIES):
        return True
    return f.parent.name == "scripts" and f.name in SHARED and f.parent.parent.name != SHARED[f.name]


def old(start="."):
    """start から上へたどって最初の、前のバージョンの factory.toml のフォルダ。なければ None。"""
    d = Path(start).resolve()
    return next((x for x in (d, *d.parents) if (x / OLD).is_file()), None)


def locate(start="."):
    """(設定のファイル, ワークスペース)。なければ None（言葉は missing）。上に前のバージョンの factory.toml があるときも None にして 2 に進まない
    （移す前のワークスペースの中で、~/.desk.toml の別のワークスペースに書かない）。"""
    return local(start) or (None if old(start) else user())


def missing(start="."):
    """locate が None のときに止める言葉。前のバージョンのワークスペースなら desk-migrate、なければ desk-init を案内する。"""
    if o := old(start):
        return f"{o} は前のバージョンのワークスペース（factory.toml）。desk-migrate で desk.toml に移す"
    looked = f"{u} もない" if (u := user_config()) else "DESK_CONFIG が空なので、個人の設定は読まない"
    return f"desk.toml が見つからない（今いるフォルダから上へ探した。{looked}）。desk-init で作る（ワークスペースの直下の desk.toml か、~/.desk.toml）"


def front(text):
    """md の先頭の frontmatter（--- の行の間の「key: value」）。値は 1 行の文字、[a, b] の並び、続く「  - a」の行の並び。閉じていない・ないときは {}。"""
    lines = text.lstrip("﻿").split("\n")
    if lines[0].strip() != "---":
        return {}
    out, key = {}, None
    for x in lines[1:]:
        if x.strip() == "---":
            return out
        if key and x.lstrip().startswith("- ") and (out[key] == "" or isinstance(out[key], list)):  # 値を書かなかった key の並び（paths:\n  - a.md）
            out[key] = [*out[key], x.strip()[2:].strip().strip("'\"")]
            continue
        k, sep, v = x.partition(":")
        key = None
        if sep and k.strip() and not x.startswith((" ", "\t", "#")):
            key, v = k.strip(), v.strip()
            v = v[:v.find(v[0], 1) + 1] if v[:1] in ("'", '"') and v.find(v[0], 1) > 0 else v.split(" #")[0].strip()  # 引用符の中の # はコメントでない
            v = "" if v[:1] in ("|", ">", "#") else v  # 複数行の値（description: >）は読まない（値のないものとして、doctor.py・gate が知らせる）。# から後ろはコメント
            out[key] = [s.strip().strip("'\"") for s in v[1:-1].split(",") if s.strip()] if v.startswith("[") and v.endswith("]") else v.strip("'\"")
    return {}


def described(meta):
    """frontmatter の description（1 行の文字）。ないか、文字でなければ ""。"""
    d = meta.get("description")
    return d if isinstance(d, str) else ""


def listed(meta, key):
    """frontmatter の key を並びにする（1 つだけ書いたものも）。"""
    v = meta.get(key) or []
    return [v] if isinstance(v, str) else v


def kind(meta):
    """レシピの出し方: material（per_material: true。資料ごとに選び、構成案の「使う決まり」に書く）、gather・build（その作業のとき）、make（資料を作るどの作業でも）。"""
    if str(meta.get("per_material", "")).lower() == "true":
        return "material"
    return s if (s := meta.get("step")) in STEPS else "make"


def triggers(ref):
    """プラグインのファイル ref（<スキル>/<ファイル>）の作業で開くレシピの種類。"""
    return {k for k, globs in TRIGGERS.items() if any(fnmatch.fnmatchcase(ref, g) for g in globs)}


def rules(ws):
    """ワークスペースの決まり（レシピ）[(RECIPE.md のパス, frontmatter)]。recipes/ の下の RECIPE.md で、frontmatter に description のあるもの。
    RECIPE.md のないフォルダは、レシピを集めるフォルダ。レシピのフォルダのほかのファイル（テンプレート・checks.py など）は資源で、決まりとして出さない。
    テンプレートの templates/ の下は見ない。"""
    root = Path(ws) / RECIPES
    out = []
    for p in sorted(root.rglob(RECIPE)) if root.is_dir() else []:
        if "templates" in p.relative_to(root).parts[1:-1] or p.parent == root or not p.is_file():  # レシピのフォルダの中の templates/（recipes/templates/ という名前のレシピは見る）と、フォルダのない recipes/RECIPE.md
            continue
        try:
            meta = front(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # 読めない、UTF-8 でない
            continue
        if described(meta):
            out.append((p, meta))
    return out


def with_workspace(text, ws):
    """設定の文字列の先頭（頭のコメントのあと、最初の値か表の前）に workspace を足す（desk-init と desk-migrate が ~/.desk.toml を書くとき）。ホームの下は ~/ で書く。
    書けないときは止める（何も書かない）。"""
    if "workspace" in loads(text, "写す設定"):  # フォルダの desk.toml では読まない値。どちらを残すかは人が決める
        sys.exit("写す設定の先頭に workspace がもうある（フォルダの desk.toml では読まない値）。その行を消してから回す")
    ws = Path(ws).resolve()
    home = Path.home().resolve()
    value = "~/" + ws.relative_to(home).as_posix() if ws.is_relative_to(home) else str(ws)
    line = f"workspace = {json.dumps(value, ensure_ascii=False)}  # 資料・recipes/・.desk/ を置くフォルダ（ワークスペース。ここには desk.toml を置かない）\n\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):  # 最後の行に改行がなくても、続けて書かない
        lines[-1] += "\n"
    i = next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith("#")), len(lines))  # 最初の行の値か表。複数行の値の途中には入らない
    out = "".join(lines[:i]) + line + "".join(lines[i:])
    if loads(out, "書いたあとの設定").get("workspace") != value:  # 書いたあとも読める
        sys.exit(f"workspace を書けない（{value}）。設定の先頭に手で書く")
    return out


def old_agents(ws):
    """ワークスペースの AGENTS.md が、2026-10-31 までの desk-init の雛形の写しか（その節の見出しが半分より多く残る）。
    doctor.py が、レシピに移すよう知らせるための目安（台帳は AGENTS.md を決まりのファイルにしない）。持ち主が書いた AGENTS.md は、プラグインは読まない。"""
    try:
        text = (Path(ws) / "AGENTS.md").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    text = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", text)  # コードの囲みの中の見出しは数えない（引いただけのもの）
    heads = {m.group(1).strip() for m in re.finditer(r"(?m)^#{2,3}\s+(.+?)\s*$", text)}
    return len(heads & set(AGENTS_TEMPLATE)) > len(AGENTS_TEMPLATE) // 2

RULE_PATH = r"recipes/[\w./-]+?/RECIPE\.md"  # 「使う決まり」に書くレシピのパス
USE = re.compile(r"(?m)^[ \t]*(?:[-*][ \t]*)?\**使う決まり\**[ \t]*[:：]\**(.*)$")  # 構成案の先頭の「使う決まり」の行（- **使う決まり:** recipes/a/RECIPE.md、recipes/b/RECIPE.md）
GROUPS = (("make", "どの作業でも（step なし）", "資料を書く・組む・レビューするとき。資料を作り始めるときに開き、ページを書くサブエージェントとレビューのサブエージェントにも渡す"),
          ("gather", "集めるとき（step: gather）", "材料を集めるとき（手順 1〜5、顧客の profile、定期の収集）と、調べもの"),
          ("build", "組むとき（step: build）", "Google Slides・Docs・Vids に組むとき（組む前に開く）"))


def workspace(cwd):
    """スクリプトが cwd で使うワークスペース（desk.locate）。cwd がその中になければ（プラグインのフォルダなど）、会話を開いたフォルダ（Claude Code の CLAUDE_PROJECT_DIR）から探したもの。
    Claude Code は会話の中で cd した先を cwd に渡すので、プラグインのフォルダへ cd したあとも、開いたワークスペースを見つける（2026-10-27 に資料を作る会話で見つけた）。
    前のバージョンのワークスペース（factory.toml）の中では、どこへも進まない（desk.locate と同じ）。個人の設定が読めなくても止めない（スクリプトが止めて知らせる）。"""
    def find(d):
        try:
            return locate(d)
        except SystemExit:
            return None
    f = find(cwd)
    if not (f and Path(cwd).resolve().is_relative_to(f[1])) and not old(cwd) and (p := os.environ.get("CLAUDE_PROJECT_DIR")):
        if not local(p) and old(p):  # 会話を開いたのが前のバージョンのワークスペース（その中の新しいワークスペースでなく）なら、~/.desk.toml の別のワークスペースにも進まない（found が desk-migrate を案内する）
            return None
        f = find(p) or f
    return f[1] if f else None


def found(cwd):
    """スクリプトが cwd で使うワークスペース（workspace）。なければ止める。設定が読めない・指すフォルダがない・前のバージョンのときは、その理由で止める（workspace は理由を捨てるので、locate に言わせる）。"""
    if not (ws := workspace(cwd)):
        locate(cwd)
        opened = os.environ.get("CLAUDE_PROJECT_DIR")  # 会話を開いたフォルダが前のバージョンのワークスペースなら、desk-migrate を案内する
        sys.exit(missing(opened if opened and not local(opened) and old(opened) else cwd))
    return ws


def materials(files):
    """資料ごとに選ぶレシピ（per_material: true のもの）。desk.py recipes と desk-feedback の recipe_menu.py が同じ選び方をする。"""
    return [(p, m) for p, m in files if kind(m) == "material"]


def row(ws, p, m):
    """レシピの一覧の 1 行（パス（作るもの、資料の種類）: いつ使うか）。フォルダのほかのファイル（テンプレート・checks.py・画像）があれば、名前を 5 つまで添える。"""
    nested = {q.parent for q in p.parent.rglob(RECIPE) if q != p}  # 中のレシピのフォルダ（そのファイルは、そのレシピのもの）
    files = []
    for x in p.parent.rglob("*"):
        rel = x.relative_to(p.parent)
        if x.is_file() and x != p and not any(s.startswith(".") or s == "__pycache__" for s in rel.parts) and not any(d in nested for d in x.parents):
            files.append(rel.as_posix())
    files.sort()
    more = f"（資源: {'・'.join(files[:5])}{f' ほか {len(files) - 5} 件' if len(files) > 5 else ''}）" if files else ""
    return f"- {p.relative_to(ws)}（{'・'.join(listed(m, 'targets')) or '全部'}、{'・'.join(listed(m, 'audience')) or '全部'}）: {m['description']}{more}"


def index(ws, files):
    """資料ごとに選ぶレシピ（per_material: true のもの）の一覧。desk.py recipes の一節で、desk-feedback の recipe_menu.py が試しの子に渡す文。"""
    return ("## 資料ごとに選ぶ（per_material: true）\n\n行は「パス（作るもの、資料の種類）: いつ使うか」。この資料に合うものを選び、"
            "構成案の先頭に「- **使う決まり:** recipes/a/RECIPE.md、recipes/b/RECIPE.md」（合うものがなければ「なし」）と書いて、選んだものを開く。\n\n"
            + "\n".join(row(ws, p, m) for p, m in files))


def chosen(p):
    """資料のフォルダか構成案 p の構成案（p が構成案ならそれ、フォルダならその中のいちばん新しい 構成案*.md）と、その「使う決まり」に書いたレシピのパス: (構成案, 値)。
    値は、行がなければ None、「なし」で始まれば（添え書きにパスがあっても）[]、レシピのパスに読めない値も入れる（rules/b.md、recipes/b）。レシピのパスのない行は、その値（空なら「（空）」）。構成案がなければ（まだないフォルダも）(None, None)。"""
    p = Path(p)
    try:
        outline = p if p.is_file() and p.name.startswith("構成案") else max(p.glob("構成案*.md"), key=lambda x: x.stat().st_mtime, default=None) if p.is_dir() else None
        if not outline:
            return None, None
        text = outline.read_text(encoding="utf-8")
    except (OSError, ValueError):  # 読めない、UTF-8 でない
        return None, None
    if not (lines := USE.findall(text)):
        return outline, None
    line = " ".join(lines)
    if line.strip(" \t*`").startswith("なし"):  # 「なし（recipes/cxo/RECIPE.md は合わない）」の添え書きのパスは、選んだものでない
        return outline, []
    names = re.findall(RULE_PATH, line)
    extra = [v for v in (x.strip("`*") for x in re.split(r"[\s、,，]+", re.sub(RULE_PATH, " ", line))) if re.fullmatch(r"(?:rules?|recipes?)/[\w./-]*", v, re.ASCII)]  # パスに読めない値（rules/b.md、recipes/b）。添え書き（「memory.md も見る」「顧客の memory: Customers/a/memory.md」）は数えない
    if names or extra:
        return outline, names + extra
    return outline, [] if "なし" in line else [line.strip(" \t*") or "（空）"]


TOPS = ("customers", "internal", "research")  # ワークスペースの直下の、資料を置くフォルダ（desk-init の「Workspace layout」）


def material(ws, folder):
    """folder（資料のフォルダか、その中のファイル。まだなくてもよい）の資料: (資料のフォルダ, 「使う決まり」を読む先)。読む先は、構成案のファイルか資料のフォルダで、
    資料のフォルダでない（顧客のフォルダ、その直下のファイル、ワークスペースの直下、recipes/ など）なら None。資料のフォルダは置き方で決める
    （Customers/<顧客>/<資料>/、Internal/<資料>/、Research/ の下は渡したフォルダ。deck-workflow の start.md の 1）ので、build/ の下のファイルもその資料のもの。
    相対のパスは、Customers/・Internal/・Research/ で始まればワークスペースから（手順 1 で決めたフォルダはこう書く）、ほかは今いるフォルダから（build と書けば今の資料の build/）。
    あるかどうかでは決めない（まだないパスを、ほかの資料やワークスペースの直下と取り違えるため）。ワークスペースの外なら止める。"""
    ws = Path(ws).resolve()
    f = Path(os.path.expanduser(str(folder)))
    if not f.is_absolute() and f.parts and f.parts[0].lower() in TOPS:  # 先頭のフォルダは、ワークスペースにある名前に合わせる（大文字と小文字を分けるファイルシステムでも）
        real = next((x.name for x in ws.iterdir() if x.is_dir() and x.name.lower() == f.parts[0].lower()), f.parts[0]) if ws.is_dir() else f.parts[0]
        f = ws / real / Path(*f.parts[1:])
    elif not f.is_absolute():
        f = Path.cwd() / f
    f = Path(os.path.realpath(f))  # /tmp と /private/tmp のようなリンクもたどる
    rel = os.path.relpath(f, ws)
    if rel == ".." or rel.startswith("../"):
        sys.exit(f"資料のフォルダが、ワークスペース（{ws}）の中にない: {folder}（相対のパスは、Customers/・Internal/・Research/ から書く）")
    parts = () if rel == "." else Path(rel).parts
    top = parts[0].lower() if parts else ""
    filelike = f.is_file() or not f.exists() and bool(f.suffix)  # まだないファイル（memory.md・profile.md）も。あるフォルダは、名前に点があってもフォルダ
    if top in ("customers", "internal"):
        depth = 3 if top == "customers" else 2
        if len(parts) < depth or len(parts) == depth and filelike:  # 顧客のフォルダか、その直下のファイルは、資料でない
            return ws.joinpath(*parts[:max(1, len(parts) - filelike)]), None
        d = ws.joinpath(*parts[:depth])
    elif top == "research" and len(parts) > 1 and not (len(parts) == 2 and filelike):  # Research/ の下のフォルダは、置き方が決まっていないので、渡したフォルダ（ファイルならそのフォルダ）。直下のメモは資料でない
        d = f.parent if filelike else f
    else:
        return f.parent if filelike else f, None
    return d, f if f.is_file() and f.name.startswith("構成案") and f.parent == d else d


STALE = "は、レシピにない（名前が変わったか、消えたか、frontmatter の description がない）。desk.py recipes の一覧から選び直して、構成案を直す"


def for_material(ws, folder, files):
    """資料のフォルダ（か、その中のファイル。まだなくてもよい）folder で開くもの: 顧客の memory.md と、構成案の「使う決まり」のレシピ。文の行の並び。"""
    ws = Path(ws).resolve()
    d, target = material(ws, folder)
    parts = d.relative_to(ws).parts
    out = [f"## この資料で開くもの: {'/'.join(parts) or '.'}", ""]
    if len(parts) >= 2 and parts[0].lower() == "customers":
        mem = ws.joinpath(*parts[:2], "memory.md")
        out.append(f"- 顧客の memory: {mem.relative_to(ws)}（この顧客の資料への好み。レシピとプラグインより優先する）" if mem.is_file()
                   else f"- 顧客の memory: まだない（{mem.relative_to(ws)}）")
    outline, picks = chosen(target) if target else (None, None)
    names = {p.relative_to(ws).as_posix() for p, _ in files}
    if not target:
        out.append("- 資料のフォルダでない（Customers/<顧客>/<資料>/ か Internal/<資料>/ を渡すと、その資料の「使う決まり」も出す）")
    elif not outline:
        out.append("- 構成案: まだない（手順 5 で書くときに、下の「資料ごとに選ぶ」から選んで「使う決まり」を書く）")
    elif picks is None:
        out.append(f"- 構成案の「使う決まり」: 行がない（{outline.name}。下の「資料ごとに選ぶ」から選び、構成案の先頭に書く）")
    else:
        out.append(f"- 構成案の「使う決まり」: {'、'.join(x for x in picks if x in names) or 'なし'}")
        if stale := [x for x in picks if x not in names]:
            out.append(f"- 「使う決まり」の {'・'.join(stale)} {STALE}")
    return out


def reminder(ws):
    """lint が毎回の出力に添える 1 行の案内（ワークスペースにレシピか顧客の memory があるとき。なければ ""）。組む・直すどの道も lint を回すので、
    要約のあとも、道具のスキルだけで組んでも、子も、ここで思い出す（2026-11-04 に hook をやめた代わり）。どの資料を lint しているかは推し量らない
    （今いるフォルダや構成案の URL から決めると、ほかの顧客の memory を出したり、正しい資料の memory を落としたりするため）。開くものは desk.py recipes が出す。"""
    ws = Path(ws)
    n, mem = len(rules(ws)), any(d.name.lower() == "customers" and any(d.glob("*/memory.md")) for d in ws.iterdir() if d.is_dir()) if ws.is_dir() else False
    if not (n or mem):
        return ""
    what = "と".join(x for x in (f"このワークスペースのレシピ（{n} 本）" if n else "", "顧客の memory " if mem else "") if x)
    return (f"\n{what}は、プラグインより優先する。この文脈でまだ開いていなければ、"
            "desk.py recipes <資料のフォルダ>（この lint のスクリプトと同じフォルダの desk.py）を回し、この資料のこの作業に当たるものを開く。")


def recipes(ws, folder=None):
    """desk.py recipes の文: レシピをいつ開くもので分けた一覧と、folder があればその資料で開くもの。"""
    files = rules(ws)
    out = [f"# ワークスペースのレシピ: {ws}", "",
           "このワークスペースだけの決まり（パスはワークスペースから）。プラグインと食い違うところは、レシピに従う。"
           "いまの作業の組のうち description が当たるものを、1 本ずつ全文で開く（desk-feedback の routing.md の「Workspace rules」）。"
           "同じフォルダのほかのファイル（テンプレート・checks.py）は、RECIPE.md が使い方を書いている。", ""]
    if (ws / "rules").is_dir() and any((ws / "rules").rglob("*.md")):
        out += [f"- 前のバージョンの rules/ がある（{ws}/rules/。もう読まない）。desk-migrate の SKILL.md を開いて、recipes/ に移す", ""]
    if folder is not None:
        out += [*for_material(ws, folder, files), ""]
    if not files:
        out.append("レシピはまだない（recipes/<名前>/RECIPE.md で、frontmatter に description のあるもの）。")
        return "\n".join(out)
    for k, title, when in GROUPS:
        rows = [row(ws, p, m) for p, m in files if kind(m) == k]
        out += [f"## {title}", "", f"{when}。", "", *(rows or ["（なし）"]), ""]
    free = materials(files)
    out.append(index(ws, free) if free else "## 資料ごとに選ぶ（per_material: true）\n\n（なし。構成案の「使う決まり」は「なし」と書く）")
    return "\n".join(out)


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        ws, sand, other, conf = tmp / "Documents", tmp / "Documents" / "sandbox", tmp / "elsewhere", tmp / "home" / ".desk.toml"
        for d in (sand / "sub", ws / "Customers", other, conf.parent):
            d.mkdir(parents=True)
        os.environ["DESK_CONFIG"] = str(conf)
        assert not old_agents(ws)  # ない
        (ws / "AGENTS.md").write_text("# 自分の決まり\n## 書き方\n- 敬体。\n前は「## 決まりの優先」があった。\n")
        assert not old_agents(ws)  # 節が 1 つ同じ・見出しを文の中で引いただけ
        (ws / "AGENTS.md").write_text("# 題を替えた\n" + "".join(f"## {h}\n" for h in AGENTS_TEMPLATE[:5]))
        assert old_agents(ws)  # 題を書き替えた写しも、節で見つける
        (ws / "AGENTS.md").write_text("# 自分の決まり\n```md\n" + "".join(f"## {h}\n" for h in AGENTS_TEMPLATE) + "```\n")
        assert not old_agents(ws)  # コードの囲みの中で引いただけ
        (ws / "AGENTS.md").unlink()
        assert locate(other) is None  # 3: どちらもない
        conf.write_text(with_workspace("[drive]\ndesk = \"u\"\n", ws))
        assert locate(other) == locate(ws / "Customers") == (conf, ws)  # 2: ほかのフォルダでも、ワークスペースの中でも
        (sand / NAME).write_text('workspace = "/nope"\n')
        assert locate(sand / "sub") == (sand / NAME, sand)  # 1: 上へたどって見つかったもの。そこの workspace は読まない
        os.environ["DESK_CONFIG"] = ""
        assert locate(other) is None and locate(sand) == (sand / NAME, sand)  # 空の DESK_CONFIG は 2 を飛ばす
        os.environ["DESK_CONFIG"] = str(tmp / "none.toml")
        assert locate(other) is None  # ないパスも同じ
        os.environ["DESK_CONFIG"] = str(conf)
        conf.write_text('workspace = "../Documents"\n')
        assert user() == pointed() == (conf, ws)  # 相対のパスは設定のファイルのフォルダから
        conf.write_text('workspace = "../not-yet"\n')
        assert pointed() == (conf, tmp / "not-yet")  # まだないフォルダでも、指すパスは出す（user は止める）
        for text, msg in ((b"[drive]\n", "workspace"), (b'workspace = ""\n', "workspace"), (b'workspace = "../nope"\n', "フォルダがない"), (b"workspace = \n", "読めない"),
                          (b'workspace = "~nosuchuser/x"\n', "フォルダがない"), (b"\x82\xa0", "読めない")):  # 止めるのは SystemExit だけ（~user・UTF-8 でないものも）
            conf.write_bytes(text)
            try:
                locate(other)
                raise AssertionError(text)
            except SystemExit as e:
                assert msg in str(e), (text, e)
        assert with_workspace("", Path.home() / "Documents").startswith('workspace = "~/Documents"') and with_workspace("", "/srv/w").startswith('workspace = "/srv/w"')
        t = with_workspace("# 頭のコメント\n[desk]\nprivate = []\n", "/srv/w")
        assert t.index("workspace") < t.index("[desk]") and t.startswith("# 頭のコメント\n") and tomllib.loads(t)["desk"] == {"private": []}
        assert tomllib.loads(with_workspace("names = [\n  [1, 2],\n]\n[drive]\n", "/srv/w"))["names"] == [[1, 2]]  # 複数行の値の途中に入れない
        assert tomllib.loads(with_workspace("# c", "/srv/w"))["workspace"] == "/srv/w"  # 改行で終わらないコメントだけでも
        for text in ('workspace = "/x"\n', "a = \n"):  # もう workspace がある、読めない: 止めて何も書かない
            try:
                with_workspace(text, "/srv/w")
                raise AssertionError(text)
            except SystemExit:
                pass
        conf.write_text('workspace = "../Documents"\n')
        (other / OLD).write_text("")
        assert locate(other) is None and locate(ws / "Customers") == (conf, ws) and "desk-migrate" in missing(other)  # 前のバージョンのワークスペース（factory.toml）の中では、~/.desk.toml に進まない
        (sand / "old").mkdir()
        (sand / "old" / OLD).write_text("")
        assert locate(sand / "old") is None and local(sand) == (sand / NAME, sand)  # 新しいワークスペースの中の、前のバージョンのワークスペースでも、外側の desk.toml に進まない
        (sand / "old" / "new").mkdir()
        (sand / "old" / "new" / NAME).write_text("")
        env = dict(os.environ)
        try:  # 前のバージョンのワークスペースの中の、新しいワークスペースで開いた会話は、止めない
            os.environ["CLAUDE_PROJECT_DIR"] = str(sand / "old" / "new")
            assert workspace(tmp) == sand / "old" / "new" and found(tmp) == sand / "old" / "new"
        finally:
            os.environ.clear()
            os.environ.update(env)
            (sand / "old" / "new" / NAME).unlink()
            (sand / "old" / "new").rmdir()
        (sand / "old" / OLD).unlink()
        conf.write_text(f'workspace = "{other}"\n')
        try:
            locate(tmp)  # 外からも、前のバージョンのワークスペースには解決しない
            raise AssertionError
        except SystemExit as e:
            assert "desk-migrate" in str(e), e
        conf.write_text('workspace = "../Documents"\n')
        (other / OLD).unlink()
        (ws / NAME).write_text("")
        assert local(ws / "Customers") == (ws / NAME, ws) and locate(other) == (conf, ws)  # 既定のワークスペースにも desk.toml があると、中と外で読む設定が変わる（doctor.py が出す）
        assert front("---\ndescription: 顧客向けの資料: 共通\ntargets: [slides, 'docs']  # 省くと全部\npaths:\n  - a/b.md\n- a/c.md\naudience: 顧客向け\n---\n本文") == {
            "description": "顧客向けの資料: 共通", "targets": ["slides", "docs"], "paths": ["a/b.md", "a/c.md"], "audience": "顧客向け"}
        assert front('---\ndescription: "Issue #12 の件"  # c\n---\n')["description"] == "Issue #12 の件"
        assert [described(front(f"---\ndescription: {v}\n  長い説明\n---\n")) for v in (">", "|-", "[a, b]", " # TODO", "x")] == ["", "", "", "", "x"]  # 複数行と並びは、description がないとみなす
        assert front("---\npaths: a.md\n  - b.md\n---\n")["paths"] == "a.md"  # 値のある key の下の「- 」は並びにしない（字に切らない）
        assert front("# 見出し\n---\n") == front("---\ndescription: x\n") == {} and listed({"audience": "顧客向け"}, "audience") == ["顧客向け"] and listed({}, "paths") == []  # 閉じていない
        r = ws / RECIPES
        for f, t in (("a/RECIPE.md", "---\ndescription: x\n---\n"), ("README.md", "# recipes/\n"), ("s/b/RECIPE.md", "---\ndescription:\n---\n"), ("a/note.md", "---\ndescription: 資源\n---\n"),
                     ("p/templates/q/RECIPE.md", "---\ndescription: テンプレート\n---\n"), ("s/c/RECIPE.md", "---\ndescription: y\n---\n"), ("d.md", "---\ndescription: 前の形\n---\n"),
                     ("templates/RECIPE.md", "---\ndescription: テンプレートの使い分け\n---\n"), ("RECIPE.md", "---\ndescription: フォルダがない\n---\n")):
            (r / f).parent.mkdir(parents=True, exist_ok=True)
            (r / f).write_text(t)
        assert [str(p.relative_to(r)) for p, _ in rules(ws)] == ["a/RECIPE.md", "s/c/RECIPE.md", "templates/RECIPE.md"] and rules(other) == []  # RECIPE.md だけ（description のないもの・資源・テンプレート・前の形の .md は入れない）
        assert [kind(m) for m in ({}, {"step": "gather"}, {"step": "build"}, {"step": "x"}, {"per_material": "true", "step": "build"})] == ["make", "gather", "build", "make", "material"]
        assert copied("x/build-docs/assets/gcp/a.png") and not copied("/p/skills/build-docs/assets/README.md") and not copied("x/build-slides/assets/README.md")
        assert copied("x/build-docs/scripts/gapi.py") and not copied("x/build-slides/scripts/gapi.py") and copied("x/deck-review/scripts/yomiyasu/scripts/yomiyasu_diff.py") and not copied("x/build-docs/scripts/docs.py")
        assert triggers("deck-workflow/materials.md") == {"gather", "make"} and triggers("build-slides/pages.md") == {"build", "make"} and triggers("deck-review/SKILL.md") == {"make"}
        assert triggers("customer-profile/SKILL.md") == {"gather"} and triggers("desk-init/doctor.md") == set()  # 資料づくりの外の作業では、step のないものは開かない
        for f, t in (("cxo/RECIPE.md", "---\ndescription: CxO に提案するとき\nper_material: true\naudience: [顧客向け]\n---\n"), ("tools/RECIPE.md", "---\ndescription: 社内の道具\nstep: gather\n---\n"),
                     ("logo/RECIPE.md", "---\ndescription: ロゴ\nstep: build\n---\n")):
            (r / f).parent.mkdir(parents=True, exist_ok=True)
            (r / f).write_text(t)
        out = recipes(ws)
        make, gather, build, free = (out.index(f"## {g}") for g in ("どの作業でも", "集めるとき", "組むとき", "資料ごとに選ぶ"))
        assert make < out.index("recipes/a/RECIPE.md（全部、全部）: x") < gather < out.index("recipes/tools/RECIPE.md") < build < out.index("recipes/logo/RECIPE.md") < free < out.index("recipes/cxo/RECIPE.md（全部、顧客向け）"), out
        assert "この資料で開くもの" not in out and "rules/" not in out.replace("recipes/", "")
        deck = ws / "Customers" / "acme" / "plan_202611"
        deck.mkdir(parents=True)
        assert "構成案: まだない" in recipes(ws, deck) and "顧客の memory: まだない" in recipes(ws, deck)
        (ws / "Customers" / "acme" / "memory.md").write_text("- 敬体\n")
        (deck / "構成案.md").write_text("# 構成案\n")
        out = recipes(ws, deck / "構成案.md")
        assert "## この資料で開くもの: Customers/acme/plan_202611\n" in out and "顧客の memory: Customers/acme/memory.md" in out and "行がない（構成案.md" in out, out
        (deck / "構成案.md").write_text("- **使う決まり:** recipes/cxo/RECIPE.md、recipes/gone/RECIPE.md\n")
        out = recipes(ws, deck)
        assert "「使う決まり」: recipes/cxo/RECIPE.md\n" in out and "recipes/gone/RECIPE.md は、レシピにない" in out, out
        (deck / "構成案.md").write_text("- **使う決まり:** なし\n")
        assert "「使う決まり」: なし" in recipes(ws, deck)
        (deck / "構成案.md").write_text("- **使う決まり:** recipes/cxo/RECIPE.md（memory.md も見る）。顧客の memory: Customers/acme/memory.md\n")
        assert "レシピにない" not in recipes(ws, deck) and "「使う決まり」: recipes/cxo/RECIPE.md\n" in recipes(ws, deck)  # 添え書きのパスは、レシピにないと知らせない
        (deck / "構成案.md").write_text("- **使う決まり:** recipes/cxo/RECIPE.md、memory.md も見る\n")
        assert "レシピにない" not in recipes(ws, deck)
        (deck / "構成案.md").write_text("- **使う決まり:** なし（recipes/cxo/RECIPE.md は社内向けなので合わない）\n")
        assert "「使う決まり」: なし" in recipes(ws, deck) and "recipes/cxo/RECIPE.md\n" not in recipes(ws, deck).split("## どの作業でも")[0]  # 「なし」の添え書きのパスは選んだものでない
        assert "顧客の memory" not in recipes(ws, sand) and "資料のフォルダでない" in recipes(ws, sand)  # 資料を置くフォルダの外
        assert "構成案: まだない" in recipes(ws, ws / "Internal" / "new_202611")  # まだないフォルダ
        (ws / "Customers" / "acme" / "構成案.md").write_text("- **使う決まり:** recipes/cxo/RECIPE.md\n")
        out = recipes(ws, ws / "Customers" / "acme" / "new_202611")
        assert "構成案: まだない" in out and "recipes/cxo/RECIPE.md\n" not in out.split("## どの作業でも")[0], out  # まだないフォルダは、親の構成案を拾わない
        (deck / "build" / "assets").mkdir(parents=True)
        (deck / "build" / "assets" / "x.png").write_text("")
        for f in (deck / "build", deck / "build" / "assets" / "x.png"):  # build/ の下のファイルは、その資料のもの
            assert "## この資料で開くもの: Customers/acme/plan_202611\n" in recipes(ws, f), f
        assert "資料のフォルダでない" in recipes(ws, ws / "Customers" / "acme") and "顧客の memory: Customers/acme/memory.md" in recipes(ws, ws / "Customers" / "acme")  # 顧客のフォルダの構成案は拾わない
        (ws / "Customers" / "beta").mkdir()
        here = os.getcwd()
        try:
            for cwd in (other, deck / "build"):  # プラグインのフォルダ、ほかの資料の中: Customers/ から書いたパスはワークスペースから
                os.chdir(cwd)
                out = recipes(ws, "Customers/beta/new_202611")
                assert "## この資料で開くもの: Customers/beta/new_202611\n" in out and "Customers/acme/memory.md" not in out, (cwd, out)
                assert "## この資料で開くもの: Customers/acme/plan_202611\n" in recipes(ws, "Customers/acme/plan_202611")
            assert "## この資料で開くもの: Customers/acme/plan_202611\n" in recipes(ws, ".")  # ほかは今いるフォルダ（build/）から
            for rel in ("p9.json", "new/p1.json"):  # まだないファイルも、今の資料のもの
                assert "## この資料で開くもの: Customers/acme/plan_202611\n" in recipes(ws, rel) and "顧客の memory: Customers/acme/memory.md" in recipes(ws, rel), rel
            os.chdir(deck)
            assert "Customers/acme/memory.md（" in recipes(ws, "build/p1.json")  # まだない build/ の下
            os.chdir(ws)
            (ws / "Internal" / "v1.5_202611").mkdir(parents=True)
            assert "## この資料で開くもの: Internal/v1.5_202611\n" in recipes(ws, "Internal/v1.5_202611")  # 名前に点のあるフォルダ
            for rel in (".", "recipes/cxo", "Customers/README.md", "Customers/acme/x.txt", "Research/note_1.md"):  # 資料のフォルダでない（まだないファイルも）
                out = recipes(ws, rel)
                assert "資料のフォルダでない" in out and "README.md/memory.md" not in out and "構成案: まだない" not in out, (rel, out)
        finally:
            os.chdir(here)
        try:
            recipes(ws, other)
            raise AssertionError(other)
        except SystemExit as e:
            assert "資料のフォルダ" in str(e), e
        (ws / "rules").mkdir()
        (ws / "rules" / "a.md").write_text("x")
        assert "前のバージョンの rules/" in recipes(ws) and "レシピはまだない" in recipes(other)
        (r / "cxo" / "templates" / "poc").mkdir(parents=True)
        (r / "cxo" / "templates" / "poc" / "doc.md").write_text("x")
        assert "CxO に提案するとき（資源: templates/poc/doc.md）" in recipes(ws)  # レシピのフォルダのほかのファイル
        assert "## この資料で開くもの: Customers/acme/plan_202611\n" in recipes(ws, "customers/acme/plan_202611")  # 先頭のフォルダの大文字と小文字
        assert "資料のフォルダでない" in recipes(ws, ws / "Customers" / "acme" / "memory.md")  # 顧客のフォルダの直下のファイル
        assert "このワークスペースのレシピ（6 本）と顧客の memory は、" in reminder(ws) and "）は" not in reminder(ws) and "desk.py recipes <資料のフォルダ>" in reminder(ws), reminder(ws)
        assert reminder(other) == ""  # レシピも memory もない
        assert "資料のフォルダでない" in recipes(ws, ws / "Customers" / "acme" / "profile.md")  # まだない直下のファイル
        assert found(ws / "Customers") == ws
        conf.write_text('workspace = "../nope"\n')
        try:
            found(other)  # 設定が指すフォルダがない: missing() の「desk.toml が見つからない」でなく、その理由で止める
            raise AssertionError
        except SystemExit as e:
            assert "フォルダがない" in str(e), e
        conf.write_text('workspace = "../Documents"\n')
        (other / OLD).write_text("")
        env = dict(os.environ)
        try:
            for cfg in ("", str(conf)):  # 会話を開いたフォルダが前のバージョンのワークスペース: desk-init でなく desk-migrate を案内する（~/.desk.toml の別のワークスペースにも進まない）
                os.environ.update(DESK_CONFIG=cfg, CLAUDE_PROJECT_DIR=str(other))
                try:
                    found(tmp)
                    raise AssertionError(cfg)
                except SystemExit as e:
                    assert "desk-migrate" in str(e), (cfg, e)
        finally:
            os.environ.clear()
            os.environ.update(env)
            (other / OLD).unlink()
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    if sys.argv[1:2] == ["recipes"] and len(sys.argv) <= 3:
        folder = sys.argv[2] if len(sys.argv) == 3 else None
        start = os.path.expanduser(folder or "")
        print(recipes(found(start if os.path.isabs(start) else os.getcwd()), folder))  # 絶対のパスなら、その資料のワークスペース
        sys.exit(0)
    if sys.argv[1:]:
        sys.exit("usage: " + __doc__.split("usage: ")[1])
    if not (f := locate()):
        sys.exit(missing())
    print(f[1])
