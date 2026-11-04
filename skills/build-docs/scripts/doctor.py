#!/usr/bin/env python3
"""usage: doctor.py [<ワークスペース>] [--local]   （--selftest で自己確認）
AI Desk Tools を動かす前提を確かめる。--local は手元だけ見て、Google の API を呼ばない。
1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。標準ライブラリだけ。"""
import io, contextlib, math, os, re, shutil, sys, tempfile, tomllib, urllib.parse
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]  # このスキルと並ぶスキルのフォルダ（ワークスペースの .agents/skills などとの重なりを、名前だけで見る）
sys.dont_write_bytecode = True
import desk  # noqa: E402  ワークスペースと設定のファイルの探し方
import gapi  # noqa: E402  Google の API（connection を通すときの確かめと、proxy の断りの見分け。build-slides のものの写し）


OLD_1104 = {"google-slides": "scripts/gslides.py", "google-docs": "scripts/doc_lint.py", "google-vids": "scripts/vids_internal.py"}  # 2026-11-02〜11-04 の道具のスキルの名前と、その写しにしかないファイル（ほかのパッケージにも同じ名前のスキルがあるので、これで見分ける）
OLD_NAMES = ("slides-build", "docs-build", "vids-build", "vids-voice", *OLD_1104, "desk-doctor")  # 道具のスキルの前の名前（2026-11-02 に google-*、2026-11-04 に build-* にした）と、2026-11-05 に desk-init に入れた desk-doctor
CHECKS = "connection にログインしてあるか（人ごとの OAuth）、USE CONNECTION の権限、connection の OAuth の scope（drive・presentations・documents）、databricks auth login"


def proxy_fail(e):
    """connection を通して通らなかったときのメッセージ。原因は当てない（状態コードと本文からの見分けは外れる。2026-11-01 の review-loop）。
    proxy が自分で断ったもの（gapi.rejected。返事にログインの URL がある）だけを分け、ほかは返事の先頭と確かめることの一覧を出す。"""
    first, *rest = (str(e) or type(e).__name__).splitlines()
    if first.startswith(gapi.REJECTED):
        return f"{first}。ワークスペースの画面で connection にログインする: {' '.join(rest)[:400]}"
    body = " ".join(rest)[:300]
    return f"{first}{f'（{body}）' if body else ''}。確かめる: {CHECKS}"


def check(ws, local=False):
    """(区分, 項目, 詳しく) の並び。区分は OK・要修正・要確認。"""
    out = []
    ok = lambda name, detail="": out.append(("OK", name, detail))
    ng = lambda name, detail: out.append(("要修正", name, detail))
    warn = lambda name, detail: out.append(("要確認", name, detail))

    (ok if sys.version_info >= (3, 11) else ng)("Python 3.11 以上", sys.version.split()[0])
    (ok if shutil.which("uv") else ng)("uv", shutil.which("uv") or "ない。画像での測り（box_pad.py・doc_layout.py・sheet.py）が動かない。https://docs.astral.sh/uv/ で入れる")
    npx = shutil.which("npx")  # docs.py の mermaid_png が mermaid-cli を取ってくる
    (ok if npx else warn)("mermaid の図", npx or "Node.js（npx）がない。doc.md の ```mermaid を組めない（ほかは組める）。https://nodejs.org/ で入れる")
    try:
        found = desk.locate(ws)
    except SystemExit as e:  # 上に desk.toml がなく、~/.desk.toml が読めない・workspace がない
        ng("個人の設定", str(e))
        return out
    if not found:
        if old := desk.old(ws):  # factory.toml だけがある、2026-10-25 より前のワークスペース
            ng("前のバージョンのワークスペース", f"{old} は前のバージョン（factory.toml・.factory/）。desk-migrate で desk.toml・.desk/ に移す")
        else:
            ng("desk.toml", desk.missing(ws))
        return out
    conf, root = found
    ok("設定", str(conf))
    ok("ワークスペース", str(root))
    try:
        user = desk.user()
    except SystemExit as e:  # このワークスペースは自分の desk.toml を読むので動く
        user = None
        warn("個人の設定", f"{e}。ほかのフォルダで開いた会話とスクリプトが止まる")
    if user and (loc := desk.local(user[1])):  # 既定のワークスペースか、その上に desk.toml がある。中で開くか外で開くかで、読む設定が変わる
        warn("設定が 2 つ", f"{user[0]} の workspace（{user[1]}）の中では {loc[0]} を読む（外では {user[0]}。混ぜない）。片方にする: 値を {user[0]} に寄せて "
                         f"{loc[0]} を .desk/migrate/ に移すか、{user[0]} を消す（desk-migrate の SKILL.md の「Move the settings to `~/.desk.toml`」の 2）")
    try:
        cfg = tomllib.loads(conf.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        ng(f"{conf.name} の書き方", str(e))
        return out
    for name in ("references_index.md", "drive_folders.md"):
        (ok if (root / name).is_file() else warn)(name, "" if (root / name).is_file() else "ない。desk-init で置く")
    if old := sorted((root / "Customers").glob("*/CLAUDE.md")):
        how = lambda p: f"{p.relative_to(root)}（{'memory.md に中身を移して消す' if (p.parent / 'memory.md').exists() else 'memory.md に名前を変える'}）"
        warn("顧客の memory", f"前の形の CLAUDE.md がある。Claude Code しか読まない（作る会話が資料を作り始めるときに開くのは memory.md）: {', '.join(map(how, old))}")
    if desk.old_agents(root):  # 持ち主が書いた AGENTS.md・CLAUDE.md には何も言わない
        warn("前の雛形の AGENTS.md", "AGENTS.md が、2026-10-31 までの desk-init が置いた雛形の写しに見える（その節の見出しが半分より多く同じ）。写しなら、プラグインはもう決まりを戻さない。"
             "エージェントはどの会話にもスキルより強く読み込むので、資料を作らない作業にも効く。ワークスペースだけの決まりはレシピに移し、プラグインのスキルにある文は消す"
             "（desk-migrate の SKILL.md の「Move an AGENTS.md from the old template」）")
    odd, top = [], root / desk.RECIPES  # レシピの形と frontmatter（desk-feedback/routing.md の「Workspace rules」）
    for p, m in (rules := desk.rules(root)):
        rel = p.relative_to(root)
        if "paths" in m:
            odd.append(f"{rel} に paths がある（前のバージョンの書き方で、もう読まない。材料を集めるときなら step: gather、組むときなら step: build、資料を作るどの作業でもなら書かない）")
        if m.get("step", "") not in ("", *desk.STEPS):
            odd.append(f"{rel} の step の {m['step']}（{'・'.join(desk.STEPS)} のどれか。資料を作るどの作業でも開くなら書かない）")
        if desk.kind(m) == "material" and m.get("step"):
            odd.append(f"{rel} に per_material と step の両方がある（資料ごとに選ぶレシピは、構成案の「使う決まり」で開く。step は効かない）")
        odd += [f"{rel} の {k} の {v}（{'・'.join(vals)} のどれか）" for k, vals in (("targets", desk.TARGETS), ("audience", desk.AUDIENCES)) for v in desk.listed(m, k) if v not in vals]
        if (n := len(p.read_text(encoding="utf-8"))) > desk.RULE_MAX:
            odd.append(f"{rel} が {n:,} 字（{desk.RULE_MAX:,} 字まで。もっと狭い目的のレシピに分ける）")
        if skill := next((x for x in p.relative_to(top).parts[:-1] if (SKILLS / x / "SKILL.md").is_file()), None):
            odd.append(f"{rel} がスキルの名前のフォルダ（{skill}）にある（目的の名前にする。desk-feedback の recipes.md の §2）")
        if p.parent != top and (p.parent.parent / desk.RECIPE).is_file():
            odd.append(f"{rel} がほかのレシピのフォルダの中にある（desk.py recipes は両方を別々のレシピとして並べる。資源なら RECIPE.md の名前を替える）")
    have = {p for p, _ in rules}
    for p in sorted(top.rglob("*.md")) if top.is_dir() else []:  # 一覧に出ないもの: レシピのフォルダの外の .md と、description のない RECIPE.md
        rel = p.relative_to(root)
        inside = any((d / desk.RECIPE).is_file() for d in p.parents if d.is_relative_to(top) and d != top)
        if p.name == desk.RECIPE and p.parent != top and p not in have and "templates" not in p.relative_to(top).parts[1:]:
            odd.append(f"{rel} の先頭に frontmatter の description がない（ないと desk.py recipes の一覧に出ない）")
        elif not inside and p != top / "README.md" and "templates" not in p.relative_to(top).parts[1:]:
            odd.append(f"{rel} はレシピでない（決まりは recipes/<名前>/RECIPE.md に書く。desk.py recipes の一覧に出ない）")
    if (top / "README.md").is_file() and re.search(r"hook (?:が|は名前)", (top / "README.md").read_text(encoding="utf-8", errors="ignore")):  # 2026-11-03 までの雛形の写し（hook が出すと書いてある）
        odd.append("recipes/README.md が前の雛形（hook がレシピと memory を出すと書いてある。2026-11-04 から、作る会話が desk.py recipes を見て自分で開く）。desk-init の雛形の recipes/README.md で置き換える")
    (warn if odd else ok)("ワークスペースの決まり", "、".join(odd) if odd else f"レシピ {len(rules)} 個")
    if cfg.get("desk", {}).get("source"):  # 2026-10-14 まで、desk-kaizen が worktree を作る checkout（前の [factory] source。desk-migrate が [desk] にする）
        warn("desk.source", "使わなくなった（desk-kaizen は .desk/kaizen/ に自分で clone する）。desk.toml から消す")
    names = sorted({p.parent.name for p in SKILLS.glob("*/SKILL.md")} | set(OLD_NAMES))  # 前の名前で置いた写しも（名前がぶつからないので、プラグインのものと両方が効く）
    found = {}  # 実体ごとに 1 回（.claude/skills は .agents/skills へのリンクのことが多い）
    for d in (".agents/skills", ".claude/skills"):
        for name in names:
            if (root / d / name / "SKILL.md").is_file() and (root / d / name).resolve() != (SKILLS / name).resolve() and (name not in OLD_1104 or (root / d / name / OLD_1104[name]).is_file()):  # このスキルを入れた場所そのもの（ワークスペースの .claude/skills に 1 つずつ入れたとき）は重なりでない
                found.setdefault((root / d / name).resolve(), f"{d}/{name}")
    dup, old = [x for x in found.values() if x.rsplit("/", 1)[1] not in OLD_NAMES], [x for x in found.values() if x.rsplit("/", 1)[1] in OLD_NAMES]
    (warn if dup or old else ok)("スキルの重なり", "、".join(x for x in (f"ワークスペースにも同じ名前のスキルがある（プラグインと二重に読まれる）: {', '.join(dup)}" * bool(dup),
                                                                f"前のバージョンの名前のスキルがある（今の build-slides・build-docs・build-vids と両方が効く）: {', '.join(old)}" * bool(old)) if x))
    g, dr = cfg.get("google", {}), cfg.get("drive", {})
    try:
        px = gapi.uc(cfg)  # 型の違う設定は gapi.uc が断る（スクリプトも同じところで止まる）
        if cfg.get("uc_connections", {}).get("proxy"):
            ok("uc_connections", f"有効: {', '.join(h for h, n in px['proxy'].items() if n) or 'connection の名前がない（直接呼ぶ）'}" if px else "無効（enabled = false。Google を直接呼ぶ）")
    except gapi.ApiError as e:
        ng("uc_connections", str(e))
        px = {"bad": True}  # Google への呼び出しはどれも同じ理由で止まるので、下では見ない
    via = {h: n for h, n in px.get("proxy", {}).items() if n}  # gapi.route と同じ。名前が空のホストは直接呼ぶ
    bad_uc = px.get("bad", False)
    if not g.get("quota_project") and not all(urllib.parse.urlsplit(u).netloc in via for u in (gapi.DRIVE, gapi.SLIDES, gapi.DOCS)):  # 直接呼ぶホストがある
        warn("google.quota_project", "空。gcloud の既定の OAuth クライアントで取ったトークンなら、Slides・Docs が 403 になる")
    review = cfg.get("review", {})  # 書いていなければ既定。読むのはエージェント（deck-workflow の 5 と 9）
    if (p := review.get("plan_reviewer", "ai")) not in ("ai", "human"):
        ng("review.plan_reviewer", f"{p!r} は使えない。\"ai\" か \"human\" にする")
    if type(n := review.get("deck_review_max_rounds", 3)) is not int or not 1 <= n <= 3:  # bool は int の子なので type で見る
        ng("review.deck_review_max_rounds", f"{n!r} は使えない。1〜3 の整数にする（直すと欠陥が増えるので 3 より多くしない）")
    if type(h := cfg.get("feedback", {}).get("google_comments", {}).get("watch_hours", 0)) not in (int, float) or not math.isfinite(h) or h < 0:  # 0 か書いていなければ、頼まれたときだけ見張る（deck-workflow の comments.md）
        ng("feedback.google_comments.watch_hours", f"{h!r} は使えない。時間の数にする（見張らないなら 0）")
    if not (type(lang := cfg.get("desk", {}).get("default_language", "ja")) is str and re.fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})*", lang)):  # スクリプトは主の部分だけを比べる（gapi.language）
        ng("desk.default_language", f"{lang!r} は使えない。言語のコード（\"ja\"・\"en\"・\"zh-Hant\" など）にする")
    for k in ("customers", "internal", "docs", "desk"):
        if not dr.get(k):
            warn(f"drive.{k}", "空。資料の置き場所が決まらない")
    if local or bad_uc:
        return out

    gapi.find_config = lambda: (conf, root)  # gapi も、ここで見つけて出した設定を読む（ワークスペースから探し直すと、上に desk.toml があるときに別のものを読む）
    try:  # ワークスペースの URL が決まるか（gapi.route と同じ確かめとメッセージ）。決まらなければ、どの connection も同じ理由で通らないので 1 行だけ出す
        gapi.route(f"https://{next(iter(via))}/") if via else None  # databricks auth describe を呼ぶので --local では見ない
    except gapi.ApiError as e:
        ng("uc_connections", str(e))
        if "www.googleapis.com" in via:  # Drive も通らない（下の確かめはどれも同じ理由で止まる）
            return out
        via = {}
    probe = {urllib.parse.urlsplit(u).netloc for u in (gapi.SLIDES, gapi.DOCS)}  # API の説明（$discovery、v1）を ID なしで取れる、プラグインが使うホスト
    for host, conn in via.items():  # Drive（下の「Google の認証」）のほかの connection。Drive が通らなくても見る
        if host in probe:
            try:
                gapi.request("GET", f"https://{host}/$discovery/rest?version=v1")
                ok(f"uc_connections.proxy.{host}", f"{conn} に届く（OAuth の scope は、使うときに 403 で分かる）")
            except Exception as e:  # 1 つのホストが通らなくても、ほかのホストを見続ける（回線のエラー・形の違う返事も）
                ng(f"uc_connections.proxy.{host}", f"connection {conn} で通らない: {proxy_fail(e)}")
        elif host != "www.googleapis.com":
            ok(f"uc_connections.proxy.{host}", f"{conn}（プラグインは呼ばないホストなので、確かめていない）")
    try:
        who = gapi.request("GET", f"{gapi.DRIVE}/about?fields=user(emailAddress)")["user"]["emailAddress"]
        ok("Google の認証", who)
    except Exception as e:  # 回線のエラー・形の違う返事（キーがない JSON など）も、トレースバックにしない
        first = (str(e) or type(e).__name__).splitlines()[0]
        if conn := via.get("www.googleapis.com"):  # Drive を connection で呼んだ
            ng("Google の認証", f"Unity Catalog の connection {conn} で通らない: {proxy_fail(e)}")
            return out
        how = "GOOGLE_OAUTH_ACCESS_TOKEN" if os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") else str(gapi.credentials_path())  # gapi.token() と同じ順
        fix = "google.quota_project を書く（空だと gcloud の既定の OAuth クライアントのトークンは 403）" if first.startswith("403") and not g.get("quota_project") else f"作り直す: {gapi.LOGIN}"
        ng("Google の認証", f"{how} で通らない: {first}。{fix}")
        return out
    targets = [(f"drive.{k}", v) for k, v in dr.items() if v]  # テンプレートは slides_doctor.py（build-slides）と docs_doctor.py（build-docs）が開く
    for name, url in targets:
        fid = gapi.folder_id(url) if "/folders/" in url else gapi.file_id(url)
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{fid}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except Exception as e:  # connection を通すと、回線のエラーや proxy の断り・形の違う返事もここに来る。行ごとに知らせ、ほかの行を落とさない
            w = (str(e) or type(e).__name__).split()[0]
            ng(name, f"開けない（{w}）: {url}" if w[:3].isdigit() else f"開けない: {url}。{proxy_fail(e)}")
    return out


def main(args):
    local = "--local" in args
    rest = [a for a in args if a != "--local"]
    rows = check(Path(rest[0] if rest else ".").expanduser().resolve(), local)
    for kind, name, detail in rows:
        print(f"{kind}\t{name}\t{detail}")
    n = sum(k == "要修正" for k, _, _ in rows)
    print(f"\n要修正 {n}・要確認 {sum(k == '要確認' for k, _, _ in rows)}" + ("（--local: Google の API は見ていない）" if local else ""))
    return 1 if n else 0


BASE = ('[desk]\ndefault_language = "ja"\n\n[google]\nquota_project = ""\n\n[review]\nplan_reviewer = "ai"\ndeck_review_max_rounds = 3\n\n'
        '[feedback.google_comments]\nwatch_hours = 0\n\n[drive]\ndesk = ""\nshared_themes = ""\ncustomers = ""\ninternal = ""\ndocs = ""\n')  # selftest のワークスペース（desk-init の雛形の、ここで見る値だけ）


def workspace(ws, user=None):
    """selftest のワークスペース。user があれば、設定はそのパスに workspace を書いて置く（~/.desk.toml の形）。"""
    for d in ("Customers", "Internal", "Research", ".desk"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    for name in ("references_index.md", "drive_folders.md"):
        (ws / name).write_text("x\n")
    if user:
        user.parent.mkdir(parents=True, exist_ok=True)
        user.write_text(f'workspace = "{ws}"\n\n' + BASE)
    else:
        (ws / "desk.toml").write_text(BASE)


def selftest():
    me = Path(__file__).resolve().parents[1].name  # このスクリプトのスキル（desk-init か、写しを持つ build-slides・build-docs）。隣にほかのスキルがなくても回る
    assert "connection にログインする: Please login" in proxy_fail(Exception(f"{gapi.REJECTED}: GET u\nPlease login"))  # 返事のログインの URL を見せる
    m = proxy_fail(Exception('503 GET u\n<html>bad gateway</html>'))
    assert m.startswith("503 GET u（<html>bad gateway</html>）。確かめる: ") and CHECKS in m and proxy_fail(TimeoutError()) == f"TimeoutError。確かめる: {CHECKS}"  # 原因は当てない
    with tempfile.TemporaryDirectory() as tmp:  # ~/.desk.toml の workspace を使う。ワークスペースにも desk.toml があれば要確認
        ws, conf = Path(tmp, "Documents").resolve(), Path(tmp, "home", ".desk.toml")
        os.environ["DESK_CONFIG"] = str(conf)
        rows = lambda at: {n: (k, d) for k, n, d in check(at, local=True)}
        assert rows(Path(tmp))["desk.toml"][0] == "要修正"  # どちらもない
        workspace(ws, conf)
        r = rows(Path(tmp))  # ワークスペースの外で回しても
        assert r["設定"] == ("OK", str(conf)) and r["ワークスペース"] == ("OK", str(ws)) and "設定が 2 つ" not in r and "前の雛形の AGENTS.md" not in r
        (ws / "desk.toml").write_text("")
        r = rows(ws / "Customers")
        assert r["設定"] == ("OK", str(ws / "desk.toml")) and r["設定が 2 つ"][0] == "要確認" and rows(Path(tmp))["設定が 2 つ"][0] == "要確認"
        (ws / "desk.toml").rename(Path(tmp, "desk.toml"))  # 既定のワークスペースの上にある desk.toml も、中で開くと勝つ
        assert str(Path(tmp, "desk.toml")) in rows(conf.parent)["設定が 2 つ"][1]
        Path(tmp, "desk.toml").rename(ws / "desk.toml")
        conf.write_text("[drive]\n")
        assert rows(Path(tmp))["個人の設定"][0] == "要修正" and rows(ws)["個人の設定"][0] == "要確認"  # 読めない ~/.desk.toml。中ではワークスペースの desk.toml で動く
    os.environ["DESK_CONFIG"] = ""  # 手元の ~/.desk.toml に左右されない
    with tempfile.TemporaryDirectory() as tmp:
        kinds = lambda: {n: k for k, n, _ in check(Path(tmp), local=True)}
        assert kinds()["desk.toml"] == "要修正"
        (Path(tmp) / "factory.toml").write_text("")
        assert kinds()["前のバージョンのワークスペース"] == "要修正"  # 2026-10-25 より前の名前
        (Path(tmp) / "factory.toml").unlink()
        workspace(Path(tmp))
        (Path(tmp) / ".agents" / "skills" / me).mkdir(parents=True)
        (Path(tmp) / ".agents" / "skills" / me / "SKILL.md").write_text("x")
        (Path(tmp) / ".claude" / "skills" / "slides-build").mkdir(parents=True)
        (Path(tmp) / ".claude" / "skills" / "slides-build" / "SKILL.md").write_text("x")
        for n, f in (("google-slides", "scripts/gslides.py"), ("google-docs", "SKILL.md")):  # google-docs は、ほかのパッケージの同じ名前のスキル（doc_lint.py がない）
            (Path(tmp) / ".claude" / "skills" / n / f).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / ".claude" / "skills" / n / f).write_text("x")
        (Path(tmp) / ".claude" / "skills" / "google-slides" / "SKILL.md").write_text("x")
        got = next(d for _, n, d in check(Path(tmp), local=True) if n == "スキルの重なり")
        assert "前のバージョンの名前のスキルがある（今の build-slides・build-docs・build-vids と両方が効く）: .claude/skills/google-slides, .claude/skills/slides-build" in got and "google-docs" not in got, got  # 前の名前で置いた写しも
        k = kinds()
        assert k["スキルの重なり"] == "要確認" and k["drive.customers"] == "要確認"
        (Path(tmp) / "Customers" / "acme").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").write_text("x")
        assert kinds()["顧客の memory"] == "要確認"
        (Path(tmp) / "Customers" / "acme" / "memory.md").write_text("y")
        assert "中身を移して消す" in next(d for _, n, d in check(Path(tmp), local=True) if n == "顧客の memory")  # 名前を変えると memory.md を上書きする
        (Path(tmp) / "Customers" / "acme" / "memory.md").unlink()
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").rename(Path(tmp) / "Customers" / "acme" / "memory.md")
        assert "顧客の memory" not in kinds()
        readme = Path(tmp) / "recipes" / "README.md"
        readme.parent.mkdir(exist_ok=True)
        readme.write_text("構成案を開くたびに hook が出す。\n")
        assert "recipes/README.md が前の雛形" in next(d for _, n, d in check(Path(tmp), local=True) if n == "ワークスペースの決まり")  # hook が出すと書いた前の雛形
        readme.write_text("作る会話が開く。\n")
        assert "前の雛形" not in next(d for _, n, d in check(Path(tmp), local=True) if n == "ワークスペースの決まり")
        conf, base = Path(tmp) / "desk.toml", (Path(tmp) / "desk.toml").read_text()
        for bad in ('uc_connections = "on"\n', '[uc_connections]\nenabled = "false"\n', '[uc_connections]\nprofile = 5\n', '[uc_connections]\nhost = 5\n',
                    '[uc_connections.proxy]\n"slides.googleapis.com" = 5\n'):  # 表でない・型の違う設定は要修正（トレースバックにしない）
            conf.write_text(bad + base)  # 先頭に書く（末尾だと、最後の表のキーになる）
            assert kinds()["uc_connections"] == "要修正", bad
        hosts = '[uc_connections.proxy]\n"www.googleapis.com" = "d"\n"slides.googleapis.com" = "s"\n"docs.googleapis.com" = "x"\n'
        conf.write_text(base + hosts)
        k = kinds()
        assert k["uc_connections"] == "OK" and "google.quota_project" not in k  # 全部 connection を通すなら、quota project は要らない
        conf.write_text(base + hosts.replace('"x"', '""'))
        assert kinds()["google.quota_project"] == "要確認"  # Docs は直接呼ぶ
        conf.write_text(base + "[uc_connections]\nenabled = false\n" + hosts)
        assert "無効" in next(d for _, n, d in check(Path(tmp), local=True) if n == "uc_connections") and kinds()["google.quota_project"] == "要確認"
        conf.write_text(base)
        agents = Path(tmp) / "AGENTS.md"
        assert "前の雛形の AGENTS.md" not in kinds() and "前のバージョンのワークスペース" not in kinds()  # 今の雛形は AGENTS.md を置かない
        assert kinds()["ワークスペースの決まり"] == "OK"
        rx = Path(tmp) / "recipes" / "x"
        rx.mkdir(parents=True)
        (rx / "RECIPE.md").write_text("---\ndescription: x\npaths: [deck-design/slides.md]\nstep: review\ntargets: [video]\n---\n" + "あ" * desk.RULE_MAX)
        d = next(d for k, n, d in check(Path(tmp), local=True) if n == "ワークスペースの決まり")
        assert kinds()["ワークスペースの決まり"] == "要確認" and "paths がある" in d and "step の review" in d and "targets の video" in d and f"字（{desk.RULE_MAX:,} 字まで" in d, d
        (rx / "RECIPE.md").write_text("---\ndescription: x\nstep: build\n---\n- 16pt\n")
        (rx / "templates" / "t").mkdir(parents=True)
        (rx / "templates" / "t" / "doc.md").write_text("# テンプレート\n")
        (rx / "note.md").write_text("資源\n")
        assert kinds()["ワークスペースの決まり"] == "OK"  # 資源とテンプレートは決まりでない
        (Path(tmp) / "recipes" / "loose.md").write_text("---\ndescription: 前の形\n---\n")
        (Path(tmp) / "recipes" / "RECIPE.md").write_text("---\ndescription: フォルダがない\n---\n")
        (Path(tmp) / "recipes" / me / "y").mkdir(parents=True)
        (Path(tmp) / "recipes" / me / "y" / "RECIPE.md").write_text("---\ndescription: y\n---\n")
        (Path(tmp) / "recipes" / "z").mkdir()
        (Path(tmp) / "recipes" / "z" / "RECIPE.md").write_text("- description がない\n")
        d = next(d for k, n, d in check(Path(tmp), local=True) if n == "ワークスペースの決まり")
        assert "recipes/loose.md はレシピでない" in d and "recipes/RECIPE.md はレシピでない" in d and f"スキルの名前のフォルダ（{me}）" in d and "recipes/z/RECIPE.md の先頭に frontmatter の description がない" in d, d
        shutil.rmtree(Path(tmp) / "recipes")
        agents.write_text("# 自分の決まり\n- 社内向けは敬体。\n")
        assert "前の雛形の AGENTS.md" not in kinds()  # 持ち主が書いたものには言わない
        agents.write_text("# 自分の決まり\n\n移したメモ: 前は「# このワークスペースの運用ルール」の下に「## 決まりの優先」があった。\n## 書き方\n- 敬体。\n")
        assert "前の雛形の AGENTS.md" not in kinds()  # 前の雛形の見出しを引いただけ・節が 1 つ同じだけでは言わない
        agents.write_text("# Documents の運用ルール\n" + "".join(f"\n## {h}\n\n- 前の雛形の文。\n" for h in desk.AGENTS_TEMPLATE[:5]))
        assert kinds()["前の雛形の AGENTS.md"] == "要確認"  # 頭の題を書き替えた写しも、節で見つける
        agents.unlink()
        toml = Path(tmp) / "desk.toml"
        assert "review.plan_reviewer" not in kinds() and "review.deck_review_max_rounds" not in kinds()  # 雛形の既定
        toml.write_text(toml.read_text().replace('plan_reviewer = "ai"', 'plan_reviewer = "AI"').replace("deck_review_max_rounds = 3", "deck_review_max_rounds = 5"))
        assert kinds()["review.plan_reviewer"] == "要修正" and kinds()["review.deck_review_max_rounds"] == "要修正"
        assert "desk.default_language" not in kinds()  # 雛形の ja
        toml.write_text(toml.read_text().replace('default_language = "ja"', 'default_language = "日本語"'))
        assert kinds()["desk.default_language"] == "要修正"
        toml.write_text(toml.read_text().replace('default_language = "日本語"', 'default_language = "ja_JP"'))
        assert "desk.default_language" not in kinds()
        toml.write_text(toml.read_text().replace('plan_reviewer = "AI"', 'plan_reviewer = "human"').replace("deck_review_max_rounds = 5", "deck_review_max_rounds = true"))
        assert "review.plan_reviewer" not in kinds() and kinds()["review.deck_review_max_rounds"] == "要修正"
        toml.write_text(toml.read_text().replace("deck_review_max_rounds = true", "deck_review_max_rounds = 1"))
        assert "review.deck_review_max_rounds" not in kinds()
        assert "feedback.google_comments.watch_hours" not in kinds()  # 雛形の 0（見張らない）
        for v, ok in (('"48h"', False), ("-1", False), ("true", False), ("inf", False), ("nan", False), ("48", True), ("1.5", True), ("0", True)):
            toml.write_text(re.sub(r"(?m)^watch_hours = .*$", f"watch_hours = {v}", toml.read_text(), count=1))
            assert ("feedback.google_comments.watch_hours" not in kinds()) == ok, v
        with contextlib.redirect_stdout(io.StringIO()):
            assert main([tmp, "--local"]) == (0 if shutil.which("uv") else 1)
        cwd, saved = os.getcwd(), gapi.request
        gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else {"name": "x"}
        try:
            assert ("OK", "Google の認証", "me") in check(Path(tmp))
            (Path(tmp) / "w").mkdir()  # 外で回して ~/.desk.toml の w を出したら、gapi も同じものを読む（w から探し直すと、上の desk.toml を読む）
            Path(tmp, "u.toml").write_text(f'workspace = "{Path(tmp, "w")}"\n')
            os.environ["DESK_CONFIG"] = str(Path(tmp, "u.toml"))
            assert next(d for _, n, d in check(Path("/")) if n == "設定") == str(Path(tmp, "u.toml")) and gapi.config_path() == Path(tmp, "u.toml")
            os.environ["DESK_CONFIG"] = ""
        finally:
            gapi.request = saved
            os.chdir(cwd)
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
