#!/usr/bin/env python3
"""ワークスペースと設定のファイルの探し方。スキルのスクリプトと hooks/rules_overlay.py（pi の拡張も）が、ここだけで探す（標準ライブラリだけ）。
1. 今いるフォルダから上へ desk.toml を探す。見つかれば、そのフォルダがワークスペースで、その desk.toml だけを読む（workspace を書いても読まない）。
2. なければ個人の設定（DESK_CONFIG のパス、なければ ~/.desk.toml）を読み、その workspace をワークスペースにする（資料・rules/・.desk/ はそこに置く）。
3. どちらもなければ None（呼ぶ側が止めて desk-init を案内する）。
2 つを混ぜない（sandbox の desk.toml に書き忘れた [drive] が ~/.desk.toml から入ると、本番の Drive に書くため）。
DESK_CONFIG を空にすると 2 を飛ばす（selftest と開発の worktree。~/.desk.toml の本番のワークスペースに戻らない）。
usage: desk.py              ワークスペースのパスを出す（なければ exit 1）
       desk.py --selftest"""
import json, os, sys, tempfile, tomllib
from pathlib import Path

NAME = "desk.toml"


def user_config():
    """個人の設定のパス（DESK_CONFIG、なければ ~/.desk.toml）。DESK_CONFIG が空なら None。"""
    p = os.environ.get("DESK_CONFIG", "~/.desk.toml")
    return Path(p).expanduser() if p else None


def user():
    """(個人の設定のファイル, その workspace)。ファイルがなければ None。読めない・workspace がない・そのフォルダがないときは止める（黙ってほかへ移らない）。"""
    if not ((p := user_config()) and p.is_file()):
        return None
    try:
        w = tomllib.loads(p.read_text(encoding="utf-8")).get("workspace")
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"{p} の書き方: {e}")
    if not isinstance(w, str) or not w.strip():
        sys.exit(f'{p} に workspace（資料を置くフォルダ。例: workspace = "~/Documents"）がない。desk-init で書く')
    ws = (p.parent / Path(w).expanduser()).resolve()  # 相対のパスは設定のファイルのフォルダから
    if not ws.is_dir():
        sys.exit(f"{p} の workspace（{w}）のフォルダがない。作るか、正しいパスに直す")
    return p, ws


def locate(start="."):
    """(設定のファイル, ワークスペース)。なければ None。"""
    d = Path(start).resolve()
    if ws := next((x for x in (d, *d.parents) if (x / NAME).is_file()), None):
        return ws / NAME, ws
    return user()


def with_workspace(text, ws):
    """設定の文字列の、最初の表の前に workspace を足す（desk-init と desk-migrate が ~/.desk.toml を書くとき）。ホームの下は ~/ で書く。"""
    ws = Path(ws).resolve()
    home = Path.home().resolve()
    value = "~/" + ws.relative_to(home).as_posix() if ws.is_relative_to(home) else str(ws)
    line = f"workspace = {json.dumps(value, ensure_ascii=False)}  # 資料・rules/・.desk/ を置くフォルダ（ワークスペース。ここには desk.toml を置かない）\n\n"
    lines = text.splitlines(keepends=True)
    i = next((i for i, x in enumerate(lines) if x.lstrip().startswith("[")), len(lines))
    out = "".join(lines[:i]) + line + "".join(lines[i:])
    assert tomllib.loads(out)["workspace"] == value  # 書いたあとも読める
    return out


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        ws, sand, other, conf = tmp / "Documents", tmp / "Documents" / "sandbox", tmp / "elsewhere", tmp / "home" / ".desk.toml"
        for d in (sand / "sub", ws / "Customers", other, conf.parent):
            d.mkdir(parents=True)
        os.environ["DESK_CONFIG"] = str(conf)
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
        assert user() == (conf, ws)  # 相対のパスは設定のファイルのフォルダから
        for text, msg in (("[drive]\n", "workspace"), ('workspace = ""\n', "workspace"), ('workspace = "../nope"\n', "フォルダがない"), ("workspace = \n", "書き方")):
            conf.write_text(text)
            try:
                locate(other)
                raise AssertionError(text)
            except SystemExit as e:
                assert msg in str(e), (text, e)
        assert with_workspace("", Path.home() / "Documents").startswith('workspace = "~/Documents"') and with_workspace("", "/srv/w").startswith('workspace = "/srv/w"')
        t = with_workspace("# 頭のコメント\n[desk]\nprivate = []\n", "/srv/w")
        assert t.index("workspace") < t.index("[desk]") and t.startswith("# 頭のコメント\n") and tomllib.loads(t)["desk"] == {"private": []}
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    if not (f := locate()):
        sys.exit("desk.toml が見つからない（今いるフォルダから上へ探し、~/.desk.toml もない）。desk-init で作る")
    print(f[1])
