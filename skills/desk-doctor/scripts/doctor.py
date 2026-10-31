#!/usr/bin/env python3
"""usage: doctor.py [<ワークスペース>] [--local]   （--selftest で自己確認）
AI Desk Tools を動かす前提を確かめる。--local は手元だけ見て、Google の API を呼ばない。
1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。標準ライブラリだけ。"""
import io, contextlib, json, math, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]  # プラグインの skills/
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILLS.parent / "lib"))
sys.path.insert(0, str(SKILLS / "slides-build" / "scripts"))
sys.path.insert(0, str(SKILLS / "docs-build" / "scripts"))
sys.path.insert(0, str(SKILLS / "desk-migrate" / "scripts"))
import desk  # noqa: E402  ワークスペースと設定のファイルの探し方
import migrate  # noqa: E402  前のバージョンのワークスペースか（desk-migrate）


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
        if old := migrate.workspace(ws):  # factory.toml だけがある、2026-10-25 より前のワークスペース
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
        cfg = tomllib.loads(conf.read_text())
    except tomllib.TOMLDecodeError as e:
        ng(f"{conf.name} の書き方", str(e))
        return out
    for name in ("references_index.md", "drive_folders.md"):
        (ok if (root / name).is_file() else warn)(name, "" if (root / name).is_file() else "ない。desk-init で置く")
    if old := sorted((root / "Customers").glob("*/CLAUDE.md")):
        how = lambda p: f"{p.relative_to(root)}（{'memory.md に中身を移して消す' if (p.parent / 'memory.md').exists() else 'memory.md に名前を変える'}）"
        warn("顧客の memory", f"前の形の CLAUDE.md がある。Claude Code しか読まない（hook が Claude Code・Codex・pi で続けて出すのは memory.md）: {', '.join(map(how, old))}")
    if desk.old_agents(root):  # 持ち主が書いた AGENTS.md・CLAUDE.md には何も言わない
        warn("前の雛形の AGENTS.md", "AGENTS.md が、2026-10-31 までの desk-init が置いた雛形の写しに見える（その節の見出しが半分より多く同じ）。写しなら、プラグインはもう決まりを戻さない。"
             "エージェントはどの会話にもスキルより強く読み込むので、資料を作らない作業にも効く。ワークスペースだけの決まりはレシピに移し、プラグインのスキルにある文は消す"
             "（desk-migrate の SKILL.md の「Move an AGENTS.md from the old template」）")
    if old := migrate.needs(root):  # 前の名前の rules/ は読まれず、前の ID は台帳とつながらない
        ng("前のバージョンのワークスペース", f"desk-migrate で今のバージョンへ移す（2026-10-24 にスキルの名前・ファイルの分け方・決まりの ID を、2026-10-25 に設定と記録と管理のスキルの名前を変え、2026-10-27 に決まりのファイルの先頭に frontmatter を置き、ワークスペースの決まりの ID を外し、2026-10-29 に rules/ を recipes/<名前>/RECIPE.md にし、source-scout を desk-crawl にし、索引の references_index.md を台帳から作るものにした）: {', '.join(old[:5])}" + (f" ほか {len(old) - 5} 件" if len(old) > 5 else ""))
    odd, top = [], root / desk.RECIPES  # レシピの形と frontmatter（desk-feedback/routing.md の「Workspace rules」）
    for p, m in (rules := desk.rules(root)):
        rel = p.relative_to(root)
        if "paths" in m:
            odd.append(f"{rel} に paths がある（前のバージョンの書き方で、hook は読まない。材料を集めるときなら step: gather、組むときなら step: build、資料を作るどの作業でもなら書かない）")
        if m.get("step", "") not in ("", *desk.STEPS):
            odd.append(f"{rel} の step の {m['step']}（{'・'.join(desk.STEPS)} のどれか。資料を作るどの作業でも出すなら書かない）")
        if desk.kind(m) == "material" and m.get("step"):
            odd.append(f"{rel} に per_material と step の両方がある（資料ごとに選ぶレシピは、構成案を開いたときだけ出る。step は効かない）")
        odd += [f"{rel} の {k} の {v}（{'・'.join(vals)} のどれか）" for k, vals in (("targets", desk.TARGETS), ("audience", desk.AUDIENCES)) for v in desk.listed(m, k) if v not in vals]
        if (n := len(p.read_text(encoding="utf-8"))) > desk.RULE_MAX:
            odd.append(f"{rel} が {n:,} 字（{desk.RULE_MAX:,} 字まで。memory と並ぶと hook が途中で切るので、もっと狭い目的のレシピに分ける）")
        if skill := next((x for x in p.relative_to(top).parts[:-1] if (SKILLS / x / "SKILL.md").is_file()), None):
            odd.append(f"{rel} がスキルの名前のフォルダ（{skill}）にある（目的の名前にする。desk-feedback の recipes.md の §2）")
        if p.parent != top and (p.parent.parent / desk.RECIPE).is_file():
            odd.append(f"{rel} がほかのレシピのフォルダの中にある（hook は両方を別々のレシピとして出す。資源なら RECIPE.md の名前を替える）")
    have = {p for p, _ in rules}
    for p in sorted(top.rglob("*.md")) if top.is_dir() else []:  # 決まりとして出ないもの: レシピのフォルダの外の .md と、description のない RECIPE.md
        rel = p.relative_to(root)
        inside = any((d / desk.RECIPE).is_file() for d in p.parents if d.is_relative_to(top) and d != top)
        if p.name == desk.RECIPE and p.parent != top and p not in have and "templates" not in p.relative_to(top).parts[1:]:
            odd.append(f"{rel} の先頭に frontmatter の description がない（ないと hook が出さない）")
        elif not inside and p != top / "README.md" and "templates" not in p.relative_to(top).parts[1:]:
            odd.append(f"{rel} はレシピでない（決まりは recipes/<名前>/RECIPE.md に書く。hook は出さない）")
    (warn if odd else ok)("ワークスペースの決まり", "、".join(odd) if odd else f"レシピ {len(rules)} 個")
    if cfg.get("desk", {}).get("source"):  # 2026-10-14 まで、desk-kaizen が worktree を作る checkout（前の [factory] source。desk-migrate が [desk] にする）
        warn("desk.source", "使わなくなった（desk-kaizen は .desk/kaizen/ に自分で clone する）。desk.toml から消す")
    names = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    found = {}  # 実体ごとに 1 回（.claude/skills は .agents/skills へのリンクのことが多い）
    for d in (".agents/skills", ".claude/skills"):
        for name in names:
            if (root / d / name / "SKILL.md").is_file():
                found.setdefault((root / d / name).resolve(), f"{d}/{name}")
    dup = list(found.values())
    (warn if dup else ok)("スキルの重なり", f"ワークスペースにも同じ名前のスキルがある（プラグインと二重に読まれる）: {', '.join(dup)}" if dup else "")
    g, sl, dr = cfg.get("google", {}), cfg.get("slides", {}), cfg.get("drive", {})
    if not g.get("quota_project"):
        warn("google.quota_project", "空。gcloud の既定の OAuth クライアントで取ったトークンなら、Slides・Docs が 403 になる")
    from brand import COPYRIGHT_FOOTER  # 9pt で通す著作権表示の形（slides.py が全ページに書く）
    import slides  # 仮の著作権表示（PLACEHOLDER_COPYRIGHT。need_brand と同じ）と、テーマのファイルの読み方（read_theme）
    brand = cfg.get("brand", {})
    marks = [("brand.copyright", brand.get("copyright", ""))]  # テーマの copyright は、そのテーマのデッキで [brand] の代わりに書く（slides.py の use_theme）
    mine = {}  # ワークスペースのテーマのファイル（themes/slides/<名前>.json）。組むときに止まる値（形・色・copyright・書体）を、組む前に出す（slides.py と同じ read_theme で見る）
    for f in sorted(root.joinpath(*slides.WS_THEMES).glob("*.json")):
        try:
            mine[f.stem] = slides.read_theme(f)
        except SystemExit as e:
            ng(f"themes/slides/{f.name}", str(e).replace(f"{f}: ", ""))
    marks += [(f"themes/slides/{n}.json の copyright", t["copyright"]) for n, t in mine.items() if "copyright" in t]
    import docs as docs_py  # ドキュメントのテーマのファイル（themes/docs/<名前>.json）も、docs.py と同じ read_theme で見る
    doc_themes = {}
    for f in sorted(root.joinpath(*docs_py.WS_THEMES).glob("*.json")):
        try:
            doc_themes[f.stem] = docs_py.read_theme(f)
        except SystemExit as e:
            ng(f"themes/docs/{f.name}", str(e).replace(f"{f}: ", ""))
    for key, c in marks:
        if not (c := str(c).strip()):
            ng(key, "空。スライドもドキュメントも組めない（全ページの左下に書く著作権表示がない）。自分の会社の著作権表示を書く")
        elif c == slides.PLACEHOLDER_COPYRIGHT:
            ng(key, f"「{c}」は書いていないときの仮の値。スライドもドキュメントも組めない。自分の会社の著作権表示を書く")
        elif not COPYRIGHT_FOOTER.fullmatch(c):
            ng(key, f"「{c}」は「© <年> <社名> All rights reserved.」の形でない。lint が全ページの著作権表示を「11pt 未満の文字」の要確認に出す")
    if not brand.get("company"):
        warn("brand.company", "空。表紙の左下に社名を置かない")
    docs = cfg.get("docs", {})
    files = {**{f.stem: t for f in slides.BUILTIN_THEMES.glob("*.json") for t in [slides.read_theme(f)]}, **mine}  # ワークスペースのものが勝つ
    theme, temps = sl.get("default_theme", "navy"), {k: v for k, v in sl.get("templates", {}).items() if v}
    if old := sl.get("themes"):  # 2026-10-16 までの書き方
        ng("slides.themes", f"{', '.join(old)} はプラグインが読まない。テーマはワークスペースの themes/slides/<名前>.json（kind theme。色は colors の下に同じ名前で書く）に、"
                            "テンプレートの url は [slides.templates] の「<名前> = \"<url>\"」に移して消す（テンプレートのある名前は slides.py theme <url> でも写せる。../../slides-build/themes.md）")
    if "base_template" in sl:  # 2026-10-14 までの書き方
        ng("slides の base", "slides.base_template を消す。元のテンプレートは desk.toml に持たず、template.py <テーマ> --from-base <元の URL> で渡す（渡さなければ白紙の pptx から作る）")
    if sl.get("template_folder"):  # 2026-10-12 までの書き方
        warn("slides.template_folder", "プラグインは読まない。新しく作るテンプレートは [drive] desk の下の Themes に作る（前のバージョンのスクリプトで動かさなくなったら消す）")
    (ok if temps.get(theme) else warn)("slides.templates", ", ".join(temps) if temps.get(theme) else
                                       f"既定のテーマ {theme} のテンプレートがない。template.py {theme} --from-base で作るか、共有のテーマ（slides.py themes）を slides.py theme <url> で写す")
    if bare := [n for n in temps if n not in files]:
        ng("テーマのファイル", f"{', '.join(bare)} のテンプレートはあるが、themes/slides/<名前>.json がない。組めない。slides.py theme <[slides.templates] の URL> で写す")
    if theme not in files:
        ng("slides.default_theme", f"{theme} のテーマのファイルがない（themes/slides/{theme}.json）。テーマを書かない資料が組めない")
    if no_desc := [n for n in temps if n in files and not files[n].get("description")]:
        warn("テーマの説明", f"{', '.join(no_desc)} に description がない。エージェントが資料ごとにテーマを選べない（themes/slides/<名前>.json の description に、どの資料・聞き手に使うかを書く）")
    if old := docs.get("themes"):  # 2026-10-19 までの書き方
        ng("docs.themes", f"{', '.join(old)} はプラグインが読まない。ワークスペースの themes/docs/<名前>.json（kind theme。見出しの大きさは styles、色は colors）に移して消す"
                          "（../../docs-build/SKILL.md を開いてから、その themes.md の docs-write-010）")
    if bad := [n for n, t in doc_themes.items() if not t.get("description")]:
        warn("ドキュメントのテーマの説明", f"{', '.join(bad)} に description がない。エージェントが資料ごとにテーマを選べない（themes/docs/<名前>.json の description に書く）")
    if (d := docs.get("default_theme")) and d not in doc_themes and d != "standard":  # standard は組み込み（docs.py の STANDARD）
        ng("docs.default_theme", f"{d} のテーマのファイルがない（themes/docs/{d}.json）。theme を書かない doc.md が組めない")
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
    if local:
        return out

    import gapi
    gapi.find_config = lambda: (conf, root)  # gapi も、ここで見つけて出した設定を読む（ワークスペースから探し直すと、上に desk.toml があるときに別のものを読む）
    try:
        who = gapi.request("GET", f"{gapi.DRIVE}/about?fields=user(emailAddress)")["user"]["emailAddress"]
        ok("Google の認証", who)
    except gapi.ApiError as e:
        how = "GOOGLE_OAUTH_ACCESS_TOKEN" if os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") else str(gapi.credentials_path())  # gapi.token() と同じ順
        first = str(e).splitlines()[0]
        fix = "google.quota_project を書く（空だと gcloud の既定の OAuth クライアントのトークンは 403）" if first.startswith("403") and not g.get("quota_project") else f"作り直す: {gapi.LOGIN}"
        ng("Google の認証", f"{how} で通らない: {first}。{fix}")
        return out
    targets = [(f"slides.templates.{k}", v) for k, v in temps.items()] + [(f"docs.templates.{k}", v) for k, v in cfg.get("docs", {}).get("templates", {}).items()]
    targets += [(f"drive.{k}", v) for k, v in dr.items() if v]
    for name, url in targets:
        fid = gapi.folder_id(url) if "/folders/" in url else gapi.file_id(url)
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{fid}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except gapi.ApiError as e:
            ng(name, f"開けない（{str(e).split()[0]}）: {url}")
    if dr.get("shared_themes"):  # 全社の共有テーマのフォルダ。探すときだけ読む（使うテーマは slides.py theme <url> で写す）
        try:
            files, have = slides.shared_files(), {gapi.file_id(u) for u in temps.values()}  # 自分の Themes は読まない（slides.py themes が出す）
            names, new = [f["properties"][slides.THEME_PROP] for f in files], [f["properties"][slides.THEME_PROP] for f in files if f["id"] not in have]
            bare = 0 if names else len(slides.theme_files(gapi.folder_id(dr["shared_themes"]), named=False))  # 名前のあるものが 1 つでもあれば数えない（base の写しのように、名前がなくて正しいものもある）
        except slides.READ_ERRORS:  # 開けないことは drive.shared_themes に出ている
            return out
        if dup := sorted({n for n in names if names.count(n) > 1}):
            warn("共有テーマ", f"同じ名前のテーマが 2 つ以上ある（どれを写すか迷う。古いほうをフォルダから外す）: {', '.join(dup)}")
        elif bare:  # テーマの名前を書く前（2026-10-14 より前）の template.py で作ったもの
            warn("共有テーマ", f"Google Slides が {bare} 個あるが、どれにもテーマの名前（{slides.THEME_PROP}）がない。持ち主が template.py <テーマ> で合わせ直すと書かれる")
        elif not names:
            warn("共有テーマ", "テーマがない。管理者が template.py で作ったテンプレートを置く（ほかのファイルは読まない）")
        else:
            ok("共有テーマ", ", ".join(names) + (f"（[slides.templates] にない: {', '.join(new)}。使うなら slides.py theme <url> で写す）" if new else ""))
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


def selftest():
    with tempfile.TemporaryDirectory() as tmp:  # ~/.desk.toml の workspace を使う。ワークスペースにも desk.toml があれば要確認
        ws, conf = Path(tmp, "Documents").resolve(), Path(tmp, "home", ".desk.toml")
        os.environ["DESK_CONFIG"] = str(conf)
        rows = lambda at: {n: (k, d) for k, n, d in check(at, local=True)}
        assert rows(Path(tmp))["desk.toml"][0] == "要修正"  # どちらもない
        subprocess.run([sys.executable, str(SKILLS / "desk-init" / "scripts" / "init.py"), str(ws), "--user"], check=True, capture_output=True)
        r = rows(Path(tmp))  # ワークスペースの外で回しても
        assert r["設定"] == ("OK", str(conf)) and r["ワークスペース"] == ("OK", str(ws)) and "設定が 2 つ" not in r and "AGENTS.md" not in r and not (ws / "AGENTS.md").exists()
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
        subprocess.run([sys.executable, str(SKILLS / "desk-init" / "scripts" / "init.py"), tmp], check=True, capture_output=True)
        (Path(tmp) / ".agents" / "skills" / "slides-build").mkdir(parents=True)
        (Path(tmp) / ".agents" / "skills" / "slides-build" / "SKILL.md").write_text("x")
        k = kinds()
        assert k["スキルの重なり"] == "要確認" and k["slides.templates"] == "要確認" and k["drive.customers"] == "要確認"
        (Path(tmp) / "Customers" / "acme").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").write_text("x")
        assert kinds()["顧客の memory"] == "要確認"
        (Path(tmp) / "Customers" / "acme" / "memory.md").write_text("y")
        assert "中身を移して消す" in next(d for _, n, d in check(Path(tmp), local=True) if n == "顧客の memory")  # 名前を変えると memory.md を上書きする
        (Path(tmp) / "Customers" / "acme" / "memory.md").unlink()
        (Path(tmp) / "Customers" / "acme" / "CLAUDE.md").rename(Path(tmp) / "Customers" / "acme" / "memory.md")
        assert "顧客の memory" not in kinds()
        agents = Path(tmp) / "AGENTS.md"
        assert "前の雛形の AGENTS.md" not in kinds() and "前のバージョンのワークスペース" not in kinds()  # 今の雛形は AGENTS.md を置かない
        (Path(tmp) / "rules" / "deck-build").mkdir(parents=True)
        (Path(tmp) / "rules" / "deck-build" / "checks.py").write_text("x")
        assert kinds()["前のバージョンのワークスペース"] == "要修正"  # 前のバージョンの rules/ が残っている
        shutil.rmtree(Path(tmp) / "rules")
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
        (Path(tmp) / "recipes" / "slides-build" / "y").mkdir(parents=True)
        (Path(tmp) / "recipes" / "slides-build" / "y" / "RECIPE.md").write_text("---\ndescription: y\n---\n")
        (Path(tmp) / "recipes" / "z").mkdir()
        (Path(tmp) / "recipes" / "z" / "RECIPE.md").write_text("- description がない\n")
        d = next(d for k, n, d in check(Path(tmp), local=True) if n == "ワークスペースの決まり")
        assert "recipes/loose.md はレシピでない" in d and "recipes/RECIPE.md はレシピでない" in d and "スキルの名前のフォルダ（slides-build）" in d and "recipes/z/RECIPE.md の先頭に frontmatter の description がない" in d, d
        shutil.rmtree(Path(tmp) / "recipes")
        agents.write_text("# 自分の決まり\n- 社内向けは敬体。\n")
        assert "前の雛形の AGENTS.md" not in kinds()  # 持ち主が書いたものには言わない
        agents.write_text("# 自分の決まり\n\n移したメモ: 前は「# このワークスペースの運用ルール」の下に「## 決まりの優先」があった。\n## 書き方\n- 敬体。\n")
        assert "前の雛形の AGENTS.md" not in kinds()  # 前の雛形の見出しを引いただけ・節が 1 つ同じだけでは言わない
        agents.write_text("# Documents の運用ルール\n" + "".join(f"\n## {h}\n\n- 前の雛形の文。\n" for h in desk.AGENTS_TEMPLATE[:5]))
        assert kinds()["前の雛形の AGENTS.md"] == "要確認"  # 頭の題を書き替えた写しも、節で見つける
        agents.unlink()
        toml = Path(tmp) / "desk.toml"
        assert kinds()["brand.copyright"] == "要修正" and kinds()["brand.company"] == "要確認"
        toml.write_text(toml.read_text().replace("[brand]", '[brand]\ncopyright = "© Acme 2026"', 1))
        assert kinds()["brand.copyright"] == "要修正"
        toml.write_text(toml.read_text().replace('"© Acme 2026"', '"© 2026 Example, Inc. All rights reserved."'))
        assert kinds()["brand.copyright"] == "要修正"  # 仮の値をそのまま書いた
        toml.write_text(toml.read_text().replace('"© 2026 Example, Inc. All rights reserved."', '"© 2026 Acme, Inc. All rights reserved."'))
        assert "brand.copyright" not in kinds()
        themes = Path(tmp, "themes", "slides")
        themes.mkdir(parents=True)
        put = lambda n, o: (themes / f"{n}.json").write_text(json.dumps({"apiVersion": "slides/v1", "kind": "theme", **o}))
        put("mine", {"copyright": "© Me 2026"})
        assert kinds()["themes/slides/mine.json の copyright"] == "要修正"  # テーマの copyright にも同じ確かめ
        put("mine", {"copyright": "© 2026 Me. All rights reserved.", "colors": {"TEXT": "red"}})
        dthemes = Path(tmp, "themes", "docs")
        dthemes.mkdir(parents=True)
        dput = lambda n, o: (dthemes / f"{n}.json").write_text(json.dumps({"apiVersion": "docs/v1", "kind": "theme", **o}))
        dput("us2", {"mono": "Fira Code"})
        assert kinds()["themes/slides/mine.json"] == "要修正" and kinds()["themes/docs/us2.json"] == "要修正"  # 6 桁でない色、リガチャの出る等幅
        (dthemes / "us2.json").unlink()
        assert "themes/slides/mine.json の copyright" not in kinds()
        put("mine", {"copyright": 2026})
        assert kinds()["themes/slides/mine.json"] == "要修正" and "themes/slides/mine.json の copyright" not in kinds()  # 文字列でない copyright は 1 回だけ出す
        put("mine", {})
        assert "themes/slides/mine.json" not in kinds() and "slides.themes" not in kinds()
        toml.write_text(toml.read_text().replace("\n[slides.templates]", '\n[slides.templates]\nmine = "x"\nacme = "y"', 1))
        k = kinds()
        assert k["テーマのファイル"] == "要修正" and "acme" in next(d for _, n, d in check(Path(tmp), local=True) if n == "テーマのファイル")  # テンプレートだけで、テーマのファイルがない
        assert k["テーマの説明"] == "要確認"  # mine に description がない
        put("mine", {"description": "自分の"})
        toml.write_text(toml.read_text().replace('mine = "x"\nacme = "y"', 'mine = "x"', 1))
        assert "テーマのファイル" not in kinds() and "テーマの説明" not in kinds()
        toml.write_text(toml.read_text() + '\n[slides.themes.visual]\nurl = "x"\n')
        assert kinds()["slides.themes"] == "要修正"  # 2026-10-16 までの書き方
        toml.write_text(toml.read_text().replace('\n[slides.themes.visual]\nurl = "x"\n', ""))
        assert "slides の base" not in kinds() and "slides.default_theme" not in kinds()  # 雛形には書いていない。既定の navy は組み込み
        toml.write_text(toml.read_text().replace('default_theme = "navy"', 'default_theme = "nope"\nbase_template = ""', 1))
        assert kinds()["slides の base"] == "要修正" and kinds()["slides.default_theme"] == "要修正"  # 2026-10-14 までの書き方（空でも消す）、ファイルのない既定のテーマ
        toml.write_text(toml.read_text().replace('default_theme = "nope"\nbase_template = ""', 'default_theme = "navy"', 1))
        toml.write_text(toml.read_text() + '\n[docs]\ndefault_theme = "acme"\n\n[docs.themes.us]\npage = [215.9, 279.4]\n')
        dput("us", {"page": [215.9, 279.4]})
        k = kinds()
        assert k["docs.default_theme"] == "要修正" and k["ドキュメントのテーマの説明"] == "要確認" and k["docs.themes"] == "要修正"  # 既定のテーマがない、説明がない、前の書き方
        toml.write_text(toml.read_text().replace("\n[docs.themes.us]\npage = [215.9, 279.4]\n", ""))
        toml.write_text(toml.read_text().replace('default_theme = "acme"', 'default_theme = "standard"'))
        assert "docs.default_theme" not in kinds()  # 組み込みの standard
        toml.write_text(toml.read_text().replace('default_theme = "standard"', 'default_theme = "us"'))
        dput("us", {"description": "米国向け", "page": [215.9, 279.4]})
        assert "docs.default_theme" not in kinds() and "ドキュメントのテーマの説明" not in kinds() and "docs.themes" not in kinds()
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
        toml.write_text(toml.read_text().replace('shared_themes = ""', 'shared_themes = "shared"'))
        import gapi, slides
        cwd, saved = os.getcwd(), (gapi.request, slides.shared_files, slides.theme_files)
        gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else {"name": "x"}
        shared = lambda: next(d for _, n, d in check(Path(tmp)) if n == "共有テーマ")

        def unreadable(folder, named=True):
            raise gapi.ApiError("404")
        try:
            slides.shared_files, slides.theme_files = lambda: [], lambda folder, named=True: [{"id": "a"}, {"id": "b"}]
            assert "2 個あるが" in shared()  # 名前のない Slides だけ
            slides.theme_files = lambda folder, named=True: []
            assert shared().startswith("テーマがない")
            slides.shared_files = lambda: [{"id": "a", "properties": {slides.THEME_PROP: "acme"}}]
            slides.theme_files = lambda folder, named=True: 1 / 0  # 名前のあるものがあれば、もう 1 回は読まない
            assert shared().startswith("acme")
            slides.shared_files, slides.theme_files = lambda: [], unreadable
            assert "共有テーマ" not in {n for _, n, _ in check(Path(tmp))}  # 読めなければ出さない（止まらない）
            (Path(tmp) / "w").mkdir()  # 外で回して ~/.desk.toml の w を出したら、gapi も同じものを読む（w から探し直すと、上の desk.toml を読む）
            Path(tmp, "u.toml").write_text(f'workspace = "{Path(tmp, "w")}"\n')
            os.environ["DESK_CONFIG"] = str(Path(tmp, "u.toml"))
            assert next(d for _, n, d in check(Path("/")) if n == "設定") == str(Path(tmp, "u.toml")) and gapi.config_path() == Path(tmp, "u.toml")
            os.environ["DESK_CONFIG"] = ""
        finally:
            gapi.request, slides.shared_files, slides.theme_files = saved
            os.chdir(cwd)
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
