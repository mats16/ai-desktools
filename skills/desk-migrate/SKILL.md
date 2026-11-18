---
name: desk-migrate
description: Move a workspace made with an earlier version of AI Desk Tools to the current one - after a backup, rename and move its settings, records, and rules into today's names and layout (recipes), keeping the user's rules and their history. Also moves a workspace's desk.toml to ~/.desk.toml. Use when doctor.py (desk-init) reports an earlier version, after updating the plugin, or when asked 「移行して」「migrate して」「設定を ~/.desk.toml に移して」.
---

# Move a workspace to the current version

Run in the workspace (the folder with `desk.toml`, or `factory.toml` before 2026-10-25; a workspace set in `~/.desk.toml` is found from any folder). `migrate.py` changes only the workspace's own files (`rules/` and `recipes/`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `Customers/*/memory.md`, the 「使う決まり」 lines of outlines, `.desk/ledger.jsonl`, `.desk/harness/`, and, when splitting a hand-written index, `references_index.md`, `drive_folders.md`, `Research/references.md`, and empty 「使い道」 cells of ledgers) and takes a backup first, because these hold the user's rules and their history.

## Scripts

Script paths are relative to this skill's folder; resolve them from there.

| Task | Command and result |
|---|---|
| See what would change | `python3 scripts/migrate.py check` lists what moves, the files rewritten, and the IDs changed. Changes nothing |
| Migrate | `python3 scripts/migrate.py apply` backs up to `.desk/migrate/<time>/`, then moves and rewrites |
| Settle a split file's proposal (from 「要判断」) | `python3 scripts/migrate.py relink <P-ID> <rules/ file>\|--split` |
| Settle a workspace rule ID (from 「要判断」) | `python3 scripts/migrate.py relink-id <ws-ID> <workspace file>\|戻さない` records where it goes, then removes it |
| Move the settings to `~/.desk.toml` | `python3 scripts/migrate.py to-user` (below) |

| Situation | Open |
|---|---|
| **Apply's lines:** what each line `apply` prints means (by the version that introduced it) and what to tell the user | [apply_lines.md](apply_lines.md) |

## Steps

1. **Check.** Run `check` and show the user the list in one message (what moves, which files are rewritten, and the IDs each file changes as old → new). Do not wait for approval: the backup makes it reversible.
2. **Apply.** Run `apply` and relay its lines as they are (「控え」「移した」「写した」「書き換えた」「番号を替えた」「台帳を合わせた」「移していない」「要判断」). Open [apply_lines.md](apply_lines.md) for each line it printed, and do what it says: some lines need a merge, a `relink-id`, or a message to the user.
3. **Settle the ledger proposals of split files (「要判断: 台帳の P…」), only if listed.** A full `apply` turns each old file into a recipe with its whole text, so its proposals follow it and nothing is listed. The lines appear only for a workspace an earlier version migrated part way:
   - Proposals in the ledger that target a split file (still to apply, or applied) keep the old `file`, so `ledger.py apply` and `undo` would not find their text. When the text now sits in exactly one other file, `apply` moves the proposal there (「台帳を合わせた」). Rejected, withdrawn, undone, and sent proposals are left alone.
   - 「要判断: 台帳の P… の変更先 …」: the destination cannot be read from the text. Decide it, and record the decision with `relink`, because `check` and `doctor.py` keep reporting the workspace as an earlier version until every one is decided:
     - an add proposal not applied yet (no old text): `migrate.py relink <P-ID> <rules/ file>`, the file it should add to (the same file if it still fits there);
     - a proposal not applied yet whose old text moved: `relink` to the file that now holds that text, or withdraw it with `ledger.py withdraw <P-ID>` if it is no longer needed;
     - an applied proposal whose text you split across files: `migrate.py relink <P-ID> --split`. It records the split; that proposal can then no longer be undone (say so in the report). If its text is in one file, `relink` to that file instead.
4. **Check again.** Run `check` (it should print 「移すものはない（今の版）」) and `doctor.py --local` (`desk-init`).
5. **Report.** In one message: what moved, the recipes made and their `step`, and the backup folder. Tell the user that deleting the backup is their call.

## Move an AGENTS.md from the old template

When `doctor.py` reports 「前の雛形の AGENTS.md」, open [agents_md.md](agents_md.md) and move it with the user (`migrate.py` does not move it).

## Move the settings to `~/.desk.toml`

Only when the user installs the plugin for the whole user, or asks for it (2026-10-25 in `docs/decisions.md`). A workspace with its own `desk.toml` keeps working as it is, so do not suggest this otherwise.

1. Run `to-user` in the workspace. It writes `~/.desk.toml` (the path in `DESK_CONFIG` if set) from the workspace's `desk.toml` with `workspace = "<workspace>"` added at the top, and moves the old file to `.desk/migrate/desk.toml`. Relay its line as it is.
2. 「移していない（… がもうある）」: `~/.desk.toml` already exists. Show both to the user, merge the values they choose into `~/.desk.toml` (keep `workspace`), then move the workspace's `desk.toml` to `.desk/migrate/` by hand, because the two are never merged when read.
3. If the workspace is a git repository, tell the user that `desk.toml` now shows as deleted (the current `.gitignore` template no longer includes it).
4. Run `doctor.py` (`desk-init`) from a folder outside the workspace: 「設定」 should be `~/.desk.toml` and 「ワークスペース」 this workspace.

## Notes

- `apply` and `check` can be run any number of times. Files already in the current form are not changed.
- `.desk/migrate/relink.json` (the proposals to a split file that existed at the first migration: those not applied yet, and applied ones whose text was in place; proposals made later are never watched, so a current workspace is not reported as an earlier version) and `relink_done.json` (the decisions made with `relink`) are kept next to the backups. Keep them until the overrides are split; the backup folders themselves can be deleted.
- It does not touch the material folders (`Customers/<customer>/<material>/`, `Internal/`, `Research/`), because they are records of past work, except the 「使う決まり」 line of an outline (`desk.py recipes` reads it), and, when splitting the old index, an empty 「使い道」 in a ledger row and `Research/references.md` (created, or appended to). Other old IDs and paths in an outline or memo stay as they were; look them up in `scripts/ids_*.json` when needed.
- 2026-11-01: the outline section 「書き方の決め」 was renamed 「書き方の取り決め」. `apply` does not rewrite it in existing outlines (they are records of past work, as above). The skills that name the section read either name, so nothing needs to move; when you edit an old outline, keep its heading as it is.
- In the ledger, the fields that hold people's own words (`quote`, `a`, `reason`) are not rewritten, so the user's words stay as said; old IDs or names in them stay too.
- The ID maps are `scripts/ids_<date>.json` (`ids`: old → new plugin ID; `prefixes`: old → new prefix, used for `ws-` IDs before they are removed and for plugin IDs no longer in the plugin), applied in date order: `ids_20261024.json` (IDs by topic), `ids_20261025.json` (`factory-dreaming` → `desk-dreaming`), and `ids_20261029.json` (`source-scout` → `desk-crawl`). IDs do not change otherwise (`desk-feedback/routing.md` "Rule IDs"); a future rename adds another dated map.
- To undo, copy the backup folder's contents back over the workspace.
