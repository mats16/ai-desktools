#!/usr/bin/env python3
"""usage: slides_doctor.py [<ワークスペース>] [--local] [--own]   （--selftest で自己確認）
スライドを組む前提を確かめる: [brand] の著作権表示と社名、ワークスペースのテーマのファイル（themes/slides/<名前>.json）、[slides] のテーマとテンプレート、
共有テーマのフォルダ。--local は手元だけ見て、Google の API を呼ばない。desk-init の doctor.md から、ほかの前提と一緒に回す（2026-11-02 に doctor.py から分けた）。
1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。"""
import contextlib, io, json, os, sys, tempfile, tomllib
from pathlib import Path

sys.dont_write_bytecode = True
import desk, doctor, gapi, slides  # noqa: E402
from brand import copyright_problem  # noqa: E402  著作権表示の確かめ（docs_doctor.py と同じ）


def check(ws, local=False, own=False):
    """(区分, 項目, 詳しく) の並び。区分は OK・要修正・要確認。own が偽なら、desk-init の doctor.py（写し）の行から始める。"""
    out = [] if own else doctor.check(ws, local)  # desk-init の doctor.py と同じ前提（設定・道具・Google の認証・Drive）。このスキルだけを入れても足りる。--own は desk-init の doctor.py が先に出したとき
    ok = lambda name, detail="": out.append(("OK", name, detail))
    ng = lambda name, detail: out.append(("要修正", name, detail))
    warn = lambda name, detail: out.append(("要確認", name, detail))
    try:
        found = desk.locate(ws)
    except SystemExit:  # 設定の見つからなさ・読めなさは doctor.check（か、先に回した desk-init の doctor.py）が出す
        return out
    if not found:
        return out
    conf, root = found
    try:
        cfg = tomllib.loads(conf.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):  # 読めないことは doctor.check が出す
        return out
    sl, dr = cfg.get("slides", {}), cfg.get("drive", {})
    brand = cfg.get("brand", {})
    marks = [("brand.copyright", brand.get("copyright", ""))]  # テーマの copyright は、そのテーマのデッキで [brand] の代わりに書く（slides.py の use_theme）
    mine = {}  # ワークスペースのテーマのファイル（themes/slides/<名前>.json）。組むときに止まる値（形・色・copyright・書体）を、組む前に出す（slides.py と同じ read_theme で見る）
    for f in sorted(root.joinpath(*slides.WS_THEMES).glob("*.json")):
        try:
            mine[f.stem] = slides.read_theme(f)
        except SystemExit as e:
            ng(f"themes/slides/{f.name}", str(e).replace(f"{f}: ", ""))
    marks += [(f"themes/slides/{n}.json の copyright", t["copyright"]) for n, t in mine.items() if "copyright" in t]
    for key, c in marks:
        if bad := copyright_problem(c):
            ng(key, bad[1])
    if not brand.get("company"):
        warn("brand.company", "空。表紙の左下に社名を置かない")
    files = {**{f.stem: t for f in slides.BUILTIN_THEMES.glob("*.json") for t in [slides.read_theme(f)]}, **mine}  # ワークスペースのものが勝つ
    theme, temps = sl.get("default_theme", "navy"), {k: v for k, v in sl.get("templates", {}).items() if v}
    if old := sl.get("themes"):  # 2026-10-16 までの書き方
        ng("slides.themes", f"{', '.join(old)} はプラグインが読まない。テーマはワークスペースの themes/slides/<名前>.json（kind theme。色は colors の下に同じ名前で書く）に、"
                            "テンプレートの url は [slides.templates] の「<名前> = \"<url>\"」に移して消す（テンプレートのある名前は slides.py theme <url> でも写せる。build-slides の themes.md）")
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
    if local:
        return out
    gapi.find_config = lambda: (conf, root)
    if any(k == "要修正" and (n == "Google の認証" or n.startswith("uc_connections")) for k, n, _ in out):  # 通らない認証では、テンプレートを開けるかは見ない
        return out
    if own:  # 認証の行は desk-init の doctor.py が出した。通らなければ、テンプレートごとに同じ断りを重ねない
        try:
            gapi.request("GET", f"{gapi.DRIVE}/about?fields=user(emailAddress)")
        except Exception:  # 回線のエラー・形の違う返事も
            return out
    for name, url in [(f"slides.templates.{k}", v) for k, v in temps.items()]:
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{gapi.file_id(url)}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except Exception as e:  # 回線のエラーや proxy の断り・形の違う返事も。行ごとに知らせ、ほかの行を落とさない
            w = (str(e) or type(e).__name__).split()[0]
            ng(name, f"開けない（{w}）: {url}" if w[:3].isdigit() else f"開けない: {url}。{doctor.proxy_fail(e)}")  # HTTP のほか（proxy の断り・回線）は、確かめることを添える（doctor.py と同じ）
    if dr.get("shared_themes"):  # 全社の共有テーマのフォルダ。探すときだけ読む（使うテーマは slides.py theme <url> で写す）
        try:
            shared, have = slides.shared_files(), {gapi.file_id(u) for u in temps.values()}  # 自分の Themes は読まない（slides.py themes が出す）
            names, new = [f["properties"][slides.THEME_PROP] for f in shared], [f["properties"][slides.THEME_PROP] for f in shared if f["id"] not in have]
            bare = 0 if names else len(slides.theme_files(gapi.folder_id(dr["shared_themes"]), named=False))  # 名前のあるものが 1 つでもあれば数えない（base の写しのように、名前がなくて正しいものもある）
        except slides.READ_ERRORS:  # 開けないことは desk-init の doctor.py の drive.shared_themes に出る
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
    local, own = "--local" in args, "--own" in args
    rest = [a for a in args if a not in ("--local", "--own")]
    rows = check(Path(rest[0] if rest else ".").expanduser().resolve(), local, own)
    for kind, name, detail in rows:
        print(f"{kind}\t{name}\t{detail}")
    n = sum(k == "要修正" for k, _, _ in rows)
    print(f"\n要修正 {n}・要確認 {sum(k == '要確認' for k, _, _ in rows)}" + ("（--local: Google の API は見ていない）" if local else ""))
    return 1 if n else 0


BASE = '[slides]\ndefault_theme = "navy"\n\n[brand]\n\n[slides.templates]\n\n[drive]\nshared_themes = ""\n'


def selftest():
    os.environ["DESK_CONFIG"] = ""  # 手元の ~/.desk.toml に左右されない
    with tempfile.TemporaryDirectory() as tmp:
        kinds = lambda: {n: k for k, n, _ in check(Path(tmp), local=True, own=True)}
        assert kinds() == {} and ("要修正", "desk.toml") in {(k, n) for k, n, _ in check(Path(tmp), local=True)}  # --own でなければ、desk-init の doctor.py と同じ前提も出す（このスキルだけを入れても足りる）
        Path(tmp, "desk.toml").write_text("[slides\n")
        assert kinds() == {} and "desk.toml の書き方" in {n for _, n, _ in check(Path(tmp), local=True)}
        toml = Path(tmp) / "desk.toml"
        toml.write_text(BASE)
        assert kinds()["brand.copyright"] == "要修正" and kinds()["brand.company"] == "要確認" and kinds()["slides.templates"] == "要確認"
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
        assert kinds()["themes/slides/mine.json"] == "要修正" and "themes/slides/mine.json の copyright" not in kinds()  # 6 桁でない色
        put("mine", {"copyright": 2026})
        assert kinds()["themes/slides/mine.json"] == "要修正" and "themes/slides/mine.json の copyright" not in kinds()  # 文字列でない copyright は 1 回だけ出す
        put("mine", {})
        assert "themes/slides/mine.json" not in kinds() and "slides.themes" not in kinds()
        toml.write_text(toml.read_text().replace("\n[slides.templates]", '\n[slides.templates]\nmine = "x"\nacme = "y"', 1))
        k = kinds()
        assert k["テーマのファイル"] == "要修正" and "acme" in next(d for _, n, d in check(Path(tmp), local=True, own=True) if n == "テーマのファイル")  # テンプレートだけで、テーマのファイルがない
        assert k["テーマの説明"] == "要確認"  # mine に description がない
        put("mine", {"description": "自分の"})
        toml.write_text(toml.read_text().replace('mine = "x"\nacme = "y"', 'mine = "x"', 1))
        assert "テーマのファイル" not in kinds() and "テーマの説明" not in kinds()
        toml.write_text(toml.read_text() + '\n[slides.themes.visual]\nurl = "x"\n')
        assert kinds()["slides.themes"] == "要修正"  # 2026-10-16 までの書き方
        toml.write_text(toml.read_text().replace('\n[slides.themes.visual]\nurl = "x"\n', ""))
        assert "slides の base" not in kinds() and "slides.default_theme" not in kinds()  # 既定の navy は組み込み
        toml.write_text(toml.read_text().replace('default_theme = "navy"', 'default_theme = "nope"\nbase_template = ""', 1))
        assert kinds()["slides の base"] == "要修正" and kinds()["slides.default_theme"] == "要修正"  # 2026-10-14 までの書き方（空でも消す）、ファイルのない既定のテーマ
        toml.write_text(toml.read_text().replace('default_theme = "nope"\nbase_template = ""', 'default_theme = "navy"', 1))
        with contextlib.redirect_stdout(io.StringIO()):
            assert main([tmp, "--local", "--own"]) == 0
        toml.write_text(toml.read_text().replace('shared_themes = ""', 'shared_themes = "shared"'))
        saved = (gapi.request, slides.shared_files, slides.theme_files)
        gapi.request = lambda method, url, *a, **k: (_ for _ in ()).throw(gapi.ApiError("401 GET about"))
        rows = check(Path(tmp))
        assert ("要修正", "Google の認証") in {(k, n) for k, n, _ in rows} and "slides.templates.mine" not in {n for _, n, _ in rows}
        assert not [r for r in check(Path(tmp), own=True) if r[1].startswith("slides.templates.")]  # --own でも、通らない認証ではテンプレートを開かない  # 認証が通らなければ、開けるかは見ない
        gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else {"name": "x"}
        shared = lambda: next(d for _, n, d in check(Path(tmp), own=True) if n == "共有テーマ")

        def unreadable(folder, named=True):
            raise gapi.ApiError("404")
        try:
            assert ("OK", "slides.templates.mine", "x") in check(Path(tmp), own=True)  # テンプレートを開ける
            slides.shared_files, slides.theme_files = lambda: [], lambda folder, named=True: [{"id": "a"}, {"id": "b"}]
            assert "2 個あるが" in shared()  # 名前のない Slides だけ
            slides.theme_files = lambda folder, named=True: []
            assert shared().startswith("テーマがない")
            slides.shared_files = lambda: [{"id": "a", "properties": {slides.THEME_PROP: "acme"}}]
            slides.theme_files = lambda folder, named=True: 1 / 0  # 名前のあるものがあれば、もう 1 回は読まない
            assert shared().startswith("acme")
            slides.shared_files, slides.theme_files = lambda: [], unreadable
            assert "共有テーマ" not in {n for _, n, _ in check(Path(tmp), own=True)}  # 読めなければ出さない（止まらない）
        finally:
            gapi.request, slides.shared_files, slides.theme_files = saved
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
