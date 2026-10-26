#!/usr/bin/env python3
"""プラグインの改善を、過去の資料で確かめてから Issue にする（手順は ../SKILL.md）。ワークスペース（探し方は ../../deck-practices/scripts/desk.py）で回す。
usage:
  kaizen.py start   <名前>                          元のリポジトリ（plugin.json の repository）を clone して kaizen/<名前> のブランチを作る。前の版（main）も写す
  kaizen.py lint    <名前> <資料の URL ...>          いまの資料の JSON に、前の版と変えた版の lint をかけて比べる
  kaizen.py rebuild <名前> <資料のフォルダ ...> [--pages 2,5] [--keep]   build/ の正本（deck.json・pages.py・doc.md）を前の版と変えた版で仮に組み、ページの画像を並べて比べる
  kaizen.py probe   <名前> [--fixtures 02,05] [<資料のフォルダ> ...] [--agent claude|codex|pi] [--model <モデル>] [--jobs 2] [--timeout 1800]
                    同じ依頼（docs/fixtures の試しと、過去の資料の構成案から書き直す再演）を、前の版と変えた版のプラグインで子のエージェントに 1 回ずつ書かせ、
                    どちらの出力も変えた版の lint（組まずに手元で）で数え、版を伏せた選ぶ役の子に成果物だけを見て選ばせる（Google は使わない）
  kaizen.py open    <名前> --title <題> --body <本文.md>   本文と検証の記録と変更案の差分をまとめて、プラグインのリポジトリに Issue を作る（commit は先に済ませる。Issue があれば本文を書き換える）
  kaizen.py clean   <名前>                          clone と検証の記録を消す（Issue が閉じられたあと）
  kaizen.py --selftest
置き場所は <ワークスペース>/.desk/kaizen/<名前>/（repo/ 変える版、base/ 前の版、verify/ 検証の記録）。資料の名前・URL・本文は verify/detail.md にだけ書き、
Issue には「資料 1」のような番号と、規則ごとの数の変化と、選んだ画像と、変更案の差分だけを出す。ブランチは push しない。"""
import json, os, re, secrets, shutil, subprocess, sys, tempfile, time, tomllib
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deck-practices" / "scripts"))
import gapi

SECTIONS = ("## 変えること", "## 理由", "## 背景", "## 過去資料での検証", "## 影響", "## 迷ったところ")
MAX_BODY = 60000  # GitHub の Issue の本文は 65536 字まで
DESIGN = re.compile(r"skills/((slides|docs)-build/visual\.md|slides-build/(scripts/(slides|template|box_pad)\.py|assets/)|docs-build/scripts/(docs|doc_layout)\.py|deck-practices/scripts/brand\.py)")  # 見た目が変わりうるファイル
URL_ID = re.compile(r"https://docs\.google\.com/(?:presentation|document)/d/([\w-]+)")
COUNT = re.compile(r"^== (要修正|要確認)[^:]*: (\d+)(?:（[^）]*）)? ==$", re.M)  # 「== 要確認: 16（うち見積もり 11。画像で確定する） ==」も
HIT = re.compile(r"^\[(.+?)\] (.*)$", re.M)
REPO = json.loads((Path(__file__).resolve().parents[3] / ".claude-plugin" / "plugin.json").read_text())["repository"].removeprefix("https://github.com/")  # Issue を出すリポジトリ
MAIN = "origin/main"  # 差分の起点（start が REPO から clone する）
AUTH = ("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")  # git に設定がなくても、gh のログインで push する
SIDES = ("base", "head")
CODEX_KEEP = ("model_providers", "profiles", "features", "shell_environment_policy")  # 子の CODEX_HOME に写す表（モデルを呼ぶのに要るものだけ）
NO_WEB = ("--disallowedTools", "WebFetch", "WebSearch")
CODEX_NO_WEB = ("-c", 'web_search="disabled"')  # codex の Web 検索はサーバーの側で動き、sandbox では止まらない
CODEX_SEARCH = re.compile(r"\s*(web_search\w*|standalone_web_search|search_tool)\s*=")  # 写した設定から外す（Web 検索を入れる鍵）  # claude の子は使う人の settings.json の許しを受け継ぐ。止める指定は許しより強い
AGENTS = ("claude", "codex", "pi")
PROBE = "### 走らせて比べる"  # verify/pr.md の probe の節。skills/ の md を変えたら、これか「検証しない理由」が要る
RULE_TEXT = re.compile(r"skills/.+\.md$")  # 決まりと手順の文（子のエージェントが読むもの）
CHANGED_ID = re.compile(r"\[((?:ws-)?[a-z][\w-]*?-\d{3})\]")
SKIP = shutil.ignore_patterns(".git", "docs", "tests", "sandbox", "__pycache__")  # 子に渡すプラグインの写し。docs/fixtures の「見るところ」（答えの基準）を子に見せない
SELECT = Path(__file__).resolve().parents[1] / "prompt_select.md"
REPLAY = ("desk-tools のスキル（deck-practices と slides-build）に従い、{folder}/{outline} の構成で、スライドを JSON のページで書き直してください。"
          "構成はもう決まっています。聞き手への確認、構成案のレビュー、代表の 3 枚のレビュー、/deck-review はせず、Google で組むことも画像を取ることもしないでください。"
          "{folder}/build/ に deck.json と各ページの JSON を書き、slides.py lint deck.json の要修正を 0 にしたところで止めてください。")


def sh(*cmd, cwd=None, env=None, check=True):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    except FileNotFoundError:
        sys.exit(f"{cmd[0]} がない。入れてから回す（gh なら入れて gh auth login）")
    if check and r.returncode:
        sys.exit(f"止まった（exit {r.returncode}）: {' '.join(map(str, cmd))}\n{r.stderr.strip()[-1500:]}")
    return r


class Work:
    def __init__(self, name):
        self.ws = gapi.workspace()
        self.name, self.branch = name, f"kaizen/{name}"
        self.dir = self.ws / ".desk" / "kaizen" / name
        self.repo, self.base, self.verify = self.dir / "repo", self.dir / "base", self.dir / "verify"

    @cached_property
    def assets(self):
        """画像を置くリポジトリ。REPO に書けるなら REPO、書けなければ自分の fork（なければ GitHub に作る。あれば同じものが返る）。"""
        perm = sh("gh", "repo", "view", REPO, "--json", "viewerPermission", "-q", ".viewerPermission").stdout.strip()
        if perm in ("ADMIN", "MAINTAIN", "WRITE"):
            return REPO
        fork = sh("gh", "api", "-X", "POST", f"repos/{REPO}/forks", "-q", ".full_name").stdout.strip()
        for _ in range(30):  # 作ったばかりの fork は、GitHub が写し終えるまで見えない
            if (r := sh("git", *AUTH, "ls-remote", f"https://github.com/{fork}.git", "HEAD", check=False)).returncode == 0:
                return fork
            time.sleep(2)
        sys.exit(f"fork の {fork} が見えない: {r.stderr.strip()[-500:]}")

    def need(self):
        if not self.repo.is_dir():
            sys.exit(f"{self.repo} がない。先に kaizen.py start {self.name}")
        if (self.repo / ".git").is_file():  # 2026-10-14 までの start が、[factory] source（前の版）の checkout に作った worktree（origin が fork のことがあり、差分の起点がずれる）
            sys.exit(f"{self.repo} は前の版の start で作った worktree。kaizen.py clean {self.name} のあと start し直す（元の checkout では git worktree prune）")

    def label(self, key):
        """資料の番号（Issue には資料の名前を出さない）。"""
        self.verify.mkdir(parents=True, exist_ok=True)
        f = self.verify / "labels.json"
        labels = json.loads(f.read_text()) if f.is_file() else {}
        labels.setdefault(key, f"資料 {len(labels) + 1}")
        f.write_text(json.dumps(labels, ensure_ascii=False, indent=1))
        return labels[key]

    def scripts(self, side, skill="slides-build"):
        return (self.base if side == "base" else self.repo) / "skills" / skill / "scripts"

    def log(self, detail, public):
        self.verify.mkdir(parents=True, exist_ok=True)
        for f, text in (("detail.md", detail), ("pr.md", public)):
            with open(self.verify / f, "a", encoding="utf-8") as fh:
                fh.write(text.rstrip() + "\n\n")


def compare(before, after):
    """lint の出力 2 つから、数と、規則ごとの指摘の増減。"""
    counts = lambda out: {k: sum(int(n) for kk, n in COUNT.findall(out) if kk == k) for k in ("要修正", "要確認")}
    hits = lambda out: {(k, v) for k, v in HIT.findall(out)}
    b, a = hits(before), hits(after)
    rules = sorted({k for k, _ in b ^ a})
    delta = {k: (sum(x == k for x, _ in b), sum(x == k for x, _ in a)) for k in rules}
    return counts(before), counts(after), delta, sorted(b - a), sorted(a - b)


def report(label, kind, cb, ca, delta, gone, new, title=""):
    head = f"#### {label}（{kind}）\n\n| | 前の版 | 変えた版 |\n|---|---|---|\n" + "".join(f"| {k} | {cb[k]} | {ca[k]} |\n" for k in cb)
    rules = "".join(f"- {k}: {x} → {y}\n" for k, (x, y) in delta.items()) or "- 指摘の変化なし\n"
    detail = f"{head}\n{title}\n\n{rules}\n消えた指摘:\n" + "".join(f"- [{k}] {v}\n" for k, v in gone[:20]) + "\n増えた指摘:\n" + "".join(f"- [{k}] {v}\n" for k, v in new[:20])
    return detail, f"{head}\n規則ごとの指摘の数:\n\n{rules}"


def start(w):
    if w.repo.exists() or w.base.exists():  # clone に失敗すると、git は repo/ を消して親のフォルダだけ残す（それならやり直せる）
        sys.exit(f"{w.dir} に前の start が残っている（続けるならそのまま使う。やり直すなら kaizen.py clean {w.name}）")
    sh("gh", "auth", "status", "--hostname", "github.com")  # ログインしていないと open で止まるので、確かめる作業の前に見る（github.com だけ。ほかのホストのログインが切れていても止めない）
    sh("git", "clone", "-q", "--single-branch", "-b", "main", f"https://github.com/{REPO}.git", w.repo)
    sh("git", "-C", w.repo, "switch", "-q", "-c", w.branch)
    w.base.mkdir(parents=True)
    arch = subprocess.run(["git", "-C", str(w.repo), "archive", MAIN], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(w.base)], input=arch, check=True)
    print(f"変える版: {w.repo}（ブランチ {w.branch}）\n前の版: {w.base}（{REPO} の main）\n変えたら commit し、kaizen.py lint・rebuild で確かめる")


def lint_cmd(w, urls):
    w.need()
    for url in urls:
        fid = gapi.file_id(url)
        kind, data = ("ドキュメント", gapi.request("GET", f"{gapi.DOCS}/{fid}")) if "/document/" in url else ("スライド", gapi.request("GET", f"{gapi.SLIDES}/{fid}"))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
        skill, script = ("docs-build", "doc_lint.py") if kind == "ドキュメント" else ("slides-build", "lint.py")
        outs = [sh(sys.executable, w.scripts(side, skill) / script, f.name, cwd=w.ws, env={"DESK_VERIFY": "1"}, check=False).stdout for side in ("base", "head")]
        os.unlink(f.name)
        detail, public = report(w.label(url), kind, *compare(*outs), title=f"{data.get('title', '')} {url}")
        w.log("### lint\n\n" + detail, "### lint\n\n" + public)
        print(detail)


def is_slides(build):
    """build/ の正本がスライド（deck.json か pages.py）なら True、ドキュメント（doc.md）なら False。両方のスライドがあるときは slides.py が止める。"""
    if any((build / f).is_file() for f in ("deck.json", "pages.py")):
        return True
    if (build / "doc.md").is_file():
        return False
    sys.exit(f"{build} に deck.json も pages.py も doc.md もない")


def rebuild(w, folders, pages=None, keep=False):
    w.need()
    out_dir = gapi.config().get("drive", {}).get("desk") or sys.exit("desk.toml の drive.desk（仮に組む Drive のフォルダ）がない")
    img = w.verify / "img"
    img.mkdir(parents=True, exist_ok=True)
    for folder in map(Path, folders):
        build = folder.resolve() / "build"
        slides = is_slides(build)
        label = w.label(str(folder.resolve().relative_to(w.ws)))
        made, outs, shots = [], [], {}
        try:
            for side in ("base", "head"):
                s = w.scripts(side, "slides-build" if slides else "docs-build")
                r = sh(sys.executable, s / ("slides.py" if slides else "docs.py"), "new", out_dir, f"{time.strftime('%Y%m%d')}_検証_{w.name}_{label.replace(' ', '')}_{side}", cwd=build, env={"DESK_VERIFY": "1"})
                fid = URL_ID.findall(r.stdout)[-1]
                made.append(fid)
                cmd = [sys.executable, s / ("gslides.py" if slides else "docs.py"), "check", fid] + (["--pages", pages] if pages and slides else [])
                outs.append(sh(*cmd, cwd=build, env={"DESK_VERIFY": "1"}, check=False).stdout)
                shots[side] = {p.name: p for p in sorted(Path(f"/tmp/{'slides' if slides else 'docs'}_{fid[:8]}").glob("p-*.png"))}
        finally:
            for fid in made if not keep else []:
                gapi.trash(fid)
        changed, want = [], {int(x) for x in pages.split(",")} if pages else None
        for n in sorted(set(shots["base"]) & set(shots["head"]), key=lambda x: int(re.sub(r"\D", "", x))):
            page = int(re.sub(r"\D", "", n))
            if want and page not in want or shots["base"][n].read_bytes() == shots["head"][n].read_bytes():
                continue  # 選んでいないページと、前後で同じ画像のページ
            num = re.sub(r"\D", "", label)  # f-string の中の \ は Python 3.12 から
            out = img / f"deck{num}_p{page}.png"  # エージェントが読み書きするファイルは英数字の名前
            sh("uv", "run", "-q", w.scripts("head", "deck-practices") / "sheet.py", out, shots["base"][n], shots["head"][n], "--cols", "2", "--width", "800")
            changed.append((page, out))
        detail, public = report(label, "スライド" if slides else "ドキュメント", *compare(*outs), title=str(folder))
        pics = "変わったページ: " + (", ".join(f"p{p}" for p, _ in changed) or "なし") + "（左が前の版、右が変えた版）\n\n" + "".join(f"<!-- img:{o.name} -->\n" for _, o in changed)
        w.log("### 組み直し\n\n" + detail + "\n" + pics, "### 組み直し\n\n" + public + "\n" + pics)
        print(detail + "\n" + pics + (f"\n画像: {img}" if changed else "") + ("" if not keep else f"\n仮の資料（--keep）: {', '.join(made)}"))


def fixture_task(w, n):
    """docs/fixtures/<番号>-*.md の依頼文（```text）。「見るところ」は子に渡さない（プラグインの写しからも docs/ を外す）。"""
    f = next(iter(sorted((w.repo / "docs" / "fixtures").glob(f"{n}-*.md"))), None) or sys.exit(f"docs/fixtures/{n}-*.md がない")
    m = re.search(r"^```text\n(.*?)\n```", f.read_text(encoding="utf-8"), re.S | re.M) or sys.exit(f"{f.name} に依頼文（```text）がない")
    return {"id": f"fixture-{n}", "label": f"試し {f.stem}", "prompt": m.group(1), "folder": None}


def replay_task(w, folder):
    """過去の資料を、決まった構成案から書き直させる依頼。Issue には「資料 N」だけを出す。"""
    src = (Path.cwd() / folder).resolve()
    src.is_dir() and src.is_relative_to(w.ws) or sys.exit(f"ワークスペースの中の資料のフォルダでない: {folder}")
    (src / "build" / "deck.json").is_file() or sys.exit(f"{folder}/build/deck.json がない（再演は JSON のスライドだけ。ドキュメントは組まずに回す lint がないので、まだできない）")
    outline = sorted(src.glob("構成案*.md")) or sys.exit(f"{folder} に構成案がない")
    rel, label = str(src.relative_to(w.ws)), w.label(str(src.relative_to(w.ws)))
    return {"id": "deck-" + label.split()[-1], "label": label, "prompt": REPLAY.format(folder=rel, outline=outline[-1].name), "folder": rel, "src": src}


def inputs(src, dst):
    """資料のフォルダの材料（構成案・出典の台帳・調べもの）。build/（答え）と社内メモ・レビューの記録（作り手の記録）は写さない。"""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "社内メモ_*", "review*.md"), dirs_exist_ok=True)


def setup_ws(w, plugin, ws, task):
    """書く役の子の作業場。その版の雛形（desk-init）から作り、Google に組める設定は入れない（雛形の desk.toml では組めない）。
    再演は、資料の材料と、顧客の memory・profile、ワークスペースのテーマを写す。ワークスペースの rules/ は写さない（ほかの人にも効くかを見るので）。"""
    sh(sys.executable, plugin / "skills" / "desk-init" / "scripts" / "init.py", ws, env={"DESK_CONFIG": ""})
    if not task["folder"]:
        return
    inputs(task["src"], ws / task["folder"])
    parts = Path(task["folder"]).parts
    for name in ("memory.md", "profile.md") if parts[0] == "Customers" else ():
        if (f := w.ws / "Customers" / parts[1] / name).is_file():
            shutil.copy2(f, ws / "Customers" / parts[1] / name)
    if (w.ws / "themes").is_dir():
        shutil.copytree(w.ws / "themes", ws / "themes", dirs_exist_ok=True)


def codex_home(tmp, name, plugin=None):
    """Codex の子の CODEX_HOME。書く役にはその版のプラグインだけを入れ、選ぶ役（plugin なし）には何も入れない（docs/development.md の「Codex」）。
    ログインとモデルの経路（頭のキーと model_providers・profiles・features・shell_environment_policy の表）だけを ~/.codex から写す。MCP サーバー・apps・hooks・skills・
    プラグインなどは写さない（sandbox の外で動き、ネットワークに出られる。本番の desk-tools と重なる）。"""
    home, src = tmp / name, Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    home.mkdir(parents=True)
    if (src / "auth.json").is_file():
        shutil.copy2(src / "auth.json", home)
    if (src / "config.toml").is_file():
        keep, top, out = True, True, []
        for line in (src / "config.toml").read_text(encoding="utf-8").splitlines():
            if m := re.match(r"\s*\[+\s*\"?([\w-]+)", line):
                keep, top = m.group(1) in CODEX_KEEP, False
            elif top and (k := re.match(r"\s*\"?([\w-]+)\"?\s*([.=])\s*(\{)?", line)) and (k.group(2) == "." or k.group(3)) and k.group(1) not in CODEX_KEEP:
                continue  # 頭の点つきの鍵と、その場の表（mcp_servers.x.command = …・tools = { … }）も、表と同じに見る
            keep and not CODEX_SEARCH.match(line) and out.append(line)
        text = "\n".join(out) + "\n"
        if bad := codex_leftovers(text):
            sys.exit(f"~/.codex/config.toml を子に写せない（{'、'.join(bad)} が残る）。Codex の子に MCP サーバーや Web 検索を渡さないため。書き方を表（[…]）にするか、--agent claude か pi で回す")
        (home / "config.toml").write_text(text, encoding="utf-8")
    for cmd in (("marketplace", "add", str(plugin)), ("add", "desk-tools@desk-tools")) if plugin else ():
        sh("codex", "plugin", *cmd, env={"CODEX_HOME": str(home)})
    return home


def codex_leftovers(text):
    """子に写す config.toml に残ってはいけないもの（読めない・許した表のほかの表・Web 検索と MCP の鍵）。"""
    try:
        d = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return [f"読めない写し（{e}）"]
    bad = [k for k, v in d.items() if isinstance(v, dict) and k not in CODEX_KEEP]
    def walk(x, path):
        for k, v in x.items():
            if re.fullmatch(r"web_search\w*|standalone_web_search|search_tool|mcp_servers", k):
                bad.append(path + k)
            if isinstance(v, dict):
                walk(v, f"{path}{k}.")
    walk(d, "")
    return bad


def writer_cmd(agent, plugin, ws, prompt, model):
    """書く役の子。その版のプラグインだけを読ませ、Web の道具は渡さない（claude は許す道具の一覧と WebFetch・WebSearch を止める指定、codex は workspace-write の sandbox と
    MCP サーバーを写さない CODEX_HOME。pi は Bash から外に出られる）。ponytail: 外に出るのを止めるのは道具の層だけ。試しの依頼文と見るところは公開のリポジトリにある"""
    m = lambda flag: [flag, model] if model else []
    if agent == "claude":
        return ["claude", "--plugin-dir", str(plugin), "-p", prompt, "--permission-mode", "acceptEdits", "--output-format", "stream-json", "--verbose", *m("--model"),
                "--strict-mcp-config", *NO_WEB, "--allowedTools", "Bash(python3:*)", "Bash(uv run:*)", "Bash(ls:*)", "Bash(mkdir:*)"]  # MCP サーバーも読ませない（使う人の settings.json が mcp__ の道具を許していても）
    if agent == "pi":
        return ["pi", "-p", "--no-session", "--approve", "--no-mcp", "--no-extensions", "-e", str(plugin / "extensions" / "rules.ts"), "--no-skills", "--skill", str(plugin / "skills"), *m("--model"), "--", prompt]
    return ["codex", "exec", *CODEX_NO_WEB, "-C", str(ws), "-s", "workspace-write", "--skip-git-repo-check", "--dangerously-bypass-hook-trust", *m("-m"), prompt]


def child(cmd, cwd, env, timeout):
    """(stdout, stderr, 終わり方, 秒)。終わり方は ok・exit <番号>・時間切れ。"""
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env={**os.environ, "DESK_CONFIG": "", **env})
        out, err, end = r.stdout, r.stderr, "ok" if r.returncode == 0 else f"exit {r.returncode}"
    except subprocess.TimeoutExpired as e:
        text = lambda x: x.decode(errors="ignore") if isinstance(x, bytes) else x or ""
        out, err, end = text(e.stdout), text(e.stderr), "時間切れ"
    except FileNotFoundError:
        sys.exit(f"{cmd[0]} がない。入れてから回す")
    return out, err, end, time.time() - t0


def claude_meta(out, plugin):
    """claude の stream-json から、費用と、読み込んだ desk-tools のパス（その版の写しでなければ、比べが成り立たない）。"""
    cost, loaded = None, None
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            loaded = next((p.get("path", "") for p in e.get("plugins", []) if p.get("name") == "desk-tools"), "")
        elif e.get("type") == "result":
            cost = e.get("total_cost_usd")
    warn = f"読み込んだ desk-tools が写しでない（{loaded or 'なし'}）" if loaded is not None and Path(loaded).resolve() != plugin.resolve() else ""
    return cost, warn


def write_one(w, tmp, plugins, task, side, agent, model, timeout, homes, names):
    ws = tmp / task["id"] / names[side]  # 版の名前をパスに出さない（成果物に書かれたパスから、選ぶ役が A・B を見分けないように）
    setup_ws(w, plugins[side], ws, task)
    out, err, end, secs = child(writer_cmd(agent, plugins[side], ws, task["prompt"], model), ws, {"CODEX_HOME": str(homes[side])} if side in homes else {}, timeout)
    log = f"$ 終わり方: {end}、{secs:.0f} 秒\n{out}\n--- stderr\n{err}"  # 記録に書くのは、選ぶ役が終わってから（probe）
    cost, warn = claude_meta(out, plugins[side]) if agent == "claude" else (None, "")
    want = ws / task["folder"] / "build" if task["folder"] else None
    found = [want] if want and (want / "deck.json").is_file() else sorted(p.parent for p in ws.rglob("build/deck.json") if ".desk" not in p.parts)
    return {"build": found[0] if found else None, "end": end, "secs": secs, "cost": cost, "warn": warn, "log": log}


def select_one(w, tmp, task, builds, agent, model, timeout, head_a):
    """版を伏せて選ばせる（Harness² の Selector）。選ぶ役は依頼と材料と成果物だけを見る（ハーネスも軌跡も lint も見せない）。
    head_a は変えた版を A に置くか（probe が依頼の順で交互にし、始まりは回すたびに変える。置き場所を好む選ぶ役でも版の差に見えず、前の記録から並びも当てられない）。"""
    d = tmp / task["id"] / "select"
    order = {"A": "head" if head_a else "base", "B": "base" if head_a else "head"}
    for k, side in order.items():
        shutil.copytree(builds[side], d / k)
    (d / "task.md").write_text(task["prompt"] + "\n", encoding="utf-8")
    if task["folder"]:
        inputs(task["src"], d / "inputs")
    prompt = SELECT.read_text(encoding="utf-8").split("\n---\n", 1)[-1].strip().replace("{dir}", str(d))  # 線より下だけ
    prompt += "\n\nFiles in `{}`: {}".format(d, ", ".join(f"`{f.relative_to(d)}`" for f in sorted(d.rglob("*")) if f.is_file()))  # pi の選ぶ役は read だけなので、並びを渡す
    m = lambda flag: [flag, model] if model else []
    home = codex_home(d.parent, secrets.token_hex(4)) if agent == "codex" else None  # 選ぶ役には、使う人の入れた desk-tools を読ませない（どちらかの版に寄る）
    cmd = {"claude": ["claude", "-p", prompt, "--output-format", "json", "--disable-slash-commands", "--strict-mcp-config", *m("--model"), *NO_WEB, "Bash", "--allowedTools", "Read", "Glob", "Grep"],
           "pi": ["pi", "-p", "--no-session", "--approve", "--no-mcp", "--no-extensions", "--no-skills", "--tools", "read", *m("--model"), "--", prompt],
           "codex": ["codex", "exec", *CODEX_NO_WEB, "-C", str(d), "-s", "read-only", "--skip-git-repo-check", *m("-m"), prompt]}[agent]
    try:
        out, err, end, _ = child(cmd, d, {"CODEX_HOME": str(home)} if home else {}, timeout)
    finally:
        home and shutil.rmtree(home, ignore_errors=True)  # ログインの写しを残さない
    text, cost = out, None
    if agent == "claude":
        try:
            j = json.loads(out)
            text, cost = j.get("result", ""), j.get("total_cost_usd")
        except ValueError:
            pass
    return parse_choice(text, order) | {"select_cost": cost, "select_log": f"$ 終わり方: {end}、A = {order['A']}、B = {order['B']}\n{text}\n--- stderr\n{err}"}


def parse_choice(text, order):
    pick, why = re.findall(r"```choice\s*\n\s*(A|B|差なし)\s*\n\s*```", text), re.search(r"<why>(.*?)</why>", text, re.S)
    side = order.get(pick[-1]) if pick else None
    return {"pick": {"head": "変えた版", "base": "前の版"}.get(side, "差なし" if pick else "選べなかった"), "why": why.group(1).strip() if why else text.strip()[-800:]}


def lint_build(plugin, build):
    """変えた版の lint を、組まずに手元で（どちらの出力も同じ物差しで数える）。回らなければ None。"""
    if not build:
        return None
    out = sh(sys.executable, plugin / "skills" / "slides-build" / "scripts" / "slides.py", "lint", "deck.json", "--all", cwd=build, env={"DESK_VERIFY": "1", "DESK_CONFIG": ""}, check=False).stdout  # --all: 既定は前に回したときから変わったページだけで、書く役の最後の lint のあとでは、ほとんどのページを見ない
    return out if COUNT.search(out) else None


PICKS = ("変えた版", "前の版", "差なし")  # 選ぶ役が答えた（選べなかった・止まったは入らない）


def compared(r):
    """比べた依頼: 両方が出し切って lint が回り、選ぶ役が答えたもの（見立てと、open が数えるのはこれだけ）。"""
    return bool(r["lint"]) and r["pick"] in PICKS


def delivered(x):
    """書く役が最後まで終えて、成果物を出したか（時間切れや異常な終わり方のあとに残った build/ は、途中の物なので数えない）。"""
    return bool(x["build"]) and x["end"] == "ok"


def probe_verdict(rows, ids):
    """変えた版の見立て（Harness² の振り返り: helped・hurt・no observed effect・confounded）。1 本ずつの比べなので、1 本だけの差は揺れのうち。"""
    lost = [r["label"] for r in rows if delivered(r["base"]) and not delivered(r["head"])]
    broken = [r["label"] for r in rows if r.get("head_lint_broken")]  # 前の版の出力では回る lint が、変えた版の出力では回らない
    paired = [r for r in rows if compared(r)]
    skipped = [r["label"] for r in rows if not compared(r) and r["label"] not in lost + broken]
    head, base = (sum(r["pick"] == k for r in paired) for k in ("変えた版", "前の版"))
    worse = [r["label"] for r in paired if r["lint"][1]["要修正"] > r["lint"][0]["要修正"]]
    better = [r["label"] for r in paired if r["lint"][1]["要修正"] < r["lint"][0]["要修正"]]
    if lost:
        v = f"害が出た（変えた版だけ出し切れなかった: {'、'.join(lost)}）"
    elif broken:
        v = f"害が出た（変えた版の出力で lint が回らなかった: {'、'.join(broken)}）"
    elif not paired:
        v = f"比べられない（両方が出し切って lint が回り、選ぶ役が答えた依頼がない: {'、'.join(skipped)}）"
    elif len(worse) - len(better) >= 2:  # 要修正の増減も、選んだ版と同じく 1 本の差は揺れのうち
        v = f"害が出た（変えた版の出力で要修正が増えた依頼が 2 本以上多い: {'、'.join(worse)}）"
    elif base - head >= 2:
        v = "害が出た（前の版を選んだ依頼のほうが 2 本以上多い）"
    elif head - base >= 2:
        v = "効いた"
    else:
        v = "差が見えない（選んだ版の差は 1 本以下で、揺れのうち。依頼を足すと確かになる）"
    if worse and len(worse) - len(better) < 2:
        v += f"（要修正が増えた依頼: {'、'.join(worse)}。1 本の差は揺れのうち）"
    if skipped and paired:
        v += f"（比べられなかった依頼: {'、'.join(skipped)}）"
    if len(ids) > 1:
        v += f"・混ざっている（変えた決まり {', '.join(ids[:5])}{' ほか' if len(ids) > 5 else ''}。どの直しが効いたかは分けられない）"
    return v


def probe(w, fixtures, folders, agent="claude", model=None, jobs=2, timeout=1800):
    w.need()
    agent in AGENTS or sys.exit(f"--agent は {'・'.join(AGENTS)}")
    tasks = [fixture_task(w, n) for n in fixtures] + [replay_task(w, f) for f in folders]
    tasks or sys.exit("比べる依頼がない（--fixtures 02,05 か、資料のフォルダを渡す）")
    if sh("git", "-C", w.repo, "status", "--porcelain").stdout.strip():  # 比べたものと、記録する commit と、Issue の差分をそろえる
        sys.exit("変える版に commit していない変更がある。commit してから probe する（open と同じ）")
    head = sh("git", "-C", w.repo, "rev-parse", "--short", "HEAD").stdout.strip()  # どの commit を比べたか（open は今の commit の probe だけを数える）
    tmp = Path(tempfile.mkdtemp(prefix="desk-probe-")).resolve()  # 回すたびに別の作業場（ほかの probe と混ざらず、ほかの人から見えない）。点で始まるフォルダ（.desk/）の下では、claude -p の子が書けない（docs/development.md）
    names = {side: secrets.token_hex(4) for side in SIDES}  # 版の名前をパスに出さない
    plugins = {side: tmp / names[side] for side in SIDES}
    runs = [(t, side) for t in tasks for side in SIDES]
    homes, rows, done = {}, [], {}
    print(f"書く役の子を {len(runs)} 回（{agent}、同時に {jobs}）と、選ぶ役の子を最大 {len(tasks)} 回起こす。1 回 {timeout} 秒まで。作業場: {tmp}（終わったら消す）")
    try:
        for side, src in zip(SIDES, (w.base, w.repo)):
            shutil.copytree(src, plugins[side], ignore=SKIP)
        for side in SIDES if agent == "codex" else ():  # 1 つずつ足す（2 つ目で止まっても、1 つ目の写しを finally で消す）
            homes[side] = codex_home(tmp, secrets.token_hex(4), plugins[side])
        with ThreadPoolExecutor(jobs) as ex:
            done = dict(zip(((t["id"], side) for t, side in runs), ex.map(lambda r: write_one(w, tmp, plugins, r[0], r[1], agent, model, timeout, homes, names), runs)))
        for t in tasks:
            b, h = done[(t["id"], "base")], done[(t["id"], "head")]
            lints = [lint_build(plugins["head"], x["build"]) for x in (b, h)]
            for x in (b, h):  # 成果物は、版の分からない名前の一時フォルダに移す（記録に書くのは、選ぶ役が終わってから）
                if x["build"]:
                    hold = tmp / secrets.token_hex(4)
                    shutil.copytree(x["build"], hold)
                    x["build"] = hold
            r = {"label": t["label"], "base": b, "head": h, "lint": None, "delta": {}, "pick": "選べなかった", "why": "", "select_cost": None}
            if delivered(b) and delivered(h) and all(lints):  # 比べるのは、両方が出し切って lint が回った依頼だけ（途中の物の数で見立てない）
                cb, ca, r["delta"], _, _ = compare(*lints)
                r["lint"] = (cb, ca)
            elif delivered(b) and delivered(h):
                r["pick"] = "比べられず（lint が回らなかった: " + "・".join(k for k, x in (("前の版", lints[0]), ("変えた版", lints[1])) if not x) + "）"
                r["head_lint_broken"] = bool(lints[0]) and not lints[1]
            else:
                r["pick"] = "出し切れず（" + "、".join(f"{k}: {x['end'] if x['build'] else '成果物なし'}" for k, x in (("前の版", b), ("変えた版", h)) if not delivered(x)) + "）"
            rows.append(r)
        for x in [*plugins.values(), *homes.values(), *(tmp / t["id"] for t in tasks)]:  # 選ぶ前に、書く役の作業場とプラグインの写しを消す（選ぶ役の届く所に、版の分かる物を残さない）
            shutil.rmtree(x, ignore_errors=True)
        start = secrets.randbelow(2)
        for n, (t, r) in enumerate((t, r) for t, r in zip(tasks, rows) if r["lint"]):
            r |= select_one(w, tmp, t, {"base": r["base"]["build"], "head": r["head"]["build"]}, agent, model, timeout, (n + start) % 2 == 0)
    finally:
        save_probe(w, tasks, done, rows)  # 選ぶ役が終わってから（止まったときも）、子の出力と成果物を記録に写す
        for x in homes.values():  # ログインの写し（auth.json）を残さない
            shutil.rmtree(x, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)  # 依頼の材料（顧客の構成案など）も一時フォルダに残さない
    patch = sh("git", "-C", w.repo, "diff", f"{MAIN}...HEAD").stdout
    ids = sorted({i for line in patch.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---")) for i in CHANGED_ID.findall(line)})
    detail, public = probe_report(rows, agent, model, probe_verdict(rows, ids), head)
    w.log(detail, public)
    print(detail + f"\n記録: {w.verify / 'pr.md'}（Issue に載る）・{w.verify / 'detail.md'}・{w.verify / 'probe'}/（子の出力と成果物）")


def save_probe(w, tasks, done, rows):
    """子の出力（verify/probe/<依頼>_<base|head|select>.log）と成果物（verify/probe/<依頼>/<base|head>/）を記録に写す。選ぶ役が終わる前に書くと、
    選ぶ役が版の名前の付いた記録から A・B を見分けられる（codex の read-only はディスクのどこでも読める）。"""
    out = w.verify / "probe"
    out.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        for side in SIDES:
            if not (x := done.get((t["id"], side))):
                continue
            (out / f"{t['id']}_{side}.log").write_text(x["log"], encoding="utf-8")
            keep = out / t["id"] / side
            shutil.rmtree(keep, ignore_errors=True)
            if x["build"] and Path(x["build"]).is_dir():
                shutil.copytree(x["build"], keep)
    for t, r in zip(tasks, rows):
        if r.get("select_log"):
            (out / f"{t['id']}_select.log").write_text(r["select_log"], encoding="utf-8")


def probe_report(rows, agent, model, verdict, head=""):
    num = lambda x, k: str(x[k]) if x else "-"
    money = lambda c: f"{c:.2f}" if isinstance(c, (int, float)) else "-"
    title = (f"{PROBE}（{agent}、モデル: {model or 'その CLI の既定'}、変えた版 {head}）\n\n"
            "同じ依頼を、前の版と変えた版のプラグインで子のエージェントに 1 回ずつ書かせた。どちらの出力も変えた版の lint（組まずに手元で）で数え、"
            "版を伏せた選ぶ役の子が、依頼と材料と成果物だけを見て選んだ。\n\n"
            "| 依頼 | 選んだ版 | 要修正（前の版 → 変えた版） | 要確認 | 時間（分） | 費用（$、書く役） | 終わり方 |\n|---|---|---|---|---|---|---|\n")
    table = "".join(f"| {r['label']} | {r['pick']} | {num(r['lint'] and r['lint'][0], '要修正')} → {num(r['lint'] and r['lint'][1], '要修正')} | "
                    f"{num(r['lint'] and r['lint'][0], '要確認')} → {num(r['lint'] and r['lint'][1], '要確認')} | {r['base']['secs'] / 60:.1f}・{r['head']['secs'] / 60:.1f} | "
                    f"{money(r['base']['cost'])}・{money(r['head']['cost'])} | {r['base']['end']}・{r['head']['end']} |\n" for r in rows)
    count = lambda k: sum(r["pick"] == k for r in rows)
    costs = [c for r in rows for c in (r["base"]["cost"], r["head"]["cost"], r["select_cost"]) if isinstance(c, (int, float))]
    tail = (f"\n- 変えた版 {count('変えた版')}・前の版 {count('前の版')}・差なし {count('差なし')}・ほか {len(rows) - count('変えた版') - count('前の版') - count('差なし')}（全 {len(rows)} 本）\n"
            f"- 比べた依頼: {sum(map(compared, rows))} 本（両方が出し切って lint が回り、選ぶ役が答えたもの）\n- 見立て: {verdict}\n" + (f"- 費用の合計（書く役と選ぶ役）: ${sum(costs):.2f}\n" if costs else ""))
    rules = "".join(f"- {r['label']}: " + "、".join(f"{k} {x} → {y}" for k, (x, y) in r["delta"].items()) + "\n" for r in rows if r["delta"])
    warns = "".join(f"- {r['label']}（{side}）: {r[side]['warn']}\n" for r in rows for side in SIDES if r[side]["warn"])
    public = title + table + tail + (f"- 規則ごとの指摘の数（前の版の出力 → 変えた版の出力）:\n{rules}" if rules else "") + (f"- 比べが成り立たないおそれ: {warns.count(chr(10))} 件（detail.md）\n" if warns else "")
    why = "".join(f"\n#### {r['label']}: {r['pick']}\n\n{r['why']}\n" for r in rows)
    return public + (f"\n比べが成り立たないおそれ:\n{warns}" if warns else "") + "\n選ぶ役の理由:\n" + why, public


def upload_images(w, files):
    """画像を w.assets（書けなければ自分の fork）の pr-assets ブランチ（main とは別の、画像だけのブランチ）に置き、Issue から見える URL を返す。"""
    repo, url = str(w.repo), f"https://github.com/{w.assets}.git"
    r = sh("git", *AUTH, "ls-remote", url, "refs/heads/pr-assets")
    env = {"GIT_INDEX_FILE": str(w.dir / "assets.index")}
    Path(env["GIT_INDEX_FILE"]).unlink(missing_ok=True)
    if parent := r.stdout.split("\t")[0].strip():  # 前に置いた画像を残して足す
        sh("git", "-C", repo, *AUTH, "fetch", "-q", url, "pr-assets")
        sh("git", "-C", repo, "read-tree", parent, env=env)
    for f in files:
        blob = sh("git", "-C", repo, "hash-object", "-w", f).stdout.strip()
        sh("git", "-C", repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{w.branch}/{f.name}", env=env)
    tree = sh("git", "-C", repo, "write-tree", env=env).stdout.strip()
    commit = sh("git", "-C", repo, "commit-tree", tree, *(["-p", parent] if parent else []), "-m", f"{w.branch} の画像").stdout.strip()
    sh("git", "-C", repo, *AUTH, "push", "-q", url, f"{commit}:refs/heads/pr-assets")
    return {f.name: f"https://github.com/{w.assets}/blob/pr-assets/{w.branch}/{f.name}?raw=true" for f in files}


def private_words(ws, extra=()):
    """Issue に出してはいけない語: Customers/ の顧客の名前、Customers/<顧客>/ と Internal/ の資料のフォルダの名前（年の 4 桁の数字が入ったもの。
    決まりでは <内容>_<日付>。review_2026q3 のような形も入る）、desk.toml の [desk] private（日本語の社名・製品名、日付のないフォルダの名前など）。
    日付のないフォルダ（assets・drafts など）は、ありふれた語で関係のない Issue を止めるので、名前だけでは入れない（要るなら private に書く）。"""
    names = {p.name for p in (ws / "Customers").glob("*") if p.is_dir()}
    names |= {p.name for p in [*(ws / "Customers").glob("*/*"), *(ws / "Internal").glob("*")] if p.is_dir() and re.search(r"\d{4}", p.name)}
    extra = [extra] if isinstance(extra, str) else list(extra)  # private = "アクメ" と書いても 1 語（1 字ずつに分けない）
    return sorted(names | {str(x).strip() for x in extra if str(x).strip()})  # 空の語は何にでも合うので外す


def leaks(text, words):
    """text に出てくる words（大文字と小文字は区別しない。前後が英数字のときは別の語とみなす）。"""
    return [x for x in words if re.search(rf"(?<![A-Za-z0-9]){re.escape(x)}(?![A-Za-z0-9])", text, re.I)]


def outgoing(title, body, branch, patch, changed):
    """Issue と pr-assets で外に出る文字。open が leaks で確かめる。ブランチは push しないので、コミットメッセージと途中のコミットは出ない:
    題、本文、ブランチの名前（pr-assets の置き場所とコミット）、本文の「変えたファイル」に入る名前、Issue に載せる差分のすべて
    （消した行と前後の行も）。"""
    return "\n".join([title, body, branch, *changed, patch])


def binary_files(numstat):
    """git diff --numstat で、行の数の代わりに「-」が出るファイル（バイナリ）。"""
    return [x.split("\t", 2)[2] for x in numstat.splitlines() if x.startswith("-\t-\t")]


def probed(verify_text, head):
    """今の commit（head）の probe で、比べた依頼が 1 本以上あったか（前の commit の probe は数えない。head が空なら commit を見ない）。"""
    for sha, sec in re.findall(rf"{PROBE}（[^\n]*?変えた版 (\w*)）(.*?)(?=\n### |\Z)", verify_text, re.S):
        if (not head or sha == head) and (m := re.search(r"^- 比べた依頼: (\d+) 本", sec, re.M)) and int(m.group(1)) > 0:
            return True
    return False


def check_body(body, changed, verify_text, images, head=""):
    """足りないものの一覧（空なら出せる）。"""
    miss = [f"本文に「{s}」の節がない" for s in SECTIONS if s not in body]
    if not verify_text and "検証しない理由" not in body:
        miss.append("過去資料での検証がない（kaizen.py lint か rebuild を回す。回せないなら「過去資料での検証」の節に「検証しない理由:」を書く）")
    if any(DESIGN.search(f) for f in changed) and not images:
        miss.append("見た目に関わるファイルを変えたのに、前後の画像がない（kaizen.py rebuild で、変わるページのある資料を組み直す）")
    if any(RULE_TEXT.match(f) for f in changed) and not probed(verify_text, head) and "検証しない理由" not in body:  # 文の決まりは、走らせないと効くか分からない（Harness² では、走らせずに直すと下がった）
        miss.append(f"skills/ の md（決まりと手順の文）を変えたのに、今の commit（{head or '-'}）で走らせて比べていない（kaizen.py probe。比べられない で終わったものは数えない。回せないなら「過去資料での検証」の節に「検証しない理由:」を書く）")
    return miss


def skill_shape(repo):
    """変える版のスキルの形（tests/skills/check.py。前の版のリポジトリになければ見ない）。"""
    c = repo / "tests" / "skills" / "check.py"
    r = sh(sys.executable, c, cwd=repo, check=False) if c.is_file() else None
    if not r or not r.returncode:
        return []
    return [f"スキルの形: {x}" for x in r.stdout.strip().splitlines()] or [f"スキルの形: check.py が止まった（{r.stderr.strip()[-300:]}）"]


def place_images(verify_text, urls):
    """目印（<!-- img:<ファイル名> -->、rebuild が変わったページに付ける）を画像に替える。目印のない画像（verify/img/ に手で置いたもの）は、黙って落とさず末尾にまとめて載せる。"""
    marked = set(re.findall(r"<!-- img:(.+?) -->", verify_text))
    text = re.sub(r"<!-- img:(.+?) -->", lambda m: f"![{m.group(1)}]({urls[m.group(1)]})" if m.group(1) in urls else "", verify_text)
    rest = [n for n in urls if n not in marked]
    return text.rstrip() + "\n\n### ほかの画像（verify/img/ に手で置いたもの）\n\n" + "".join(f"![{n}]({urls[n]})\n" for n in rest) if rest else text


def issue_body(body, changed, base, verify_text, patch):
    """Issue の本文。差分が長くて本文が上限を超えるなら、差分を載せずに行数だけ書く。"""
    head = body.rstrip() + "\n\n## 検証の記録（desk-kaizen）\n\n前の版: `" + base + "`（差分の起点の commit）\n\n変えたファイル: " + ", ".join(f"`{f}`" for f in changed) + "\n\n" + verify_text.rstrip()
    lines = len(patch.splitlines())
    fence = "`" * max(4, 1 + max(map(len, re.findall(r"`+", patch)), default=0))  # 差分の中の ``` で囲いが閉じないように、中のどれより長くする
    diff = f"\n\n## 変更案の差分\n\n<details><summary>git diff（{lines} 行）</summary>\n\n{fence}diff\n{patch.rstrip()}\n{fence}\n\n</details>\n"
    if len(head) + len(diff) > MAX_BODY:  # ponytail: 長い差分は載せない。要るなら差分を分けた Issue にする
        diff = f"\n\n## 変更案の差分\n\n差分が長い（{lines} 行）ので載せていない。\n"
    return head + diff


def open_issue(w, title, body_file):
    w.need()
    if sh("git", "-C", w.repo, "status", "--porcelain").stdout.strip():
        sys.exit("変える版に commit していない変更がある。commit してから open する")
    git = lambda *a: sh("git", "-c", "core.quotepath=false", "-C", w.repo, *a).stdout  # 日本語のファイルの名前を \343… に書き換えさせない（確かめで見えなくなる）
    changed = git("diff", "--name-only", f"{MAIN}...HEAD").splitlines()
    if not changed:
        sys.exit(f"{MAIN} からの変更がない")
    body = Path(body_file).read_text()
    pr_md = w.verify / "pr.md"
    verify_text = pr_md.read_text() if pr_md.is_file() else ""
    images = sorted((w.verify / "img").glob("*.png")) if (w.verify / "img").is_dir() else []
    if miss := check_body(body, changed, verify_text, images, git("rev-parse", "--short", "HEAD").strip()) + skill_shape(w.repo):
        sys.exit("Issue にできない:\n" + "\n".join(f"- {m}" for m in miss))
    # 差分に中身の出ないバイナリ（assets/ の png）は、画像と同じく pr-assets に上げて載せる。消したものは差分の「Binary files … /dev/null」で分かる
    binaries = [w.repo / f for f in binary_files(git("diff", "--numstat", "--no-renames", f"{MAIN}...HEAD")) if (w.repo / f).is_file()]
    if binaries:
        verify_text += "\n\n### 変えたバイナリのファイル（変えた版）\n\n" + "".join(f"`{f.relative_to(w.repo)}`\n\n<!-- img:{f.name} -->\n\n" for f in binaries)
    # 外に出す前に（画像を上げる前に）、外に出るものを全部確かめる。本文は、足す検証の記録（ワークスペースの点検の規則の名前も入る）と画像の名前まで含める
    patch = git("diff", f"{MAIN}...HEAD")
    text = outgoing(title, "\n".join([body, verify_text, *(f.name for f in images)]), w.branch, patch, changed)
    if hit := leaks(text, private_words(w.ws, gapi.config().get("desk", {}).get("private", []))):
        sys.exit("Issue にできない: 題・本文（検証の記録を含む）・ファイルの名前・差分に、顧客や社内の資料の名前がある: " + "、".join(hit)
                 + "。「顧客向けの資料」「（顧客）」のような一般の形にして commit し直す")
    base = git("rev-parse", "--short", git("merge-base", MAIN, "HEAD").strip()).strip()  # 差分の起点の commit
    files = images + binaries
    names = [f.name for f in files]  # pr-assets の置き場所と、本文の目印は名前で決まる
    len(set(names)) == len(names) or sys.exit("Issue にできない: 載せる画像の名前が重なる（verify/img/ と、変えた png）。verify/img/ の画像の名前を変える")
    guess = {f.name: "x" * (200 + len(w.branch) + len(f.name)) for f in files}  # 画像の URL より長めの仮の値
    if (n := len(issue_body(body, changed, base, place_images(verify_text, guess), ""))) > MAX_BODY:  # 画像を上げる前に止める
        sys.exit(f"Issue にできない: 本文と検証の記録が長すぎる（{n} 字。{MAX_BODY} 字まで）。検証の記録（verify/pr.md）を減らすか、分けて出す")
    saved = w.dir / "issue.txt"  # 2 回目からは、同じ Issue の題と本文を書き換える（検証をやり直したとき）
    url = saved.read_text().strip() if saved.is_file() else ""
    if url and (state := sh("gh", "issue", "view", url, "--json", "state", "-q", ".state", cwd=w.repo).stdout.strip()) != "OPEN":
        sys.exit(f"{url} は閉じている（{state}）。出し直すなら kaizen.py clean {w.name} のあと、別の名前で start する")
    urls = upload_images(w, files) if files else {}
    (w.dir / "issue_body.md").write_text(issue_body(body, changed, base, place_images(verify_text, urls), patch))
    if url:
        sh("gh", "issue", "edit", url, "--title", title, "--body-file", w.dir / "issue_body.md", cwd=w.repo)
    else:
        url = (sh("gh", "issue", "create", "-R", REPO, "--title", title, "--body-file", w.dir / "issue_body.md", cwd=w.repo).stdout.split() or [""])[-1]
        url.startswith("https://") or sys.exit(f"gh issue create が URL を返さなかった。{REPO} に Issue ができていれば、その URL を {saved} に書いてから open し直す")
        saved.write_text(url)
    print(url)


def clean(w):
    shutil.rmtree(w.dir, ignore_errors=True)
    print(f"消した: {w.dir}")


def selftest():
    before = "== 要修正: 1 ==\n[絵文字] p1: 「✅」\n\n== 要確認: 2 ==\n[あおり] p2: 「このままでは」\n[空疎な言い回し] p3: 「実現する」\n"
    after = "== 要修正: 0 ==\n\n== 要確認: 2 ==\n[あおり] p2: 「このままでは」\n[空疎な言い回し] p3: 「実現する」\n\n== 要確認（ワークスペースの点検）: 1 ==\n[気になる語] p4\n"
    cb, ca, delta, gone, new = compare(before, after)
    assert cb == {"要修正": 1, "要確認": 2} and ca == {"要修正": 0, "要確認": 3}
    assert delta == {"気になる語": (0, 1), "絵文字": (1, 0)} and gone == [("絵文字", "p1: 「✅」")] and new == [("気になる語", "p4")]
    detail, public = report("資料 1", "スライド", cb, ca, delta, gone, new, title="Acme様_秘密の資料")
    assert "Acme" in detail and "Acme" not in public and "✅" not in public  # Issue には資料の名前も本文も出さない
    body = "\n".join(SECTIONS)
    assert check_body(body, ["skills/slides-build/scripts/lint.py"], "x", []) == []
    assert len(check_body(body, ["skills/slides-build/visual.md"], "x", [])) == 2  # 見た目なのに画像がない。決まりの文なのに走らせていない
    probe_ok = f"{PROBE}（claude、モデル: x、変えた版 abc1234）\n\n- 比べた依頼: 2 本（両方が出し切って lint が回ったもの）\n- 見立て: 効いた\n"
    assert len(check_body(body, ["skills/slides-build/visual.md"], probe_ok, [], "abc1234")) == 1  # 画像がないだけ
    assert len(check_body(body, ["skills/slides-build/visual.md"], probe_ok, [], "def5678")) == 2  # 前の commit の probe は数えない
    assert len(check_body(body, ["skills/slides-build/visual.md"], probe_ok.replace("2 本", "0 本").replace("効いた", "害が出た（変えた版だけ出し切れなかった: 試し）"), [], "abc1234")) == 2  # 比べた依頼がなければ数えない
    assert COUNT.findall("== 要修正: 0 ==\n== 要確認: 16（うち見積もり 11。画像で確定する） ==\n") == [("要修正", "0"), ("要確認", "16")]
    assert len(check_body("## 理由", ["skills/slides-build/scripts/lint.py"], "", [])) == 6  # 節が 5 つと、検証がない
    assert check_body(body + "\n検証しない理由: 文の直しだけ", ["skills/desk-dreaming/SKILL.md"], "", []) == []
    urls = {"deck1_p2.png": "u1", "sample_p1.png": "u2"}
    placed = place_images("### 組み直し\n\n<!-- img:deck1_p2.png -->\n", urls)
    assert placed.index("![deck1_p2.png](u1)") < placed.index("### ほかの画像") < placed.index("![sample_p1.png](u2)") and placed.count("](u1)") == 1  # 目印のない画像も落とさず、末尾に 1 回だけ
    assert place_images("x\n<!-- img:deck1_p2.png -->\n", {"deck1_p2.png": "u1"}) == "x\n![deck1_p2.png](u1)\n"  # みな目印があれば、末尾には足さない
    full = issue_body(body, ["skills/x.md"], "abc1234", "### lint\n", "+++ b/skills/x.md\n+顧客向けの資料\n")
    assert full.index("## 検証の記録") < full.index("`abc1234`") < full.index("## 変更案の差分") and "+顧客向けの資料" in full
    assert binary_files("3\t1\tskills/x.md\n-\t-\tskills/slides-build/assets/gcp/a b.png\n") == ["skills/slides-build/assets/gcp/a b.png"]
    long = issue_body(body, [], "abc1234", "", "+x\n" * MAX_BODY)
    assert "載せていない" in long and "+x" not in long  # 長い差分は載せない
    fenced = issue_body(body, [], "abc1234", "", " ````` 前からある行\n+x\n")
    assert "\n``````diff\n" in fenced and fenced.rstrip().endswith("``````\n\n</details>")  # 差分の中の ````` より長い囲い
    assert re.fullmatch(r"[\w.-]+/[\w.-]+", REPO), REPO  # plugin.json の repository から <持ち主>/<名前> が取れる
    def assets(perm):  # gh の代わりに答える。(画像を置くリポジトリ, gh を呼んだ回数)
        global sh
        calls = []
        def fake(*cmd, cwd=None, env=None, check=True):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, perm if cmd[:2] == ("gh", "repo") else "me/ai-desktools", "")
        real, sh = sh, fake
        try:
            return object.__new__(Work).assets, len(calls)
        finally:
            sh = real
    assert assets("ADMIN") == (REPO, 1) and assets("WRITE") == (REPO, 1)  # 書けるなら、fork を作らない
    assert assets("READ") == ("me/ai-desktools", 3)  # 書けないなら、自分の fork（作って、見えるのを待つ）
    def stops(f, word):
        try:
            f()
        except SystemExit as e:
            return word in str(e)
    assert stops(lambda: sh("kaizen-no-such-command"), "がない")  # 入っていないコマンドは traceback にしない
    with tempfile.TemporaryDirectory() as d:  # 前の版の start が作った worktree（.git がファイル）では、lint・rebuild・open を止める
        w = object.__new__(Work)
        w.name, w.repo = "x", Path(d) / "repo"
        w.repo.mkdir()
        (w.repo / ".git").write_text("gitdir: /src/.git/worktrees/x\n")
        assert stops(w.need, "worktree")
        (w.repo / ".git").unlink()
        (w.repo / ".git").mkdir()
        w.need()  # start が clone したもの（.git がフォルダ）は通す
    with tempfile.TemporaryDirectory() as d:  # rebuild の正本: JSON のデッキ（deck.json だけ）もスライド
        b = Path(d)
        assert stops(lambda: is_slides(b), "deck.json も pages.py も doc.md もない")
        (b / "doc.md").touch()
        assert is_slides(b) is False
        (b / "deck.json").touch()
        assert is_slides(b) is True
        (b / "deck.json").unlink()
        (b / "pages.py").touch()
        assert is_slides(b) is True
    with tempfile.TemporaryDirectory() as d:  # 顧客と資料のフォルダの名前、[desk] private の語が Issue に入ったら止める
        for x in ("Customers/Acme/sample_briefing_202610", "Customers/Acme/review_2026q3", "Customers/Acme/assets", "Internal/grok_study_202610", "Internal/drafts"):
            (Path(d) / x).mkdir(parents=True)
        words = private_words(Path(d), ["アクメ"])
        assert words == ["Acme", "grok_study_202610", "review_2026q3", "sample_briefing_202610", "アクメ"], words  # 年の数字の入ったフォルダは見る。日付のないフォルダ（assets・drafts）は普通の語なので見ない
        assert leaks("+（2026-10-09、`Customers/ACME/sample_briefing_202610` p.2 でアクメの）", words) == ["Acme", "sample_briefing_202610", "アクメ"]
        assert leaks("+顧客向けの資料の p.2（AcmeCorp ではない）", words) == []
        removed = "diff --git a/skills/x.md b/skills/x.md\n--- a/skills/x.md\n+++ b/skills/x.md\n-Acme の古い行（もとの版）\n+顧客向けの資料\n"
        plain = removed.replace("Acme", "前")
        out = lambda patch=plain, changed=("skills/x.md",), branch="kaizen/lint": leaks(outgoing("題", "本文", branch, patch, list(changed)), words)
        assert out() == [] and out(patch=removed) == ["Acme"]  # 消した行も Issue に載るので見る
        assert out(patch=plain.replace("skills/x.md", "skills/acme_rules.md")) == ["Acme"]  # ファイルの名前
        assert out(patch=plain + "+sample_briefing_202610 の p.2\n") == ["sample_briefing_202610"]  # 足した行
        assert out(branch="kaizen/acme-fix") == ["Acme"]  # ブランチの名前
        assert private_words(Path(d), "アクメ")[-1] == "アクメ" and "" not in private_words(Path(d), ["", " "])  # 文字列でも 1 語、空の語は外す
    # probe: 試しの依頼文だけを取り（見るところは渡さない）、選ぶ役の答えを版に戻し、見立てを出す
    with tempfile.TemporaryDirectory() as d:
        w = object.__new__(Work)
        w.repo = Path(d)
        (w.repo / "docs" / "fixtures").mkdir(parents=True)
        (w.repo / "docs" / "fixtures" / "02-gantt.md").write_text("# 02\n\n## 依頼文\n\n```text\nガントを書いて\n```\n\n## 見るところ\n\n- gantt を使う\n")
        t = fixture_task(w, "02")
        assert (t["prompt"], t["label"], t["folder"]) == ("ガントを書いて", "試し 02-gantt", None)
        assert stops(lambda: fixture_task(w, "99"), "がない")
    with tempfile.TemporaryDirectory() as d:  # 再演: 構成案と材料と顧客の memory は写し、答え（build/）と作り手の記録（社内メモ・レビュー）は写さない
        w = object.__new__(Work)
        w.ws, w.verify = Path(d).resolve() / "ws", Path(d).resolve() / "verify"
        deck = w.ws / "Customers" / "acme" / "brief_202610"
        (deck / "build").mkdir(parents=True)
        (deck / "research").mkdir()
        for f in ("構成案.md", "構成案_v2.md", "references.md", "社内メモ_brief.md", "review.md", "build/deck.json", "research/a.md", "../memory.md", "../profile.md"):
            (deck / f).write_text("x")
        (w.ws / "themes" / "slides").mkdir(parents=True)
        (w.ws / "themes" / "slides" / "internal.json").write_text("{}")
        t = replay_task(w, str(deck))
        assert t["label"] == "資料 1" and t["id"] == "deck-1" and "Customers/acme/brief_202610/構成案_v2.md の構成で" in t["prompt"]  # 新しい構成案
        out = Path(d) / "probe"
        sh_real, calls = sh, []
        globals()["sh"] = lambda *a, **k: calls.append(a)  # desk-init は呼んだことだけ見る
        try:
            setup_ws(w, Path("/plugin"), out, t)
        finally:
            globals()["sh"] = sh_real
        got = sorted(str(f.relative_to(out)) for f in out.rglob("*") if f.is_file())
        assert got == ["Customers/acme/brief_202610/references.md", "Customers/acme/brief_202610/research/a.md", "Customers/acme/brief_202610/構成案.md",
                       "Customers/acme/brief_202610/構成案_v2.md", "Customers/acme/memory.md", "Customers/acme/profile.md", "themes/slides/internal.json"], got
        assert str(calls[0][1]).endswith("desk-init/scripts/init.py")
        (deck / "build" / "deck.json").unlink()
        assert stops(lambda: replay_task(w, str(deck)), "JSON のスライドだけ")
    assert SKIP(".", ["docs", "tests", "skills", ".git", "hooks"]) == {"docs", "tests", ".git"}  # 子に渡す写しに、試しの見るところとテストの期待を入れない
    order = {"A": "head", "B": "base"}
    assert parse_choice("<why>p3 の数字が材料と合う</why>\n```choice\nA\n```", order) == {"pick": "変えた版", "why": "p3 の数字が材料と合う"}
    assert parse_choice("```choice\nB\n```", order)["pick"] == "前の版" and parse_choice("```choice\n差なし\n```", order)["pick"] == "差なし"
    assert parse_choice("決められない", order)["pick"] == "選べなかった"
    ok = ({"要修正": 0}, {"要修正": 0})
    row = lambda pick, h=True, lint=ok, end="ok": {"label": "試し", "pick": pick, "base": {"build": True, "end": "ok"}, "head": {"build": h, "end": end}, "lint": lint}
    assert probe_verdict([row("変えた版"), row("変えた版"), row("差なし")], ["slides-visual-012"]) == "効いた"
    assert probe_verdict([row("変えた版"), row("変えた版"), row("出し切れず", end="時間切れ")], []).startswith("害が出た（変えた版だけ出し切れなかった")  # 時間切れのあとに残った build/ は数えない
    assert probe_verdict([row("変えた版"), row("変えた版"), row("差なし", lint=None)], []) == "効いた（比べられなかった依頼: 試し）"
    assert probe_verdict([row("変えた版"), row("変えた版"), row("比べられず", lint=None) | {"head_lint_broken": True}], []).startswith("害が出た（変えた版の出力で lint が回らなかった")
    assert probe_verdict([row("選べなかった")] * 3, []).startswith("比べられない（") and not compared(row("選べなかった"))  # 選ぶ役がみな止まったら、比べたことにしない
    both_failed = {"label": "試し", "pick": "出し切れず", "base": {"build": True, "end": "時間切れ"}, "head": {"build": True, "end": "時間切れ"}, "lint": None}
    assert probe_verdict([both_failed] * 3, []).startswith("比べられない（両方が出し切って")  # 途中の物しかなければ、差が見えないとは言わない
    assert delivered({"build": "x", "end": "ok"}) and not delivered({"build": "x", "end": "exit 1"}) and not delivered({"build": None, "end": "ok"})
    assert probe_verdict([row("変えた版")], []).startswith("差が見えない（") and probe_verdict([row("前の版")] * 2, []).startswith("害が出た（前の版を")
    assert probe_verdict([row("変えた版"), row("変えた版"), row("前の版", h=None)], []).startswith("害が出た（変えた版だけ出し切れなかった")  # 成果物の出ない直しは危ない（Harness² の UNSAFE）
    worse = ({"要修正": 0}, {"要修正": 2})
    assert probe_verdict([row("変えた版", lint=worse)], []).startswith("差が見えない（") and "要修正が増えた依頼: 試し" in probe_verdict([row("変えた版", lint=worse)], [])  # 1 本だけなら揺れのうち
    assert probe_verdict([row("変えた版", lint=worse)] * 2, []).startswith("害が出た（変えた版の出力で要修正が増えた依頼が 2 本以上多い")
    assert codex_leftovers('model = "x"\n[model_providers.a]\nname = "a"\n') == []
    assert set(codex_leftovers('tools.web_search = true\n[profiles.p]\nweb_search = "live"\n')) == {"tools", "tools.web_search", "profiles.p.web_search"}  # 点つきの鍵の表と、許した表の中の Web 検索も残さない
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:  # 写すときに、頭の点つきの鍵・その場の表・表・Web 検索の鍵を落とす
        conf = Path(src) / "config.toml"
        conf.write_text('model = "m"\nweb_search = "live"\ntools.web_search = true\nmcp_servers.s.command = "npx"\napps = { a = 1 }\n[model_providers.x]\nname = "x"\n[mcp_servers.t]\ncommand = "y"\n[features]\nweb_search_request = true\n')
        old_home, os.environ["CODEX_HOME"] = os.environ.get("CODEX_HOME"), src
        try:
            got = tomllib.loads((codex_home(Path(dst), "h") / "config.toml").read_text())
            assert got == {"model": "m", "model_providers": {"x": {"name": "x"}}, "features": {}}, got
            conf.write_text('[profiles.p]\ntools = { web_search = true }\n')  # 落とせない形は、写さずに止める
            assert stops(lambda: codex_home(Path(dst), "h2"), "写せない")
        finally:
            os.environ.pop("CODEX_HOME") if old_home is None else os.environ.__setitem__("CODEX_HOME", old_home)
    assert "混ざっている（変えた決まり a-001, b-002" in probe_verdict([row("差なし")], ["a-001", "b-002"])
    assert claude_meta('{"type":"system","subtype":"init","plugins":[{"name":"desk-tools","path":"/elsewhere"}]}\n{"type":"result","total_cost_usd":1.5}', Path("/tmp/x")) == (1.5, "読み込んだ desk-tools が写しでない（/elsewhere）")
    print("selftest ok")


def main(a):
    if a == ["--selftest"]:
        return selftest()
    if len(a) < 2 or a[0] not in ("start", "lint", "rebuild", "probe", "open", "clean"):
        sys.exit(__doc__)
    w, rest = Work(a[1]), a[2:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    plain = [x for i, x in enumerate(rest) if not x.startswith("--") and (i == 0 or rest[i - 1] not in ("--pages", "--title", "--body", "--fixtures", "--agent", "--model", "--jobs", "--timeout"))]
    if a[0] == "start":
        start(w)
    elif a[0] == "lint":
        lint_cmd(w, plain)
    elif a[0] == "rebuild":
        rebuild(w, plain, opt("--pages"), "--keep" in rest)
    elif a[0] == "probe":
        probe(w, [x for x in (opt("--fixtures") or "").split(",") if x], plain, opt("--agent") or "claude", opt("--model"), int(opt("--jobs") or 2), int(opt("--timeout") or 1800))
    elif a[0] == "open":
        open_issue(w, opt("--title") or sys.exit("--title が要る"), opt("--body") or sys.exit("--body が要る"))
    else:
        clean(w)


if __name__ == "__main__":
    gapi.run(lambda: main(sys.argv[1:]))
