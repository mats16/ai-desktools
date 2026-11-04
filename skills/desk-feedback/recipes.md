# Writing recipes

A recipe is one workspace rule set for one purpose: `recipes/<name>/RECIPE.md`, plus the files it uses (document templates, `checks.py`, images) in the same folder. [deck-rules-009] **Open this file before every edit of a recipe, whoever edits it:** the making conversation routing a correction on the spot ("Routing corrections" in [routing.md](routing.md)), a conversation the user asks to edit rules directly, and desk-dreaming's proposals and rewrites (4h and 4j in `desk-dreaming` → running, and its child agents through its propose prompt). All of them follow §1–§4, so a rule reads the same however it got in. `ledger.py` checks the same things on both paths: `apply` stops a proposal that breaks them, and `add --to` and `route` print what to fix after an edit on the spot.

When recipes are opened (`desk.py recipes`), the 3,800-character limit, precedence, and how to record and route a correction are in [routing.md](routing.md) ("Workspace rules", "Routing corrections", "Verifying rules"). This file does not repeat them.

## 1. Where a rule goes

| What it is | Where |
|---|---|
| A rule for making materials or gathering, for one purpose (§2), including one that seems to hold everywhere (a recipe without `step` is opened in every step of making a material) | `recipes/<name>/RECIPE.md` |
| Countable in the JSON (size, font, characters, position, a banned string) | `checks.py` in the folder of the recipe it enforces, plus the rule text saying 「lint が〜」 (deck-rules-002) |
| A company document template | `recipes/<name>/templates/<template>/doc.md` (`docs.py init <template>`), with when to use it in that `RECIPE.md` |
| One customer's preferences | `Customers/<customer>/memory.md` (deck-rules-005) |
| A fact about a customer | `Customers/<customer>/profile.md` |
| Helps other people too | The plugin, through `desk-kaizen` |

Before writing a new recipe, read the `description` of every recipe (`head -6 recipes/*/RECIPE.md recipes/*/*/RECIPE.md`). Add to the recipe whose purpose fits; make a new one only when none does.

## 2. One recipe per purpose

[deck-rules-006] **Divide recipes by purpose: what the maker is doing when the rules are needed.** Each item belongs to exactly one recipe, and each recipe is one of three kinds.

| Kind | Purpose | Frontmatter | When the maker opens it |
|---|---|---|---|
| Material recipe | One kind of material or scene (an Account Plan, a CxO proposal, a summary of product updates, explaining a mechanism's internals, a hands-on workshop) | `per_material: true`, plus `audience` and `targets` when they narrow it | Chosen in step 5 and written in 「使う決まり」 of the outline; opened by the maker, and named in the briefs of page writers and reviewers |
| Common recipe | Content and look that hold for every material (how to build an outline, figures, page forms) | No `step` | At every step of making a material: at its start (`deck-workflow` → steps 1–5), before building, and in the briefs of page writers and reviewers |
| Step recipe | Knowledge used only while gathering or only while building (the company's search tools and sources, where logos and icons come from, a theme procedure, an API pitfall) | `step: gather` or `step: build` | `gather`: while gathering (`deck-workflow` → gathering materials and steps 1–5, `customer-profile`, `desk-crawl`, `desk-research`) and during plain research (the workspace's `Research/` and `references_index.md`). `build`: before building (`build-slides`, `build-docs`, `build-vids`, `deck-workflow` → steps 6–8 for decks) |

- **Put all of one material's rules in its material recipe,** whatever step they touch (structure, wording, figures, review aspects), because the maker then holds one recipe for that material. A CxO proposal's structure, its review aspect, and its tone go in one `cxo` recipe.
- **Decide the kind by the item's wording, not by the material it came from.** An item learned on an Account Plan that holds for every material (「棒グラフの軸は 0 から」) goes in a common recipe; an item that holds only for that kind of material goes in its material recipe.
- **Use `step` only for knowledge that is useless at the other steps.** Most rules about the material itself are needed while writing and while reviewing, so leave them without `step`, even ones that came from a build file such as `deck-design` → slides: they are then opened for writing and reviewing too, which is the point. Give a gathering recipe `step: gather` also when plain research uses it, because the same tools and sources serve both.
- **Do not keep a recipe of only one or two items.** Merge it into the recipe with the same purpose; a lone item for a narrow material goes in the material recipe of the wider kind (a schedule deck's item in the `customer` recipe). Each extra recipe is one more line to choose from in step 5 and one more file to open.
- **When a recipe nears 3,800 characters, split it by a narrower purpose** (「顧客向けの提案」 into 「CxO 向け」 and 「技術者向け」), so each part stays whole for its material. The common recipes and the recipes of one step are opened together at that step, so keep the common recipes short and move what only some materials need into material recipes.
- **Name the folder in lowercase English after its purpose:** `recipes/account_plan/`, `recipes/cxo/`, `recipes/internal_tools/`. Do not name it after a skill or plugin file (`recipes/build-slides/`), because plugin files are split and renamed, and a recipe per plugin file mixes unrelated scenes; `ledger.py` stops a new recipe there.
- **Group recipes in a folder only when several (about three or more) share a wider purpose** (`recipes/explain/internals/RECIPE.md`, `recipes/explain/tool_guide/RECIPE.md`). A folder without `RECIPE.md` is a group; do not put a recipe inside another recipe's folder.

## 3. Frontmatter and resources

- **`description`:** the maker sees only this line in step 5, so it must decide the choice alone. Start with the scene in the user's words (「Account Plan を作るとき」「顧客の CxO に提案するとき」), then name the main topics in parentheses, about five, not every item: `description: 社内の Account Plan を作るとき（章立て、数字の出し方、図、最後のページ）`. Do not name plugin files in it; say when, not where.
- **`targets` and `audience`:** add them only when they are true of every item. They narrow the choice of recipes (`desk.py recipes` prints them on each line).
- **Who fills the frontmatter:** a person writing a rule needs only the `description` and the items. The agent picks the kind and fills `step` or `per_material`; nobody needs to know the plugin's files.
- **Resources:** keep the files a recipe uses in its folder, and say in `RECIPE.md` when to use each (「顧客向けの PoC は `templates/poc_customer/doc.md`、社内の PoC は `templates/poc_internal/doc.md`」). The maker reads `RECIPE.md` and opens the other files only when it says to, so put the rules in `RECIPE.md`, not in a resource. Template names must be unique across `recipes/`, because `docs.py init <template>` looks for them by name. `checks.py` may define `slides(p, r)`, `doc(doc, r)`, or both; lint loads every `checks.py` under `recipes/` (how to write one: `recipes/README.md`).

## 4. Items

[deck-rules-007] **Write one rule per bullet in the form 「〜のときは〜する（<短い理由>）。」** The condition says when it applies, the action what to do, and the reason why. The reason lets the maker judge cases the rule did not foresee, and lets desk-dreaming merge items with the same gist.

- **Make the action checkable.** A reviewer must be able to tell from the material whether it was followed (what to write, put, order, or leave out). 「わかりやすくする」 is not a rule; 「1 ページの主張は 1 つにする」 is. An ideal the axes in `deck-writing` and `deck-design` do not already hold becomes a best practice with its reason (the next item).
- **Write knowledge as a best practice, not as the instructions it explains.** When several items share one reason that any expert would agree with, not one that belongs to this environment, write one item that states the practice, its reason, and its source when there is one, with one 「例:」 of before and after, and remove the items it explains, except items the user decided, which stay as written (「離れた凡例は目を行き来させるので、系列の名前は線の端や棒のそばに書く（Knaflic『Storytelling with Data』）。例: 右上の凡例 → 各線の右端に名前」). The maker can then judge pages the items never named. Keep 「〜のときは〜する」 for what no principle decides.
- **With a prohibition, say what to do instead** (「〜にしない。〜にする」), because a bare ban gets replaced with another empty word (`deck-writing` → content §6).
- **Write only the difference from the plugin.** Do not copy plugin text; it is read anyway, and desk-dreaming removes copies (「写しを消す」). When an item contradicts a plugin rule, add 「（slides-visual-012 より優先。<理由>）」, with the ID unbracketed, or 「（プラグインの〇〇の節より優先）」 for a section without IDs.
- **Say when lint checks it** (「lint が〜」), and add the check to the recipe's `checks.py` the first time (deck-rules-002).
- **Keep out of the text:** IDs, dates, the user's words, material folders, customer names, people's names, and internal-only numbers. The ledger keeps the history, and a customer name in a general recipe slips into other customers' materials. When one of them carries meaning, say the meaning instead: a date as 「調べた時点では」, a customer used as a model by what it is (「社内で手本にしている計画の例」), a person by role (「担当の AE」).
- **Turn a quoted reason into a short reason in your own words.** When no reason is known, leave the item without one rather than invent it.
- **Use `##` headings for sub-scenes** once a recipe holds more than about ten items (「章立て」「数字」「図」), so the maker finds the part for the page at hand.
- **Keep examples to one line** and mark them 「例:」, because examples are copied literally.

## 5. Regrouping existing recipes

[deck-rules-008] **Regroup through the ledger, as one set of proposals applied together,** so no rule is lost or left in two places and its findings stay linked. Use this after desk-migrate moved a workspace from before 2026-10-29 (it turns each old file into its own recipe, named after the old file), and for many small recipes.

1. **Take stock.** Run `python3 $L drift --record` first, so hand edits become versions (`L=<desk-feedback folder>/scripts/ledger.py`). For each recipe, note its frontmatter, `wc -m`, its other files, and `python3 $L why <recipe>` (findings with the user's words, 「ユーザーが決めた」, 「手で直した」 versions). Also run `python3 $L list --odd` (findings whose destination is a path plus an old ID, such as 「recipes/pages/RECIPE.md ws-slides-pages-007」; `why` and `list --to` miss them), `python3 $L questions`, `python3 $L pending` (proposals not applied yet), and `python3 $L pending --status 却下` and `--status 戻した` (rejected and undone proposals; their `file` names the recipe).
2. **Plan.** List the purposes (§2) and assign every item to one new recipe: a table of item → new recipe, with each recipe's kind, `description`, `step` or `per_material`, `targets`, and `audience`, the files it takes along (templates, `checks.py`), and the findings (c-IDs) behind each item. Match a finding to its item by its words, not by the file it is linked to, because findings often point to a file the item has since left. Keep what every rule says. Merging items with the same gist is part of regrouping, and so is the §4 cleanup that leaves the meaning alone: drop dates, the user's words, material folders, c-IDs, and people's names; write customer names in examples as 「A 社」; drop the old preambles and headings that named the plugin file (「〜.md への足し」). Show the plan to the user and wait for agreement, because it changes when each rule appears.
3. **Check the protections against the plan.** Every finding marked 「ユーザーが決めた」, every 「手で直した」 version, and every item a rejected or reverted proposal tried to remove must stand in one of the new recipes. A finding that matches no item: if a plugin rule now covers it, link it to that rule ID (`python3 $L route <c-ID> <ID>`); if it is decided and nothing covers it, ask the user before going on. A finding behind items in two recipes goes to the one holding its main point, because a finding links to one destination.
   - **Proposals not applied yet on an old recipe** will not find their file after the regroup. Fold the ones still wanted into the new recipe's text and withdraw them all (`python3 $L withdraw <P-ID> --reason 組み直しに入れた`).
4. **Write** each new `RECIPE.md` whole, and the remaining text of each old one (empty when everything moved), under `.desk/tmp/regroup/` (name each by its path with `/` replaced by `__`). Also write the fixes to other workspace files that name an old recipe (`grep -rn <old recipe> Customers/*/memory.md recipes/ .desk/recipe_cases.md`). Move each template and `checks.py` into the folder of the recipe that uses it; desk-migrate parks them in `recipes/doc_templates/` and `recipes/slide_checks/`・`doc_checks/` only because it cannot tell which recipe that is.
5. **Propose and apply together.** For each new recipe: `python3 $L propose --file recipes/<name>/RECIPE.md --rewrite .desk/tmp/regroup/<name> --kind 組み直し --why 目的ごとに組み直す --src <the c-IDs of its items>`; the same without `--src` for each old recipe, and `--kind パスの直し` for each other fixed file (only recipes get 「組み直し」, which stops `--auto` there). Apply all of them in one call, `python3 $L apply <P-ID> …`, because `apply` checks every proposal before writing any; it also links each `--src` finding to the new recipe. Then move the resources with `mv` (a moved `checks.py` starts a new version history at its new path), delete the emptied old folders, and delete `.desk/tmp/regroup/`.
6. **Check.**
   - `python3 $L list --to <old recipe>` for each old recipe prints nothing (link a leftover with `python3 $L route <c-ID> <new recipe>`).
   - `doctor.py --local` (`desk-doctor`) reports no recipe problems (sizes, frontmatter, folder names).
   - Answer the questions that name an old recipe (`python3 $L answer <Q-ID> --a <answer naming the new recipe>`) only with the user; until then, say in the report which new recipe each refers to.
   - Fix 「使う決まり」 in the outlines of materials still in progress; `desk.py recipes <material folder>` names entries that point to a deleted recipe.

**What does not follow the items.** The ledger keys review results, 「手で直した」 versions, rejected proposals, and questions by file path, and an item cannot be traced from an old recipe to a new one. So `ledger.py` stops `--auto` deletions in any recipe with a 「組み直し」 version (as it does for 「手で直した」), counts in `rules` and `effects` start again from the new recipes, and an unanswered question keeps naming the old recipe (answer it with the new recipe in the answer). Say this in the report.

## 6. Writing a recipe with the user

Use this when the user opens a conversation to write or change a recipe (「〜のレシピを作りたい」「決まりを一緒に書きたい」), not to fix a material. Gather evidence before drafting, because a recipe written from one sentence holds only the case the user had in mind. Write the ledger commands with the full path (`python3 <desk-feedback folder>/scripts/ledger.py …`), because each shell call starts fresh.

1. **Look first, then ask.** Read every recipe's `description` (§1). For an existing recipe, read `ledger.py why <recipe>`; for a new purpose, look for findings in the ledger that already say it (`ledger.py list | grep -i <a word of the scene>`; the whole list is too long to read). Corrections already recorded are the user's own words on a real material, so they outweigh what is said in the abstract.
2. **Ask only what the evidence leaves open,** a few questions at a time: the scene (which material, who reads it, how the maker tells it is this scene), one past material where it went wrong and what the user changed, and what the user wants instead. Open that material's outline and pages, because the user's summary drops the details the rule needs.
3. **Draft** the place and kind (§1, §2), the `description` (§3), and the items (§4). Show the draft with, for each item, where it came from (the user's words in this conversation, or a c-ID).
4. **Test a material recipe's `description`** (§7) before writing it in, and show the result. Rewrite what failed and test again.
5. **Write and record one item at a time:** edit the file for one item, then link its evidence, and only then the next item. `ledger.py` keeps a version only when the file changed since the last one, and gives that version the finding recorded with it, so items written together end up under the first finding ("Routing corrections" in [routing.md](routing.md)). Link a finding already in the ledger with `ledger.py route <c-ID> recipes/<name>/RECIPE.md`, and an item the user stated in this conversation with `ledger.py add --deck <the material it came from, or . from the workspace root when none> --quote "<the user's words>" --to recipes/<name>/RECIPE.md --scope <資料・顧客・環境・知見> --check <lint・レビュー・なし>`, judging the scope for each item ("Classifying corrections" in `SKILL.md`; a recipe is for 環境, so an item judged otherwise goes where that judgment points instead), and adding `--decided` when the user stated it outright.

## 7. Testing a recipe

The maker picks material recipes in step 5 from the list `desk.py recipes` prints, by their `description` alone, and picks them together: one outline's 「使う決まり」 is a set. Test the descriptions before writing one in, by giving a child agent the same list and scenes whose answers the user decided. `ledger.py effects` tells whether a recipe worked only after weeks of materials, and with one to five findings per recipe it often cannot tell at all.

The answers come from the user, not from past outlines: makers given the same request often chose different recipes, and earlier outlines chose from earlier descriptions, so a past 「使う決まり」 is a hint for writing a scene, never its answer.

1. **Scenes.** Keep them in `.desk/recipe_cases.md`, one table for the whole workspace, because the choice is made among all material recipes at once and a broad description takes its neighbors' scenes. Each row is a request as the maker sees it at step 5 (the user's words, the kind of material, the audience) and the whole set of recipes to choose, or 「なし」. Write the request alone, without words that give away the answer, because the child reads that column. Give each material recipe a few scenes of its own and a few near misses that a neighbor takes or that no recipe takes, because the boundaries are where descriptions fail. Draft scenes from the requests in past outlines and from corrections where the wrong recipe was used, then have the user decide every answer. Keep the file in `.desk/`, outside `recipes/`, so a maker who searches or lists the recipes never meets the answers. When a recipe is renamed or regrouped, fix its paths here too (§5).

   ```markdown
   # 選ばれ方を確かめる場面

   | 場面（依頼・資料の種類・聞き手） | 選ぶレシピ | 理由 |
   | --- | --- | --- |
   | 「来週の役員会に出す提案をまとめて」。顧客向けの提案。聞き手は CIO | `recipes/cxo/RECIPE.md`、`recipes/customer/RECIPE.md` | 決める人に見せる提案 |
   | 「同じ内容を現場の技術者向けにして」。顧客向けの説明。聞き手は技術者 | `recipes/customer/RECIPE.md` | 決める人ではない |
   | 「チームの振り返りのメモ」。社内のメモ。聞き手は自分たち | なし | 資料ごとのレシピの場面でない |
   ```

2. **The list.** `python3 <desk-feedback folder>/scripts/recipe_menu.py` prints the list exactly as `desk.py recipes` shows it at step 5, from the same workspace. For a draft not written in yet, add `--draft <file> --as recipes/<name>/RECIPE.md`: it replaces that recipe in the list, or adds it (it says which), and stops when the draft would not be listed there.
3. **The child.** Give a child agent with no conversation context, a different model when one is available (`deck-workflow` → child agents), the list and the scene column only, in the brief itself. The list starts, under its heading, with the instruction to write 「使う決まり」 into the outline; tell the child to answer in its final message instead, one line per scene with the paths it would write (or 「なし」), and to name the scenes where the descriptions made the choice hard. Tell it that it needs no files, and give it no path to `.desk/recipe_cases.md`, because the answers are there. Check that it used no tools where the harness reports it (Claude Code returns the child's count of tool uses with its result); a run that opened a file is not a test. Models vary between runs, so run it twice with a new child each time, and count a scene as passing only when both runs pick exactly its set. When the two runs disagree on a scene, run that scene twice more before changing a `description`: if the four runs still disagree, the scene marks a boundary to say more clearly; if three agree with the answer, it was noise and passes.
4. **Compare and fix.** Compare each run's picks with the scene's set as sets (order and notes do not matter), and show the user the scenes that failed, with what each run picked. A recipe missing from a scene, or added to one, means a `description` leaves a boundary open: two recipes that both claim the scene, or a scene no recipe names. Say the scene in the user's words and which neighbor takes the near case, then test again, with every scene, because a changed `description` can take scenes from any recipe. The scenes the child named as hard point to the same boundaries.

This shows only whether the descriptions get the recipes chosen in the scenes the user decided, not whether a recipe's items prevent the corrections behind them (`ledger.py effects` still answers that). When a real material still picks the wrong recipes, record it as a correction linked to the recipe whose `description` misled (`ledger.py add … --to recipes/<name>/RECIPE.md`), and add the scene to `.desk/recipe_cases.md`.
