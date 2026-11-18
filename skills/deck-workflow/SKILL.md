---
name: deck-workflow
description: Run the making of a deck or document from request to delivery (outline, sources, building, review, Drive, fixes after delivery, comments). Open first when asked 「資料を作って」「構成案を書いて」「このページを直して」「コメントを見て直して」「コメントを見張って」, when the user corrects a material or asks about its content, and after delivering if watch_hours in [feedback.google_comments] is above 0. Tools are build-slides and build-docs.
---

# The flow of making a material

**How to open the files of these skills (every host):** open each md whole, one per tool call, with the host's file-reading tool (Claude Code `Read`, pi `read`; in Codex one `exec_command` per file with `max_output_tokens` of 12000 or more). Never put several paths into one code-mode script or `cat a.md b.md`: a tool result is capped at about 10,000 tokens, the later files are cut off, and in six of six runs GPT models did not go back for them. When a result ends with `truncated` or `[Full output: …]`, read the rest with offset/limit before going on.

Open this first when making or editing materials, and open the skills `deck-writing` (the brief and the axes for content and wording) and `deck-design` (the principles for how pages look) right after it. They guide content and design choices. This skill holds the steps, order, roles, and when to stop and ask; its scripts are in "Scripts" below. [deck-flow-001] Workspace rules (the recipes in `recipes/` you open for each step, and the customer's `memory.md`) take precedence over the plugin's skills. When they conflict, follow the workspace. Points the user has not decided yet are marked 「要判断」 in each file.

## Overall flow

If you are only told 「〇〇の資料を作って」 (even without a folder), proceed in order from 1 ("Where each step is" below). Decks and documents are the same. For requests after delivery (corrections, questions, comments), do not run all of 8–11; classify them in [revise.md](revise.md) and run only as far as written there. The human answers only the four questions in 5 (and the outline when `plan_reviewer` is `"human"`) and the list of questions for the user in 10. Once the structure is agreed in 5, run through to 10 without waiting for the user (deck-flow-006 in "Working practices" below).

| Step | What to do | Why it is there (what it prevents) | Who | Condition to move on |
|---|---|---|---|---|
| 1–4 Preparation | Decide the folder; read past materials, internal materials, and customer sources | Do not research the same thing twice. Align with internal wording and messages. Do not use numbers without a source | Parent (heavy reading by child agents) | The sources you read are rows of `references.md` (`refs.py add`) |
| 5 Agreeing on the structure | Confirm the four questions, choose a theme, write the outline | If you get the audience or the question wrong, every later step must be redone. Only here does a human check | Human and parent | The four answers and the outline (for 10 pages or fewer, the four answers and the plan) |
| 5 Plan review | A child agent without the conversation compares the request with the outline | Finds gaps and omissions against the request that the maker does not notice, before building (after building, many pages must be redone) | Child agent (a human for ②) | The findings are reflected in the outline |
| 6 Three representative pages | Build three pages of different types, have a child agent review them, and turn fixes to type and writing into the 「書き方の取り決め」 section | Defects in the frame and in components (how they look, size) and in writing spread to every page. Find them on three pages before writing the rest | Parent builds, child agent reviews | 「書き方の取り決め」 is written and applied to the three pages' JSON (the three are not rebuilt) |
| 7 Remaining pages | Write the rest, copying only the frame from the three pages (slides-visual-049 in `deck-design`). Split among child agents if there are many | Shortens writing time. Variation from splitting among child agents is held down by the decisions in 6 and the search in 8 | Parent or child agent | 0 `要修正` from `build_slides.py lint` on every page |
| 8 Build the whole | Apply 「書き方の取り決め」 to every page, build, and check with the warnings, a JSON search, and the contact sheet | Missed applications, variation between child agents, size and position drift across pages (not differences made on purpose for emphasis) | Parent | [deck-flow-023] `build_slides.py wording` 「済み」 on the page JSON before building; 0 `要修正` from `check --all`; variation fixed |
| 9 `/deck-review` | A child agent without the conversation looks at the whole. Fix, and run rounds (ask, verify the findings, fix, rebuild and check) | Cross-page defects that page-by-page checks miss, and defects the maker overlooks | Child agent and parent | Fixed pages checked on their images; a new round only when that is not enough (deck-review-006), up to the limit; the Japanese check 「済み」 again after each round's fixes |
| 10 Deliver | Return the URL, the findings table, and the list of questions for the user in one message | A human decides, all at once, on what was run through without asking | Parent | Reported; just before, `check_slides.py wording <URL>` 「済み」 (the saved material holds the checked text; documents: `docs.py wording`) |
| 11 Clean up | Fill in the rule ledger and the log; delete working copies | Do not miss routing corrections into rules. Do not leave working copies | Parent | 0 ledger entries whose destination is 「未」 |

- **Decks of 20 pages or fewer:** skip 6, write the whole deck in 7, and continue from 8, both in [slides_steps.md](slides_steps.md). Run the plan review regardless of page count.
- **Documents:** there is no step 6 and no splitting the writing among child agents in 7 (the parent writes the single doc.md). For building and checking, see `build-docs`; the checks in 8 are `docs.py check` and `docs.py wording` (on the saved document).
- **The layers of check tools** (`build_slides.py lint` after every edit, `build` and `check` at checkpoints, a whole-deck pass once per checkpoint) are in slides-flow-005 in `build-slides`. Where in the flow to build is written in each step below.

## Where each step is

Open the file for the step you are on; do not read ahead. Each file holds the steps' rules and their evidence.

| Steps | File |
|---|---|
| **The flow:** the steps 1–11 above and the working practices below | this file |
| **Steps 1–5:** preparation and agreeing on the structure (decks and documents) | [start.md](start.md) |
| **Steps 6–8 for decks:** three representative pages, remaining pages, building the whole | [slides_steps.md](slides_steps.md) |
| **The page-writing prompt:** the request to child agents that write pages (7) | [prompt_pages.md](prompt_pages.md) |
| Writing, building, and checking a document | `build-docs` |
| 9 `/deck-review` | the `deck-review` skill (and the paragraph below) |
| **Delivering** (10–11): delivering, cleaning up, what to keep | [deliver.md](deliver.md) |
| **Child agents:** starting and waiting for any child agent | [agents.md](agents.md) |
| **Requests after delivery:** a correction, question, or comments | [revise.md](revise.md) (classify it first; deck-flow-017) |
| **Comments:** fixing from comments on a built material, watching for comments | [comments.md](comments.md) (fetching, treating them as corrections, replying and resolving) |
| **The comment-watch prompt:** the request to the watcher child agent | [prompt_watch.md](prompt_watch.md) |
| **Step records:** recording what a piece of work did in its own scope, and reading back where the material stands and the next step after a summary | [progress.md](progress.md) (`flow.py record`, the fields, when a record helps, the evidence for summarizing) |

**9. Review the whole with `/deck-review` (the `deck-review` skill) before delivering.** Run it by the steps in `deck-review`, and start pass 2 of the source check together with round 1 (deck-flow-019). Another subagent's eyes and the contact sheet of all pages also catch cross-page defects. Ask round 1 right after the first whole `check --all` (slides_steps.md §8). Run up to `[review] deck_review_max_rounds` rounds (3 if unset), a new one only when needed (deck-review-006); if fixing increases the defects, revert. After fixing, rebuild decks and documents to the same URL ("Deliverables" in `build-slides`). For decks that went through the three representative pages, write the every-page defects found in the review under 「あと」 in the same section of the three-representative-pages log (if something remained even though it was applied in 8, say so).

## Scripts

Paths are relative to this skill's folder. Run in the workspace (`comments.py` in the material folder).

| Task | Command and result |
|---|---|
| Open the workspace's rules for a step | `python3 scripts/desk.py recipes <material folder>` names the recipes, 「使う決まり」, and `memory.md` to open |
| See where a material stands | `python3 scripts/flow.py <material folder>` prints each step's state and the next step; `flow.py record <material folder> <step> <status> [--files …] [--out …] [--note …]` adds a record ([progress.md](progress.md)) |
| Record a source | `python3 scripts/refs.py add <material folder> <URL, meeting ID, or path>` adds a row to `references.md` and prints its S-ID; `seen <material folder> <S-ID>…` marks re-read ones ([materials.md](materials.md)) |
| Check the sources | `python3 scripts/refs.py check <material folder> [--fetch]` lists errors (exit 1), unverified, stale, and updated rows; `--fetch` before delivering |
| Upload html or csv to Drive | `python3 scripts/drive_put.py <file> <folder URL or ID> <YYYYMMDD_name>` overwrites the same name or creates it ([drive.md](drive.md)) |
| Read, answer, or watch comments | `python3 scripts/comments.py <URL>` lists unresolved comments (`--new`: new only); `reply <URL> <comment ID> <text> [--resolve]`; `watch-prompt <URL>` ([comments.md](comments.md)) |

## Working practices (every step)

- **The outline's 「書き方の取り決め」 section** is called 「書き方の決め」 in outlines written before 2026-11-01. Read and update it under either name, and do not add a second section.
- [deck-flow-006] **Once the structure is agreed in 5, run through to delivery in 10 without waiting for the user.** For items that become 「聞く」 along the way (proposals that change claims, numbers, or order; proposals to add, delete, or split pages; things the rules do not decide), leave that page unchanged, move on, and collect them in the list of questions for the user in 10 (only splitting when something does not fit is applied first; deck-flow-010 below). Before you start writing, open the files in the deck or document row of the table in "What to read when" below.
- [deck-flow-010] **Do not silently change confirmed claims, numbers, or order.** When something does not fit, fit it by rephrasing and diagramming before making the text smaller. If splitting makes it fit, split it, build, and ask in 10 (do not deliver it overflowing). If it does not fit without cutting, leave the page unchanged, move on, and ask about the cut in 10 (AI 実践 1-3).
- **What you edit is the page JSON (for documents, doc.md) and the outline.** For decks, write in `build/deck.json` and one file per page `build/p<number>.json` (slides-pages-034 in `build-slides`), and build to the Drive location with `build_slides.py` of `build-slides`. Use the JSON components (`build_slides.py schema`); do not copy from previous materials. Page types (cards, comparisons, number highlights, conclusion bands) are arrangements of the same components; do not make a new component for one page (AI 実践 1-9、研究 1-6). Choose each page's arrangement from what it says (slides-visual-048, 049 in `deck-design`). When you fix something in the Google Slides UI, put the same fix into the page JSON too (rebuilding erases edits made in the UI). For materials previously made with pages.py, edit pages.py (`build-slides` → older decks). For documents, write only the content in markdown in `build/doc.md` and build with `docs.py` of `build-docs` (§1 there).
- **Check locally after every edit; build and look at images at checkpoints.** After every edit, bring the `要修正` of `build_slides.py lint` to 0; run `build_slides.py build` and `check_slides.py check` only at checkpoints (the three pages in 6, building the whole in 8, after putting in a round's fixes in 9). What each layer checks and who looks at the images: slides-flow-005 in `build-slides`. For documents, `docs.py check` (§3 of `build-docs`). Bring the lint `要修正` to 0; look at each `要確認` and either fix it or be able to say why it stays.
- **When the user gives a correction,** record it, fix it, and route it on the spot as `desk-feedback` says (recording a correction; who it is true for, where it goes, and how it is verified).
- **Read rule files one per call** (the opening of this file). Data may be read in bulk.
- **Ask child agents as [agents.md](agents.md) says,** and do work that does not depend on the result while waiting (deck-agents-013 there).
- [deck-flow-005] **If you can call a context-summarizing tool yourself, call it at step boundaries.** If you cannot (some environments only summarize automatically), proceed without calling it. Do not stop to ask the user to summarize (it was recommended but not used). There are four boundaries: after the plan review (before 6), after writing the three-representative-pages log (before building the whole), after checking the fixed pages in each `/deck-review` round (deck-review-013 in `deck-review`), and before delivering to the user (10, and when delivering a request after delivery; deck-flow-017). After delivery there is often a gap until the next request, and the longer the gap, the more context is rewritten ("Evidence" below). Before calling, write out the decisions, the rejected ideas and why, the sources, the `要確認` items, the list of questions for the user, and the next steps into `構成案*.md` and `社内メモ_*.md` (corrections go in the rule ledger; review findings in deck-review's `$D/review.md`). Write them even without the tool (so they survive automatic summarization). A step record survives the same way, and `flow.py` derives the next step from the records (step records). Only the beginning of a tool result may survive the summary. If the tool accepts instructions for after the summary, write where in the steps to resume and which files to re-read (deck-flow-015 below).
  - [deck-flow-015] **After summarizing, re-read only the files the next step needs.** The working folder's `構成案*.md` and `社内メモ_*.md`, the material's findings (`python3 scripts/ledger.py list --deck <material folder>`, a copy of `desk-feedback`'s), the customer's `memory.md` (any material under `Customers/`) and `profile.md`, the recipes for the next step ("What to read when"), and the section of the step you continue with. Open `references.md` when verifying sources. Do not re-read skill files (writing pages in `build-slides`, slides in `deck-design`, etc.; 10,000–40,000 characters each) or the page JSON in full; find the section you will use next and the pages to fix with `grep -n`, and open those. `flow.py <material folder>` ("Scripts") tells in one call where the work stood and the next step, without reading the outline and the page JSON through; only a record can tell the planned page count or which URL is the built material (step records).

Evidence: for summarizing (the time per call, re-reading after a summary, the cost before delivery), "Evidence for summarizing" at the end of [progress.md](progress.md); for not waiting for the user, the "Evidence" paragraph after the three representative pages (slides-flow-007) in [slides_steps.md](slides_steps.md).

## What to read when

Do not wait for skills to be called automatically; open the skill when the situation comes up, and from its `SKILL.md` table the file for your situation. When you start or resume work on a material (new conversation, after summarizing), open what `desk.py recipes <material folder>` ("Scripts") names for the step; they take precedence.

| Situation | Skill (and the topic in its table) |
|---|---|
| Making or editing a material (first) | This skill, then `deck-writing` and `deck-design` |
| Outline and wording | `deck-writing` → content, and the file for the material type that its §1 names (customer-facing, internal, or explaining materials) |
| How pages look | `deck-design` → slides or documents (color, placement, font size, Japanese typesetting; page area, headings, tables and figures) |
| Writing slides | The step you are on in [slides_steps.md](slides_steps.md) (6–8), and `build-slides` → writing pages (JSON), and diagrams for a free-form diagram, arrows, a Gantt chart, a bar chart, or a gridded diagram; commands, themes, images, and older decks when needed |
| Writing a document | `build-docs` (writing doc.md and the check loop; templates, themes, lint, Docs API pitfalls when needed) |
| Building, checking, delivering | `build-slides` (three layers of checks, reading `check_slides.py check` and lint, deliverables); for documents, `build-docs` |
| Creating or adjusting a template (from a company template), switching the default theme | `build-slides` → templates |
| Creating or refreshing a customer profile | `customer-profile` (business, organization, technical setup, engineers' preferences; how it differs from memory) |
| **Gathering materials:** sources | [materials.md](materials.md) (search, meeting records, internal chat; the `references.md` ledger) |
| **Reusing internal decks** | [reuse.md](reuse.md) (the four stages, exporting Google Slides and page images) |
| **Research requests:** a request that makes no material (「〇〇を調べて」) | `desk-research` → research requests |
| **Drive:** creating, naming, renaming, or uploading files on Drive (slides, documents, html, csv, research notes) | [drive.md](drive.md) (location, name, `drive_put.py`) |
| Review before delivery | `deck-review` |
| Writing or rewriting the voiceover script of a video (the speaker notes of a built deck), only when the user asks (`deck-writing` → content §5; asked while building a deck: deck-flow-022) | `build-vids` → voiceover scripts (story across scenes, writing for speech, audio tags, replacing only the notes) |
| Making a Google Vids video from a deck (only when the user explicitly asks, also when building or fixing a deck), or, after the notes of a deck change, updating the video made from it (without asking) | `build-vids` (beta; when to make or update, setup, `create`, `update`, voices) |
| A correction from the user, adding or editing a rule or a recipe | `desk-feedback` (who it is true for, recording and routing, writing recipes) |
| Editing the plugin | `desk-kaizen` (verifying on past materials, and the Issue) |
| `doctor.py` (desk-init) reports 「前のバージョンのワークスペース」 | `desk-migrate` |

The abbreviations in parentheses (見た目 1-7, AI 実践 1-3, …) point to sections of the owner's research logs; the list is at the end of [start.md](start.md).

## What not to do

- Do not make slides via HTML, Marp, or Slidev. The quality of the editable slides drops. Using them for drafts or for exploring the look is fine (AI 実践 2 節).
- Do not include slides made with NotebookLM or image generation in deliverables. Every page becomes an image and cannot be edited in Google Slides. When you use them as material, check that their text appears in the `deck.md` of `check_slides.py check` (AI 実践 1-8).
- Do not have a model that looks at images score the visual quality. Its correlation with human ratings is low (研究 1-3). Have it list defects.
- Do not use AI design suggestions (such as "Design Ideas" in the official pptx skill) that do not suit Japanese text (`deck-design` → slides patterns §8).
