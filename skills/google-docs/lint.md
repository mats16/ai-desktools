# lint and the image measurements for documents

Open when you read the output of `docs.py check`, or when deciding whether a `要確認` may stay.

## What docs.py check does

1. Writes the `documents.get` JSON to `/tmp/docs_<first 8 chars of the ID>/doc.json`
2. Writes the text to `text.md` (headings as `#`, each table row joined with ` | `, images as `［画像］`. Passed to reviews)
3. Runs `lint_gdoc` in `doc_lint.py` on the JSON ("lint (Docs rules)" below)
4. Saves Drive's PDF export (the pages Google rendered) as `doc.pdf` and page images as `p-N.png` (110 dpi. 910 × 1286 for A4)
5. `doc_layout.py` measures the layout from line positions in the PDF (`bbox.html` from `pdftotext -bbox-layout`) and the images ("What is measured on images" below)
6. Prints the fonts used in the PDF (Arial for bullet symbols and numbers is fine, because the API cannot change it)
7. **Matching doc.md against the built document** (turns the doc.md in the current folder and the built document's JSON into the same one-element-per-line form and compares them. `canon_doc`, `canon_json`): paper and margins, named styles (font, size, bold, color), order and kind of blocks (headings, paragraphs, source lines, quotes, bullet levels and numbering, table size and column widths, cells, figure widths, figure and table titles, code, page breaks, cover), and text, bold, links, and code. Differences are `要修正`. The cause is one of: not rebuilt, edited in the UI, or docs.py's building is broken. Rebuild, or fix docs.py
8. **Matching against the template** (when the header has `template:`. [templates.md](templates.md)). Missing sections, table columns, cover, theme, and leftover tags and notes are `要修正`; section order and added sections are `要確認`
9. **Comparing the skeleton with the original document** (when the header has `source:`. Run in the template's folder). Differences are `要確認` (only counts for sections listed in `skeleton_ok:`)

[docs-write-004] If the lint or matching has `要修正`, it returns exit 1. If the doc.md to match against is not in the current folder, it is looked up from the folder that `docs.py build` recorded in the document (`docs_py_src` in Drive's appProperties. A path relative to Documents). So 7–9 run no matter where you run it from, as with `/deck-review`. If it is not found, or the doc.md `name` is not in the document's name, it reports that matching was not done.

## lint (Docs rules)

The content and sources of the rules are in `deck-design` → documents and `deck-writing` → content. They are `lint_gdoc` in `scripts/doc_lint.py`; the text rules shared with slides are in `scripts/textlint.py` (a copy; the owner is `google-slides`).

- **List of headings and first sentences of paragraphs:** Lays out the headings by level and lists the first sentence of each paragraph. Check that the story holds with headings alone, and that reading the first sentences in order gives a summary (`deck-design` → documents §3). It also prints the **body character count** and **characters per line**.
- **`要修正` (exit 1):** emoji, long dashes, leftover placeholders, replacement tags, fonts other than the theme's font (default Noto Sans JP) (monospace fonts for code pass), Japanese in the monospace font, paper that is not A4, links with tracking markers (`utm_source=`), Japanese periods (「。」) in headings (including mid-sentence ones), and headings and titles that end in 「〜ください」「〜します」 (`deck-design` → documents §2).
- **Wording `要確認` (deck-lint-027, from yomiyasu's lint):** the same as for slides except 「見出しと箇条の間の読点」: 「動詞を名詞にした語」, 「直訳の語」, and 「たとえの動詞」. Quotes, code, and source lines are not checked. How to rewrite them is deck-content-065 in `deck-writing` → content.
- **`要確認`:** text under 9pt (as for slides, whether it is wrong depends on the place), the same text rules as for slides (empty phrases, fear-mongering, missing spaces between Japanese and Latin text, spaces around punctuation marks, leftover 「要確認」 or TBD, confidentiality labels, and so on), source lines without links, and numbers not in the 「出典の表」 (`出典の表にない数字`, deck-lint-026; when `docs.py check` runs with the document's folder). Document-only ones (values and sources in `deck-design` → documents):
  - Sentences: mixed writing style (「です・ます」 and 「だ・である」 at sentence ends in body paragraphs. Reports the less frequent one), sentences over 100 characters, paragraphs of 9 or more sentences, a page area with more than 40 characters per line
  - Headings: skipped levels, level 4 or deeper, only one child, duplicates, bold inside headings, headings with no content, bold paragraphs used instead of headings, titles ending in 「について」, a first chapter that is not a summary, a trailing 「まとめ」
  - Tables and figures: missing table or figure titles, figures wider than the body, sections (per H1 and H2) whose numbers have no source link
  - Habits typical of AI-made documents (Docs 1-15): too much bold (more than 3 places per 1,000 body characters), bullets that start with bold and a colon, sentences that end in a colon, lists with only one item, mixed use of periods across bullets, runs of empty paragraphs
- Slide-only rules (「です・ます」, 8 body lines, conclusion band, notes, section dividers) are not checked.
- [docs-lint-005] **Do not report what the template or theme decides** (it would appear every time and people would learn to skip it): 「冒頭に要旨がない」 for documents written from a template and for template samples (doc.md header has `template:` or `source:`) (the template decides the section order), 「1 行の字数が多い」 for themes on paper other than A4 (`page` in `themes/docs/<name>.json`), and 「図の題がない」 for a figure directly followed by a page break (the cover logo).
- **Log:** Written to the same `.desk/lint_runs.jsonl` as for slides, and counted with `textlint.py --stats` (in `scripts/`) (step 5 of `desk-dreaming` → running). Documents whose names contain tmp, 「作業用」, or 「テンプレート」 are not logged.

## What is measured on images (doc_layout.py)

The JSON does not tell where pages break or where lines wrap. These are measured on the Google-rendered PDF and reported as 「要確認（画像で測った）」.

- **Heading at the end of a page:** Headings use the "keep with next" style, so if this appears, the formatting has come off.
- **Punctuation at the start of a line:** Google Docs pushes it to the next line together with the preceding character, so it usually does not appear. If it does, suspect the font or the paragraph formatting.
- **Last lines of only 1–2 characters:** Only short paragraphs (up to 80 characters) such as headings, figure and table titles, and table cells are checked. Do not fix the last line of body paragraphs (`deck-design` → documents §5).
- **Overflow into the margins:** Anything drawn in the left or right margin (30 mm). Tables with fixed widths, large figures, the left line.
- **Pages with empty space at the bottom:** Pages where the bottom 30% or more of the body area is empty (except the last page and pages whose next page starts with H1). Suspect a table or figure pushed to the next page.

## Japanese check (docs.py wording)

[docs-lint-020] **After a document is built, check its Japanese on the saved document, fix it in doc.md, and check again.** It is the same check as for slides (`wording.py` is a copy; the owner is `google-slides`): writing-time rules and the review left 56–68% of the wording findings undecided until the last check (2026-11-04 in `docs/decisions.md`). Unlike slides, which are checked on the page JSON before building, a document is checked on the saved document (`documents.get`), because there is no way to turn doc.md into that form without Google; doc.md stays markdown. So one run records both facts that slides keep apart, the check and the match with the saved document, with the same reasons not to pass, and a fix made only in doc.md and never built does not pass.

```sh
cd <folder>/build
python3 $K/docs.py check <URL>      # first: the page images of the built document (the check stops without them)
python3 $K/docs.py wording <URL>    # the Japanese check. exit 1 until 「済み」. Writes <folder>/wording.json
python3 $K/wording.py keep <folder> <W…> … --why <reason>      # keep a finding unchanged
python3 $K/wording.py ask  <folder> <W…|R…> … --why <question> # leave it to the user (the questions at delivery)
python3 $K/wording.py ok   <folder> <R…> … --why <reason>      # a meaning risk you checked and intended
```

- **What it reads:** the paragraphs the lint's wording rules read (headings, body, list items, table cells), one at a time. Not read: quotes and code (paragraphs with a left border or shading), source lines, text without Japanese, URLs, and anything inside 「」『』“”.
- **Rules (deck-lint-028):** the three yomiyasu rules for documents (「動詞を名詞にした語」, 「直訳の語」, 「たとえの動詞」) and the Japanese text rules of `textlint.py` (「空疎な言い回し」, 「あおり」, 「和欧間のスペース抜け」, 「約物の前後のスペース」). Each finding has an ID (`W…`), the paragraph, and the line of `build/doc.md`.
- **The loop:** fix doc.md (rewrite who does what, deck-content-065 in `deck-writing`; keep the claim, numbers, conditions, negation, certainty, quotes, proper nouns, code, and URLs; `ask` when the only rewrite changes what the document says), `docs.py build`, `docs.py check` (look at the pages: a rewrite can move a page break), `docs.py wording` again.
- **Meaning risks, 「済み」, decisions, the limit of 2 rewrites, and the record** work as for slides (`google-slides` → lint, "Japanese check"): risks `R…` (protected words, yomiyasu_diff's meaning risks, and 「書き換えた文を読み比べる」 for a text whose 〔書き換え〕 finding went away) compare with the last accepted text and stay until reverted or `ok`ed; 「済み」 needs no open finding or risk and no reason not to pass (the document was edited in the UI after `docs.py build`, `docs.py check` has not seen the built body, or doc.md has edits that were not built: the same match against the built document as `docs.py check`); decisions are tied to the hash of the text; `flow.py` of `deck-workflow` shows the check and the match with the saved document (「未実施」, 「古い」 when doc.md changed after the run, 「通らない」).
