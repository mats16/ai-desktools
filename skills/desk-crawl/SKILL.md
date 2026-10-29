---
name: desk-crawl
description: Decide which places a recurring collection job reads and how often, and learn it from every run. Per topic (an area to read, such as `vendor-updates`), keeps the list of places (Slack channels and searches, mail searches, RSS and Atom feeds, web pages and searches, wiki pages) and a record of each run. Plans each run (reads the places that pay, spaces out the ones that rarely do, catches up on what was skipped or failed, tries new and pointed-to candidates), briefs child agents to read them shallowly (title, link, summary, where each item was seen), merges the finds, and learns from what the consumers used and missed. Reads only the places in its list, within the window. Does not research a question, verify claims, keep citations, pick items, or write the output; the consumers do that with their own interests. Use for scheduled collection 「毎朝の〜のアップデートを集めて」, when asked 「どこを読めばいいか学ばせて」「読む先を見直して」, and when setting up a new recurring collection.
---

# Crawl the places a recurring job reads

This skill decides where and when to read, and learns from each run. A topic is an area to read, not a project or a reader. Make one topic per area (`vendor-updates`) and collect it once, at the shortest interval any consumer needs, so the same channel is not read once per project. The consumers (a daily digest, a project's watch, a customer's news) pick from the merged candidates by their own interests and write their outputs. They return two things only: the outputs (to mark what was used) and what they missed. Keep interests, categories, wording, and who may see what in the consumers, not here. A place only one consumer needs (a customer's newsroom) goes in its own topic.

| File | Use |
|---|---|
| `scripts/crawl.py` | Plan, extra reads, child prompts, feeds, merge, record, report, and the list of places (has `--selftest`) |
| [prompt_collect.md](prompt_collect.md) | The child agent's brief, filled by `crawl.py prompt` |
| [kinds.md](kinds.md) | How to read each kind of place (Slack, mail, feeds, web, wiki), the tool pitfalls, finding a site's feed, and naming a new kind. Children read it |
| `<workspace>/.desk/crawl/<topic>/sources.json` | The list of places: tier, group, pinned, url, notes. Edited only through `crawl.py set` and `record` |
| `<workspace>/.desk/crawl/<topic>/runs.jsonl` | One line per run: reads, candidates with the places they were seen in, what was used, misses, discoveries, lessons |

```sh
S=<desk-crawl folder>/scripts/crawl.py   # run in the workspace
```

## Inputs from the prompt

Take these from the prompt and do not guess them. If one is missing in a scheduled run, use the default and say so in the report.

- **Topic** (`vendor-updates`, `cloud-jp`): the folder name under `.desk/crawl/`. Required.
- **Goal**: what the consumers look for, in a few lines. Pass it to every child as `--goal`, because the children report the candidates that fit it.
- **Window**: `--hours 24` by default, or `--since`/`--until` as the prompt says (「月曜は 72 時間」 → `--hours 72` on Mondays). Measure from the run time, not from the end of the last run.
- **Consumers and outputs**: who picks from this run and what each makes (a markdown digest, slides, a post). Each output keeps each item's source URL, because `record --published` marks an item as used when an output contains its URL.
- **Seed places** (first run only): channels, queries, feeds the prompt names.

## Each run

1. **Plan.** `python3 $S plan <topic> --hours 24` prints the groups to read, each place's start (where it was last read, up to 7 days back), its notes, the candidates to explore, the `follow` places skipped by their interval, and the changes to ask the user about. Keep the "ask" lines for the report.
2. **Collect in parallel.** For each group except `feed`, run `python3 $S prompt <topic> <n> --goal "<goal>"` and pass the output as the whole prompt to a new child agent, all in one message so they run at the same time (in T3 Code, `delegate_task` with `mode` `async`; in Claude Code, Agent with the same model as yours). Do not fill `prompt_collect.md` by hand. Make a new folder for this run (`D=$(mktemp -d /tmp/<topic>.XXXX)`), so that replies from an earlier run never get merged again. Meanwhile run `python3 $S feeds <topic> --out $D/feeds.json`. Save each child's JSON to `$D/<n>.json`. Rerun a failed or timed-out group once; if it fails again, go on without it (`merge` records its places as failed, and the next run reads them from this window's start).
3. **Merge.** `python3 $S merge <topic> $D/*.json --out $D.run.json` joins the same news across places, marks items used before (`［使われた済み］`) and similar titles (`［似ている］`), and prints a numbered list. Read only this list, not the children's raw output.
4. **Read more (when the list calls for it).** If an item points to a place worth reading today (the channel of a product announced today, a vendor's release page, a place a child discovered), run `python3 $S more <topic> <id>...` (up to 3 per run), brief one more child with the group number it prints, save the reply in `$D`, and merge again with every reply. Each extra read counts as exploration, so places that give nothing rest.
5. **Hand the list to the consumers.** Each picks by its own interest, opens the pages it needs, and writes its output with each item's source URL. Skip `［使われた済み］` items unless they changed; check `［似ている］` ones against the earlier output.
6. **Record.** `python3 $S record <topic> $D.run.json --published <output>... [--missed <file>...]`. Pass every output made from this run so far. When a consumer finishes later, record again with all the outputs; it replaces the run, keeps the misses added before, and does not apply lessons twice. Recording again with only `--missed` keeps the items marked used before. Record before building slides or posting, because a later failure should not lose what was learned. A run is identified by the end of its window, so a new `plan` starts a new run.
   - The misses file lists items a consumer learned elsewhere that this crawl should have found: `[{"url": "<item URL>", "source": "<kind>:<ref>, if known", "why": "<one line>"}]`. A miss reported after its run goes into the next run's record.
   - Relay `record`'s lines in the report. For each 「読む先にないサイト」, open the site: if it is a stream of updates (a blog, release notes), find its feed ("Finding a site's feed" in `kinds.md`) and add it with `set <topic> feed:<URL> tier=candidate`; if it is reference material (docs), run `set <topic> web:https://<host> tier=dropped` so it is not suggested again.
7. **Report.** Paste `python3 $S report <topic>` into an output as 「## 情報源」 if the prompt wants it. In the final report, list places that failed, what `record` changed, the "ask" lines from `plan` and `record`, and the trend line from `report`.

## How it learns

- [desk-crawl-001] **Credit goes to the places that would be missed.** Each used item gives 1 point, split across every place it was seen in. A place whose items always appear elsewhere too earns little, even if it is busy. A miss gives 1 point to its place when the place is known, because learning only from used items can only read less. The value of a place is its credit per day it covered, weighted to recent runs (each older run counts 0.93 times the next, so the weight halves in about 10 runs), because channels change over time and because a place read every 4 runs covers 4 days at once.
- [desk-crawl-002] **Applied without asking:**
  - Interval: a `follow` place is read every run, every 2 runs, or every 4 runs, by its value against the median of the topic's `follow` places (at least half: every run; at least a quarter: every 2 runs; below: every 4 runs). A place read fewer than 5 times is read every run, because one empty read says little. It is read anyway after 6 days since its last read, after a failed read, and in the run after it was used, missed, or pointed to. `pinned` places are read every run. A skipped place is read from where it was last read, so spacing delays items but never drops them.
  - A candidate that earns 2 points becomes `follow` (one the user moved back to candidate counts only the runs after that). Lessons become notes. A place that failed is read again from where it failed. Each change is printed and recorded in the run.
- [desk-crawl-003] **Asked, never applied:** dropping a `follow` place that, read every 4 runs, gave almost nothing in its last 10 reads; removing a note voted down twice; a place failing twice in a row. Apply the user's answer with `set` (`tier=dropped`, or `pinned=true` to read it every run and stop asking). Do not drop on your own, because a dropped place is never read again, so nothing it carries can be noticed.
- **Exploring.** Each run reads up to 3 candidates (`--explore`): first the places credited in the last run (the origin of a miss or of a forward), then new places (created within 14 days, found by a channel search or a link), then those with the highest upper estimate (little read, often found, or credited). A candidate explored with nothing used rests for 10 runs.
- **Discovering.** Children report places they were pointed to (forwards, `#channel` links, channel searches, wiki contact pages) in `discovered`; they become candidates without any edit. `record` lists the sites that used items cite (`public_url`) and that are not in the list yet. `more` reads the places today's items point to.
- **Notes stay short and few.** One fact per note, with votes; a near-duplicate lesson adds a vote instead of a copy. Children get the top 5 notes per place and for the topic. A note with no helpful vote for 30 runs is no longer passed (it stays, and `sources` shows it), so the brief does not grow with every run. Topic-wide tips go in with source `*`.
- **Watching it improve.** `report` compares the last 10 runs with the 10 before: places read per run, items used, misses, and items used from exploration and extra reads. Fewer places read with no more misses means it is learning. The record learns from what the consumers chose, so a drift in their choices shows up here too.

## Set up a topic

1. Write the seed places from the prompt to a JSON list: `[{"id": "slack:C0123456789", "name": "team-announce", "tier": "follow"}, {"id": "feed:https://example.com/feed.xml", "name": "release notes", "tier": "follow"}]`. Name ids as in the kinds table in `kinds.md`. Use `group` for places one child should read together (a digest bot and its source channels). Put how to read a place in `notes` (the markers for a busy channel, 「要約の bot。元の投稿を開く」).
2. `python3 $S set <topic> --from <file>`, then `python3 $S sources <topic>` to check.
3. To start from a similar topic, run `python3 $S sources <old topic> --json > <file>`, then `set <new topic> --from <file>`. It copies the `follow` places and the notes passed to children, not the record, so the new topic measures them again; spacing keeps the cost of copying too many small. The same file moves a list to another workspace or person. It holds channel IDs and names, so share it only where those may go.
4. For a schedule, register a prompt that names this skill, the topic, the goal, the window, and the consumers and their outputs (in T3 Code, `schedule_task`). Keep interests and output rules (categories, wording, who may see what) in that prompt or in the consumer, not here.
