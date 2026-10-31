#!/usr/bin/env python3
"""usage: init.py [<ワークスペース>] [--user]   （--selftest で自己確認）
ワークスペースに、決まり（recipes/。AGENTS.md・CLAUDE.md は置かない）、設定（desk.toml）、索引（references_index.md。refs.py が台帳から作り直す）と Drive の置き場所（drive_folders.md）の雛形と、資料のフォルダを置く。
--user: 設定はワークスペースに置かず、個人の設定（~/.desk.toml。DESK_CONFIG があればそのパス）に置き、頭の workspace にワークスペースを書く。
あるファイルは上書きしない（置いたもの・残したものを出す）。標準ライブラリだけ。ワークスペースを省くと、今いるフォルダ。"""
import os, sys, tempfile, tomllib
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
sys.path.insert(0, str(TEMPLATES.parents[2] / "lib"))
import desk  # noqa: E402  個人の設定の場所と、workspace の書き方
DIRS = ("Customers", "Internal", "Research", ".desk")  # 雛形のないフォルダ（雛形のある recipes/ は写すときにできる）


def init(ws, user=False):
    ws = Path(ws).expanduser().resolve()
    conf = desk.user_config() if user else None  # 設定を置く個人の設定のパス（--user のときだけ）
    if user:  # 個人の設定に置く。ファイルを置く前に、置けるかを決める
        if not conf:
            sys.exit("DESK_CONFIG が空。個人の設定に置くなら、DESK_CONFIG を外すか、置くパスにする")
        if f := desk.local(ws):  # 両方あると、中で開くか外で開くかで設定が変わる（上のフォルダの desk.toml も、中では勝つ）
            sys.exit(f"{f[0]} がある（{ws} の中で開くと、こちらを読む）。" + ("個人の設定に移すなら desk-migrate の to-user で移す" if f[1] == ws else "そのワークスペースの外のフォルダにする"))
        if o := desk.old(ws):  # 移す前のワークスペースを指すと、記録が .factory/ と .desk/ に分かれる
            sys.exit(f"{o} は前の版のワークスペース（factory.toml）。先に desk-migrate の apply で移し、そのあと to-user で個人の設定に移す")
        if (have := desk.user()) and have[1] != ws:  # 個人の設定は 1 つ（読めなければ、desk.user が止める）
            sys.exit(f"{conf} はもう {have[1]} を指している（個人の設定は 1 つ）。このフォルダを使うなら、{conf} の workspace を書き替えるか、--user を付けずにこのフォルダに desk.toml を置く")
    else:  # ワークスペースに置く。既定のワークスペースか、その上に置くと、中で開いたときにこちらが勝つ
        try:
            have = desk.pointed()  # まだないフォルダを指していても、そのパスで確かめる
        except SystemExit:  # 読めない個人の設定は、ここに desk.toml を置くのを止める理由にならない（desk-doctor が出す）
            have = None
        if have and have[1].is_relative_to(ws):
            sys.exit(f"{have[0]} の workspace（{have[1]}）が {ws} の中にある。ここに desk.toml を置くと、中で開いたときにこちらを読む（設定が 2 つ）。"
                     "そのワークスペースなら --user を付けて回す（足りないものだけ置く）")
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
            out.append(f"残した（もうある）: {dst}{note}")  # 個人の設定なら、上で同じワークスペースを指すと確かめてある
    return out


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp, "local")
        local.mkdir()
        (local / "drive_folders.md").write_text("mine")
        out = init(local)
        assert (local / "drive_folders.md").read_text() == "mine" and any("残した" in o and "drive_folders.md" in o for o in out)
        assert not (local / "AGENTS.md").exists() and not (local / "CLAUDE.md").exists()  # 置くかは持ち主が決める
        assert (local / "desk.toml").is_file() and (local / "recipes" / "README.md").is_file() and (local / "Customers").is_dir()
        assert all("残した" in o for o in init(local))  # 2 回目は何も上書きしない
        ws, conf = Path(tmp, "ws").resolve(), Path(tmp, "home", ".desk.toml")
        os.environ["DESK_CONFIG"] = str(conf)
        out = init(ws, user=True)  # 設定は個人の設定に置き、ワークスペースには置かない
        assert not (ws / "desk.toml").exists() and (ws / "recipes" / "README.md").is_file() and desk.locate(ws) == (conf, ws)
        assert f"置いた: {conf}（workspace = {ws}）" in out and tomllib.loads(conf.read_text())["slides"]["default_theme"] == "navy"
        assert f"残した（もうある）: {conf}（workspace = {ws}）" in init(ws, user=True)  # もうあれば上書きしない
        for at, points in ((ws, ws), (Path(tmp), ws), (Path(tmp, "later"), Path(tmp, "later", "Documents"))):  # --user なしで、既定のワークスペースか、その上に desk.toml を置かない（まだないフォルダを指していても）
            conf.write_text(f'workspace = "{points}"\n')
            try:
                init(at)
                raise AssertionError(at)
            except SystemExit as e:
                assert "--user" in str(e) and not (at / "desk.toml").exists(), e
        conf.write_text(desk.with_workspace("", ws))
        for at, text, msg in ((Path(tmp, "ws2"), None, "もう"), (ws, "workspace = \n", "読めない")):  # ほかのワークスペースを指す・読めない: 何も置かずに止める
            if text:
                conf.write_text(text)
            try:
                init(at, user=True)
                raise AssertionError(at)
            except SystemExit as e:
                assert msg in str(e) and not Path(tmp, "ws2").exists(), e
        (Path(tmp, "old") / "factory.toml").parent.mkdir()
        (Path(tmp, "old") / "factory.toml").write_text("")
        for at, msg in ((local, "to-user"), (local / "Customers" / "x", "外のフォルダ"), (Path(tmp, "old"), "desk-migrate")):  # ワークスペースか、その上に desk.toml がある、前の版のワークスペース
            try:
                init(at, user=True)
                raise AssertionError(at)
            except SystemExit as e:
                assert msg in str(e), e
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
