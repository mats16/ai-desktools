---
name: build-slides
description: Create, edit, and check Google Slides presentations in Japanese and other languages. Use before writing slides or delivering a deck, and when asked to revise pages, check layout and text, use a company's slide template, create or adjust a theme, or change the default theme. The overall workflow is deck-workflow; visual design is deck-design; documents are build-docs.
---

# Build and check Google Slides presentations

Slides are built directly in Google Slides with the Slides API (switched from pptx on 2026-10-07). To go back to the pptx method, see the workspace's `Archive/pptx_pipeline_20261007/README.md`. This skill is the tool: what the page JSON can say, how to build and check it, and the API's pitfalls. How the work runs (steps 6–8 of a new deck, splitting pages among child agents, reusing internal decks, Drive) is in `deck-workflow`, and how pages should look is in `deck-design` → slides. Documents (Google Docs) are `build-docs`. The parts shared with documents (`gapi.py` for the Google APIs, `textlint.py` for the shared text rules and the run log, `brand.py` for fonts, colors, and the copyright notice, `sheet.py` for contact sheets) are in `scripts/`. This skill owns them: other skills (`build-docs`, `build-vids`, `deck-workflow`, and others) keep byte-identical copies, so fix them here and copy them out with `tests/skills/check.py --sync` in the plugin repository.

Use the available theme fonts for the deck's language. Font choices and text-width estimates have limits; see [template_fonts.md](template_fonts.md). Script paths below are relative to this skill's directory. Resolve them from there when working in another folder.

**Workspace recipes.** The workspace may add to or override this skill in its recipes, which take precedence. Before building, run `python3 scripts/desk.py recipes <material folder>` and open, each whole, the recipes without `step` and with `step: build` whose `description` fits, those the outline's 「使う決まり」 names, and the customer's `memory.md` it names ("Workspace rules" in `desk-feedback` → routing). Skip the ones you already opened in this context.

| What you make | Read before you start writing |
|---|---|
| **Writing pages:** writing or fixing pages | [pages.md](pages.md) (the page JSON), with `deck-design` → slides (how slide pages should look) |
| **Diagrams:** pages with a free-form diagram, arrows, a Gantt chart, a bar chart, or a gridded diagram | [diagrams.md](diagrams.md) (`frame`, `arrow`, `gantt`, `bars`, and the build warnings for positions), in addition to the two above |
| **Samples:** pages that cover the usual ways of writing each component | `samples/json/` (open the page that uses the components you chose; copy the syntax, not the form) |
| **Commands:** editing JSON, building, build warnings, command options | [commands.md](commands.md) |
| **Themes:** choosing, copying, or changing a theme | [themes.md](themes.md) |
| **Images:** images, logos, icons | [images.md](images.md) |
| **Assets:** the reused images, logos, and the blank template (`blank.pptx`), with where each came from | `assets/` (its `README.md`) |
| **Lint:** reading `check_slides.py check` and lint output; the Japanese check on the page JSON (`build_slides.py wording`) and the final gate on the saved deck (`check_slides.py wording`) | [lint.md](lint.md) |
| **Slides API pitfalls:** changing `build_slides.py`, raw requests, unexpected build failures | [api.md](api.md) |
| **Older decks:** decks built with `pages.py`, or pptx from before 2026-10-07 | [legacy.md](legacy.md) |
| **Templates:** creating or adjusting a template from a company template, switching the default theme | [template.md](template.md) |
| **Creating a template:** the three cases (a Japanese template, only an English one, none) | [template_create.md](template_create.md) |
| **Dark themes:** a theme with a dark body background | [template_dark.md](template_dark.md) |
| **Fonts:** choosing or changing the font | [template_fonts.md](template_fonts.md) |
| Steps 6–8 of a new deck (three representative pages, remaining pages, building and checking the whole; decks of 20 pages or fewer also run 7–8) | `deck-workflow` → steps 6–8 for decks |
| Splitting pages among child agents, reusing internal decks, Drive | `deck-workflow` (the page-writing prompt, reusing internal decks, Drive). Reuse uses `scripts/check_slides.py` here for the page list and images of a Google Slides deck, and `keep` and `jp` to make replacement pages |

## Scripts

Run commands from the material's `build/` folder, using the resolved script paths. `<URL>` is the Google Slides URL. More options: [commands.md](commands.md).

| Task | Command and result |
|---|---|
| Create or rewrite pages | Write `deck.json` (page order) and one JSON file per page directly; see [pages.md](pages.md). Then run `python3 scripts/build_slides.py lint` |
| Fix existing JSON | `python3 scripts/build_slides.py patch …` edits the named values and runs lint. Common edits below |
| Find valid keys or inspect positions | `python3 scripts/build_slides.py schema --brief` lists types and keys; `python3 scripts/build_slides.py resolve p05.json` prints resolved positions and values |
| Check without publishing | `python3 scripts/build_slides.py lint [<URL>]` checks local pages changed since the last run. Use the URL when the theme has no local file |
| Check Japanese | `python3 scripts/build_slides.py wording` checks local page text before building; see [lint.md](lint.md) |
| Create the Google Slides file | `python3 scripts/build_slides.py new <Drive folder URL> <YYYYMMDD_name> [--theme <theme>]` makes the first build. Choose a theme from `build_slides.py themes`; tell the user the printed URL (deck-drive-003 in `deck-workflow`) |
| Inspect and publish changes | `python3 scripts/build_slides.py plan <URL>` shows planned changes without writing. `python3 scripts/build_slides.py build <URL>` rebuilds changed pages at checkpoints, keeping the URL; it stops on UI edits |
| Inspect Google's rendering | `python3 scripts/check_slides.py check <URL>` takes changed-page images and runs checks; `--all` takes every page, `--talk` checks a talk. Open the images |
| Confirm saved text | `python3 scripts/check_slides.py wording <URL>` after the last build and check confirms that the saved deck holds the checked text |

### Common JSON edits

Prefer direct JSON and existing tools for edits and checks; custom code usually adds overhead. Choose code when it is more efficient. `patch` edits local JSON; publish with `build` at a checkpoint. A file editor or `sed` also works for simple replacements; run lint after other edits.

Copy the file and path from lint or inspect the page JSON. Array indexes start at 0. Quote paths containing brackets so zsh does not expand them. Replace these example paths and values with the target's.

```sh
# Replace a complete text value; := parses a JSON number, boolean, list, or object
python3 scripts/build_slides.py patch 'p05.json.lead=修正後の文' 'p05.json.body.0.items.0.size:=14'

# Replace a phrase without finding its path; it must occur exactly once in this file
python3 scripts/build_slides.py patch p05.json --replace '変更前の語句' '変更後の語句'

# Insert before body[1], or remove that item (separate examples)
python3 scripts/build_slides.py patch --insert p05.json.body.1 '{"type":"text","text":"補足の文"}'
python3 scripts/build_slides.py patch --delete p05.json.body.1

# Batch known fixes across files with one lint run
python3 scripts/build_slides.py patch 'p05.json.lead=修正後の文' 'p06.json.body.0.size:=14'
```

`=` writes text; `:=` writes a JSON value. A missing final object key is added; an array index equal to its length appends. A missing path or ambiguous `--replace` stops before writing. A write failure or invalid page structure triggers restoration; ordinary lint findings leave the edits for further fixes. Full-file writes, standard input, and restoration limits: slides-command-039 in [commands.md](commands.md). `patch` does not edit older `pages.py` decks.

## Three layers of checks

[slides-flow-005] Split checks into 3 layers, like test layers. Building and taking images are slow, and there is a limit of 60 images per minute, so do not build after every edit; check locally whatever the local lint can catch. Build only at checkpoints, and check things that span pages once per checkpoint. Which steps are checkpoints is in "Overall flow" of `deck-workflow`.

| Layer | When | With | What it checks |
|---|---|---|---|
| unit | After every edit | `build_slides.py lint <URL>` (no build. 2–7 seconds for 53 pages) | Lint on JSON that turns the build requests into the presentations.get shape locally, and build warnings (positions of `frame` diagrams: an arrow line passes over a component, arrowheads gather at one point, components partly overlap. slides-pages-038 in diagrams.md). By default, pages changed since the last run and pages that still had `要修正` (all pages if the deck or the lint rules changed. `--pages 3,5`, `--all`). Deck-wide rules (number of covers, section dividers, conclusion bands, and so on) and the workspace check always look at all pages |
| e2e | When you build at a checkpoint | `build_slides.py build` → `check_slides.py check` | Builds only changed pages, takes images of those pages, and measures the padding inside boxes on the images (box_pad). Writes the changed pages, images, and findings to `changed.json` |
| whole | Once per checkpoint (before `/deck-review`, and so on) | `check_slides.py check --all`, the contact sheet (`sheet.py`), `deck.md` | Things that span pages: drift in size and position of components of the same type (a clear difference a page uses on purpose for emphasis stays; deck-design-007 in `deck-design`), inconsistent naming, the flow of headings |

- **unit:** Findings marked 「（見積もり）」 (a heading or lead on 2 lines, the number of body lines, a line break inside a phrase, a last line of 1–2 characters, overlapping text that overflows its frame, empty space) and build warnings (the table in `commands.md`) use the same character-width estimate as the build, so confirm them on the images. The line-break findings (a break inside a phrase, a last line of 1–2 characters, in frames and table cells) name the `<br>` to put in and matched Google's rendering about 9 times in 10, so fix them in the JSON before building ("Line breaks" in `lint.md`). Everything else is fixed by the JSON and produces the same findings as the lint after building. The padding in boxes measured on images, and the line breaks and image frames that Google renders, cannot be known locally. Child agents that write pages may also run it on their own files (`build_slides.py lint pages_<owner>.json <URL>`. No build).
- **Checkpoints:** when you build the three representative pages, when you build the whole deck for the first time (also once here when you merge the child agents' pages), and when you finish a batch of fixes (such as the fixes from one review round). Do not build between checkpoints. Bring the unit `要修正` to 0 before you build.
- **The parent agent takes the images in one place.** Do not let child agents run `check_slides.py check`. Page images are limited to 60 per person per minute (the same per-minute quota counts your conversation, child agents, and other conversations together). Over the limit you get 429 and stop until the quota frees up. `check_slides.py` counts the images this machine took in the last minute and waits before the limit.
- **Checking changed pages (e2e):** If 1–3 pages changed, the parent agent opens the images in `changed.json` itself without starting child agents. If 4 or more changed, you may split them into groups of a few pages (by chapter, or pages of the same type) and show them to child agents. Do not make one child agent per page (each child agent costs startup and skill loading, and the model API has rate limits). Give the child agent the `changed.json` entries for its pages (the `image`, and the `lint` and `box_pad` findings), `deck.md` (the full text. Without knowing abbreviations and numbers from earlier pages, it gives off-target findings), the outline, and `deck-design` → slides. How to start them and how they reply is the same as the page owners in "How to ask" and "Split and ask in parallel" of `deck-review` → asking (starting a child: `deck-workflow` → child agents). Child agents do not build and do not take images. Have them return suspicions that span pages marked 「全体へ」, and check those in the whole layer.
  - **When you build the whole deck for the first time and go straight into `/deck-review`,** do not open the changed pages one by one at full size. The first round's review child agents (the page owners, if split by page) look at full-size images (`deck-review` → asking, "Split and ask in parallel"). Ask the round-1 children first, right after `check --all` (`deck-workflow` → steps 6–8 for decks, §8); while they look, the parent agent checks the following 3 things and puts the fixes into the page JSON, built together with round 1's fixes. Open at full size only the pages caught by 1 and 3 (you may crop with `sips -c`). This is because full-size images stay in the parent agent's context until summarized ("Basis" below).
    1. Build warnings, and the `要修正` and `要確認` from `check_slides.py check --all` (including padding measured on images)
    2. For decks split among child agents, inconsistencies between child agents found by searching `build/*.json` (drift in `h` and `size` of components of the same type, keeping a clear difference a page uses on purpose for emphasis, slides-visual-057 in `deck-design`; character counts of cards, the 「デッキで共通」 lines and names from the 「書き方の取り決め」 (「書き方の決め」 in outlines written before 2026-11-01) section)
    3. On the contact sheet of all pages (`sheet.py`), drift in size and position of components of the same type (not the clear differences made on purpose for emphasis; deck-design-007 in `deck-design`), density, and color
- **box_pad:** Do not let child agents measure it. Measure it by laying out the pages that `check_slides.py check` took.

Basis: 20% of the time spent making materials went to building and checking, and the median number of builds per deck was 24 (2026-10-15. The workspace's `Internal/deck_speed_20261015/`). We confirmed on 5 past decks (234 findings in total) that the local lint gives the same findings as after building (2026-10-15). A full-size image costs about 1,500 tokens (opening 16 of 25 pages costs about 25,000; 2 contact sheets about 3,000. An estimate).

## Reading the results

- **What each check and lint rule does** is in [lint.md](lint.md). Open it when a finding is unclear.
- **Images:** After building, open the images of the changed pages (`changed.json`), look at them, and fix (the e2e in "Three layers of checks" above. When you build the whole deck for the first time and go straight into `/deck-review`, the review child agents look at full size. slides-flow-005 above). Look for overflow (text is not clipped even when it leaves its frame), overlaps, collisions with the source line or footer, punctuation at the start of a line, last lines of only 1–2 characters, and line breaks inside a word or phrase. Judge the finish by these Google-rendered images.
- **Text:** Read `deck.md` for missing content or wrong order.
- **Japanese:** Once the pages are written, run `build_slides.py wording` and close every finding by fixing it in the page JSON (then run it again), `keep`, or `ask`; it needs no build. After the last build and `check`, run `check_slides.py wording <URL>`: a separate gate that the saved deck holds the checked text (slides-lint-035 in [lint.md](lint.md) → Japanese check).
- **lint:** Bring `要修正` to 0. Check each `要確認` one by one, and either fix it or be able to say why it stays (example: which pages may keep です・ます is in `deck-writing` → content §6).
- **Before delivering:** Review a newly made material as a whole with `/deck-review` (the `deck-review` skill) before returning it to the user. It looks with a separate subagent's eyes and with the contact sheet of all pages. For fixes after delivery, run only the scope decided by deck-flow-017 in `deck-workflow`.
- When checking is done, you may delete `/tmp/slides_<ID>/`. Do not keep it in the material's folder.

## Deliverables

- **Deliver slides as Google Slides and documents as Google Docs (`build-docs`). Do not make PDFs.** Materials that were HTML turned into PDF before delivery (such as customer-facing materials) are kept. Slides before 2026-10-07 are pptx (how to fix them is legacy.md); documents before 2026-10-09 are docx (convert them to Google Docs to fix them. `build-docs` §5).
- **Fonts:** Slides and documents (Google Docs) use Noto Sans JP from Google Fonts (for slides, a theme made from a company template uses that template's font; the lint compares against the font of the template's master. [template_fonts.md](template_fonts.md). Documents stay Noto Sans JP). Only the alphanumerics in code boxes and commands use the monospace Cascadia Mono (`MONO` in `build_slides.py`. `deck-design` → slides §2. 2026-10-09).
- **Text size:** slides-visual-002 and slides-visual-037 in `deck-design` (11pt and up; 9pt only for the footer line, the page number, and supporting text inside a filled shape); what lint reports is in [lint.md](lint.md). Google Slides cannot set a language, so check punctuation at the start of lines on the images (api.md).
- **Names and revisions:** The material name is `<counterpart>_<content>_<date>`. The name on Drive is in `deck-workflow` → Drive. Overwrite revisions in the same file (for slides, the same URL); keep the previous version as `_v2` only when there is a reason. Do not make `.bak` files (except the `pages.py.bak*` that `build_slides.py merge` leaves in `build/`. Delete them when you deliver in step 7 of `/deck-review`).
- Do not edit decks built with `build_slides.py` in the UI. Edit the page JSON (pages.py for older materials) and rebuild (UI edits are lost. If someone edited in the UI, `build_slides.py build` stops. commands.md). For documents, see `build-docs` §4.
- Files that start with `~$` are PowerPoint or Word lock files. They are created while a file is open, so do not touch them.
