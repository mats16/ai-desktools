# Writing recipes

A recipe is one workspace rule set for one purpose: `recipes/<name>/RECIPE.md`, plus the files it uses (document templates, `checks.py`, images) in the same folder. [deck-rules-009] **Open this file before every edit of a recipe, whoever edits it:** the making conversation routing a correction on the spot ("Routing corrections" in [routing.md](routing.md)), a conversation the user asks to edit rules directly, and desk-dreaming's proposals and rewrites (4h and 4j in `desk-dreaming` → running, and its child agents through its propose prompt). All of them follow §1–§4, so a rule reads the same however it got in. `ledger.py` checks the same things on both paths: `apply` stops a proposal that breaks them, and `add --to` and `route` print what to fix after an edit on the spot.

How the hook shows recipes, the 3,800-character limit, precedence, and how to record and route a correction are in [routing.md](routing.md) ("Workspace rules", "Routing corrections", "Verifying rules"). This file does not repeat them.

## 1. Where a rule goes

| What it is | Where |
|---|---|
| Needed in every conversation (the user's iron rules, how to take corrections) | `AGENTS.md` |
| Needed only when making materials or gathering, for one purpose (§2) | `recipes/<name>/RECIPE.md` |
| Countable in the JSON (size, font, characters, position, a banned string) | `checks.py` in the folder of the recipe it enforces, plus the rule text saying 「lint が〜」 (deck-rules-002) |
| A company document template | `recipes/<name>/templates/<template>/doc.md` (`docs.py init <template>`), with when to use it in that `RECIPE.md` |
| One customer's preferences | `Customers/<customer>/memory.md` (deck-rules-005) |
| A fact about a customer | `Customers/<customer>/profile.md` |
| Helps other people too | The plugin, through `desk-kaizen` |

Before writing a new recipe, read the `description` of every recipe (`head -6 recipes/*/RECIPE.md recipes/*/*/RECIPE.md`). Add to the recipe whose purpose fits; make a new one only when none does.

## 2. One recipe per purpose

[deck-rules-006] **Divide recipes by purpose: what the maker is doing when the rules are needed.** Each item belongs to exactly one recipe, and each recipe is one of three kinds.

| Kind | Purpose | Frontmatter | When the hook shows it |
|---|---|---|---|
| Material recipe | One kind of material or scene (an Account Plan, a CxO proposal, a summary of product updates, explaining a mechanism's internals, a hands-on workshop) | `per_material: true`, plus `audience` and `targets` when they narrow it | Chosen in step 5 and written in 「使う決まり」 of the outline; shown whenever the outline is opened (the maker, page writers, and reviewers all read it) |
| Common recipe | Content and look that hold for every material (how to build an outline, figures, page forms) | No `step` | At every step of making a material (`deck-workflow`, `deck-writing`, `deck-design`, the build skills, `deck-review`, and the material's files) |
| Step recipe | Knowledge used only while gathering or only while building (the company's search tools and sources, where logos and icons come from, a theme procedure, an API pitfall) | `step: gather` or `step: build` | `gather`: while gathering (`deck-workflow` → gathering materials and steps 1–5, `customer-profile`, `desk-crawl`, `desk-research`) and during plain research (the workspace's `Research/` and `references_index.md`). `build`: while building (`slides-build`, `docs-build`, the vids skills, `deck-design` → slides and documents) |

- **Put all of one material's rules in its material recipe,** whatever step they touch (structure, wording, figures, review aspects), because the maker then holds one recipe for that material. A CxO proposal's structure, its review aspect, and its tone go in one `cxo` recipe.
- **Decide the kind by the item's wording, not by the material it came from.** An item learned on an Account Plan that holds for every material (「棒グラフの軸は 0 から」) goes in a common recipe; an item that holds only for that kind of material goes in its material recipe.
- **Use `step` only for knowledge that is useless at the other steps.** Most rules about the material itself are needed while writing and while reviewing, so leave them without `step`, even ones that came from a build file such as `deck-design` → slides: they are then shown in `deck-workflow`, `deck-review`, and the outline too, which is the point. Give a gathering recipe `step: gather` also when plain research uses it, because the same tools and sources serve both.
- **Do not keep a recipe of only one or two items.** Merge it into the recipe with the same purpose; a lone item for a narrow material goes in the material recipe of the wider kind (a schedule deck's item in the `customer` recipe). Each extra recipe is one more line to choose from in step 5 and one more heading in the hook's output.
- **When a recipe nears 3,800 characters, split it by a narrower purpose** (「顧客向けの提案」 into 「CxO 向け」 and 「技術者向け」), so each part stays whole for its material. The common recipes and the recipes of one step are shown together, and the hook injects at most 9,000 characters at a time (`LIMIT` in `hooks/rules_overlay.py`), so keep the common recipes plus either step's recipes under about 8,000; move what only some materials need into material recipes.
- **Name the folder in lowercase English after its purpose:** `recipes/account_plan/`, `recipes/cxo/`, `recipes/internal_tools/`. Do not name it after a skill or plugin file (`recipes/slides-build/`), because plugin files are split and renamed, and a recipe per plugin file mixes unrelated scenes; `ledger.py` stops a new recipe there.
- **Group recipes in a folder only when several (about three or more) share a wider purpose** (`recipes/explain/internals/RECIPE.md`, `recipes/explain/tool_guide/RECIPE.md`). A folder without `RECIPE.md` is a group; do not put a recipe inside another recipe's folder.

## 3. Frontmatter and resources

- **`description`:** the maker sees only this line in step 5, so it must decide the choice alone. Start with the scene in the user's words (「Account Plan を作るとき」「顧客の CxO に提案するとき」), then name the main topics in parentheses, about five, not every item: `description: 社内の Account Plan を作るとき（章立て、数字の出し方、図、最後のページ）`. Do not name plugin files in it; say when, not where.
- **`targets` and `audience`:** add them only when they are true of every item. They narrow the choice of material recipes in step 5; the hook shows common and step recipes regardless of them.
- **Who fills the frontmatter:** a person writing a rule needs only the `description` and the items. The agent picks the kind and fills `step` or `per_material`; nobody needs to know the plugin's files.
- **Resources:** keep the files a recipe uses in its folder, and say in `RECIPE.md` when to use each (「顧客向けの PoC は `templates/poc_customer/doc.md`、社内の PoC は `templates/poc_internal/doc.md`」). The hook shows `RECIPE.md` and only lists the other files by name, so put the rules in `RECIPE.md`, not in a resource. Template names must be unique across `recipes/`, because `docs.py init <template>` looks for them by name. `checks.py` may define `slides(p, r)`, `doc(doc, r)`, or both; lint loads every `checks.py` under `recipes/` (how to write one: `recipes/README.md`).

## 4. Items

[deck-rules-007] **Write one rule per bullet in the form 「〜のときは〜する（<短い理由>）。」** The condition says when it applies, the action what to do, and the reason why. The reason lets the maker judge cases the rule did not foresee, and lets desk-dreaming merge items with the same gist.

- **Make the action checkable.** A reviewer must be able to tell from the material whether it was followed (what to write, put, order, or leave out). 「わかりやすくする」 is not a rule; 「1 ページの主張は 1 つにする」 is. Ideals belong in 「いい資料の考え方」 in `AGENTS.md`.
- **With a prohibition, say what to do instead** (「〜にしない。〜にする」), because a bare ban gets replaced with another empty word (`deck-writing` → content §6).
- **Write only the difference from the plugin.** Do not copy plugin text; it is shown anyway, and desk-dreaming removes copies (「写しを消す」). When an item contradicts a plugin rule, add 「（slides-visual-012 より優先。<理由>）」, with the ID unbracketed, or 「（プラグインの〇〇の節より優先）」 for a section without IDs.
- **Say when lint checks it** (「lint が〜」), and add the check to the recipe's `checks.py` the first time (deck-rules-002).
- **Keep out of the text:** IDs, dates, the user's words, material folders, customer names, people's names, and internal-only numbers. The ledger keeps the history, and a customer name in a general recipe slips into other customers' materials. When one of them carries meaning, say the meaning instead: a date as 「調べた時点では」, a customer used as a model by what it is (「社内で手本にしている計画の例」), a person by role (「担当の AE」).
- **Turn a quoted reason into a short reason in your own words.** When no reason is known, leave the item without one rather than invent it.
- **Use `##` headings for sub-scenes** once a recipe holds more than about ten items (「章立て」「数字」「図」), so the maker finds the part for the page at hand.
- **Keep examples to one line** and mark them 「例:」, because examples are copied literally.

## 5. Regrouping existing recipes

[deck-rules-008] **Regroup through the ledger, as one set of proposals applied together,** so no rule is lost or left in two places and its findings stay linked. Use this after desk-migrate moved a workspace from before 2026-10-29 (it turns each old file into its own recipe, named after the old file), and for many small recipes.

1. **Take stock.** Run `python3 $L drift --record` first, so hand edits become versions (`L=<plugin>/lib/ledger.py`). For each recipe, note its frontmatter, `wc -m`, its other files, and `python3 $L why <recipe>` (findings with the user's words, 「ユーザーが決めた」, 「手で直した」 versions). Also run `python3 $L list --odd` (findings whose destination is a path plus an old ID, such as 「recipes/pages/RECIPE.md ws-slides-pages-007」; `why` and `list --to` miss them), `python3 $L questions`, `python3 $L pending` (proposals not applied yet), and `python3 $L pending --status 却下` and `--status 戻した` (rejected and undone proposals; their `file` names the recipe).
2. **Plan.** List the purposes (§2) and assign every item to one new recipe: a table of item → new recipe, with each recipe's kind, `description`, `step` or `per_material`, `targets`, and `audience`, the files it takes along (templates, `checks.py`), and the findings (c-IDs) behind each item. Match a finding to its item by its words, not by the file it is linked to, because findings often point to a file the item has since left. Keep what every rule says. Merging items with the same gist is part of regrouping, and so is the §4 cleanup that leaves the meaning alone: drop dates, the user's words, material folders, c-IDs, and people's names; write customer names in examples as 「A 社」; drop the old preambles and headings that named the plugin file (「〜.md への足し」). Show the plan to the user and wait for agreement, because it changes when each rule appears.
3. **Check the protections against the plan.** Every finding marked 「ユーザーが決めた」, every 「手で直した」 version, and every item a rejected or reverted proposal tried to remove must stand in one of the new recipes. A finding that matches no item: if a plugin rule now covers it, link it to that rule ID (`python3 $L route <c-ID> <ID>`); if it is decided and nothing covers it, ask the user before going on. A finding behind items in two recipes goes to the one holding its main point, because a finding links to one destination.
   - **Proposals not applied yet on an old recipe** will not find their file after the regroup. Fold the ones still wanted into the new recipe's text and withdraw them all (`python3 $L withdraw <P-ID> --reason 組み直しに入れた`).
4. **Write** each new `RECIPE.md` whole, and the remaining text of each old one (empty when everything moved), under `.desk/tmp/regroup/` (name each by its path with `/` replaced by `__`). Also write the fixes to other workspace files that name an old recipe (`grep -rn <old recipe> AGENTS.md Customers/*/memory.md recipes/`). Move each template and `checks.py` into the folder of the recipe that uses it; desk-migrate parks them in `recipes/doc_templates/` and `recipes/slide_checks/`・`doc_checks/` only because it cannot tell which recipe that is.
5. **Propose and apply together.** For each new recipe: `python3 $L propose --file recipes/<name>/RECIPE.md --rewrite .desk/tmp/regroup/<name> --kind 組み直し --why 目的ごとに組み直す --src <the c-IDs of its items>`; the same without `--src` for each old recipe, and `--kind パスの直し` for each other fixed file (only recipes get 「組み直し」, which stops `--auto` there). Apply all of them in one call, `python3 $L apply <P-ID> …`, because `apply` checks every proposal before writing any; it also links each `--src` finding to the new recipe. Then move the resources with `mv` (a moved `checks.py` starts a new version history at its new path), delete the emptied old folders, and delete `.desk/tmp/regroup/`.
6. **Check.**
   - `python3 $L list --to <old recipe>` for each old recipe prints nothing (link a leftover with `python3 $L route <c-ID> <new recipe>`).
   - `doctor.py --local` (`desk-doctor`) reports no recipe problems (sizes, frontmatter, folder names, and 「AGENTS.md のレシピの出し方」 for text in `AGENTS.md` that still describes `paths`).
   - Answer the questions that name an old recipe (`python3 $L answer <Q-ID> --a <answer naming the new recipe>`) only with the user; until then, say in the report which new recipe each refers to.
   - Fix 「使う決まり」 in the outlines of materials still in progress; the hook names lines that point to a deleted recipe each time the outline is opened.

**What does not follow the items.** The ledger keys review results, 「手で直した」 versions, rejected proposals, and questions by file path, and an item cannot be traced from an old recipe to a new one. So `ledger.py` stops `--auto` deletions in any recipe with a 「組み直し」 version (as it does for 「手で直した」), counts in `rules` and `effects` start again from the new recipes, and an unanswered question keeps naming the old recipe (answer it with the new recipe in the answer). Say this in the report.
