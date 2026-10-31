#!/usr/bin/env python3
"""usage: check.py [<skills のフォルダ>]   （--selftest で自己確認。プラグインの skills/ も確かめる）
スキルの形を確かめる（AGENTS.md の「Rules for changes」）: SKILL.md の name がフォルダの名前、description が 1,000 字以内、
本文が約 5,000 トークン以内（コンパクションのあと Claude Code が付け直すのは先頭の 5,000 トークン）、スキルのフォルダの直下の md がみな
SKILL.md から指されている（ほかのファイルからしか届かないファイルは、一部だけ読まれやすい）、md がみな 50 KB・2,000 行未満（pi の read はそこで切れ、続きを読まないモデルがいる。mats16/ai-desktools#38）、
md がほかのスキルの中のファイルを指さない（ほかのスキルは名前で呼び、その SKILL.md の表から開く。スキルで共有するコードは lib/。2026-10-31。前のパスを今のパスへ書き換える desk-migrate は除く）、「`<スキル>` → <場面>」で指した場面が、そのスキルの SKILL.md の表の太字の見出しか # の見出しにある、ほかのスキルのファイルを名前だけで指さない。desk-kaizen の open も、変える版でこれを回す。標準ライブラリだけ。"""
import fnmatch, re, sys, tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"
MAX_TOKENS, MAX_DESC, MAX_BYTES, MAX_LINES = 5000, 1000, 50 * 1024, 2000
OPEN = ("desk-migrate",)  # ほかのスキルのファイルを名前で書いてよいスキル（前の版のパスを今のパスへ書き換える表を持つ）
WORKSPACE_FILES = Path("desk-init", "templates")  # ワークスペースに写す雛形（ワークスペースのファイルなので、プラグインのパスを書いてよい）
COMMON = {"SKILL.md", "README.md"}  # どのスキルにもある名前（名前だけで書いても、ほかのスキルのファイルとは言えない）
GONE = {"visual.md", "visual_doc.md", "workflow.md", "rules.md"}  # 2026-10-31 の組み直しでなくなった名前（名前だけで残ると、どこも指さない。今の名前はスキルと場面で指す）
GONE_SKILLS = {"deck-practices", "deck-comments", "slides-template", "desk-recipes", "deck-research"}  # 2026-10-31 になくなったスキルの名前（「`deck-practices` → start」はどこも指さない）
A = r"A-Za-z0-9_-"  # 名前の区切り（Python の \w は和文の字にも当たるので、英数字だけを見る。migrate.py の B と同じ）


def labels(text):
    """SKILL.md の表の行の頭の太字（| **Writing pages:** …）と、# の見出し。ほかのスキルが「`<スキル>` → <場面>」で指す名前。行の中のほかの太字は見出しでない。"""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)  # frontmatter の # の行は見出しでない
    text = re.sub(r"(?ms)^[ \t]*(`{3,}|~{3,})(?:.*?^[ \t]*\1|.*\Z)", "", text)  # 閉じていない囲みは終わりまで  # コードの囲み（``` と ~~~、字下げしたものも）の中の # の行は見出しでない
    return {m.group(1).strip().rstrip(":").lower() for m in re.finditer(r"(?m)^\|\s*\*\*([^*\n]+?)\*\*", text)} | {re.sub(r"^#+\s*", "", x).lower() for x in text.splitlines() if x.startswith("#")}


def unknown_topics(heads, text):
    """text の「`<スキル>` → <場面>」のうち、場面がそのスキルの見出し（heads: スキル → labels）のどれでも始まらないもの。
    ponytail: 見るのは、見出しの語で始まり、語の切れ目で切れるかだけ。後ろに続く文（「running, step 4h」）は読まないので、見出しの後ろに語を足したもの
    （「the flow of …」）は通る。指し方を「`<スキル>` → <見出し>」のあとを § か句読点で区切る形に決めたら、そこで切れることまで見る"""
    out = []
    for m in re.finditer(r"`([\w-]+)`\s*→\s*([^\n|`]+)", text):  # 次の `…` の前まで（1 行に指す先が 2 つあっても、1 つずつ見る）
        if m.group(1) in GONE_SKILLS:
            out.append(f"`{m.group(1)}`（なくなったスキル） → {m.group(2)[:30]}")
            continue
        if m.group(1) not in heads:
            continue
        rest = m.group(2).lower()
        if not any(x and re.match(re.escape(x) + r"(?=$|[\s§(（,;.)、。:）」*])", rest) for x in heads[m.group(1)]):  # 見出しとちょうど同じ語で、そこで切れる（sli・the のような頭だけは通さない）
            out.append(f"`{m.group(1)}` → {m.group(2)[:40]}")
    return out


def foreign(skills, name, text):
    """text の中の、ほかのスキルの中のファイルへのパス（<スキル>/SKILL.md と、スキルの名前だけは除く）。"""
    others = sorted((s for s in skills if s != name), key=len, reverse=True)
    if not others:
        return []
    pat = re.compile(rf"(?<![{A}])(?<!(?<![{A}])rules/)(?<!(?<![{A}])recipes/)(" + "|".join(map(re.escape, others)) + rf")/(?!SKILL\.md(?![/{A}]|\.[{A}]))[./{A}]*")  # パスのどこにあっても（../・skills/・<plugin>/・$VAR/ のあと）。ワークスペースの rules/・recipes/ の下は除く
    return [m.group(0) for m in pat.finditer(text)]


def bare(files, name, text, qualified=False):
    """text の中の、自分のスキルにない、ほかのスキルのファイルの名前だけ（content.md §6、content*.md など。どのスキルのものか読み手に分からない）。
    files: スキル → 直下の md の名前。glob は、自分のスキルのどれにも当たらず、ほかのスキルのどれかに当たるとき。"""
    theirs = (set().union(*(v for k, v in files.items() if k != name)) | GONE) - files[name] - COMMON
    out = []
    for m in re.finditer(rf"(?<![./{A}])([*.{A}]+\.md)(?![/{A}])", text):
        x = m.group(1)
        if qualified and (named := re.findall(r"`([\w-]+)`", text[text.rfind("\n", 0, m.start()) + 1:m.start()])) and x in files.get(named[-1], ()):
            continue  # 雛形は「スキル `desk-feedback` の `routing.md`」と、スキルを名指ししてからファイルを書いてよい
        if x in theirs or "*" in x and not fnmatch.filter(files[name], x) and fnmatch.filter(theirs, x):
            out.append(x)
    return out


def tokens(text):
    """ponytail: 見積もり。ASCII は 4 字で 1、ほかは 1 字で 1 トークンと数える。4,500 を超えたら、API の数え方で確かめ直す"""
    a = sum(c.isascii() for c in text)
    return round(a / 4 + len(text) - a)


def problems(skills=SKILLS):
    out, names = [], {p.parent.name for p in skills.glob("*/SKILL.md")}
    heads = {n: labels((skills / n / "SKILL.md").read_text(encoding="utf-8", errors="ignore")) for n in names}
    files = {n: {f.name for f in (skills / n).glob("*.md")} for n in names}  # 直下の md だけ。下のフォルダの md は、ワークスペースの雛形（recipes/README.md など）と README.md で、ほかのスキルもワークスペースのファイルとして名指しする
    for s in sorted(skills.glob("*/SKILL.md")):
        name = s.parent.name
        for f in sorted(s.parent.rglob("*.md")):  # frontmatter がなくても見る
            try:
                text = f.read_text(encoding="utf-8")
                size, lines = f.stat().st_size, text.count("\n") + (bool(text) and not text.endswith("\n"))  # pi と同じく \n で数える
            except UnicodeDecodeError:
                out.append(f"{name}/{f.relative_to(s.parent)}: UTF-8 で読めない")
                continue
            if size >= MAX_BYTES or lines >= MAX_LINES:
                out.append(f"{name}/{f.relative_to(s.parent)}: {size:,} バイト・{lines:,} 行（{MAX_BYTES:,} バイト・{MAX_LINES:,} 行未満。read が切れる。場面ごとのファイルに分ける）")
            if name not in OPEN:
                for ref in [] if f.relative_to(skills).is_relative_to(WORKSPACE_FILES) else sorted(set(foreign(names, name, text))):  # 雛形はプラグインのパスを書いてよい（ほかの点検はかける）
                    out.append(f"{name}/{f.relative_to(s.parent)}: ほかのスキルのファイル {ref} を指している（スキルの名前で呼び、そのスキルの SKILL.md の表にある場面の名前と節で指す）")
                for ref in sorted(set(bare(files, name, text, f.relative_to(skills).is_relative_to(WORKSPACE_FILES)))):
                    out.append(f"{name}/{f.relative_to(s.parent)}: ほかのスキルのファイルを名前だけ（{ref}）で指している（どのスキルのものか分からない。スキルの名前と場面で指す）")
                for ref in unknown_topics(heads, text):
                    out.append(f"{name}/{f.relative_to(s.parent)}: {ref} の場面が、そのスキルの SKILL.md の表の見出しにない（表の行の頭に **<場面>:** を置くか、指す語を見出しにそろえる）")
        t = s.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n", t, re.S)
        if not m:
            out.append(f"{name}: SKILL.md の頭に frontmatter がない")
            continue
        head = dict(re.findall(r"^(\w+): *(.*)$", m.group(1), re.M))
        if desc := re.search(r"^description: *(.*)\n((?:[ \t]+.*\n?)*)", m.group(1) + "\n", re.M):  # 続きの行（字下げした行。> や | で折りたたんだものも）をつなぐ
            first = "" if re.fullmatch(r"[>|][-+]?", desc.group(1).strip()) else desc.group(1).strip()
            head["description"] = " ".join(x for x in [first, *(y.strip() for y in desc.group(2).splitlines())] if x)
        if head.get("name") != name:
            out.append(f"{name}: name が「{head.get('name', '')}」（フォルダの名前にする）")
        if len(head.get("description", "")) > MAX_DESC:
            out.append(f"{name}: description が {len(head['description'])} 字（{MAX_DESC} 字まで）")
        if (n := tokens(t[m.end():])) > MAX_TOKENS:
            out.append(f"{name}: SKILL.md の本文が約 {n:,} トークン（{MAX_TOKENS:,} まで。場面でしか要らない節は、表から 1 段で指すファイルに出す）")
        for f in sorted(s.parent.glob("*.md")):
            own = rf"(?:(?<![\w./-])|(?<![\w.-]){re.escape(name)}/)"  # 名前だけか <このスキル>/名前。prompt_run.md や ../ほかのスキル/run.md では指したことにしない
            if f.name != "SKILL.md" and not re.search(own + re.escape(f.name), t):
                out.append(f"{name}/{f.name}: SKILL.md から指されていない（SKILL.md の表に足す）")
    return out


def selftest():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "a").mkdir()
        (root / "a" / "SKILL.md").write_text("---\nname: a\ndescription: x\n---\n\n| 場面 | [run.md](run.md) |\n")
        (root / "a" / "run.md").write_text("x")
        assert problems(root) == []
        (root / "a" / "deep.md").write_text("run.md からだけ指す")
        (root / "b").mkdir()
        (root / "b" / "SKILL.md").write_text(f"---\nname: c\ndescription: {'x' * (MAX_DESC + 1)}\n---\n" + "word " * 4100)
        got = problems(root)
        assert len(got) == 4 and got[0].startswith("a/deep.md") and "name が「c」" in got[1] and "description" in got[2] and "トークン" in got[3], got
        (root / "c").mkdir()
        (root / "c" / "SKILL.md").write_text("# 頭がない\n")
        assert problems(root)[-1] == "c: SKILL.md の頭に frontmatter がない"
        (root / "c" / "big.md").write_text("x" * MAX_BYTES)
        assert any(x.startswith("c/big.md: ") for x in problems(root))  # frontmatter がなくても大きさは見る
        (root / "c" / "big.md").write_bytes(b"\xff\xfe")
        assert "c/big.md: UTF-8 で読めない" in problems(root)
        (root / "c" / "big.md").unlink()
        (root / "d").mkdir()
        (root / "d" / "SKILL.md").write_text(f"---\nname: d\ndescription: >\n  {'x' * MAX_DESC}\n  y\n---\n\n[prompt_run.md](prompt_run.md)、`../e/run.md`\n")
        (root / "d" / "run.md").write_text("x")
        (root / "d" / "prompt_run.md").write_text("x")
        got = [x for x in problems(root) if x.startswith("d")]
        assert len(got) == 2 and "description" in got[0] and got[1].startswith("d/run.md"), got  # 折りたたんだ description も数え、名前の一部・ほかのスキルの同じ名前は指したことにしない
        (root / "d" / "SKILL.md").write_text(f"---\nname: d\ndescription: {'x' * 600}\n  {'y' * 600}\n---\n\n`d/run.md` と [prompt_run.md](prompt_run.md)\n")
        got = [x for x in problems(root) if x.startswith("d")]
        assert len(got) == 1 and "description" in got[0], got  # 字下げで続けた description も数え、<このスキル>/名前 は指したことにする
        (root / "d" / "run.md").write_text("x" * MAX_BYTES)
        assert any(x.startswith(f"d/run.md: {MAX_BYTES:,} バイト・1 行") for x in problems(root))  # 50 KB ちょうどから止める
        (root / "d" / "run.md").write_text("x\n" * (MAX_LINES - 1) + "x")  # 最後の行に改行がなくても 2,000 行と数える
        assert any(x.startswith(f"d/run.md: {MAX_LINES * 2 - 1:,} バイト・{MAX_LINES:,} 行") for x in problems(root))  # 2,000 行でも止める（pi の read はどちらかで切れる）
        (root / "d" / "ref").mkdir()
        (root / "d" / "ref" / "deep.md").write_text("x" * MAX_BYTES)
        assert any(x.startswith("d/ref/deep.md: ") for x in problems(root))  # スキルのフォルダの下の深い md も見る
        (root / "e").mkdir()
        (root / "e" / "SKILL.md").write_text("---\nname: e\ndescription: x\n---\n\nsee d/SKILL.md. `d` と `../d/SKILL.md`、d/SKILL.md、<d folder>/x、`../../lib/desk.py`、rules/d/x.md、./rules/d/x.md、$WS/rules/d/x.md、Customers/x/recipes/d/y.md\n")
        assert not (_e := [x for x in problems(root) if x.startswith("e")]), _e  # スキルの名前、その SKILL.md、共有の lib/、ワークスペースの前の版の rules/ は指してよい
        (root / "e" / "SKILL.md").write_text("---\nname: e\ndescription: x\n---\n\n`../d/run.md` と skills/d/ref/deep.md、d/scripts/x.py、<plugin>/skills/d/a.md、~/p/skills/d/b.md、./d/c.md、<plugin>/d/e.md、$P/d/f.md、../d/、recipes/d/RECIPE.md\n")
        got = [x for x in problems(root) if x.startswith("e")]
        assert len(got) == 9 and all("ほかのスキルのファイル" in x for x in got) and any(" d/run.md " in x for x in got), got
        (root / "f").mkdir()
        (root / "f" / "SKILL.md").write_text("---\nname: f\ndescription: x\n---\n\n# Making f\n\n| **The flow:** x | y |\n| **Writing pages:** x | do **not** edit |\n\n```sh\n# Output\n```\n\n  ~~~\n  # Hidden\n  ~~~\n")
        (root / "g").mkdir()
        (root / "g" / "SKILL.md").write_text("---\nname: g\ndescription: x\n---\n\n`f` → writing pages §2、`f` → the flow、`f` → writing (short)、`f` → pages、`f` → output、`f` → writ、`f` → not edit、`f` → hidden\n")
        got = [x for x in problems(root) if x.startswith("g")]
        assert sorted(x.split(" の場面")[0].split(": ", 1)[1] for x in got) == sorted(["`f` → writing (short)、", "`f` → pages、", "`f` → output、", "`f` → writ、", "`f` → not edit、", "`f` → hidden"]), got  # 見出しとちょうど同じ語で切れるものだけ通す（頭だけ・コードの囲みの中の見出しは通さない）
        (root / "desk-init" / "templates" / "recipes").mkdir(parents=True)
        (root / "desk-init" / "SKILL.md").write_text("---\nname: desk-init\ndescription: x\n---\n")
        (root / "desk-init" / "templates" / "recipes" / "README.md").write_text("スキル `d` の `run.md`、<plugin>/skills/d/run.md、`f` → nothing、prompt_*.md\n")
        got = [x for x in problems(root) if x.startswith("desk-init")]
        assert len(got) == 2 and any("`f` → nothing" in x for x in got) and any("（prompt_*.md）" in x for x in got), got  # 雛形はパスとスキルを名指しした名前を書いてよいが、場面と名前だけの点検はかける  # 見出しで始まるか、見出しの頭なら通す（f → pages は表にない）
        (root / "h").mkdir()
        (root / "h" / "SKILL.md").write_text("---\nname: h\ndescription: x\n---\n\nmy-rules/d/a.md、スキルd/run.md、run.md §2、`f` →writing pages、`f`→ bold、d/SKILL.md/x\n| `**bold**` | x |\n")
        got = sorted(x for x in problems(root) if x.startswith("h"))
        assert len(got) == 5 and any(" d/a.md " in x for x in got) and any("d/run.md" in x for x in got) and any("（run.md）" in x for x in got) and any("`f` → bold" in x for x in got) and any("d/SKILL.md/x" in x for x in got), got  # 和文に続けたパス、名前だけ、空白のない矢印、コードの中の太字は見出しでない
        (root / "i").mkdir()
        (root / "i" / "SKILL.md").write_text("---\nname: i\ndescription: x\n---\n\nvisual.md §6、`f` → leftover、`deck-practices` → steps 1–5\n")
        (root / "f" / "SKILL.md").write_text((root / "f" / "SKILL.md").read_text() + "\n```\n# Leftover\n")
        got = [x for x in problems(root) if x.startswith("i")]
        assert len(got) == 3 and any("（visual.md）" in x for x in got) and any("`f` → leftover" in x for x in got) and any("なくなったスキル" in x for x in got), got  # なくなった名前と、閉じていない囲みの中の見出し
    assert tokens("abcd") == 1 and tokens("和文") == 2
    bad = problems()
    assert not bad, "\n".join(bad)  # プラグインのスキル
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    bad = problems(Path(a[0]) if a else SKILLS)
    print("\n".join(bad) or "スキルの形: 問題なし")
    sys.exit(1 if bad else 0)
