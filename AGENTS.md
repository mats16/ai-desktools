# Working on AI Desk Tools

This repository (`mats16/ai-desktools` on GitHub) is the source of the AI Desk Tools plugin (Claude Code, Codex) and package (pi). [README.md](README.md) covers the contents, installation, and workspace layout; [docs/development.md](docs/development.md) covers development procedures in detail.

If the conversation was opened under `sandbox/`, ignore this file. That folder is a test workspace for seeing the plugin as a user does, and this file is loaded only because it sits in a parent folder. Follow `sandbox/AGENTS.md` (the desk-init template) and act as a plugin user.

## Names

- The repository is `mats16/ai-desktools`. The plugin, the marketplace, and the pi package are all named `desk-tools`: skills are called like `desk-tools:slides-build` and installed as `desk-tools@desk-tools`. In prose, the product is "AI Desk Tools".
- Keep the former names (`ai-deck-factory`, "AI Deck Factory") where they refer to the past: past entries in 「決めたこと」 in README, moving installs made under the former name (「前の名前から移る」 and 「残っている課題」 in README), and things from earlier versions (such as the original pptx's corner radius, `slides-visual-018`). Don't update them to the new name.
- Don't rename the markers written into Google Slides templates and decks (`ai-deck-factory theme=`, `ai-deck-factory layout=`, `ai-deck-factory bar`), because existing templates and decks are read by these strings.

## Layout

| Path | Contents |
| --- | --- |
| `skills/<skill>/` | 15 skills (`SKILL.md`, per-situation files, `scripts/`). All three agents read them |
| `hooks/` | `rules_overlay.py` (appends the workspace's `rules/` files) and `hooks.json`, which calls it from Claude Code and Codex |
| `extensions/rules.ts` | The pi extension. Calls `rules_overlay.py` |
| `.claude-plugin/` | Plugin and marketplace definitions. Codex reads these too |
| `tests/render/` | Builds the samples and checks them as images (`run.py`; per-page checks in `expect.json`) |
| `docs/` | Installation and development guides. `docs/fixtures/` holds the prompts for prompt tests |
| 「決めたこと」 and 「残っている課題」 in README | Decisions the user made, and work deferred |

README is about 200 KB (94,000 characters), mostly 「決めたこと」. Don't read it through. Before changing a skill or rule, `grep -n` README for the skill name or rule ID (such as `deck-review-011`) and read only the matching entries, because they record why things are the way they are.

## Verify changes

Run every check in `sandbox/` (see "Sandbox" below), and paste the results as-is into 「過去資料での検証」 in the PR.

| Changed | How to verify |
| --- | --- |
| Scripts (`hooks/`, `skills/*/scripts/`, `tests/`) | Run `--selftest` with Python 3.11 (step 2 of "Sandbox"). Every script prints `selftest ok` |
| Visual building blocks (`slides.py`, `template.py`, `docs.py`) | Rebuild the template samples and look at the images (`slides-build/themes.md`, `docs-build/templates.md`) |
| JSON page schema and components | `python3 ../tests/render/run.py --judge` builds all samples and compares every page image with `expect.json`. When you add a key to the schema, add it to the samples; when you add a sample page, add it to `expect.json` (selftest checks both) |
| Descriptions of components and how to write them | Give a prompt from `docs/fixtures/` to a child agent with no conversation context, and check that it picks the right components from the descriptions alone ("Test with fixture prompts" in [docs/development.md](docs/development.md)) |
| Behavior of skills, hooks, and the extension | Open a conversation and go through a scene that uses the changed skill ("Claude Code", "Codex", "pi", and "Check that `rules/` is appended" in [docs/development.md](docs/development.md)) |

## Rules for changes

- Use the same source for Claude Code, Codex, and pi. Codex reads the Claude Code layout (`.claude-plugin/`, `hooks/hooks.json`) as is, so don't add Codex-specific files. When changing how `rules/` is appended, check both `hooks/hooks.json` and `extensions/rules.ts`. Don't make a fix that works for only one agent.
- Find the workspace and the settings only through `skills/deck-practices/scripts/desk.py` (walk up for `desk.toml`, else `~/.desk.toml` and its `workspace`; `DESK_CONFIG` overrides the path, and empty skips it). Scripts, `hooks/rules_overlay.py` (and through it `extensions/rules.ts`), and desk-dreaming's `run.sh` and `snapshot.sh` all use it, so the lookup order stays the same everywhere. Take the workspace from `gapi.workspace()` or `desk.locate()`, not from the folder of the settings file, because `~/.desk.toml` sits outside the workspace.
- Write scripts with the standard library only. Only scripts that need packages such as Pillow declare them in a leading `# /// script` block and run with `uv run`. Target Python 3.11 or later.
- Keep the body of each `SKILL.md` within 5,000 tokens, because after compaction Claude Code re-attaches only the first 5,000 tokens of each invoked skill. Move sections needed only in some situations (conditional steps, failure handling, steps used by a separate call) into a file linked directly from the table in `SKILL.md`. Don't create files reachable only from other files, because nested files tend to be read only in part. When you split a file, add it to `SPLIT` in `desk-migrate/scripts/migrate.py` (2026-10-24 in 「決めたこと」 in README).
- When another skill's files or a script message send the reader to a file split out of a `SKILL.md`, write "open `../<skill>/SKILL.md`, then its `<file>`" (in Japanese text such as script messages, 「`../<スキル>/SKILL.md` を開いてから、その `<ファイル>`」). The hook appends only `rules/<skill>/<file>` for the exact path opened, so opening the split file directly skips the workspace overrides in `rules/<skill>/SKILL.md`. References that only cite a rule's source by number (such as 「`desk-dreaming/run.md` の 5 で見る」) and script comments can stay as they are.
- When adding, removing, or renaming a skill, update every place that names or counts the skills: the table in README, the count in `docs/` ("15"), and paths pointing to it from other skills such as `deck-practices`.
- Record user decisions in 「決めたこと」 in README, with the date and the user's own words, verbatim. Record deferred work in 「残っている課題」.
- Write PR bodies with the sections of `.github/pull_request_template.md`. Paste the commands you ran and their output as-is. In 「レビューで見てほしいところ」, list file:line locations and the judgments you are unsure of, because reviewers, human and AI, start reading there.
- 日本語で書くところは、平易な和文で、言い切りの「〜する」。漢語やカタカナ語より、やさしい言い方を選ぶ（「検証」より「確かめる」、「ルール」より「決まり」）。例外: `/deck-review` を回す単位は「ラウンド」（README の「決めたこと」の 2026-10-19）。

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
- Decide per rule (one bullet) by its main point. When unsure, keep Japanese. Don't mix languages within one sentence. Inside an English sentence, put Japanese examples, values, and section names in 「」 or backticks (write `「修正の指示」 in AGENTS.md`, not `AGENTS.md の「修正の指示」`). Only source tags (such as （見た目 1-7）) and proper nouns (people, books, companies, typefaces) can go unquoted.
- When changing the language, keep rule IDs (such as `[slides-visual-027]`) and section numbers. Refer to sections of English files by their English heading ("Working practices" in `deck-practices/SKILL.md`) and write numbers as `§4`. Refer to sections of Japanese files (README, the install guides in `docs/`, the workspace `AGENTS.md`) by their Japanese heading. Japanese files (templates, script messages) also refer to sections of English files by the English heading. Don't rewrite past entries in 「決めたこと」 in README.
- Don't tell child agents which language to answer in (such as 「日本語で答える」), because the model picks it without being told. What they need is the instruction to copy rule text, user quotes, and sources in their original language.
- Write English as short, plain imperative sentences, and keep the reasons ("because ..."). Use the terms already in the skills: 「構成案」 → the outline, 「子」 → child agent, 「指摘」 → finding, 「修正の指示」 → correction, 「扉」 → section divider, 「一覧の画像」 → contact sheet, 「レビューの観点」 → aspect.

## Public repository

`origin` (`mats16/ai-desktools` on GitHub) is public.

- Keep customer names, the names, URLs, and content of materials, and internal-only information out of commits, PRs, and Issues. In examples, use 「顧客向けの資料」, 「（顧客）」, or 「資料 1」.
- Keep the original checkout (the first line of `git worktree list`) on `main`, and make changes in a worktree, because plugins installed in other workspaces by local path read that checkout.

## Sandbox

Put a test workspace `sandbox/` directly under the worktree, and pass it the worktree's plugin without installing it. `.gitignore` excludes `sandbox/`, so it stays out of commits and goes away with the worktree. [docs/development.md](docs/development.md) covers opening it in Claude Code, Codex, and pi, checking that `rules/` is appended, building materials, and cleanup.

1. **Create.** Run from the worktree root:

   ```sh
   python3 skills/desk-init/scripts/init.py sandbox
   cd sandbox
   python3 ../skills/desk-doctor/scripts/doctor.py --local   # skips the Google APIs
   ```

   With the template `desk.toml`, nothing can be built on Google (doctor keeps reporting `要修正`). To build, copy the production settings (the workspace's `desk.toml`, or `~/.desk.toml`; from `~/.desk.toml`, delete the `workspace` line after copying) and point `[drive]` at a test Drive folder, so production files are never overwritten ("Create the sandbox" in docs/development.md). Don't run `git init` in `sandbox/`.

2. **Run the selftests.** Run in `sandbox/` (`template.py` looks for `desk.toml`), with Python 3.11, the lowest supported version, and with `DESK_CONFIG` empty, so that your own `~/.desk.toml` does not change the results:

   ```sh
   for f in ../hooks/*.py ../skills/*/scripts/*.py ../tests/*/*.py; do
     grep -q -e --selftest "$f" && echo "$f: $(DESK_CONFIG= uv run -q --python 3.11 "$f" --selftest 2>&1 | tail -1)"
   done
   ```

   Every line ends with `selftest ok`. On PRs and pushes to `main`, GitHub Actions (`.github/workflows/selftest.yml`) creates the sandbox on Ubuntu and runs step 2.

3. **Remove.** Go back to the worktree root and run `rm -rf sandbox` (not needed if you delete the whole worktree). What was built on Google Drive and Codex's `CODEX_HOME` remain; remove them as in "Clean up" in docs/development.md.
