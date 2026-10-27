#!/usr/bin/env python3
"""ワークスペースと設定のファイルの探し方。スキルのスクリプトと hooks/rules_overlay.py（pi の拡張も）が、ここだけで探す（標準ライブラリだけ）。
1. 今いるフォルダから上へ desk.toml を探す。見つかれば、そのフォルダがワークスペースで、その desk.toml だけを読む（workspace を書いても読まない）。
2. なければ個人の設定（DESK_CONFIG のパス、なければ ~/.desk.toml）を読み、その workspace をワークスペースにする（資料・rules/・.desk/ はそこに置く）。
   上に前の版の factory.toml があれば、2 に進まない（移す前のワークスペースの中で、別のワークスペースに書かない）。workspace が前の版のワークスペースなら止める。
3. どちらもなければ None（呼ぶ側が止めて desk-init を案内する）。
2 つを混ぜない（sandbox の desk.toml に書き忘れた [drive] が ~/.desk.toml から入ると、本番の Drive に書くため）。
DESK_CONFIG を空にすると 2 を飛ばす（selftest と開発の worktree。~/.desk.toml の本番のワークスペースに戻らない）。
ワークスペースの決まりのファイル（rules/ の下の、frontmatter に description のある .md）の探し方も、ここに置く（rules・front）。
usage: desk.py              ワークスペースのパスを出す（なければ exit 1）
       desk.py --selftest"""
import json, os, sys, tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:  # hook と snapshot.sh は素の python3 で回る。上へたどって見つかるとき（1）は、TOML を読まないので 3.11 より前でも動かす
    tomllib = None

NAME, OLD = "desk.toml", "factory.toml"  # OLD は 2026-10-25 より前の設定の名前（desk-migrate で移す）
RULE_MAX = 3800  # 決まりの 1 ファイルの字数の上限。hook が memory と並べて出すとき、決まりに回す半分（4,499 字）から、入りきらないものを挙げる添え書き（NOTE の 500 字）と見出し（パスが 79 字までなら 199 字まで）を引いても、最初のファイルが丸ごと入る（deck-practices/rules.md の「Workspace rules」）
TARGETS, AUDIENCES = ("slides", "docs", "vids"), ("顧客向け", "社内向け", "コミュニティ向け")  # frontmatter の targets・audience の値（audience は deck-content-039 の資料の種類）


def loads(text, where):
    """TOML を読む。desk.py が TOML を読むのはここだけ。読めなければ止める（止めるのは SystemExit だけ。hook・import のときに読む brand.py・desk-doctor は、これだけを受けて続ける）。"""
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
    """(個人の設定のファイル, その workspace)。ファイルがなければ None。読めない・workspace がない・そのフォルダがない・前の版のワークスペースのときは止める（黙ってほかへ移らない）。"""
    if not (f := pointed()):
        return None
    p, ws = f
    if not ws.is_dir():
        sys.exit(f"{p} の workspace（{ws}）のフォルダがない。作るか、正しいパスに直す")
    if o := old(ws):  # 外から開いても、移す前のワークスペースに書かない（記録が .factory/ と .desk/ に分かれる）
        sys.exit(f"{p} の workspace（{ws}）は、前の版のワークスペース（{o}/factory.toml）。先に {o} で desk-migrate の apply を回し、"
                 f"できた desk.toml の値を {p} に寄せてから、その desk.toml を .desk/migrate/ に移す（desk-migrate の SKILL.md の「Move the settings to `~/.desk.toml`」の 2）")
    return f


def local(start="."):
    """start から上へたどって最初の desk.toml: (desk.toml, そのフォルダ)。なければ None。"""
    d = Path(start).resolve()
    ws = next((x for x in (d, *d.parents) if (x / NAME).is_file()), None)
    return (ws / NAME, ws) if ws else None


def old(start="."):
    """start から上へたどって最初の、前の版の factory.toml のフォルダ。なければ None。"""
    d = Path(start).resolve()
    return next((x for x in (d, *d.parents) if (x / OLD).is_file()), None)


def locate(start="."):
    """(設定のファイル, ワークスペース)。なければ None（言葉は missing）。上に前の版の factory.toml があるときも None にして 2 に進まない
    （移す前のワークスペースの中で、~/.desk.toml の別のワークスペースに書かない）。"""
    return local(start) or (None if old(start) else user())


def missing(start="."):
    """locate が None のときに止める言葉。前の版のワークスペースなら desk-migrate、なければ desk-init を案内する。"""
    if o := old(start):
        return f"{o} は前の版のワークスペース（factory.toml）。desk-migrate で desk.toml に移す"
    looked = f"{u} もない" if (u := user_config()) else "DESK_CONFIG が空なので、個人の設定は読まない"
    return f"desk.toml が見つからない（今いるフォルダから上へ探した。{looked}）。desk-init で作る（ワークスペースの直下の desk.toml か、~/.desk.toml）"


def front(text):
    """md の頭の frontmatter（--- の行の間の「key: value」）。値は 1 行の文字、[a, b] の並び、続く「  - a」の行の並び。閉じていない・ないときは {}。"""
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
            v = "" if v[:1] in ("|", ">", "#") else v  # 複数行の値（description: >）は読まない（値のないものとして、desk-doctor・gate が知らせる）。# から後ろはコメント
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


def rules(ws):
    """ワークスペースの決まりのファイル [(パス, frontmatter)]。rules/ の下の .md で、frontmatter に description のあるもの。
    frontmatter のない README.md と、docs-build のテンプレート（rules/docs-build/templates/<名前>/doc.md。templates/ の下）は入れない。"""
    root = Path(ws) / "rules"
    out = []
    for p in sorted(root.rglob("*.md")) if root.is_dir() else []:
        if "templates" in p.relative_to(root).parts[:-1] or not p.is_file():
            continue
        try:
            meta = front(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # 読めない、UTF-8 でない
            continue
        if described(meta):
            out.append((p, meta))
    return out


def with_workspace(text, ws):
    """設定の文字列の頭（頭のコメントのあと、最初の値か表の前）に workspace を足す（desk-init と desk-migrate が ~/.desk.toml を書くとき）。ホームの下は ~/ で書く。
    書けないときは止める（何も書かない）。"""
    if "workspace" in loads(text, "写す設定"):  # フォルダの desk.toml では読まない値。どちらを残すかは人が決める
        sys.exit("写す設定の頭に workspace がもうある（フォルダの desk.toml では読まない値）。その行を消してから回す")
    ws = Path(ws).resolve()
    home = Path.home().resolve()
    value = "~/" + ws.relative_to(home).as_posix() if ws.is_relative_to(home) else str(ws)
    line = f"workspace = {json.dumps(value, ensure_ascii=False)}  # 資料・rules/・.desk/ を置くフォルダ（ワークスペース。ここには desk.toml を置かない）\n\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):  # 最後の行に改行がなくても、続けて書かない
        lines[-1] += "\n"
    i = next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith("#")), len(lines))  # 最初の行の値か表。複数行の値の途中には入らない
    out = "".join(lines[:i]) + line + "".join(lines[i:])
    if loads(out, "書いたあとの設定").get("workspace") != value:  # 書いたあとも読める
        sys.exit(f"workspace を書けない（{value}）。設定の頭に手で書く")
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
        assert locate(other) is None and locate(ws / "Customers") == (conf, ws) and "desk-migrate" in missing(other)  # 前の版のワークスペース（factory.toml）の中では、~/.desk.toml に進まない
        conf.write_text(f'workspace = "{other}"\n')
        try:
            locate(tmp)  # 外からも、前の版のワークスペースには解決しない
            raise AssertionError
        except SystemExit as e:
            assert "desk-migrate" in str(e), e
        conf.write_text('workspace = "../Documents"\n')
        (other / OLD).unlink()
        (ws / NAME).write_text("")
        assert local(ws / "Customers") == (ws / NAME, ws) and locate(other) == (conf, ws)  # 既定のワークスペースにも desk.toml があると、中と外で読む設定が変わる（desk-doctor が出す）
        assert front("---\ndescription: 顧客向けの資料: 共通\ntargets: [slides, 'docs']  # 省くと全部\npaths:\n  - a/b.md\n- a/c.md\naudience: 顧客向け\n---\n本文") == {
            "description": "顧客向けの資料: 共通", "targets": ["slides", "docs"], "paths": ["a/b.md", "a/c.md"], "audience": "顧客向け"}
        assert front('---\ndescription: "Issue #12 の件"  # c\n---\n')["description"] == "Issue #12 の件"
        assert [described(front(f"---\ndescription: {v}\n  長い説明\n---\n")) for v in (">", "|-", "[a, b]", " # TODO", "x")] == ["", "", "", "", "x"]  # 複数行と並びは、description がないとみなす
        assert front("---\npaths: a.md\n  - b.md\n---\n")["paths"] == "a.md"  # 値のある key の下の「- 」は並びにしない（字に切らない）
        assert front("# 見出し\n---\n") == front("---\ndescription: x\n") == {} and listed({"audience": "顧客向け"}, "audience") == ["顧客向け"] and listed({}, "paths") == []  # 閉じていない
        r = ws / "rules"
        for f, t in (("a.md", "---\ndescription: x\n---\n"), ("README.md", "# rules/\n"), ("s/b.md", "---\ndescription:\n---\n"),
                     ("docs-build/templates/p/doc.md", "---\ndescription: テンプレート\n---\n"), ("s/c.md", "---\ndescription: y\n---\n")):
            (r / f).parent.mkdir(parents=True, exist_ok=True)
            (r / f).write_text(t)
        assert [str(p.relative_to(r)) for p, _ in rules(ws)] == ["a.md", "s/c.md"] and rules(other) == []  # description のないもの・テンプレートは入れない
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    if not (f := locate()):
        sys.exit(missing())
    print(f[1])
