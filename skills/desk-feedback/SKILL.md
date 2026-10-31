---
name: desk-feedback
description: Learn from the user's corrections. Judge who a correction is true for (this material only, this customer, this person's or organization's environment, or knowledge any expert would share), record it in the rule ledger with that judgment, write it where that kind of knowledge lives (the outline, the customer's memory, a workspace recipe, or a proposal to the plugin through desk-kaizen), in the form that suits it, and decide how it will be verified. Holds how to judge, how to record and route (the ledger, rule IDs, how the hook shows workspace rules, customer memory, verifying rules), and how to write and regroup recipes. Use when the user corrects a material or its content (「ここは〜にして」「次から〜」), when asked to add, edit, or regroup rules or recipes (「決まりに足して」「レシピを整理して」「決まりの書き方を教えて」), and before every edit of a recipe or a customer's memory.
---

# Learning from feedback

A correction is evidence. It says that something in the material did not work for this user, and it carries a reason, stated or not. The work is to find out who that reason holds for, and to put the knowledge where it reaches exactly those materials. Too wide a place forces it on materials it does not fit; too narrow a place makes the user say it again.

## Classifying corrections: who it is true for

| Judgment (`--scope`) | What it looks like | Where it lives |
|---|---|---|
| 資料: this material only | It is about this page's wording, a number, or an order chosen for this audience; it would mean nothing in another material | The material itself, and the outline when it shapes several pages (「書き方の決め」). Ledger destination `戻さない` |
| 顧客: this customer | It depends on who the audience is: honorifics, their stack, their position, their past decisions | `Customers/<customer>/memory.md` (preferences) or `profile.md` (facts) ("Customer memory" in [routing.md](routing.md)) |
| 環境: this person or organization | It depends on this user's world: their tools, templates, brand, house style, internal processes, names, or a taste among good options | A workspace recipe ([recipes.md](recipes.md) §1) |
| 知見: anyone's | A writing or design expert who knows nothing of this organization would agree, for a reason that holds for any audience | The workspace first, so it applies today; desk-dreaming proposes it to the plugin when the gist recurs for other customers (`desk-kaizen`) |

Some signs that help, none of them decisive:

- **Can you state the reason without naming the person, the company, the customer, or a tool?** If not, it belongs to that environment. If you can, it may be knowledge.
- **Does it follow from a principle the plugin already gives** (the axes in `deck-writing`, the principles in `deck-design`)? Then the plugin did not lack the knowledge; it was not applied. What helps is a check, a step, or a better example, not another rule.
- **Is it a choice among options that are all good** (a color, a typeface, the order of sections)? Then it is taste, and taste is the environment's, however firmly it is said.
- **Is there a published source, or the same correction across customers and materials** (`ledger.py why`, `candidates`)? That is what turns a guess about 知見 into knowledge. One material is one observation, so your judgment is a hypothesis that the counts confirm or not.
- **When you cannot tell** whether it is for this material only or should become a rule, or it conflicts with a current rule, ask the user ("Routing corrections" in [routing.md](routing.md)).

## What form it takes

Write what lets the model think, and instruct only where thinking cannot reach.

- **Knowledge** (a principle, its reason, its source, a before-and-after example) suits 知見 and the plugin. The model can apply it to pages the rule's author never saw.
- **An instruction** 「〜のときは〜する（理由）」 suits what principles do not decide: the specifics of this environment, a customer's preference, and a decision the user made. Keep the reason, so a later reader can tell when it stops holding ([recipes.md](recipes.md) §4).
- **A check** suits what can be counted (sizes, characters, positions, a banned string). Put it in a `checks.py` and say in the rule that lint checks it ("Verifying rules" in [routing.md](routing.md)).
- **Write only the difference from the plugin.** A workspace rule that repeats the plugin goes stale when the plugin changes.

## Steps

Take a correction the user gives while making a material this way, on the spot, so the next material does not need the same words. Do not stop at fixing this material, and do not leave it for the cleanup (`desk-dreaming` picks up only what was missed).

1. **Record it as soon as you receive it,** in the rule ledger as the user said it, with your judgment, because a summarized conversation can drop it: `python3 <plugin>/lib/ledger.py add --deck <material folder> --quote "<the user's words>" --fix "<what was fixed>" --to <destination> --scope <資料・顧客・環境・知見> --check <lint・レビュー・なし>` (`<plugin>` is the folder that holds `skills/` and `lib/`). Add `--decided` when the user decided it outright (chose from options, or stated it flatly). Change the judgment later with `ledger.py scope <c-ID> <value>`. The ledger is the workspace's `.desk/ledger.jsonl`; it holds customer information, so do not copy it outside.
2. **Write it** where it lives, in its form: rules for making materials in a recipe, a customer's preferences in their `memory.md`, facts about a customer in their `profile.md`. Do not keep it only in the agent's own memory, because other agents and other tools do not see it. Before editing a recipe or a memory, open [recipes.md](recipes.md) (whoever edits: the making conversation, a direct request, desk-dreaming), so a rule reads the same however it got in.
3. **Route it** after the edit (`ledger.py route <c-ID> <file>`), and decide how it will be verified (lint, review, or a principle; "Verifying rules" in [routing.md](routing.md)). At the end of the report, say which correction went where (`ledger.py list --deck <material folder>`).

## Files

| Situation | File |
|---|---|
| **Classifying corrections:** who a correction is true for, what form it takes | this file |
| **Recording a correction:** recording, writing, and routing it on the spot | this file ("Steps") |
| **Routing** (and rule IDs): recording, the destination values, the ledger's versions, how the hook shows workspace rules, customer memory, verifying rules | [routing.md](routing.md) |
| **Writing recipes:** where a rule goes, one recipe per purpose, frontmatter (`step`, `per_material`, `targets`, `audience`), the form of items, regrouping recipes | [recipes.md](recipes.md) |
| Proposals from the conversation logs (the daily cleanup) | `desk-dreaming` |
| Filing knowledge for the plugin as an Issue | `desk-kaizen` |
