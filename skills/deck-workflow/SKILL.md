---
name: deck-workflow
description: How to run the work of making a material (decks and documents) from request to delivery. Holds the overall flow of 11 steps, the working practices that hold at every step, and the files for each step (preparation and the outline, the three representative pages and building a deck, child agents, gathering materials and reusing internal decks, Drive, delivering, requests after delivery, and fixing from comments on a built material and watching for them). What makes a material good is in deck-writing and deck-design; the tools are slides-build and docs-build. Read first when asked 「資料を作って」「構成案を書いて」「このページを直して」「コメントを見て直して」「コメントを見張って」, when the user corrects a material or asks about its content, and after delivering when watch_hours in desk.toml's [feedback.google_comments] is greater than 0.
---

# The flow of making a material

Open this first when making or editing materials, and open the skills `deck-writing` (the brief and the axes for content and wording) and `deck-design` (the principles for how pages look) right after it. They hold what makes a material good and decide what the rules leave open. This skill holds how the work runs: the steps, the order, who does what, and where to stop and ask. It builds on 「いい資料の考え方」 in the root `AGENTS.md`. The ledgers it runs (`ledger.py`, `refs.py`) are in `<plugin>/lib/` (`<plugin>` is the folder that holds `skills/` and `lib/`); its own scripts are `scripts/drive_put.py` and `scripts/comments.py`. [deck-flow-001] Workspace rules (`AGENTS.md`, the recipes in `recipes/` that the hook shows, and the customer's `memory.md`) take precedence over the plugin's skills. When they conflict, follow the workspace. Points the user has not decided yet are marked 「要判断」 in each file.

## Overall flow

If you are only told 「〇〇の資料を作って」 (even without a folder), proceed in order from 1 ("Where each step is" below). Decks and documents are the same. For requests after delivery (corrections, questions, comments), do not run all of 8–11; classify them in [revise.md](revise.md) and run only as far as written there. The human answers only the four questions in 5 (and the outline when `plan_reviewer` is `"human"`) and the list of questions for the user in 10. Once the structure is agreed in 5, run through to 10 without waiting for the user (deck-flow-006 in "Working practices" below).

| Step | What to do | Why it is there (what it prevents) | Who | Condition to move on |
|---|---|---|---|---|
| 1–4 Preparation | Decide the folder; read past materials, internal materials, and customer sources | Do not research the same thing twice. Align with internal wording and messages. Do not use numbers without a source | Parent (heavy reading by child agents) | The sources you read are rows of `references.md` (`refs.py add`) |
| 5 Agreeing on the structure | Confirm the four questions, choose a theme, write the outline | If you get the audience or the question wrong, every later step must be redone. Only here does a human check | Human and parent | The four answers and the outline (for 10 pages or fewer, the four answers and the plan) |
| 5 Plan review | A child agent without the conversation compares the request with the outline | Finds gaps and omissions against the request that the maker does not notice, before building (after building, many pages must be redone) | Child agent (a human for ②) | The findings are reflected in the outline |
| 6 Three representative pages | Build three pages of different types, have a child agent review them, and turn fixes to type and writing into the 「書き方の決め」 section | Defects in the frame and in components (how they look, size) and in writing spread to every page. Find them on three pages before writing the rest | Parent builds, child agent reviews | 「書き方の決め」 is written and applied to the three pages' JSON (the three are not rebuilt) |
| 7 Remaining pages | Write the rest, copying only the frame from the three pages (slides-visual-049 in `deck-design`). Split among child agents if there are many | Shortens writing time. Variation from splitting among child agents is held down by the decisions in 6 and the search in 8 | Parent or child agent | 0 `要修正` from `slides.py lint` on every page |
| 8 Build the whole | Apply 「書き方の決め」 to every page, build, and check with the warnings, a JSON search, and the contact sheet | Missed applications, variation between child agents, size and position drift across pages | Parent | 0 `要修正` from `check --all`; variation fixed |
| 9 `/deck-review` | A child agent without the conversation looks at the whole. Fix, and run rounds (ask, verify the findings, fix, rebuild and check) | Cross-page defects that page-by-page checks miss, and defects the maker overlooks | Child agent and parent | 0 findings to fix, or the round limit |
| 10 Deliver | Return the URL, the findings table, and the list of questions for the user in one message | A human decides, all at once, on what was run through without asking | Parent | Reported |
| 11 Clean up | Fill in the rule ledger and the log; delete working copies | Do not miss routing corrections into rules. Do not leave working copies | Parent | 0 ledger entries whose destination is 「未」 |

- **Decks of 10 pages or fewer:** skip 6, write the whole deck in 7, and continue from 8, both in [slides_steps.md](slides_steps.md). Run the plan review regardless of page count.
- **Documents:** there is no step 6 and no splitting the writing among child agents in 7 (the parent writes the single doc.md). For building and checking, see `docs-build`; the check in 8 is `docs.py check`.
- **The layers of check tools** (`slides.py lint` after every edit, `build` and `check` at checkpoints, a whole-deck pass once per checkpoint) are in slides-flow-005 in `slides-build`. Where in the flow to build is written in each step below.

## Where each step is

Open the file for the step you are on; do not read ahead. Each file holds the steps' rules and their evidence.

| Steps | File |
|---|---|
| **The flow:** the steps 1–11 above and the working practices below | this file |
| **Steps 1–5:** preparation and agreeing on the structure (decks and documents) | [start.md](start.md) |
| **Steps 6–8 for decks:** three representative pages, remaining pages, building the whole | [slides_steps.md](slides_steps.md) |
| **The page-writing prompt:** the request to child agents that write pages (7) | [prompt_pages.md](prompt_pages.md) |
| Writing, building, and checking a document | `docs-build` |
| 9 `/deck-review` | `deck-review` (and the paragraph below) |
| **Delivering** (10–11): delivering, cleaning up, what to keep | [deliver.md](deliver.md) |
| **Child agents:** starting and waiting for any child agent | [agents.md](agents.md) |
| **Requests after delivery:** a correction, question, or comments | [revise.md](revise.md) (classify it first; deck-flow-017) |
| **Comments:** fixing from comments on a built material, watching for comments | [comments.md](comments.md) (fetching, treating them as corrections, replying and resolving) |
| **The comment-watch prompt:** the request to the watcher child agent | [prompt_watch.md](prompt_watch.md) |

**9. Review the whole with `/deck-review` before delivering.** Run it by the steps in `deck-review`, and start pass 2 of the source check together with round 1 (deck-flow-019). Another subagent's eyes and the contact sheet of all pages also catch cross-page defects. Run up to the `[review] deck_review_max_rounds` rounds in `desk.toml` (3 rounds if unset); if fixing increases the defects, revert. After fixing, rebuild decks and documents to the same URL ("Deliverables" in `slides-build`). For decks that went through the three representative pages, write the every-page defects found in the review under 「あと」 in the same section of the three-representative-pages log (if something remained even though it was applied in 8, say so).

## Working practices (every step)

- [deck-flow-006] **Once the structure is agreed in 5, run through to delivery in 10 without waiting for the user.** For items that become 「聞く」 along the way (proposals that change claims, numbers, or order; proposals to add, delete, or split pages; things the rules do not decide), leave that page unchanged, move on, and collect them in the list of questions for the user in 10 (only splitting when something does not fit is applied first; deck-flow-010 below). Before you start writing, open the files in the deck or document row of the table in "What to read when" below.
- [deck-flow-010] **Do not silently change confirmed claims, numbers, or order.** When something does not fit, fit it by rephrasing and diagramming before making the text smaller. If splitting makes it fit, split it, build, and ask in 10 (do not deliver it overflowing). If it does not fit without cutting, leave the page unchanged, move on, and ask about the cut in 10 (AI 実践 1-3).
- **What you edit is the page JSON (for documents, doc.md) and the outline.** For decks, write in `build/deck.json` and one file per page `build/p<number>.json` (slides-pages-034 in `slides-build`), and build to the Drive location with `slides.py` of `slides-build`. Use the JSON components (`slides.py schema`); do not copy from previous materials. Page types (cards, comparisons, number highlights, conclusion bands) are arrangements of the same components; do not make a new component for one page (AI 実践 1-9、研究 1-6). Choose each page's arrangement from what it says (slides-visual-048, 049 in `deck-design`). When you fix something in the Google Slides UI, put the same fix into the page JSON too (rebuilding erases edits made in the UI). For materials previously made with pages.py, edit pages.py (`slides-build` → older decks). For documents, write only the content in markdown in `build/doc.md` and build with `docs.py` of `docs-build` (§1 there).
- **Check locally after every edit; build and look at images at checkpoints.** After every edit, bring the `要修正` of `slides.py lint` to 0; run `slides.py build` and `gslides.py check` only at checkpoints (the three pages in 6, building the whole in 8, after putting in a round's fixes in 9). What each layer checks and who looks at the images: slides-flow-005 in `slides-build`. For documents, `docs.py check` (§3 of `docs-build`). Bring the lint `要修正` to 0; look at each `要確認` and either fix it or be able to say why it stays.
- **When the user gives a correction,** record it and fix it as 「修正の指示」 in AGENTS.md says, and route it on the spot with `desk-feedback` (who the correction is true for, where it goes, and how it is verified).
- **Ask child agents as [agents.md](agents.md) says,** and do work that does not depend on the result while waiting (deck-agents-013 there).
- [deck-flow-005] **If you can call a context-summarizing tool yourself, call it at step boundaries.** If you cannot (some environments only summarize automatically), proceed without calling it. Do not stop to ask the user to summarize (it was recommended but not used). There are four boundaries: after the plan review (before 6), after writing the three-representative-pages log (before building the whole), after checking the fixed pages in each `/deck-review` round (deck-review-013 in `deck-review`), and before delivering to the user (10, and when delivering a request after delivery; deck-flow-017). After delivery there is often a gap until the next request, and the longer the gap, the more context is rewritten (see "Evidence" below). Before calling, write out the decisions, the rejected ideas and why, the sources, the `要確認` items, the list of questions for the user, and the next steps into `構成案*.md` and `社内メモ_*.md` (corrections go in the rule ledger; review findings in deck-review's `$D/review.md`). Write them even without the tool (so they survive automatic summarization). Only the beginning of a tool result may survive the summary. If the tool accepts instructions for after the summary, write where in the steps to resume and which files to re-read (deck-flow-015 below).
  - [deck-flow-015] **After summarizing, re-read only the files the next step needs.** The working folder's `構成案*.md` and `社内メモ_*.md`, the material's findings (`ledger.py list --deck <material folder>`), the customer's `memory.md` and `profile.md` for customer-facing materials, and the section of the step you continue with. Open `references.md` when verifying sources. Do not re-read skill files (writing pages in `slides-build`, slides in `deck-design`, etc.; 10,000–40,000 characters each) or the page JSON in full; find the section you will use next and the pages to fix with `grep -n`, and open those.

Evidence:
- Summarizing: one call takes 9.6 seconds at 100k–200k, 11.7 seconds at 200k–300k, and 17.0 seconds at 300k–400k. Calls at boundaries were mostly after the plan review and before building the whole; they were rarely made in `/deck-review` rounds, and the automatic summary at 400k ran instead. Context that was 80k–90k right after a summary went back to a median of 210k after 30 calls because of bulk re-reading (2026-10-14; 23 pi logs; `Internal/deck_speed_202610/社内メモ_計測の結果.md`, p.7 and p.12 of the slides in the same folder; the earlier study is `Research/pi_compaction_deck_workflow_20261010/README.md`). Summarizing before delivery: of 67 revision requests after delivery, 41 started more than 5 minutes after the previous reply (the prompt cache expires), and the first call rewrote a median of 248k tokens. This rewriting was 24% of the cost of the 67. Summarizing before delivering is expected to save $1.0–1.2 per request (estimate; 2026-10-19; the workspace's `Internal/deck_revision_speed_20261019/`).
- Not waiting for the user: in 12 past approvals, 0 replies touched the content of the three pages (`Research/deck_rep3_approval_sessions_20261009.md`).

## What to read when

Do not wait for skills to be called automatically; open the skill when the situation comes up, and from its `SKILL.md` table the file for your situation. When you open one, the plugin hook then shows the workspace's recipes for that step of the work (workspace-only additions and overrides, which take precedence; the recipes chosen per material come with the outline). In environments where they do not appear, open them yourself (`desk-feedback` → routing and rule IDs, "Workspace rules").

| Situation | Skill (and the topic in its table) |
|---|---|
| Making or editing a material (first) | This skill, then `deck-writing` and `deck-design` |
| Outline and wording | `deck-writing` → content, and the file for the material type that its §1 names (customer-facing, internal, or explaining materials) |
| How pages look | `deck-design` → slides or documents (color, placement, font size, Japanese typesetting; page area, headings, tables and figures) |
| Writing slides | The step you are on in [slides_steps.md](slides_steps.md) (6–8), and `slides-build` → writing pages (JSON), and diagrams for a free-form diagram, arrows, a Gantt chart, a bar chart, or a gridded diagram; commands, themes, images, and older decks when needed |
| Writing a document | `docs-build` (writing doc.md and the check loop; templates, themes, lint, Docs API pitfalls when needed) |
| Building, checking, delivering | `slides-build` (three layers of checks, reading `gslides.py check` and lint, deliverables); for documents, `docs-build` |
| Creating or adjusting a template (from a company template), switching the default theme | `slides-build` → templates |
| Creating or refreshing a customer profile | `customer-profile` (business, organization, technical setup, engineers' preferences; how it differs from memory) |
| **Gathering materials:** sources | [materials.md](materials.md) (search, meeting records, internal chat; the `references.md` ledger) |
| **Reusing internal decks** | [reuse.md](reuse.md) (the four stages, exporting Google Slides and page images) |
| **Drive:** creating, naming, renaming, or uploading files on Drive (slides, documents, html, csv, research notes) | [drive.md](drive.md) (location, name, `drive_put.py`) |
| Review before delivery | `deck-review` |
| Writing or rewriting the voiceover script of a video (the speaker notes of a built deck), only when the user asks (`deck-writing` → content §5; asked while building a deck: deck-flow-022) | `vids-voice` (story across scenes, writing for speech, audio tags, replacing only the notes) |
| Making a Google Vids video from a deck (only when the user explicitly asks, also when building or fixing a deck), or, after the notes of a deck change, updating the video made from it (without asking) | `vids-build` (beta; when to make or update, setup, `create`, `update`, voices) |
| A correction from the user, adding or editing a rule or a recipe | `desk-feedback` (who it is true for, recording and routing, writing recipes) |
| Editing the plugin | `desk-kaizen` (verifying on past materials, and the Issue) |
| desk-doctor reports 「前の版のワークスペース」 | `desk-migrate` |

The history and the sources of the research are in the workspace's `Research/deck_research/log/` (the owner's logs; not included in the plugin). The abbreviations in parentheses in the text point to sections of those logs (the list of abbreviations is at the top of `state.md` in the same folder).

| Abbreviation | Log |
|---|---|
| 中身 | `20261006_jp_content.md` |
| 見た目 | `20261006_jp_visual.md` |
| AI 実践 | `20261006_jp_ai_practice.md` |
| 研究 | `20261006_en_ai_slide_research.md` |
| 仕組み | `20261006_en_skills_instructions.md` |
| 社内 | `20261006_internal_plugins.md` (internal information; do not cite it in customer-facing materials) |

## What not to do

- Do not make slides via HTML, Marp, or Slidev. The quality of the editable slides drops. Using them for drafts or for exploring the look is fine (AI 実践 2 節).
- Do not include slides made with NotebookLM or image generation in deliverables. Every page becomes an image and cannot be edited in Google Slides. When you use them as material, check that their text appears in the `deck.md` of `gslides.py check` (AI 実践 1-8).
- Do not have a model that looks at images score the visual quality. Its correlation with human ratings is low (研究 1-3). Have it list defects.
- Do not use AI design suggestions (such as "Design Ideas" in the official pptx skill) that do not suit Japanese text (`deck-design` → slides §8).
