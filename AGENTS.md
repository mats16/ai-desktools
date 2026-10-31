# Working on AI Desk Tools

This repository (`mats16/ai-desktools` on GitHub) is the source of the AI Desk Tools plugin (Claude Code, Codex) and package (pi). [README.md](README.md) covers the contents, installation, and workspace layout; [docs/development.md](docs/development.md) covers development procedures in detail.

If the conversation was opened under `sandbox/`, ignore this file. That folder is a test workspace for seeing the plugin as a user does, and this file is loaded only because it sits in a parent folder. Act as a plugin user, with only what the plugin gives (its skills, and the recipes the hook shows); the workspace has no `AGENTS.md` of its own.

## Names

- The repository is `mats16/ai-desktools`. The plugin, the marketplace, and the pi package are all named `desk-tools`: skills are called like `desk-tools:slides-build` and installed as `desk-tools@desk-tools`. In prose, the product is "AI Desk Tools".
- Keep the former names (`ai-deck-factory`, "AI Deck Factory") where they refer to the past: past entries in 「決めたこと」 in README, moving installs made under the former name (「前の名前から移る」 and 「残っている課題」 in README), and things from earlier versions (such as the original pptx's corner radius, `slides-visual-018`). Don't update them to the new name. The same holds for the skill names before 2026-10-31 (`deck-practices`, `deck-comments`, `slides-template`, `desk-recipes`, `deck-research`).
- Don't rename the markers written into Google Slides templates and decks (`ai-deck-factory theme=`, `ai-deck-factory layout=`, `ai-deck-factory bar`), because existing templates and decks are read by these strings.

## Layout

The 17 skills fall into six groups by what they hold (2026-10-31 in 「決めたこと」 in README). Keep the weight of dependencies one way: how the work runs calls the knowledge and the tools, and the knowledge and the tools work without it. A tool or knowledge file may still point the reader to a step of `deck-workflow` that happens around it (Drive, delivering, child agents), but never to rules it needs to do its own job.

| Group | Skills | Holds |
| --- | --- | --- |
| How the work runs | `deck-workflow`, `deck-review` | Steps 1–11, child agents, gathering, Drive, delivery, requests after delivery, comments; the review before delivery |
| Knowledge of good materials | `deck-writing`, `deck-design` | Content and wording (the axes, `content*.md`); how pages look (the principles, `slides.md` and `docs.md` for each format) |
| Tools | `slides-build`, `docs-build`, `vids-voice`, `vids-build` | What the page JSON and doc.md can say, how to build and check, themes and templates, API pitfalls |
| Gathering | `customer-profile`, `desk-crawl` | Customer profiles; recurring collection |
| Learning from feedback | `desk-feedback`, `desk-dreaming`, `desk-kaizen`, `desk-research` | Judging and routing corrections, writing recipes; the daily cleanup; upstream Issues; re-researching best practices |
| Environment | `desk-init`, `desk-doctor`, `desk-migrate` | Creating, checking, and migrating a workspace |

| Path | Contents |
| --- | --- |
| `skills/<skill>/` | `SKILL.md`, per-situation files linked from its table, `scripts/`. All three agents read them |
| `lib/` | Code shared by several skills and the hook: `desk.py` (workspace and settings lookup, recipes, `TRIGGERS`), `gapi.py` (Google APIs), `brand.py` (fonts, colors, copyright), `textlint.py` (text rules shared by slides and documents), `sheet.py` (contact sheets), `ledger.py` (the rule ledger), `refs.py` (the sources ledger). Not a skill |
| `hooks/` | `rules_overlay.py` (appends the workspace's recipes, `recipes/<name>/RECIPE.md`) and `hooks.json`, which calls it from Claude Code and Codex |
| `extensions/rules.ts` | The pi extension. Calls `rules_overlay.py` |
| `.claude-plugin/`, `package.json` | Plugin and marketplace definitions (Codex reads these too); the pi package |
| `tests/render/` | Builds the JSON samples and checks them as images (`run.py`; per-page checks in `expect.json`) |
| `tests/skills/` | `check.py`: the shape of each skill (`SKILL.md` within 5,000 tokens, `description` within 1,000 characters, every md linked from `SKILL.md`, every md under 50 KB and 2,000 lines, no path into another skill). Runs with the selftests and before `kaizen.py open` |
| `docs/` | Installation and development guides. `docs/fixtures/` holds the prompts for prompt tests |
| 「決めたこと」 and 「残っている課題」 in README | Decisions the user made, and work deferred |

README is about 200 KB, mostly 「決めたこと」. Don't read it through. Before changing a skill or rule, `grep -n` README for the skill name or rule ID (such as `deck-review-011`) and read only the matching entries, because they record why things are the way they are.

## Where to change what

Find the owner first, and change it there only. To find where a plugin rule is written, run `python3 ../lib/ledger.py where <ID>` in `sandbox/` (`ledger.py` needs a workspace).

| You want to change | Change | Also change |
| --- | --- | --- |
| A step, its order, who does it, when to stop and ask | `deck-workflow` (the review: `deck-review`) | The child prompts that repeat the step (`prompt_*.md` in the same skill) |
| What makes content or wording good | `deck-writing` (an axis in `SKILL.md`; by material type in `content*.md`) | The review aspects in `deck-review`'s `prompt_slides.md` and `prompt_doc.md`, if the reviewer must look for it |
| How pages look | `deck-design` (a principle in `SKILL.md`; values for a format in `slides.md` or `docs.md`) | The component's default in `slides.py` or `docs.py` if it can be built in, and lint if it can be counted |
| A key or component of the page JSON | `slides-build/scripts/slides.py`, and `pages.md` or `diagrams.md` (what the key does, not which page should use it) | A page in `samples/json/` and its checks in `tests/render/expect.json` (the selftest checks both); which form suits which message goes in `deck-design` |
| A lint check | `lint.py` (`slides-build`), `doc_lint.py` (`docs-build`), or `lib/textlint.py` (both) | The rule text says 「lint が〜」 and the check names the rule ID |
| Google API calls | `lib/gapi.py` (shared), or the tool skill's script | The pitfall in that tool's `api.md` |
| How the workspace, settings, or recipes are found; which plugin files trigger which recipes | `lib/desk.py` (`TRIGGERS`) | `hooks/rules_overlay.py` and `extensions/rules.ts` behave the same; the trigger lists in `desk-feedback/routing.md` ("Workspace rules") |
| How corrections are judged, recorded, or routed | `desk-feedback`, and `lib/ledger.py` for the ledger | `desk-dreaming`'s `run.md` if the daily cleanup reads it |
| A rule ID | New: `python3 ../lib/ledger.py next <prefix>` in `sandbox/` (the prefix from `TOPICS` in `lib/ledger.py`). Never change one, even when the rule moves | — |
| A skill's file is split, moved, or renamed; a skill is added, removed, or renamed | The files themselves | `RESTRUCTURE` (paths and names) or `SPLIT` (splits) in `desk-migrate/scripts/migrate.py`, `TRIGGERS` in `lib/desk.py`, `TABLE` in `desk-dreaming/scripts/sessions.py` (keep the old names too), the groups above, the table in README, the count in `docs/` ("17") |

## Rules for changes

- **Give knowledge, not orders.** Write principles, best practices with their reasons and sources, examples, and tools, and let the model decide. Write an instruction only for what the principles do not cover (what is left over) and for the specifics of one environment or a user's decision, because a fixed instruction applies itself to pages it was not written for (2026-10-30 and 2026-10-31 in 「決めたこと」 in README). What can be measured goes into the components' defaults and lint, not into text the model reads.
- **A skill opens only its own files.** Name another skill by its folder name (`deck-design`), and a part of it by the topic its `SKILL.md` table names, with a section number or rule ID: "`deck-design` → slides §3", "slides-visual-049 (`deck-design`)". Don't write a path into another skill, because its files then cannot move without breaking the caller, and a reader who skips the other skill's `SKILL.md` misses the context it gives. A command of another skill's script is written by name with the skill ("`slides.py lint` (`slides-build`)"); a shared script is `<plugin>/lib/<name>.py`. `tests/skills/check.py` fails on a path into another skill (only `desk-migrate`, which maps earlier paths to current ones, may name them). When you add a topic that other skills point to, add it to that skill's `SKILL.md` table under the same words.
- Use the same source for Claude Code, Codex, and pi. Codex reads the Claude Code layout (`.claude-plugin/`, `hooks/hooks.json`) as is, so don't add Codex-specific files. When changing how recipes are appended, check both `hooks/hooks.json` and `extensions/rules.ts`. Don't make a fix that works for only one agent.
- Find the workspace, the settings, and the workspace's recipes (`desk.rules`: `recipes/**/RECIPE.md` with frontmatter `description`; which plugin files trigger which `step`: `desk.TRIGGERS`) only through `lib/desk.py` (walk up for `desk.toml`, else `~/.desk.toml` and its `workspace`; `DESK_CONFIG` overrides the path, and empty skips it). Scripts, `hooks/rules_overlay.py` (and through it `extensions/rules.ts`), and desk-dreaming's `run.sh` and `snapshot.sh` all use it, so the lookup order stays the same everywhere. Take the workspace from `gapi.workspace()` or `desk.locate()`, not from the folder of the settings file, because `~/.desk.toml` sits outside the workspace.
- Write scripts with the standard library only. Only scripts that need packages such as Pillow declare them in a leading `# /// script` block and run with `uv run`. Target Python 3.11 or later. A script imports `lib/` by inserting the plugin's `lib/` folder into `sys.path` (from `skills/<skill>/scripts/`, three levels up). Don't import another skill's `scripts/`; the exceptions today are `vids-build` and `vids-voice`, which read `slides-build`'s `lint.py` and `slides.py` because a video is made from a deck (「残っている課題」 in README). A script without `--selftest` is not run by CI, so give a new script at least a `--selftest` that imports it.
- Keep the body of each `SKILL.md` within 5,000 tokens, because after compaction Claude Code re-attaches only the first 5,000 tokens of each invoked skill. Move sections needed only in some situations (conditional steps, failure handling, steps used by a separate call) into a file linked directly from the table in `SKILL.md`. Don't create files reachable only from other files, because nested files tend to be read only in part.
- Record user decisions in 「決めたこと」 in README, with the date and the user's own words, verbatim. Record deferred work in 「残っている課題」.
- Write PR bodies with the sections of `.github/pull_request_template.md`. Paste the commands you ran and their output as-is. In 「レビューで見てほしいところ」, list file:line locations and the judgments you are unsure of, because reviewers, human and AI, start reading there.
- 日本語で書くところは、平易な和文で、言い切りの「〜する」。漢語やカタカナ語より、やさしい言い方を選ぶ（「検証」より「確かめる」、「ルール」より「決まり」）。例外: `/deck-review` を回す単位は「ラウンド」（README の「決めたこと」の 2026-10-19）。

## Verify changes

Run every check in `sandbox/` (see "Sandbox" below), and paste the results as-is into 「過去資料での検証」 in the PR. While editing skill md files, `python3 tests/skills/check.py` from the worktree root is the quick loop (a second, no Google).

| Changed | How to verify |
| --- | --- |
| Skill md files | `tests/skills/check.py` prints 「スキルの形: 問題なし」 |
| Scripts (`hooks/`, `lib/`, `skills/*/scripts/`, `tests/`) | Run `--selftest` with Python 3.11 (step 2 of "Sandbox"). Every script prints `selftest ok` |
| Paths or names of skills and their files | Also `desk-migrate`'s selftest (it checks `RESTRUCTURE`), and that `hooks/rules_overlay.py --selftest` still finds the moved files |
| Visual building blocks (`slides.py`, `template.py`, `docs.py`) | Rebuild the template samples and look at the images (themes in `slides-build`, templates in `docs-build`) |
| JSON page schema and components | `python3 ../tests/render/run.py --judge` builds all samples and compares every page image with `expect.json`. When you add a key to the schema, add it to the samples; when you add a sample page, add it to `expect.json` (selftest checks both) |
| Descriptions of components, how to write them, or the routes between skills | Give a prompt from `docs/fixtures/` to a child agent with no conversation context, and check that it finds the right files and picks the right components from the descriptions alone ("Test with fixture prompts" in [docs/development.md](docs/development.md)) |
| Behavior of skills, hooks, and the extension | Open a conversation and go through a scene that uses the changed skill ("Claude Code", "Codex", "pi", and "Check that recipes are appended" in [docs/development.md](docs/development.md)) |

## Languages

Write instructions that AI reads in English. Write what people read, and rules tied to Japanese, in Japanese (2026-10-20 and 2026-10-25 in 「決めたこと」 in README).

- **English:**
  - In the `skills/` md files (including the `SKILL.md` `description` and headings, and the child prompts `prompt_*.md`): procedures, step order, how to brief child agents, file and folder handling, commands and script descriptions, verification, and rules whose meaning is unambiguous (position, size, spacing, color and contrast, components and JSON keys, alignment, arrows, tables, images, API pitfalls, Drive locations). Keep each `description` within 1,000 characters.
  - The development instructions: this file and `docs/development.md`.
- **Japanese:**
  - Rules about Japanese text (style, notation, terms and translations, spacing between Japanese and Latin text, punctuation, line-break positions, full-width character counts).
  - Rules that involve the nuance of making materials (how to phrase claims and headings, tone toward customers, how the audience takes it, the flow of the story, what to say and not say).
  - Examples, user quotes, and strings copied verbatim (file names such as `構成案.md`, section names written in the outline such as 「書き方の決め」, the lint labels `要修正` and `要確認`, ledger values, column names of tables read by scripts or people, the 「要判断」 mark).
  - Output formats shown to users or in Issues (the desk-dreaming report, Issue bodies, the skeleton of profile.md, doc.md examples).
  - What people read: README.md, the install guides in `docs/` (`claude-code-plugin.md`, `codex-plugin.md`, `pi.md`), the prompts in `docs/fixtures/`, `skills/desk-init/templates/` (workspace owners edit them), and PR, Issue, and commit bodies. Script messages and comments also stay in Japanese for now (「残っている課題」 in README).
- Decide per rule (one bullet) by its main point. When unsure, keep Japanese. Don't mix languages within one sentence. Inside an English sentence, put Japanese examples, values, and section names in 「」 or backticks (write `「社外秘と顧客の情報」 in deck-writing`, not `deck-writing の「社外秘と顧客の情報」`). Only source tags (such as （見た目 1-7）) and proper nouns (people, books, companies, typefaces) can go unquoted.
- When changing the language, keep rule IDs (such as `[slides-visual-027]`) and section numbers. Refer to sections of English files by their English heading ("Working practices" in `deck-workflow`) and write numbers as `§4`. Refer to sections of Japanese files (README, the install guides in `docs/`, `recipes/README.md`) by their Japanese heading. Japanese files (templates, script messages) also refer to sections of English files by the English heading. Don't rewrite past entries in 「決めたこと」 in README.
- Don't tell child agents which language to answer in (such as 「日本語で答える」), because the model picks it without being told. What they need is the instruction to copy rule text, user quotes, and sources in their original language.
- Write English as short, plain imperative sentences, and keep the reasons ("because ..."). Use the terms already in the skills: 「構成案」 → the outline, 「子」 → child agent, 「指摘」 → finding, 「修正の指示」 → correction, 「扉」 → section divider, 「一覧の画像」 → contact sheet, 「レビューの観点」 → aspect.

## Public repository

`origin` (`mats16/ai-desktools` on GitHub) is public.

- Keep customer names, the names, URLs, and content of materials, and internal-only information out of commits, PRs, and Issues. In examples, use 「顧客向けの資料」, 「（顧客）」, or 「資料 1」.
- Keep the original checkout (the first line of `git worktree list`) on `main`, and make changes in a worktree, because plugins installed in other workspaces by local path read that checkout.

## Sandbox

Put a test workspace `sandbox/` directly under the worktree, and pass it the worktree's plugin without installing it. `.gitignore` excludes `sandbox/`, so it stays out of commits and goes away with the worktree. [docs/development.md](docs/development.md) covers opening it in Claude Code, Codex, and pi, checking that the recipes are appended, building materials, and cleanup.

1. **Create.** Run from the worktree root:

   ```sh
   python3 skills/desk-init/scripts/init.py sandbox
   cd sandbox
   python3 ../skills/desk-doctor/scripts/doctor.py --local   # skips the Google APIs
   ```

   With the template `desk.toml`, nothing can be built on Google (doctor keeps reporting `要修正`). To build, copy the production settings (the workspace's `desk.toml`, or `~/.desk.toml`; from `~/.desk.toml`, delete the `workspace` line after copying) and point `[drive]` at a test Drive folder, so production files are never overwritten ("Create the sandbox" in docs/development.md). Don't run `git init` in `sandbox/`.

2. **Run the selftests.** Run in `sandbox/` (`template.py` looks for `desk.toml`), with Python 3.11, the lowest supported version, and with `DESK_CONFIG` empty, so that your own `~/.desk.toml` does not change the results:

   ```sh
   for f in ../hooks/*.py ../lib/*.py ../skills/*/scripts/*.py ../tests/*/*.py; do
     grep -q -e --selftest "$f" && echo "$f: $(DESK_CONFIG= uv run -q --python 3.11 "$f" --selftest 2>&1 | tail -1)"
   done
   ```

   Every line ends with `selftest ok`. On PRs and pushes to `main`, GitHub Actions (`.github/workflows/selftest.yml`) creates the sandbox on Ubuntu and runs step 2.

3. **Remove.** Go back to the worktree root and run `rm -rf sandbox` (not needed if you delete the whole worktree). What was built on Google Drive and Codex's `CODEX_HOME` remain; remove them as in "Clean up" in docs/development.md.
