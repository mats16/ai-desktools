# Step records

A material's step records live in `progress.jsonl` in the material folder, one JSON object per line. `scripts/flow.py record` appends them, and `scripts/flow.py <material folder>` shows them. This file explains what a record holds, where each field comes from, and when a record helps. Whether to record, and when, is your call; nothing else in the workflow requires it. The workflow owns the records. The tools (`slides-build`, `docs-build`, the ledgers) never write them, so they keep working without the workflow.

## Why records, not inference

`flow.py` also prints what the files and the ledger show for each step. But the files cannot tell some things. The planned page count, which Google URL is the built material, whether a 「書き方の取り決め」 section holds rules or a draft, and whether a step was finished or skipped leave no file of their own. An earlier version that inferred these from file shapes needed five local review rounds and still had findings, because each fix closed one variant and the next pass found another (2026-11-01 in `docs/decisions.md`). A record states the fact directly, so `flow.py` reads it instead of guessing. It shows each record as written and cross-checks only what the files can confirm (below); a record such as `pages=24` is not compared with the pages written, so compare it yourself.

## Fields

```sh
python3 <deck-workflow folder>/scripts/flow.py record <material folder> <step number> <status> \
  [--out <name>=<value> ...] [--note <text>] [--next <text>] [--by <who>]
```

| Field | Written by | Holds | Modeled on |
|---|---|---|---|
| `ts` | the script (UTC, seconds) | When the record was made | LangGraph checkpoint `created_at`; Temporal event time |
| `step` | you (`1`–`11`; 1–4 are one step) | The step of "Overall flow" in `SKILL.md` | Codex `update_plan` `step`; LangGraph `metadata.step` |
| `status` | you | 「始めた」, 「済んだ」, 「飛ばした」 (the step does not apply, such as step 6 for a deck of 10 pages or fewer), or 「止まった」 (waiting for the user's answer or other work) | Codex and Claude Code `pending` / `in_progress` / `completed`; GitHub Actions `skipped`; beads `blocked` |
| `out` | you (`--out`, repeatable) | Facts the step produced that files do not show, as name=value pairs | LangGraph `metadata.writes`; GitHub Actions step `outputs`; OpenTelemetry span attributes |
| `note` | you | What was decided, what was dropped and why, what is waited for | beads `notes`; Codex `explanation`; `claude-progress.txt` in Anthropic's long-running harness |
| `next` | you | The next concrete action | LangGraph `next`; beads handoff notes ("the next concrete step") |
| `by` | you | Who did it: 「親」 or the child agent's name, when children write pages | Claude Code `TaskUpdate` `owner`; beads `assignee` |

The file is append-only, as an event history is (Temporal, LangGraph checkpoints): a new record does not edit an older one, and the last record of a step is its current state. Anthropic's harness has agents change only the `passes` field of its feature list, for the same reason: a history that is only added to cannot lose what was done.

Names that help in `--out`:

| Step | Name | Example |
|---|---|---|
| 5 | `pages` (planned page count), `reviewer` (`ai` or `human`) | `pages=24` |
| 6 | `rules` (lines in 「書き方の取り決め」) | `rules=7` |
| 8 | `url` (the built material) | `url=https://docs.google.com/presentation/d/…/edit` |
| 9 | `round`, `findings` | `round=2 findings=3` |
| 10 | `asked` (questions left for the user) | `asked=2` |

## What `flow.py` shows

For each step it shows the last record with its count, then the facts from the files and the ledger. At the top it shows the newest record of any step, which is where the work last stood. It also reports two mismatches between a record and the files. One is a file in `build/` changed after a 「済んだ」 record of step 7 or later and before any later step's record (a change after the next step started belongs to that step; a file changed again later shows only its last change; the record's time is in whole seconds, so a change within the same second as the record is not listed). The other is an `out` URL at step 8 whose Google file ID is in neither the outline nor `社内メモ_*.md` (where deck-drive-003 writes the URL; the `/a/<domain>/`, `/u/0/`, and Drive forms of the same file match). Only page sources in `build/` count as changes (`.json`, `doc.md`, `pages.py`); images and `*.bak*` backups do not. Times come from the clock of the machine that wrote each record. Lines it cannot read are counted and skipped.

## When a record helps

- **Before a summary** (deck-flow-005): the record and `next` survive in the folder, and after the summary one `flow.py` call shows where to resume (deck-flow-015).
- **When the files cannot tell**: the planned page count, the built URL, a skipped step, or waiting for an answer in 「聞く」.
- **When child agents write pages** (slides-flow-016): a child can record 「始めた」 for step 7 with `--by <name>` and its pages in `--out` (`pages=p06-p10`), so the parent sees who is on which pages. Record step 7 as 「済んだ」 only from the parent, after every child has returned, because the last record of a step is the state of the whole step.

A short material finished in one sitting may need no record; the files and the outline already say enough.
