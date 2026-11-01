# Step records

A material's step records live in `progress.jsonl` in the material folder, one JSON object per line. Whoever does a piece of work, the parent or a child agent, records only its own scope: which step, what state, which files, what it produced. `scripts/flow.py` is the orchestrator: it merges the records and decides the state of each step, the next step, and whether finished files have changed since. Whether to record, and when, is your call; nothing else in the workflow requires it. The workflow owns the records. The tools (`slides-build`, `docs-build`, the ledgers) never write them, so they keep working without the workflow.

The split follows graph engines. A LangGraph node returns only its own update, and the edges decide the next node. A Temporal activity returns its result, and the workflow decides what follows. Parallel branches are merged by a reducer (LangGraph) or joined when all of them succeed (Airflow's `all_success`). Bazel and Dagster tell stale outputs by the content hash of their inputs, not by time. A writer here therefore never writes the next step: a child sees only its pages and cannot know it.

## Why records, not inference

`flow.py` also prints what the files and the ledger show for each step. But the files cannot tell some things. The planned page count, which Google URL is the built material, whether a 「書き方の取り決め」 section holds rules or a draft, and whether a step was finished or skipped leave no file of their own. An earlier version that inferred these from file shapes needed five local review rounds and still had findings, because each fix closed one variant and the next pass found another (2026-11-01 in `docs/decisions.md`). A record states the fact directly, so `flow.py` reads it instead of guessing. It shows each record as written and cross-checks only what the files can confirm (below); a record such as `pages=24` is not compared with the pages written, so compare it yourself.

## Fields

```sh
python3 <deck-workflow folder>/scripts/flow.py record <material folder> <step number> <status> \
  [--files <file> ...] [--out <name>=<value> ...] [--note <text>]
```

| Field | Written by | Holds | Modeled on |
|---|---|---|---|
| `ts` | the script (UTC, seconds) | When the record was made | LangGraph checkpoint `created_at`; Temporal event time |
| `step` | you (`1`–`11`; 1–4 are one step) | The step of "Overall flow" in `SKILL.md` | Codex `update_plan` `step`; LangGraph `metadata.step` |
| `status` | you | 「始めた」, 「済んだ」, 「飛ばした」 (the step does not apply, such as step 6 for a deck of 10 pages or fewer), or 「止まった」 (waiting for the user's answer or other work) | Codex and Claude Code `pending` / `in_progress` / `completed`; GitHub Actions `skipped`; beads `blocked` |
| `inputs` | the script, from `--files` | Your scope: the files you work on (paths from the material folder), each with the sha256 of its content when you recorded. A file not written yet (planned, or dropped and deleted) can be named in any status but 「済んだ」, with no hash. Without `--files`, the scope is the whole material | Bazel action inputs; Dagster data versions |
| `out` | you (`--out`, repeatable) | Facts your work produced that files do not show, as name=value pairs | LangGraph `metadata.writes`; GitHub Actions step `outputs`; OpenTelemetry span attributes |
| `note` | you | What was decided, what was dropped and why, what is waited for | beads `notes`; Codex `explanation`; `claude-progress.txt` in Anthropic's long-running harness |

The file is append-only, as an event history is (Temporal, LangGraph checkpoints): a new record does not edit an older one. Anthropic's harness has agents change only the `passes` field of its feature list, for the same reason: a history that is only added to cannot lose what was done.

Names that help in `--out`:

| Step | Name | Example |
|---|---|---|
| 5 | `pages` (planned page count), `reviewer` (`ai` or `human`) | `pages=24` |
| 6 | `rules` (lines in 「書き方の取り決め」) | `rules=7` |
| 8 | `url` (the built material) | `url=https://docs.google.com/presentation/d/…/edit` |
| 9 | `round`, `findings` | `round=2 findings=3` |
| 10 | `asked` (questions left for the user) | `asked=2` |

## What `flow.py` shows

- **The state of each step.** For each file, and for the whole material (records without `--files`), the last record is its state; no record replaces another. A step is 「止まった」 if any of these is, 「始めた」 if any is still open, and otherwise 「済んだ」 (「飛ばした」 if all were skipped), so a step is done only when every scope is. The order is the order of lines in the file, never the clock: the file is only appended to, under a lock.
- **Where the work is, and the next step.** The first step still 「始めた」 or 「止まった」 is where the work is (so going back to an earlier step for a fix after delivery shows, with the furthest recorded step beside it to tell rework from a forgotten close), and the next action is to continue it or clear what stopped it, with the scopes still open. Files changed after 「済んだ」 are also listed at the top, so a fix made without a record shows there. If no step is open, the next step is the one after the furthest recorded step in "Overall flow"; record a step that does not apply as 「飛ばした」 and move on.
- **Changed since finished.** For each file whose last record is 「済んだ」, a content that no longer matches the recorded hash, or a missing file. A file changed and changed back matches again. After reworking a page on purpose, record it again (「済んだ」 with `--files`) to take the new content as finished. A link inside the folder counts as the file it points to.
- **The built URL.** An `out` URL at step 8 whose Google file ID is in neither the outline nor `社内メモ_*.md` (where deck-drive-003 writes the URL; the `/a/<domain>/`, `/u/0/`, and Drive forms of the same file match).
- **The facts.** What the files and the ledger show for each step. Other `out` values, such as `pages=24`, are shown as written and not compared with the files, so compare them yourself. Lines it cannot read are counted and skipped.

## When a record helps

- **Before a summary** (deck-flow-005): the records survive in the folder, and after the summary one `flow.py` call shows where to resume (deck-flow-015).
- **When the files cannot tell**: the planned page count, the built URL, a skipped step, or waiting for an answer in 「聞く」.
- **When child agents write pages** (slides-flow-016): record step 7 「始めた」 for the whole material and, when you hand out the pages, 「始めた」 with `--files` for each child's planned pages (they need not exist yet), because the join sees only scopes that have a record. Ask each child to record its own pages when it finishes (`flow.py record <material folder> 7 済んだ --files build/p06.json build/p07.json`). Step 7 is 「済んだ」 only after the parent records it 「済んだ」 for the whole material and every child's pages are 「済んだ」 or 「飛ばした」. A page dropped from the plan is recorded 「飛ばした」 with `--files`, even after the file is deleted; the children's hashes keep watching the pages after step 7 closes.

A short material finished in one sitting may need no record; the files and the outline already say enough.
