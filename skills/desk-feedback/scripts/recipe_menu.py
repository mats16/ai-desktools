#!/usr/bin/env python3
"""資料ごとに選ぶレシピの一覧を、作る会話が手順 5 で desk.py recipes から受け取る文のとおりに出す。標準ライブラリだけ。
レシピを試すとき（../recipes.md の "Testing a recipe"）に、サブエージェントに頼む文に入れる。一覧は desk.py recipes と同じ desk.index() で作るので、作る会話が見る文と食い違わない。
usage:
  recipe_menu.py [--draft <下書きの RECIPE.md> --as recipes/<名前>/RECIPE.md]
      --draft は、ワークスペースに書き込む前の下書きを、--as のパスのレシピとして一覧に入れる（あれば置き換える、なければ足す）。
      今のレシピの写しに下書きを置き、desk.py recipes と同じ探し方で読むので、資料ごとに選ぶレシピとして並ばない場所や frontmatter なら止める。
      資料ごとに選ぶレシピがなければ止める（一覧が「なし」になる）。ワークスペースは desk.py recipes と同じ探し方で決める
  recipe_menu.py --selftest"""
import argparse, contextlib, io, os, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desk  # noqa: E402  ワークスペースとレシピの探し方（desk-init の desk.py の写し）
from desk import found, index, materials  # noqa: E402  ワークスペースの探し方、手順 5 で desk.py recipes が出す一覧と、その選び方（desk.py recipes もこれを使う）


def render(ws, files):
    if not (free := materials(files)):  # desk.py recipes と同じ選び方（desk.rules の順）
        sys.exit("資料ごとに選ぶレシピ（per_material: true）がない。手順 5 の一覧は「なし」になる")
    return index(ws, free)


def menu(ws, draft=None, as_path=None):
    if not draft:
        return render(ws, desk.rules(ws))
    try:
        text = Path(draft).read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        sys.exit(f"下書きを読めない（{draft}）: {e}")
    tmp = Path(tempfile.mkdtemp())
    try:
        for p, _ in desk.rules(ws):  # 今のレシピのフォルダ（資源の名前も一覧に出る）を写し、下書きを --as に置いて、desk.py recipes と同じ探し方で読む
            for x in p.parent.rglob("*"):  # RECIPE.md は中身ごと、ほかのファイル（資源）は名前だけの空のファイルにする（一覧には名前しか出ないので、大きいテンプレートを写さない）
                if x.is_file():
                    (dst := tmp / x.relative_to(ws)).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(x, dst) if x.name == desk.RECIPE else dst.touch()
        target = (tmp / as_path).resolve()
        if not target.is_relative_to((tmp / desk.RECIPES).resolve()) or target.name != desk.RECIPE:
            sys.exit(f"--as は recipes/<名前>/RECIPE.md の形で書く: {as_path}")
        replaced = target.is_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        files = desk.rules(tmp)
        if not any(p.resolve().samefile(target) and desk.kind(m) == "material" for p, m in files):  # 大文字と小文字を分けないファイルシステムでも、同じファイルなら同じ
            sys.exit(f"下書きを {as_path} に置いても、資料ごとに選ぶレシピとして並ばない（frontmatter の description と per_material: true か、置く場所を直す）")
        name = next(p for p, _ in files if p.resolve().samefile(target)).relative_to(tmp).as_posix()  # 一覧に出る名前（--as の大文字と小文字でなく）
        print(f"下書きを {name} として{'置き換えた' if replaced else '足した'}", file=sys.stderr)
        return render(tmp, files)
    finally:
        shutil.rmtree(tmp)


def main(argv):
    ap = argparse.ArgumentParser(prog="recipe_menu.py")
    ap.add_argument("--draft")
    ap.add_argument("--as", dest="as_path")
    a = ap.parse_args(argv)
    if bool(a.draft) != bool(a.as_path):
        sys.exit("--draft と --as は一緒に書く")
    print(menu(found(os.getcwd()), a.draft, a.as_path))
    return 0


def selftest():
    tmp = Path(tempfile.mkdtemp())
    try:
        def put(rel, text):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")
        put("recipes/cxo/RECIPE.md", "---\ndescription: 顧客の CxO に提案するとき\nper_material: true\naudience: [顧客向け]\n---\n- a\n")
        put("recipes/figures/RECIPE.md", "---\ndescription: 図\n---\n- a\n")
        put("draft/cxo.md", "---\ndescription: 顧客の役員に見せる資料を作るとき\nper_material: true\n---\n- a\n")
        put("draft/new.md", "---\ndescription: パートナー向けの勉強会\nper_material: true\n---\n- a\n")
        put("draft/common.md", "---\ndescription: 図\n---\n- a\n")
        got = menu(tmp)
        assert got == index(tmp, [(tmp / "recipes/cxo/RECIPE.md", desk.rules(tmp)[0][1])]), got  # desk.py recipes と同じ文
        assert "recipes/cxo/RECIPE.md（全部、顧客向け）: 顧客の CxO に提案するとき" in got and "figures" not in got, got
        got = menu(tmp, tmp / "draft/cxo.md", "recipes/cxo/RECIPE.md")
        assert "顧客の役員に見せる資料" in got and "CxO" not in got, got  # 置き換える
        got = menu(tmp, tmp / "draft/new.md", "recipes/partner/RECIPE.md")
        assert "recipes/partner/RECIPE.md" in got and "CxO" in got, got  # 足す
        for draft, as_path in (("draft/common.md", "recipes/x/RECIPE.md"), ("draft/new.md", "recipes/RECIPE.md"), ("draft/new.md", "other/x/RECIPE.md"), ("draft/none.md", "recipes/x/RECIPE.md"),
                               ("draft/new.md", "recipes/../x/RECIPE.md"), ("draft/new.md", "recipes/cxo/templates/q/RECIPE.md")):
            try:
                menu(tmp, tmp / draft, as_path)
                raise AssertionError((draft, as_path))
            except SystemExit:
                pass
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            menu(tmp, tmp / "draft/cxo.md", "recipes/cxo/RECIPE.md")
            menu(tmp, tmp / "draft/new.md", "recipes/partner/RECIPE.md")
        assert "recipes/cxo/RECIPE.md として置き換えた" in err.getvalue() and "recipes/partner/RECIPE.md として足した" in err.getvalue(), err.getvalue()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert menu(tmp) in desk.recipes(tmp)  # 一覧は、desk.py recipes の一節と同じ
        assert not err.getvalue(), err.getvalue()
        for argv in (["--draft", "x.md"], ["--as", "recipes/x/RECIPE.md"]):
            try:
                main(argv)
                raise AssertionError(argv)
            except SystemExit as e:
                assert "一緒に書く" in str(e), e
        here, env = os.getcwd(), dict(os.environ)
        try:  # ワークスペースの外では、desk.py recipes と同じく見つからず止まる（個人の設定も会話のフォルダも読まない）
            os.chdir(tmp / "draft")
            os.environ["DESK_CONFIG"] = ""
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            try:
                main([])
                raise AssertionError("ワークスペースがないのに出した")
            except SystemExit as e:
                assert "desk.toml が見つからない" in str(e), e
        finally:
            os.chdir(here)
            os.environ.clear()
            os.environ.update(env)
        empty = tmp / "empty"
        (empty / "recipes/figures").mkdir(parents=True)
        (empty / "recipes/figures/RECIPE.md").write_text("---\ndescription: 図\n---\n", encoding="utf-8")
        try:
            menu(empty)
            raise AssertionError("一覧がないのに出した")
        except SystemExit:
            pass
    finally:
        shutil.rmtree(tmp)
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:]))
