#!/usr/bin/env python3
"""資料ごとに選ぶレシピの一覧を、作る会話が手順 5 で hook から受け取る文のとおりに出す。標準ライブラリだけ。
レシピを試すとき（../recipes.md の "Testing a recipe"）に、子への頼む文に入れる。一覧は hook の index() で作るので、hook が見せる文と食い違わない。
usage:
  recipe_menu.py [--draft <下書きの RECIPE.md> --as recipes/<名前>/RECIPE.md]
      --draft は、ワークスペースに書き込む前の下書きを、--as のパスのレシピとして一覧に入れる（あれば置き換える、なければ足す）。
      今のレシピの写しに下書きを置き、hook と同じ探し方で読むので、hook が出さない場所や frontmatter なら止める。
      資料ごとに選ぶレシピがなければ止める（hook は一覧を出さない）。一覧だけで hook の 1 回の差し込みの上限を超えれば、切られると知らせる
      （顧客の memory などと並ぶと、もっと短くても切られる）。ワークスペースは hook と同じ探し方で決める
  recipe_menu.py --selftest"""
import argparse, contextlib, io, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "hooks")]
import desk  # noqa: E402  ワークスペースとレシピの探し方
from rules_overlay import LIMIT, index, workspace  # noqa: E402  手順 5 で hook が出す一覧、1 回の差し込みの上限、ワークスペースの探し方


def render(ws, files):
    if not (free := [(p, m) for p, m in files if desk.kind(m) == "material"]):  # hook と同じ選び方（desk.rules の順）
        sys.exit("資料ごとに選ぶレシピ（per_material: true）がない。hook は手順 5 で一覧を出さない")
    if len(text := index(ws, free)) > LIMIT:  # hook は合わせて LIMIT 字までなら切らない（cut）
        print(f"一覧だけで {len(text):,} 字あり、hook が 1 回に差し込める {LIMIT:,} 字を超える。作り手には途中で切れて見える", file=sys.stderr)
    return text


def menu(ws, draft=None, as_path=None):
    if not draft:
        return render(ws, desk.rules(ws))
    try:
        text = Path(draft).read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        sys.exit(f"下書きを読めない（{draft}）: {e}")
    tmp = Path(tempfile.mkdtemp())
    try:
        for p, _ in desk.rules(ws):  # 今のレシピの RECIPE.md を写し、下書きを --as に置いて、hook と同じ探し方で読む
            (tmp / p.relative_to(ws)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, tmp / p.relative_to(ws))
        target = (tmp / as_path).resolve()
        if not target.is_relative_to((tmp / desk.RECIPES).resolve()) or target.name != desk.RECIPE:
            sys.exit(f"--as は recipes/<名前>/RECIPE.md の形で書く: {as_path}")
        replaced = target.is_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        files = desk.rules(tmp)
        if not any(p.resolve().samefile(target) and desk.kind(m) == "material" for p, m in files):  # 大文字と小文字を分けないファイルシステムでも、同じファイルなら同じ
            sys.exit(f"下書きを {as_path} に置いても、hook は資料ごとに選ぶレシピとして出さない（frontmatter の description と per_material: true か、置く場所を直す）")
        name = next(p for p, _ in files if p.resolve().samefile(target)).relative_to(tmp).as_posix()  # hook が出す名前（--as の大文字と小文字でなく）
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
    if not (ws := workspace(os.getcwd())):
        sys.exit(desk.missing())
    print(menu(ws, a.draft, a.as_path))
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
        assert got == index(tmp, [(tmp / "recipes/cxo/RECIPE.md", desk.rules(tmp)[0][1])]), got  # hook と同じ文
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
        put("draft/long.md", "---\ndescription: " + "長い" * (LIMIT // 2) + "\nper_material: true\n---\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            menu(tmp, tmp / "draft/long.md", "recipes/long/RECIPE.md")
        assert "途中で切れて見える" in err.getvalue(), err.getvalue()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            menu(tmp)
        assert not err.getvalue(), err.getvalue()  # 上限までは知らせない
        for argv in (["--draft", "x.md"], ["--as", "recipes/x/RECIPE.md"]):
            try:
                main(argv)
                raise AssertionError(argv)
            except SystemExit as e:
                assert "一緒に書く" in str(e), e
        here, env = os.getcwd(), dict(os.environ)
        try:  # ワークスペースの外では、hook と同じく見つからず止まる（個人の設定も会話のフォルダも読まない）
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
