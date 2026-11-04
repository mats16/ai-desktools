#!/usr/bin/env python3
"""usage: docs_doctor.py [<ワークスペース>] [--local] [--own]   （--selftest で自己確認）
ドキュメントを組む前提を確かめる: [brand] の著作権表示、ワークスペースのテーマのファイル（themes/docs/<名前>.json）、[docs] の既定のテーマとテンプレート。
--local は手元だけ見て、Google の API を呼ばない。desk-doctor の SKILL.md から、ほかの前提と一緒に回す（2026-11-02 に doctor.py から分けた）。
著作権表示はスライドと同じ確かめ（brand.copyright_problem）で、build-docs だけを入れても見る。1 行 1 項目で「OK」「要修正」「要確認」を出す。要修正が 1 つでもあれば exit 1。"""
import contextlib, io, json, os, sys, tempfile, tomllib
from pathlib import Path

sys.dont_write_bytecode = True
import desk, doctor, gapi  # noqa: E402
from brand import copyright_problem  # noqa: E402  著作権表示の確かめ（slides_doctor.py と同じ）
import docs as docs_py  # noqa: E402  テーマのファイルは docs.py と同じ read_theme で見る


def check(ws, local=False, own=False):
    """(区分, 項目, 詳しく) の並び。区分は OK・要修正・要確認。own が偽なら、desk-doctor の doctor.py（写し）の行から始める。"""
    out = [] if own else doctor.check(ws, local)  # desk-doctor と同じ前提（設定・道具・Google の認証・Drive）。このスキルだけを入れても足りる。--own は desk-doctor が先に出したとき
    ok = lambda name, detail="": out.append(("OK", name, detail))
    ng = lambda name, detail: out.append(("要修正", name, detail))
    warn = lambda name, detail: out.append(("要確認", name, detail))
    try:
        found = desk.locate(ws)
    except SystemExit:  # 設定の見つからなさ・読めなさは doctor.check（か、先に回した desk-doctor）が出す
        return out
    if not found:
        return out
    conf, root = found
    try:
        cfg = tomllib.loads(conf.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):  # 読めないことは doctor.check が出す
        return out
    if bad := copyright_problem(cfg.get("brand", {}).get("copyright", "")):  # ドキュメントも全ページのフッターに書く（brand.need_brand で組む前に止まる）
        ng("brand.copyright", bad[1])
    docs = cfg.get("docs", {})
    themes = {}
    for f in sorted(root.joinpath(*docs_py.WS_THEMES).glob("*.json")):
        try:
            themes[f.stem] = docs_py.read_theme(f)
        except SystemExit as e:
            ng(f"themes/docs/{f.name}", str(e).replace(f"{f}: ", ""))
    if old := docs.get("themes"):  # 2026-10-19 までの書き方
        ng("docs.themes", f"{', '.join(old)} はプラグインが読まない。ワークスペースの themes/docs/<名前>.json（kind theme。見出しの大きさは styles、色は colors）に移して消す"
                          "（build-docs の themes.md の docs-write-010）")
    if bad := [n for n, t in themes.items() if not t.get("description")]:
        warn("ドキュメントのテーマの説明", f"{', '.join(bad)} に description がない。エージェントが資料ごとにテーマを選べない（themes/docs/<名前>.json の description に書く）")
    if (d := docs.get("default_theme")) and d not in themes and d != "standard":  # standard は組み込み（docs.py の STANDARD）
        ng("docs.default_theme", f"{d} のテーマのファイルがない（themes/docs/{d}.json）。theme を書かない doc.md が組めない")
    if local:
        return out
    gapi.find_config = lambda: (conf, root)
    if any(k == "要修正" and (n == "Google の認証" or n.startswith("uc_connections")) for k, n, _ in out):  # 通らない認証では、テンプレートを開けるかは見ない
        return out
    if own:  # 認証の行は desk-doctor の doctor.py が出した。通らなければ、テンプレートごとに同じ断りを重ねない
        try:
            gapi.request("GET", f"{gapi.DRIVE}/about?fields=user(emailAddress)")
        except Exception:  # 回線のエラー・形の違う返事も
            return out
    for name, url in [(f"docs.templates.{k}", v) for k, v in docs.get("templates", {}).items() if v]:
        try:
            f = gapi.request("GET", f"{gapi.DRIVE}/files/{gapi.file_id(url)}?supportsAllDrives=true&fields=name,trashed")
            (warn if f.get("trashed") else ok)(name, f"{f['name']}{'（ゴミ箱にある）' if f.get('trashed') else ''}")
        except Exception as e:  # 回線のエラーや proxy の断り・形の違う返事も。行ごとに知らせ、ほかの行を落とさない
            w = (str(e) or type(e).__name__).split()[0]
            ng(name, f"開けない（{w}）: {url}" if w[:3].isdigit() else f"開けない: {url}。{doctor.proxy_fail(e)}")  # HTTP のほか（proxy の断り・回線）は、確かめることを添える（doctor.py と同じ）
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


def selftest():
    os.environ["DESK_CONFIG"] = ""  # 手元の ~/.desk.toml に左右されない
    with tempfile.TemporaryDirectory() as tmp:
        kinds = lambda: {n: k for k, n, _ in check(Path(tmp), local=True, own=True)}
        assert kinds() == {} and ("要修正", "desk.toml") in {(k, n) for k, n, _ in check(Path(tmp), local=True)}  # --own でなければ、desk-doctor と同じ前提も出す
        toml = Path(tmp) / "desk.toml"
        toml.write_text("[desk]\n")
        assert kinds() == {"brand.copyright": "要修正"}  # build-docs だけを入れても、組めない著作権表示を出す
        toml.write_text('[desk]\n\n[brand]\ncopyright = "© 2026 Acme, Inc. All rights reserved."\n')
        assert kinds() == {}
        dthemes = Path(tmp, "themes", "docs")
        dthemes.mkdir(parents=True)
        dput = lambda n, o: (dthemes / f"{n}.json").write_text(json.dumps({"apiVersion": "docs/v1", "kind": "theme", **o}))
        dput("us2", {"mono": "Fira Code"})
        assert kinds()["themes/docs/us2.json"] == "要修正"  # リガチャの出る等幅
        (dthemes / "us2.json").unlink()
        toml.write_text(toml.read_text() + '\n[docs]\ndefault_theme = "acme"\n\n[docs.themes.us]\npage = [215.9, 279.4]\n')
        dput("us", {"page": [215.9, 279.4]})
        k = kinds()
        assert k["docs.default_theme"] == "要修正" and k["ドキュメントのテーマの説明"] == "要確認" and k["docs.themes"] == "要修正"  # 既定のテーマがない、説明がない、前の書き方
        toml.write_text(toml.read_text().replace("\n[docs.themes.us]\npage = [215.9, 279.4]\n", ""))
        toml.write_text(toml.read_text().replace('default_theme = "acme"', 'default_theme = "standard"'))
        assert "docs.default_theme" not in kinds()  # 組み込みの standard
        toml.write_text(toml.read_text().replace('default_theme = "standard"', 'default_theme = "us"'))
        dput("us", {"description": "米国向け", "page": [215.9, 279.4]})
        assert kinds() == {}
        with contextlib.redirect_stdout(io.StringIO()):
            assert main([tmp, "--local", "--own"]) == 0
        toml.write_text(toml.read_text() + '\n[docs.templates]\nmemo = "https://docs.google.com/document/d/abc/edit"\n')
        saved = gapi.request
        try:
            gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else {"name": "memo", "trashed": True}
            assert ("要確認", "docs.templates.memo", "memo（ゴミ箱にある）") in check(Path(tmp), own=True)
            gapi.request = lambda method, url, *a, **k: {"user": {"emailAddress": "me"}} if "/about" in url else (_ for _ in ()).throw(gapi.ApiError("404 GET x"))
            assert ("要修正", "docs.templates.memo", "開けない（404）: https://docs.google.com/document/d/abc/edit") in check(Path(tmp), own=True)
        finally:
            gapi.request = saved
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
