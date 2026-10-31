---
name: desk-init
description: Create an AI Desk Tools workspace (the folder that holds materials and rules). Places templates of references_index.md, drive_folders.md, recipes/, and .gitignore, plus Customers/, Internal/, and Research/, and the settings desk.toml in the workspace or in ~/.desk.toml (never overwrites existing files), fills in the settings with the user, and checks with desk-doctor. Also holds the workspace layout (which folder holds what). Use when asked 「ワークスペースを作って」, 「setup して」, or 「AI Desk Tools を使い始めたい」.
---

# Create a workspace

A workspace is the folder that holds the material folders, the rules, and the records `.desk/` (for example `~/Documents`). Its settings `desk.toml` go in one of two places. Scripts and hooks walk up from the current folder and use the first `desk.toml` they find, and its folder is the workspace. If there is none, they read `~/.desk.toml` (or the path in the environment variable `DESK_CONFIG`) and use its `workspace`. They read only the one they find and never merge the two (`lib/desk.py`). What goes where is in "Workspace layout" below; how workspace rules take priority over the plugin is in `desk-feedback` → routing ("Workspace rules").

## Steps

When installing through a conversation (the repository's `INSTALL.md`), step 1 is already done. A conversation that just installed the plugin has not loaded this skill or any other skill, so for other skills (slides-build, desk-doctor), open `skills/<skill>/SKILL.md` in the install location and follow it.

1. **Decide the location.** If not told, ask whether the current folder is fine. Always ask for the workspace folder, because materials must stay in a folder the user sees; never put them in a hidden folder under the home folder. If the folder already has `desk.toml`, tell the user (do not overwrite; place only what is missing).
   - **Where the settings go.** Match how the plugin is installed. Installed only in the workspace (the repository's `INSTALL.md`, `--scope project`, `pi install -l`): in the workspace (`<workspace>/desk.toml`), because only conversations opened there load the plugin. Installed for the whole user: in `~/.desk.toml`, so that a conversation opened in any folder uses this workspace. A second workspace or a test one (`sandbox/`) always gets its own `desk.toml`. If `~/.desk.toml` already exists and points to another workspace, tell the user; there is only one.
2. **Place the files.**
   ```sh
   python3 <this skill's folder>/scripts/init.py <workspace>          # settings in <workspace>/desk.toml
   python3 <this skill's folder>/scripts/init.py <workspace> --user   # settings in ~/.desk.toml, with workspace = "<workspace>"; none in the workspace
   ```
   Relay the 「置いた」 and 「残した」 lines of the output as they are. With `--user`, `init.py` stops if the workspace (or a folder above it) already has `desk.toml` (to move the workspace's own, use desk-migrate's `to-user`), or if `~/.desk.toml` points to another workspace. Without it, `init.py` stops if `~/.desk.toml` points to this folder or one inside it, because a `desk.toml` there would win inside that workspace.
3. **Fill in the settings (`desk.toml`, or `~/.desk.toml`).** Ask one item at a time and write it. Leave unknown items empty; they stay as `要確認` in doctor.
   - `[user] profile`: a file with the user's name, role, and customers in charge.
   - `[desk] default_language`: the language materials are made in (`ja`, `en`, and so on; the template is `ja`). Ask as a multiple-choice question (日本語, English, another language). When installing through a conversation, write the value asked in step 1 of `INSTALL.md`. Each material uses it unless the user names another language for that material.
   - `[google]`: how to get a token. If gcloud is available, have the user run the `gcloud auth application-default login --scopes=…` that doctor prints, once (the user runs it themselves; a browser opens). If another mechanism gets the token, pass it in the environment variable `GOOGLE_OAUTH_ACCESS_TOKEN`. With gcloud's default OAuth client, `quota_project` is also required.
   - `[brand]`: `copyright` (the copyright notice at the bottom left of every page, in the form 「© <年> <社名> All rights reserved.」) is required. Without it, slides, documents, and templates cannot be built. `company` (the company name at the bottom left of the cover) and `logo` (the logo on the document cover; a path inside `assets/` or a URL) are optional.
   - `[drive] shared_themes`: the URL of the company-wide shared theme folder (where an administrator distributes templates). Leave it empty if the company does not distribute one. Once it is written, after `[drive] desk` and Google authentication, run `python3 <slides-build folder>/scripts/slides.py themes`, have the user choose which of the themes marked 「共有。」 to use, and run `python3 <slides-build folder>/scripts/slides.py theme <printed URL>` (copies the theme file `themes/slides/<name>.json` and writes the URL into `[slides.templates]`). If the shared themes are enough, the `--from-base` step below is not needed.
   - `[slides.templates]`: after filling `[drive] desk`, create templates with `python3 <slides-build folder>/scripts/template.py navy --from-base` (also `white` or `blue` if the user wants them). If the user names a template to base it on, pass its URL as `--from-base <base URL>` (it is not kept in `desk.toml`; without it, the template is built from a blank pptx 〔`slides-build` → assets (blank.pptx)〕) (created in Themes under `[drive] desk`). The URL is written into `[slides.templates]`. The colors and descriptions of navy, white, and blue are in the plugin's built-in theme files. To use the company's own template, create it with the skill `slides-build` → templates (`[brand]` and the workspace theme file `themes/slides/<name>.json`. If more than one theme is used, have the user write a `description` for each 〔which materials and audience it is for〕).
   - `[slides] default_theme`: once the two items above have produced templates, ask for the default theme as a multiple-choice question ("Choosing the default theme" in `slides-build` → templates).
   - `[drive]`: the root locations for customer-facing and internal slides and documents.
   - `[review]`: do not ask. Keep the template defaults (the outline review is done by AI; `/deck-review` runs up to 3 rounds). Change only when the user says so.
   - `[feedback.google_comments] watch_hours`: how long to watch comments after delivering a material. When installing through a conversation, write the value asked in step 1 of `INSTALL.md`. Otherwise do not ask; keep the template's 0 (no watching), and change only when the user says so.
   - `[sources]`: tools for gathering material (internal search, chat, meeting records, wiki, customer ledger, spend). Offer candidates from the MCP servers and skills in your own tool list and ask. To make per-tool usage a rule, write it in a recipe for the company's tools (such as `recipes/internal_tools/RECIPE.md`) with frontmatter `description` and `step: gather` (`desk-feedback` → writing recipes).
4. **Create the customers' folders.** Ask for the user's customers and create `Customers/<customer>/` for each ("Workspace layout" below). Ask whether to create a profile for each now; if yes, create it with the skill `customer-profile` (after filling `[sources]`).
5. **Ask whether to use git.** To keep a history of growing rules and checks, run `git init` in the workspace and make the first commit (the placed `.gitignore` includes only the rules, themes, assets, the research log, and an `AGENTS.md` or `CLAUDE.md` the owner writes; the settings hold per-person values and stay out). The user decides whether to push to a remote.
6. **Check.** Run the skill `desk-doctor` and fix until there are 0 `要修正`.

## Workspace layout

```
Customers/<customer>/<content>_<YYYYMM or YYYYMMDD>/  … one customer-facing material per folder (the contents and naming: step 1 of `deck-workflow`)
Customers/<customer>/memory.md                         … that customer's preferences for materials ("Customer memory" in `desk-feedback` → routing)
Customers/<customer>/profile.md                        … that customer's business, organization, technical setup, and engineers' preferences (`customer-profile`)
Internal/<content>_<YYYYMM or YYYYMMDD>/              … internal materials (the same contents as customer-facing ones)
Research/<topic>_<YYYYMMDD>.md                         … research notes (`deck-workflow` → research requests)
Research/deck_research/                                … desk-research's resurvey log (state.md, log/)
recipes/<name>/RECIPE.md                               … the workspace's rules (recipes; `recipes/README.md`, `desk-feedback` → writing recipes)
recipes/<name>/templates/, checks.py                   … the document templates and checks a recipe uses (lint reads the checks)
themes/slides/<name>.json                              … slide themes (the template URLs are in `[slides.templates]` of desk.toml)
assets/                                                … the user's own images ("src": "asset:<name>" in page JSON looks here first)
.desk/                                                 … records the scripts write, and earlier versions of customer profiles. Do not edit by hand
desk.toml                                              … per-person settings (not here when they are in ~/.desk.toml)
references_index.md                                    … the index of sources used before (`refs.py` rebuilds it from each folder's references.md; do not edit by hand)
drive_folders.md                                       … Drive locations and the materials uploaded there (edited by hand)
```

- `Customers/` has one folder per customer company. For a new customer, use a short English name. Internal materials about a customer go in `Internal/`.
- Name files that agents read and write with ASCII letters, digits, hyphens, and underscores only. Deliverables and the files the user reads (`構成案*.md`, `社内メモ_*.md`) keep their Japanese names.
- Do not create files directly under the workspace root other than those above. Put working copies (exported pptx, page images, PDFs for checking) in `/tmp`, and delete them when done; for materials you consulted, write the URL in `references.md` instead of keeping a copy.
- The plugin does not place or read `AGENTS.md` or `CLAUDE.md` in the workspace, and works without them. The owner may write one. Agents load such a file into every conversation and give it more weight than a skill, so a rule there also applies to work it was not written for. Keep rules for making materials in recipes, which the hook shows only in the steps they are for.

## Notes

- The templates are in `templates/`. Do not copy changes made in a workspace back into the templates (the templates are the same starting point for everyone).
- In a workspace that already has a skill with the same name (slides-build, etc.) in `.agents/skills/` or `.claude/skills/`, it is loaded twice along with the plugin's. doctor reports it as `要確認`, so ask the user which one to use.
