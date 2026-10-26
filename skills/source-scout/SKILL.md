---
name: source-scout
description: Manage and learn the sources a recurring job reads (Slack channels and searches, mail queries, RSS feeds, wiki and web pages), so each run reads where it pays. Per topic, keeps the list of sources and a record of every run (what was read, what was used, what only that source had, what was missed, what readers said) and short notes on how to read each source. From that record it plans the next run, which reads every core source, explores new and promising ones, rests sources that gave nothing, and catches up on sources that failed. It also briefs child agents to read in parallel, merges their finds, and drops what was already used. What to collect and what to make from it (goal, audience, categories, window, output) come from the prompt; this skill holds no topic. Use for scheduled collection 「毎朝の〜のアップデートを集めて」, when asked 「どのチャンネルを見ればいいか学ばせて」「読む先を見直して」, and when setting up a new recurring collection.
---

# Scout the sources of a recurring job

This skill decides where to read and learns from each run. What to collect and what to make from it come from the prompt (or from the workspace skill that calls this one): the topic name, the goal and audience, the categories, the window, and the output (a markdown digest, then slides with `slides-build` or a post). The main agent writes the output from the merged candidates; the script never decides what to publish, only which sources earned it.

| File | Use |
|---|---|
| `scripts/scout.py` | The plan, child prompts, feeds, merge, record, report, and the source list (has `--selftest`) |
| [prompt_collect.md](prompt_collect.md) | The child agent's brief, filled by `scout.py prompt` |
| [kinds.md](kinds.md) | How to read each kind of source (Slack, searches, mail, feeds, wiki, web) and the tool pitfalls. Children read it |
| `<workspace>/.desk/scout/<topic>/sources.json` | The source list: tier, mode, group, pinned, notes. Edited only through `scout.py set` and `record` |
| `<workspace>/.desk/scout/<topic>/runs.jsonl` | One line per run: reads, candidates with the sources they were seen in, what was published, discoveries, misses, lessons, reader feedback |

```sh
S=<source-scout folder>/scripts/scout.py   # run in the workspace
```

## Inputs from the prompt

Take these from the prompt and do not guess them. If one is missing in a scheduled run, use the default and say so in the report.

- **Topic** (`vendor-news`, `cloud-jp`): the folder name under `.desk/scout/`. Required.
- **Goal**: who reads the output and what they do with it, and the categories with what goes in each. Pass it to every child as `--goal`, because the children pick candidates by it.
- **Window**: `--hours 24` by default, or `--since`/`--until` as the prompt says (「月曜は 72 時間」 → `--hours 72` on Mondays). Measure from the run time, not from the end of the last run.
- **Output**: what the run makes (a markdown digest, slides, a post) and where it goes. Write each item's source URL into the markdown, because `record --published` marks an item as used when that markdown contains its URL.
- **Seed sources** (first run only): channels, queries, feeds the prompt names.

## Each run

1. **Plan.** `python3 $S plan <topic> --hours 24` prints the groups to read, each source's start (a source that failed last time starts where it failed, up to 7 days back), its mode and notes, the candidates to explore, and the changes to ask the user about. Keep the "ask" lines for the report.
2. **Collect in parallel.** For each group except `feed`, run `python3 $S prompt <topic> <n> --goal "<goal>"` and pass the output as the whole prompt to a new child agent, all in one message so they run at the same time (in T3 Code, `delegate_task` with `mode` `async`; in Claude Code, Agent with the same model as yours). Do not fill `prompt_collect.md` by hand. Make a new folder for this run (`D=$(mktemp -d /tmp/<topic>.XXXX)`), so that replies from an earlier run never get merged again. Meanwhile run `python3 $S feeds <topic> --out $D/feeds.json`. Save each child's JSON to `$D/<n>.json`. Rerun a failed or timed-out group once; if it fails again, go on without it (`merge` records its sources as failed, and the next run reads them from this window's start).
3. **Merge.** `python3 $S merge <topic> $D/*.json --out $D.run.json` joins the same news across sources, marks items already published (`［載せ済み］`) and similar titles (`［似ている］`), and prints a numbered list. Read only this list, not the children's raw output.
4. **Make the output.** Choose items by the goal, open the pages of the chosen ones (or hand them to writer children), and write the markdown the prompt asks for, with each item's source URL. Skip `［載せ済み］` items unless they changed; check `［似ている］` ones against the earlier output.
5. **Record.** `python3 $S record <topic> $D.run.json --published <the markdown>`. It marks the published items, adds the children's lessons as notes (a near-duplicate note gets a vote instead of a copy), applies votes, and promotes candidates. Relay its lines in the report. Record before building slides or posting, because a later failure should not lose what was learned. If items are added or removed after review, edit the markdown and record the same run JSON again; it replaces that run and does not apply its lessons twice. A run is identified by the end of its window, so a new `plan` starts a new run (a second run on the same day keeps the first).
6. **Report.** Paste `python3 $S report <topic>` into the markdown as 「## 情報源」 if the prompt wants it. In the final report, list sources that failed, what `record` changed, and the "ask" lines from `plan` and `record`.

## How it learns

- [source-scout-001] **Credit goes to the sources that would be missed.** Each published item gives 1 point, split across every source it was seen in. A source whose items always appear elsewhere too earns little, even if it is busy. Recent runs weigh more (each older run counts 0.93 times the next, so the weight halves in about 10 runs), because channels change over time.
- [source-scout-002] **Applied without asking:** a candidate that earns 2 points is promoted to `core` (one the user moved back to candidate counts only the runs after that); lessons become notes; a source that failed is read again from where it failed. Each change is printed and recorded in the run.
- [source-scout-003] **Asked, never applied:** demoting a `core` source whose record shows almost nothing unique after about 17 reads, removing a note voted down twice, a source failing twice in a row. Apply the user's answer with `set` (`tier=candidate`, `tier=muted`, `pinned=true` to stop asking). Do not demote on your own, because a demoted source can no longer be what a run would miss.
- **Exploring.** Each run reads up to 3 candidates (`--explore`): new sources first (created within 14 days, found by a channel search or a link), then those with the highest upper estimate (little read, often found, or credited). A candidate explored with nothing published rests for 10 runs. A `muted` source is read again once every 20 runs.
- **Discovering.** Children report sources they were pointed to (forwards, `#channel` links, channel searches, wiki contact pages) in `discovered`. They become candidates without any edit.
- **Notes stay short and itemized.** One fact per note, with votes. Do not grow a long prose file of reading tips, because it costs every run and buries the useful lines. Topic-wide tips go in with source `*`.

## Reader feedback

When readers react to the published output (a reply 「これは要らない」, a correction, a request for more on an item), add to the next run's JSON `"feedback": [{"url": "<item URL>", "value": 0, "why": "<one line>"}]` (0 for not wanted, 2 for wanted more, 1 is the default). It changes the credit of every source that item came from.

## Set up a topic

1. Write the seed sources from the prompt to a JSON list: `[{"id": "slack:C0123456789", "name": "team-announce", "tier": "core", "mode": "full"}, {"id": "feed:https://example.com/feed.xml", "name": "release notes", "tier": "core"}]`. Use `group` to keep sources that one child should read together (a digest bot and its source channels). Use `"mode": "filter"` for busy channels and `"mode": "index"` for digest bots.
2. `python3 $S set <topic> --from <file>`, then `python3 $S sources <topic>` to check.
3. To move an existing record kept in another form, convert it into `runs.jsonl` lines (`reads`, `items` with `seen_in` and `used`, `discovered`) so that the first plan starts from it.
4. For a schedule, register a prompt that names this skill, the topic, the goal, the window, and the output (in T3 Code, `schedule_task`). Keep topic rules (categories, wording, who may see what) in that prompt or in the workspace skill that calls this one, not here.
