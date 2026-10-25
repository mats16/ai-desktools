#!/usr/bin/env python3
"""usage: init.py [<ワークスペース>] [--user]   （--selftest で自己確認）
ワークスペースに、決まり（AGENTS.md・CLAUDE.md・rules/）、設定（desk.toml）、索引（references_index.md）の雛形と、資料のフォルダを置く。
--user: 設定はワークスペースに置かず、個人の設定（~/.desk.toml。DESK_CONFIG があればそのパス）に置き、頭の workspace にワークスペースを書く。
あるファイルは上書きしない（置いたもの・残したものを出す）。標準ライブラリだけ。ワークスペースを省くと、今いるフォルダ。"""
import os, sys, tempfile, tomllib
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
sys.path.insert(0, str(TEMPLATES.parents[1] / "deck-practices" / "scripts"))
import desk  # noqa: E402  個人の設定の場所と、workspace の書き方
DIRS = ("Customers", "Internal", "Research", ".desk")  # 雛形のないフォルダ（雛形のある rules/ は写すときにできる）


def init(ws, user=False):
    ws = Path(ws).expanduser().resolve()
    conf = desk.user_config() if user else None  # 設定を置く個人の設定のパス（--user のときだけ）
    if user and not conf:
        sys.exit("DESK_CONFIG が空。個人の設定に置くなら、DESK_CONFIG を外すか、置くパスにする")
    if user and (ws / desk.NAME).is_file():  # 両方あると、中で開くか外で開くかで設定が変わる
        sys.exit(f"{ws} に desk.toml がある。個人の設定に移すなら desk-migrate の to-user で移す")
    out = []
    for d in DIRS:
        (ws / d).mkdir(parents=True, exist_ok=True)
    for t in sorted(p for p in TEMPLATES.rglob("*") if p.is_file()):
        dst, text, note = ws / t.relative_to(TEMPLATES), t.read_text(encoding="utf-8"), ""
        if conf and t == TEMPLATES / desk.NAME:
            dst, text, note = conf, desk.with_workspace(text, ws), f"（workspace = {ws}）"
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(dst, "x", encoding="utf-8") as f:  # "x": あれば上書きせずに止まる
                f.write(text)
            out.append(f"置いた: {dst}{note}")
        except FileExistsError:
            if note:  # もうある個人の設定が指すワークスペースを出す（ほかのワークスペースなら、ユーザーに伝える）
                note = f"（workspace = {tomllib.loads(dst.read_text(encoding='utf-8')).get('workspace')}）"
            out.append(f"残した（もうある）: {dst}{note}")
    return out


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp, "local")
        local.mkdir()
        (local / "AGENTS.md").write_text("mine")
        out = init(local)
        assert (local / "AGENTS.md").read_text() == "mine" and any("残した" in o and "AGENTS.md" in o for o in out)
        assert (local / "desk.toml").is_file() and (local / "rules" / "README.md").is_file() and (local / "Customers").is_dir()
        assert all("残した" in o for o in init(local))  # 2 回目は何も上書きしない
        ws, conf = Path(tmp, "ws").resolve(), Path(tmp, "home", ".desk.toml")
        os.environ["DESK_CONFIG"] = str(conf)
        out = init(ws, user=True)  # 設定は個人の設定に置き、ワークスペースには置かない
        assert not (ws / "desk.toml").exists() and (ws / "AGENTS.md").is_file() and desk.locate(ws) == (conf, ws)
        assert f"置いた: {conf}（workspace = {ws}）" in out and tomllib.loads(conf.read_text())["slides"]["default_theme"] == "visual"
        assert f"残した（もうある）: {conf}（workspace = {ws}）" in init(Path(tmp, "ws2"), user=True)  # もうあれば上書きしない（指すワークスペースを出す）
        try:
            init(local, user=True)  # ワークスペースに desk.toml がある
            raise AssertionError
        except SystemExit as e:
            assert "to-user" in str(e)
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    user = "--user" in a
    a = [x for x in a if x != "--user"]
    if len(a) > 1 or a and a[0].startswith("-"):  # 前の版の --source などを、フォルダの名前と取り違えない
        sys.exit(__doc__)
    print("\n".join(init(a[0] if a else ".", user)))
