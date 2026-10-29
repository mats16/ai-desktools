---
name: desk-kaizen
description: Improve the plugin (upstream). Takes the rules, checks, and script fixes that grew in a workspace and help other people too, verifies them on past materials with the changed and previous versions, and files an Issue on the plugin repository with the reason, verification results, images, and the diff of the proposed change. The owner creates the PR. Use when applying desk-dreaming's 「プラグインに上げる」 proposals, or when asked 「工場を改善して」, 「プラグインに Issue を出して」, or 「大元を直して」.
---

# Improve the plugin (file an Issue upstream)

Treat the workspace as one product whose rules (AGENTS.md, `recipes/`) and checks (the `checks.py` in a recipe's folder) grow from accumulated corrections and exchanges. Of these, file only the ones that help other people too (not one person's taste or one customer's circumstances) as an Issue upstream (the plugin). What goes where is in "Workspace rules" of `../deck-practices/rules.md`.

The plugin owner reads the Issue, decides whether to take it, and rewrites it to fit the rest of the code as a PR. So the Issue must contain enough material for the owner to decide without seeing the workspace (what happened, counts, verification results, images, the diff of the proposed change, open questions). The proposed change only needs to work in a verifiable form. Cleaning up, shrinking, and running reviews (simplify, review-loop, etc.) are the owner's job, so do not do them here.

Prerequisites: `gh` is logged in. Run in the workspace. `start` clones the upstream repository (`repository` in `.claude-plugin/plugin.json`) into `.desk/kaizen/<name>/repo`, so no local checkout or fork is needed.

```sh
P="python3 <this skill's folder>/scripts/kaizen.py"
$P start <name>                                   # clone into .desk/kaizen/<name>/repo (branch kaizen/<name>)
$P lint <name> <material URL ...>                 # run lint with the previous and changed versions on current materials and compare
$P rebuild <name> <material folder ...> [--pages 2,5]   # build temporarily from the source of truth with both versions and lay changed pages' images side by side (the temporary materials go to the trash)
$P probe <name> [--fixtures 02,05] [<material folder ...>] [--agent claude|codex|pi] [--model <model>]   # have child agents write the same requests with both versions, lint both locally, and have a blind child pick one (no Google)
$P open <name> --title <title> --body <body.md>   # Issue on the upstream repository. From the second time, rewrites the same Issue
$P clean <name>                                   # after the Issue is closed (deletes the clone too)
```

## Steps

1. **Decide what to file.** Combine into one: what to change and why (the findings and the number of materials and customers shown by `ledger.py why <rule ID or workspace file>` in the rule ledger, recurrences and review results, figures from `.desk/lint_runs.jsonl` or desk-dreaming's records). Do not write original quotes or material names in the Issue (after `start` in step 2, write them only in `verify/detail.md`); write counts in the Issue. If a workspace recipe has a copy, frame it as moving that copy upstream. Do not file preferences from a customer's `memory.md` directly (if two or more customers share one, desk-dreaming first moves it into `rules/`; "Customer memory" in `../deck-practices/rules.md`). Give a moved rule a new ID with the plugin's prefix (the next number after the largest one with the same prefix in `.desk/kaizen/<name>/repo`; no `ws-`). In the rule text write only the ID and a short reason, not dates or original quotes ("Routing corrections" in `../deck-practices/rules.md`).
2. **Run `start`, write the proposed change inside `.desk/kaizen/<name>/repo`, and commit.** Do not edit the plugin's install location. The branch is not pushed (the diff goes into the Issue), so commit granularity and messages are free.
3. **Verify on past materials.** Choose by what changed.
   - Rules and checks (`lint.py`, `doc_lint.py`, `textlint.py`, things moved from `checks.py`): run `lint` on both materials the rule should fire on and materials it must not fire on. Candidates are the materials in `.desk/lint_runs.jsonl` (materials where that rule's finding appeared) and 「作った」 in `references_index.md`.
   - Layout and appearance (`slides.py`, `docs.py`, `template.py`, `slides-build/visual.md`, `docs-build/visual.md`, templates, images): run `rebuild` on materials that have pages that should change. Before/after images are required (`open` stops without them).
   - Changes whose appearance does not differ before and after (for example a lint-only change that also edits text in `visual.md`): `rebuild` reports 「変わったページ: なし」 and makes no images. Place images of pages where the changed rule applies (for example built samples) in `verify/img/` by hand, and write in the 「過去資料での検証」 section of the body that the appearance does not change. Images without a `rebuild` marker (`<!-- img:<file name> -->` in `verify/pr.md`) are collected by `open` under 「ほかの画像」 at the end of the verification record (to show them elsewhere, add a marker to `verify/pr.md`).
   - Rule and procedure text (`skills/**/*.md`, including `visual.md`, descriptions, and the JSON format's explanations): commit the change in `repo/`, then run `probe` on that commit (it stops on uncommitted changes, so the recorded commit is what ran; `open` stops unless `verify/pr.md` has a probe of the current commit that compared at least one request, or the body has a `検証しない理由:`; a probe that compared no request, such as one that ends 「比べられない」, does not count). Harness² found that editing a harness without running it lowered the score (Code 73.4 → 63.2; 2026-10-25 in 「決めたこと」 in README), and lint and `rebuild` only replay the same JSON, so they cannot show whether the agent now writes differently. `probe` copies both versions to a temporary folder without `docs/` and `tests/` (so children cannot read a fixture's 「見るところ」), and runs each request once per version in a template workspace (`desk-init`; nothing can be built on Google). The temporary folder is new for each run, names no version, and is removed at the end; the outputs are kept in `verify/probe/`. Requests are fixtures (`--fixtures`, the 「依頼文」 of `docs/fixtures/<number>-*.md`) and replays of past decks (material folders: write the pages again from the agreed outline; the material's `build/` and 「社内メモ」 are not copied, and the workspace's `rules/` is not used, since the Issue is about what helps other people). Both outputs are counted with the changed version's lint, and a child agent that sees only the request, the materials, and the two deliverables with the versions hidden picks one ([prompt_select.md](prompt_select.md)). Choose requests where the changed rule applies, at least two of them (a difference of one request is noise), and use the agent and model the workspace usually makes materials with. Before running, tell the user the number of child runs (two per request plus one selector each; about $0.75 and 2 minutes per writer for a one-page fixture with Claude Code on 2026-10-25). Read the verdict with the selector's reasons in `verify/detail.md`; 「混ざっている」 means several rules changed at once, so split the Issue if the verdict matters.
   - Other text-only edits (rewording that the agent does not act on, such as comments): if no verification is needed, write `検証しない理由:` in the 「過去資料での検証」 section of the body.
   - Read the results, and in `.desk/kaizen/<name>/verify/detail.md` (which contains material names and finding text) check that added findings are not false positives and that removed findings really should go away. If the results are not what you expected, go back to step 2.
4. **Write the body.** Write it in `.desk/kaizen/<name>/body.md` using the template below. Every section is required (`open` stops otherwise).
5. **Confirm with the user before `open`.** People outside the repository also read the Issue. Show these two and file only after the user approves.
   - The body
   - The images to include (`verify/img/` and changed png files; a png's content does not show in a diff, so `open` includes the changed version as an image). As a rule, do not include images from customer-facing materials (`Customers/`), because they show the customer's name, numbers, and confidential information. Re-verify with internal materials or materials with only public content.
   `open` checks that the sections are complete, that verification exists, that appearance changes have images, that changed rule text was probed, and that the skills keep their shape (`tests/skills/check.py` in the changed version: SKILL.md within about 5,000 tokens, descriptions within 1,000 characters, every file in a skill folder linked from its SKILL.md). It then puts the images on the `pr-assets` branch (of your fork if you cannot write to the upstream repository; if there is no fork, `open` creates one on GitHub), appends the verification record (materials only as numbers like 「資料 1」; no names, URLs, or text), the previous version's commit, and the diff of the proposed change (`git diff origin/main...HEAD`, based on main of the upstream repository cloned by `start`) to the body, and creates the Issue. If the diff is so long that the body exceeds the limit, leave out the diff and write only its line count (file it in parts).
6. **Report back.** Return the Issue URL. If it came from a desk-dreaming proposal to the plugin (P-ID), record it in the rule ledger with `ledger.py sent <P-ID> --issue <URL>` (if the proposed change uses an ID different from the proposal, also add `--rule <that ID>`) (so desk-dreaming does not propose the same thing again). Follow the Issue with `gh issue view <URL> --json state,stateReason`. If it is closed without being taken (`NOT_PLANNED`), run `ledger.py reject <P-ID> --reason <reason>`. If it is closed as fixed (`COMPLETED`), tell the user it arrives with `claude plugin update desk-tools@desk-tools` (for pi, depends on how it was installed), and run `clean`. Once it arrives, desk-dreaming proposes deleting the copy in the workspace `rules/` through 「写しを消す」 of `ledger.py candidates` (it checks whether the filed text is in the installed plugin; if the owner changed the text or ID, it does not appear, so desk-dreaming removes it through the overlap check in its step 4e). The source findings are already linked to the new ID by `sent`. If findings that were not used as sources remain on the copy (`ledger.py why <ws-ID>`), relink each finding with `ledger.py route <c-ID> <plugin ID>`.

## Body template

```markdown
## 変えること
<何がどう変わるか。1〜3 行>

## 理由
<なぜ大元で変えるべきか。ほかの人にも効く理由>

## 背景
<きっかけ。ユーザーの発言（原文）、起きたこと、数字（lint の残り方、desk-dreaming の記録）。顧客の名前は書かない>

## 過去資料での検証
<何で確かめたか、結果をどう読んだか（増えた指摘・消えた指摘が正しいか）。下に desk-kaizen が表と画像を足す>

## 影響
<既存の資料・ワークスペースの recipes/ への影響。ほかの人の資料で指摘が増えるか。なければ「なし」>

## 迷ったところ
<確信のない判断・前提（しきい値を何本の資料で決めたか、など）と、とらなかった案。なければ「なし」>
```

## Notes

- Do not put customer names, internal URLs, or personal names in the Issue body or images (same as 「社外秘と顧客の情報」 in AGENTS.md). `open` stops if the title, body, branch name, changed file names, or included diff (including removed lines and context lines) contain a customer name from the workspace's `Customers/`, a material folder name under `Customers/<customer>/` or `Internal/` (one containing a 4-digit year; by rule `<内容>_<日付>`), or a word in `[desk] private` of `desk.toml`. Write folder names without dates, and Japanese company and product names, in `[desk] private`. Write the source parentheses of a rule like 「顧客向けの資料の p.3」 or 「ユーザー「（顧客）は〜」」.
- Temporary materials built for verification are created in `drive.desk` and moved to the trash afterward (kept only with `--keep`). They are not recorded in the lint log (`.desk/lint_runs.jsonl`).
