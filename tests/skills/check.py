#!/usr/bin/env python3
"""usage: check.py [<skills のフォルダ>]   （--selftest で自己確認。プラグインの skills/ も確かめる）
スキルの形を確かめる（AGENTS.md の「Rules for changes」）: SKILL.md の name がフォルダの名前、description が 1,000 字以内、
本文が約 5,000 トークン以内（コンパクションのあと Claude Code が付け直すのは先頭の 5,000 トークン）、スキルのフォルダの直下の md がみな
SKILL.md から指されている（ほかのファイルからしか届かないファイルは、一部だけ読まれやすい）。desk-kaizen の open も、変える版でこれを回す。標準ライブラリだけ。"""
import re, sys, tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"
MAX_TOKENS, MAX_DESC = 5000, 1000


def tokens(text):
    """ponytail: 見積もり。ASCII は 4 字で 1、ほかは 1 字で 1 トークンと数える。4,500 を超えたら、API の数え方で確かめ直す"""
    a = sum(c.isascii() for c in text)
    return round(a / 4 + len(text) - a)


def problems(skills=SKILLS):
    out = []
    for s in sorted(skills.glob("*/SKILL.md")):
        name, t = s.parent.name, s.read_text(encoding="utf-8")
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
        (root / "d").mkdir()
        (root / "d" / "SKILL.md").write_text(f"---\nname: d\ndescription: >\n  {'x' * MAX_DESC}\n  y\n---\n\n[prompt_run.md](prompt_run.md)、`../e/run.md`\n")
        (root / "d" / "run.md").write_text("x")
        (root / "d" / "prompt_run.md").write_text("x")
        got = [x for x in problems(root) if x.startswith("d")]
        assert len(got) == 2 and "description" in got[0] and got[1].startswith("d/run.md"), got  # 折りたたんだ description も数え、名前の一部・ほかのスキルの同じ名前は指したことにしない
        (root / "d" / "SKILL.md").write_text(f"---\nname: d\ndescription: {'x' * 600}\n  {'y' * 600}\n---\n\n`d/run.md` と [prompt_run.md](prompt_run.md)\n")
        got = [x for x in problems(root) if x.startswith("d")]
        assert len(got) == 1 and "description" in got[0], got  # 字下げで続けた description も数え、<このスキル>/名前 は指したことにする
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
