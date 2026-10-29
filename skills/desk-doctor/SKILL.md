---
name: desk-doctor
description: Check the prerequisites for running AI Desk Tools. Looks at Python and uv, which settings file and workspace are used (desk.toml in the workspace, or ~/.desk.toml), AGENTS.md, overlapping skills, Google authentication (a token in an environment variable or a credentials JSON), whether templates and Drive folders are reachable, and the MCP servers for gathering material, and prints how to fix each problem. Use after desk-init, in a new environment, on 401 or 403, when 「desk.toml が見つからない」 appears, or when asked 「環境を確かめて」 or 「doctor して」.
---

# Check the prerequisites

```sh
cd <workspace>
python3 <this skill's folder>/scripts/doctor.py          # local and Google APIs
python3 <this skill's folder>/scripts/doctor.py --local  # local only (does not call APIs)
```

Prints one item per line as 「OK」, 「要修正」, or 「要確認」. Exits 1 if there is at least one `要修正`.

## What it checks

| Item | What to do on `要修正` or `要確認` |
|---|---|
| Python 3.11 or later, uv | Install them. Without uv, the image measurements (`box_pad.py`, `doc_layout.py`, `sheet.py`) and lint's phrase-break check (BudouX) do not run |
| `desk.toml`, `AGENTS.md` (`CLAUDE.md`, `references_index.md`, `drive_folders.md`) | Place them with desk-init (a hand-written `references_index.md` from before 2026-10-29 is split by desk-migrate) |
| 「設定」, 「ワークスペース」 | Always `OK`: the settings file and the workspace in use. The first `desk.toml` found walking up from the current folder, else `~/.desk.toml` (the path in `DESK_CONFIG` if set) and its `workspace` |
| 「個人の設定」 | `~/.desk.toml` cannot be read, has no `workspace`, or its folder does not exist. Fix the file. `要修正` when this workspace uses it; `要確認` when this workspace has its own `desk.toml` (conversations opened in other folders stop) |
| 「設定が 2 つ」 | The workspace in `~/.desk.toml`, or a folder above it, has `desk.toml`, so conversations read different settings inside and outside it. Ask the user which to keep: merge the values into `~/.desk.toml` and move that `desk.toml` to `.desk/migrate/` (step 2 of "Move the settings to `~/.desk.toml`" in `../desk-migrate/SKILL.md`; `to-user` refuses because `~/.desk.toml` exists), or delete `~/.desk.toml` |
| 「前の版のワークスペース」 | The workspace is still in the form of an earlier version: `factory.toml` or `.factory/` (names before 2026-10-25), or skill names, file paths, or rule IDs in `rules/` or the ledger from before 2026-10-24, or `rules/` files without frontmatter (before 2026-10-27), or a `rules/` folder at all (before 2026-10-29; rules are now `recipes/<name>/RECIPE.md`). Run desk-migrate (`../desk-migrate/SKILL.md`); write the frontmatter by hand for the files it marks 「要判断」 |
| 「ワークスペースの決まり」 | A recipe still has `paths` (the earlier form: write `step: gather` or `step: build`, or nothing for every step), `step` or `targets` or `audience` has an unknown value, a recipe has both `per_material` and `step`, a `RECIPE.md` is over `RULE_MAX` (split it by a narrower purpose), sits in a folder named after a skill or inside another recipe's folder, or has no `description`, or an `.md` under `recipes/` is not in a recipe's folder (`../desk-recipes/SKILL.md`). "Workspace rules" in `../deck-practices/rules.md` |
| `desk.source` | No longer used (desk-kaizen clones by itself). Tell the user and remove it |
| Overlapping skills | The workspace's `.agents/skills/` or `.claude/skills/` has a skill with the same name. It is loaded twice along with the plugin's, so ask the user which one to use (the user decides whether to remove the workspace's copy) |
| `google.quota_project`, `slides.templates`, `drive.*` | Fill them in as in desk-init step 3 |
| `slides.themes` (the format of an earlier version) | Move the theme table to the workspace's `themes/slides/<name>.json` (`kind: theme`; write the colors under `colors` with the same names, and do not write `url`), move `url` to 「<名前> = "<url>"」 in `[slides.templates]`, and delete the table. Names that have a template can also be copied with `slides.py theme <url>` (templates from before 2026-10-16 lack the colors not stored in the theme, `copyright`, `mono`, and `description`, so copy those from the table). Before moving, ask the user where to keep the history left in the table's comments (JSON cannot hold comments) |
| `themes/slides/<name>.json`, theme files, `slides.default_theme` | For invalid values, fix the reported location and check with `slides.py lint <file>`. For a theme that has a template but no file, copy it with `slides.py theme <URL>` |
| Theme descriptions | A theme without `description` cannot be chosen per material by the agent. Write what the theme is and which materials and audience it is for (`slides-build/themes.md`) |
| `review.*`, the plan review and post-delivery fixes in AGENTS.md | Fix `review.*` to values within the template's range (`"ai"`, `"human"`, 1 to 3). If AGENTS.md still contains the earlier template's 「人がレビューするかも選んでもらう」 or 「ユーザーに返す前に、スキル `deck-review` で全体をレビューする」, show it to the user and then replace it with the current template text (follow `[review] plan_reviewer`; newly created materials use `deck-review`, and after delivery use `deck-practices/revise.md`) (it is a workspace rule, so do not change it silently) |
| Google authentication | Have the user run the printed command (`gcloud auth application-default login --scopes=…`). How to get a token is in the comments of `[google]` in `desk.toml` |
| Templates and Drive folders | Anything that cannot be opened has a wrong URL or is not shared. Ask the owner to share it, or fix the URL |

## What to check outside the script

The script cannot see whether the tools for gathering material (`deck-practices/materials.md`) are available. Check whether each tool written in `[sources]` of `desk.toml` (an MCP server or skill name) is in your own tool list, and return the missing ones together as `要確認`. If `[sources]` is empty, ask the user which tools to use and write them. Materials can be built without them, but gathering material becomes manual.

## How to reply

Return the `要修正` and `要確認` items together with how to fix them. Separate what the user runs (login commands, share requests) from what you can fix (values in `desk.toml`). After fixing, run it again.
