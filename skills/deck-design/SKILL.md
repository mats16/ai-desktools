---
name: deck-design
description: Design knowledge for materials (decks, documents) - how a page looks. Principles from design experts (search for the design that best expresses what the page most wants to say, emphasis is relative, same or clearly different, the smallest effective difference, grouping by space, the glance test) and the best practices that follow from them (the focal point, categories and the accent, form per page and frame across pages, means of emphasis, hierarchy, color, surfaces, arrows), with the few instructions that remain (what the components and lint decide, and the order of precedence). Read before writing pages, before reviewing, and when a visual choice is not decided by a rule. Content and wording are in deck-writing. deck-workflow opens both first; child agents that write pages or review get both paths.
---

# Design knowledge

Serve the brief in `deck-writing` ("The brief": the reader gets each page's point before the details). deck-writing decides what the reader must grasp and which relationships must be seen; this file is the knowledge for how to show them. The values of one format (theme colors, sizes, positions) are in `slides.md` and `docs.md`.

This file gives knowledge, not recipes. Decide each page from the principles and the reasons below; they explain why, so that you can handle what they do not name. A practice applied to every page without a reason becomes a pattern, which is the habit they warn against.

## Design principles

1. [deck-design-005] **Search for the design that best expresses what the page most wants to say.** Start from the one sentence the page says. Think of several ways to show it (a figure, a chart, a table, a comparison, one large number, a screenshot, plain text), and keep the one a first-time reader gets fastest, not the first that came to mind or the easiest to build (Nancy Duarte, *slide:ology*: sketch many ideas before building slides, and choose the one that communicates best). Every principle below serves this one.
2. [deck-design-006] **Emphasis is relative.** Something stands out only by differing from what is around it, so every added emphasis weakens the others. The strongest pop-out is one object that differs from all the others (Colin Ware, *Visual Thinking for Design*), and highlighting is diluted as the share of highlighted things grows (Cole Nussbaumer Knaflic, *Storytelling with Data*). To make something stand out, first quiet what competes with it, before making it louder (Wathan and Schoger, *Refactoring UI*: "emphasize by de-emphasizing").
3. [deck-design-007] **Make things the same, or clearly different.** Things with the same role look the same; things with different roles differ clearly. A difference that is only slight looks like a mistake (Robin Williams, *The Non-Designer's Design Book*: contrast).
4. [deck-design-008] **Use the smallest difference that still works.** Borders, rules, fills, and arrows support the content. Make each as quiet as it can be while still clear, because loud supporting elements compete with the point (Edward Tufte, *Visual Explanations*: the smallest effective difference).
5. [deck-design-009] **Group by space before lines, and know that color groups too.** Proximity, alignment, and repetition show what belongs together; add boxes and lines only where space cannot show it (Williams). Things that share a color are read as one group (Gestalt similarity), so a color says "these belong together" whether you meant it or not.
6. [deck-design-010] **The point survives a glance.** A reader gets a page's point in about three seconds; what does not help that is noise (Nancy Duarte, the glance test).

## Best practices

- [deck-design-001] **The focal point.** Decide per page what the reader should see first, and give emphasis only to it (principle 2). A page may need no emphasis at all. Most cards and boxes keep the default surface (`card` without `fill`); a surface that changes says "look here" (principle 5).
- [deck-design-002] **Categories and the accent.** Roles, owners, and inside/outside are categories. Painting a category in the accent color groups all its members as emphasized (principle 5) and leaves no color for the page's point, and a whole column turns red (principle 2). Categories read well by position, headings, and icons. Use color sparingly, consistently, and intentionally (Knaflic): the same meaning in the same color, and color only where it carries meaning.
- [deck-design-003] **Form per page, frame across pages.** Decide the form and the fills on each page from what it says (principle 1). A color legend for categories (「外部サービス=淡い赤」) or one fill for all cards written in 「書き方の取り決め」 (「書き方の決め」 in outlines written before 2026-11-01) decides the emphasis before any page knows its point; with such a line, models colored every page the same way.
  - [slides-visual-048] **Choose the body's form for each page from what that page says.** The patterns in `slides.md` §6 are common examples, not a list to pick from. Use any form (a chart, a map on two axes, a screenshot, a table) that lets the reader get the page's one sentence from the shape of the body before reading the text.
  - [slides-visual-049] **Keep only the frame the same across pages.** The frame is the position of the heading, lead, and source line, text sizes, colors, how each component looks, and drawing the same thing with the same name, color, and position (slides-visual-033–035 in `slides.md`). Copying the body's form from the representative pages, a past deck, or a sample made every page the same composition (three cards, a three-box diagram) whatever the page said. Lined-up boxes of the same size say "these are peers", so they fit only content that truly is (見た目 1-9、AI 実践 1-5). Pages that say the same kind of thing (one page per update item or per product) may keep the same form.
- **Means of emphasis:** changing the color of what you emphasize is a good means, and so are bold and an enclosure. Use the quietest one that is still clear (principle 4); a light red fill is the loudest, so keep it for when the others are not enough. In a table, one column or one cell is enough (見た目 1-12).
- **Hierarchy:** hierarchy comes from weight and contrast as much as from size: heavier, darker text comes forward, and lighter, softer text recedes (*Refactoring UI*: "size isn't everything"). Let supporting text recede in the supporting color before making the main text bigger. Two or three text sizes on a page are usually enough.
- **Grouping:** make the gap between groups wider than the gap inside a group. Fewer borders read calmer.
- **Color:** let neutral surfaces carry the content and spend the accent on the focal point. At most four colors on one page usually suffice: background, text, main, and emphasis; grays do not count (見た目 1-6).
- **Not color alone:** combine color with bold or an enclosure, so that people who see color differently (1 in 20 Japanese men) also get it (見た目 1-6). A difference that survives in grayscale is one that everyone sees.
- **Color pairs:** red and green, or red and black, are hard to tell apart as a pair that carries meaning. The release stage GA (green) beside red emphasis makes the reader tell them apart (見た目 1-6).
- **Surfaces:** a card must stand apart from its background. On a light background, the default card (a white fill with a thin rule) does. A gray panel (`PANEL`) without a rule suits one standalone panel, not every card: with the colors in `slides.md` §1, it differs from a white background by only 1.17:1, and a light red fill differs from it by 1.03:1, so the two tell apart only by hue (principle 3; measured 2026-10-30, other themes differ). Coloring both the fill and the border doubles the signal, which is louder than the card needs (principle 4); color one or the other (見た目 1-7).
- **Arrows:** thin arrows in the body or supporting color guide the eye without becoming the subject (見た目 1-7).
- **Room:** whitespace lets the point breathe. Fewer, larger elements read faster than many small ones.

## Instructions

- [deck-design-004] **Leave what can be measured to the components and lint.** Line breaks, padding inside boxes, vertical alignment in panels, corner radius, line weights, arrow positions, and the heights of boxes in a grid row are built by the components' defaults and checked by lint and the build warnings. Do not override `pad`, `spacing`, `radius`, or `weight` to fit more text or to silence a report (a value a rule asks for, such as 110 `spacing` on two-line headings in `slides.md`, is not an override); fix the `要確認` they report by rephrasing, re-fitting the box, or removing `h`.
- **Order when things conflict:** as in `deck-writing` (the workspace rules → the user decisions written as rules → these two files; 「書き方の取り決め」 is the parent's decision).

## How to use this file

- **Maker (parent and page-writing children):** before choosing a page's form, write its one sentence and think of more than one way to show it (principle 1). Before handing the page back, look at it as a first-time reader would, for about three seconds (principle 6).
- **Reviewer:** judge each page by the principles. When a page's point does not come across at a glance because of one of the practices above, return 「直す」 with the fix you would make, ending with that practice's ID (such as 「（deck-design-002）」); the parent moves it to the 「決まり」 column. When it reads well despite a practice, leave it; when you are unsure, return 「聞く」.

## Files

| Situation | File |
|---|---|
| **Principles:** the design principles, the best practices that follow from them, and what to leave to the components and lint | this file |
| **Slides:** this folder's style, text, color, shapes, tables and charts, diagram patterns, habits typical of AI-made materials (Google Slides) | [slides.md](slides.md) |
| **Documents:** page area, fonts and line spacing, structure and headings, paragraphs, tables and figures (Google Docs) | [docs.md](docs.md) |
