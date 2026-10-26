---
name: desk-migrate
description: Move a workspace made with an earlier version of AI Desk Tools to the current one (the 2026-10-24 renaming of skills, splitting of plugin files, and new rule IDs; the 2026-10-25 renaming of factory.toml to desk.toml, .factory/ to .desk/, factory-* skills to desk-*, and dreaming to desk-dreaming with its rule IDs). After a backup, renames the settings and records, moves rules/ files, and rewrites rule IDs, names, and paths in rules/, AGENTS.md, customers' memory.md, and the rule ledger, then has you split overrides whose plugin file was split. Also moves the workspace's desk.toml to ~/.desk.toml when the plugin is installed for the whole user. Use when desk-doctor reports 「前の版のワークスペース」, after updating the plugin, or when asked 「移行して」「migrate して」「設定を ~/.desk.toml に移して」.
---

# Move a workspace to the current version

Run in the workspace (the folder with `desk.toml`, or `factory.toml` before 2026-10-25; a workspace set in `~/.desk.toml` is found from any folder). `migrate.py` changes only the workspace's own files (`rules/`, `AGENTS.md`, `Customers/*/memory.md`, `.desk/ledger.jsonl`) and takes a backup first, because these hold the user's rules and their history.

```sh
M=<this skill's folder>/scripts/migrate.py
python3 $M check                 # what would move and change. Changes nothing
python3 $M apply                 # backup to .desk/migrate/<time>/, then move and rewrite
python3 $M relink <P-ID> <rules/ file>|--split   # decide where a ledger proposal goes after the split (from 「要判断」)
python3 $M rename-id <old> <new> # rename one workspace rule ID everywhere (rules/, AGENTS.md, memory.md, the ledger, the harness snapshots in .desk/harness/); only for a mistyped or colliding ID
python3 $M to-user               # move <workspace>/desk.toml to ~/.desk.toml and add workspace (see below)
```

## Steps

1. **Check.** Run `check` and show the user the list in one message (what moves, which files are rewritten, and the IDs each file changes as old → new). Do not wait for approval: the backup makes it reversible.
2. **Apply.** Run `apply` and relay its lines as they are (「控え」「移した」「写した」「書き換えた」「番号を替えた」「台帳を合わせた」「移していない」「要判断」).
   - 「番号を替えた」: two earlier workspace rules would have got the same new ID (for example `ws-prompt_doc-001` and `ws-prompt_slides-001` both become `ws-deck-review-…`), so the later one took the next free number. The rule text and the ledger got the same new ID, so their histories stay apart.
   - 「移していない」: the new path already has a file. Open both, merge the old one's rules into the new one (keep the IDs), and delete the old one.
   - 「移した: factory.toml」 (2026-10-25): `factory.toml` became `desk.toml` in the same folder (`[factory]` → `[desk]`, `[drive] factory` → `[drive] desk`; the old file is kept as `.desk/migrate/factory.toml`), `.factory/` became `.desk/`, and `rules/factory-<x>/` became `rules/desk-<x>/`. `.gitignore` gets `!/desk.toml` in place of `!/factory.toml`. If the workspace is a git repository, tell the user that `factory.toml` now shows as renamed to `desk.toml`.
   - `rules/dreaming/` → `rules/desk-dreaming/` (2026-10-25): the skill `dreaming` became `desk-dreaming`, and its rule IDs `factory-dreaming-<n>` became `desk-dreaming-<n>` (`ws-` IDs too). The record folder `.desk/dreaming/` and the ledger's `by` value `dreaming` stay. When the workspace has `.desk/dreaming/` and still had the old name, `apply` adds 「要判断: 定期の整理…」: the scheduled cleanup was registered with the old name (the line in `prompt.txt`, or the path of `run.sh` for launchd and cron), outside the workspace, so `migrate.py` cannot fix it. Open `../desk-dreaming/SKILL.md`, then its `schedule.md`, and tell the user to remove the old registration and register again by the steps at its top, because a run that cannot find the old skill or `run.sh` stops without a report.
   - 「写した」 `checks.py`: slides lint reads `slides(p, r)` from `rules/slides-build/checks.py`, and document lint reads `doc(doc, r)` from `rules/docs-build/checks.py`. Delete the function each file does not use.
3. **Split the overrides of split files (「要判断」).** The plugin split some files (the list after 「要判断」 says into which). A workspace override (`rules/<skill>/<file>`) is shown only when its plugin file at the same path is opened, so a rule that adds to a section that moved would no longer be shown in the right place.
   - For each `ws-` rule listed under the line, `migrate.py` names the plugin file of the rules it refers to. Open that plugin file and check that the rule adds to or overrides that section. If it names nothing, decide from the content.
   - Move the rule line (with its ID) to `rules/<skill>/<that file>`. A rule may stay where it is when its plugin section is still in that file.
   - Keep the rule's ID when you move it: IDs name what a rule is about, not its file (`deck-practices/rules.md` "Rule IDs").
   - After moving the rules, run `apply` again. Proposals in the ledger that target a split file (still to apply, or applied) keep the old `file`, so `ledger.py apply`, `undo`, and `drift` would not find their text. When the text now sits in exactly one other file, `apply` moves the proposal there (「台帳を合わせた」). Rejected, withdrawn, undone, and sent proposals are left alone.
   - 「要判断: 台帳の P… の変更先 …」: the destination cannot be read from the text. Decide it, and record the decision with `relink`, because `check` and desk-doctor keep reporting the workspace as an earlier version until every one is decided:
     - an add proposal not applied yet (no old text): `migrate.py relink <P-ID> <rules/ file>`, the file it should add to (the same file if it still fits there);
     - a proposal not applied yet whose old text moved: `relink` to the file that now holds that text, or withdraw it with `ledger.py withdraw <P-ID>` if it is no longer needed;
     - an applied proposal whose text you split across files: `migrate.py relink <P-ID> --split`. It records the split; that proposal can then no longer be undone, and `ledger.py drift` lists it as text that is gone (say both in the report). If its text is in one file, `relink` to that file instead.
4. **Check again.** Run `check` (it should print 「移すものはない（今の版）」) and `desk-doctor` (`python3 <desk-doctor folder>/scripts/doctor.py --local`).
5. **Report.** In one message: what moved, the rules you split and where they went, and the backup folder. Tell the user that deleting the backup is their call.

## Move the settings to `~/.desk.toml`

Only when the user installs the plugin for the whole user, or asks for it (2026-10-25 in 「決めたこと」 in README). A workspace with its own `desk.toml` keeps working as it is, so do not suggest this otherwise.

1. Run `to-user` in the workspace. It writes `~/.desk.toml` (the path in `DESK_CONFIG` if set) from the workspace's `desk.toml` with `workspace = "<workspace>"` added at the top, and moves the old file to `.desk/migrate/desk.toml`. Relay its line as it is.
2. 「移していない（… がもうある）」: `~/.desk.toml` already exists. Show both to the user, merge the values they choose into `~/.desk.toml` (keep `workspace`), then move the workspace's `desk.toml` to `.desk/migrate/` by hand, because the two are never merged when read.
3. If the workspace is a git repository, tell the user that `desk.toml` now shows as deleted (the current `.gitignore` template no longer includes it).
4. Run `desk-doctor` from a folder outside the workspace: 「設定」 should be `~/.desk.toml` and 「ワークスペース」 this workspace.

## Notes

- `apply` and `check` can be run any number of times. Files already in the current form are not changed.
- `.desk/migrate/relink.json` (the proposals to a split file that existed at the first migration: those not applied yet, and applied ones whose text was in place; proposals made later are never watched, so a current workspace is not reported as an earlier version) and `relink_done.json` (the decisions made with `relink`) are kept next to the backups. Keep them until the overrides are split; the backup folders themselves can be deleted.
- It does not touch the material folders (`Customers/<customer>/<material>/`, `Internal/`, `Research/`), because they are records of past work. Old IDs and paths in an outline or memo stay as they were; look them up in `scripts/ids_*.json` when needed.
- In the ledger, the fields that hold people's own words (`quote`, `a`, `reason`) are not rewritten, so the user's words stay as said; old IDs or names in them stay too.
- The ID maps are `scripts/ids_<date>.json` (`ids`: old → new plugin ID; `prefixes`: old → new prefix, used for `ws-` IDs and for plugin IDs no longer in the plugin), applied in date order: `ids_20261024.json` (IDs by topic) and `ids_20261025.json` (`factory-dreaming` → `desk-dreaming`). IDs do not change otherwise (`deck-practices/rules.md` "Rule IDs"); a future rename adds another dated map.
- To undo, copy the backup folder's contents back over the workspace.
