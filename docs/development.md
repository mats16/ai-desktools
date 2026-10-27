# Checking behavior while developing

Procedures for changing the plugin. Make changes in a worktree of the repository, put a test workspace `sandbox/` under that worktree, and check by building materials there. `.gitignore` excludes `sandbox/`, so it stays out of commits and goes away with the worktree. Each worktree has its own sandbox, so you can try several branches side by side. Verified on 2026-10-12 with Claude Code and pi 1.0.0, and on 2026-10-20 with Codex CLI 0.162.1. For how users install the plugin, see [claude-code-plugin.md](claude-code-plugin.md), [codex-plugin.md](codex-plugin.md), and [pi.md](pi.md).

Keep the original checkout (the first line of `git worktree list`) on `main`. Plugins installed in other workspaces by this checkout's path read it, so they run what users get (plugins installed from GitHub or a git URL read a version separate from the checkout).

## Create the sandbox

```sh
cd <worktree>
python3 skills/desk-init/scripts/init.py sandbox && cd sandbox   # templates; keeps files that already exist
cp ~/Documents/desk.toml .         # the production settings; only to build on Google (if they are in ~/.desk.toml: cp ~/.desk.toml desk.toml)
cp -R ~/Documents/rules ~/Documents/AGENTS.md ~/Documents/CLAUDE.md .   # only to test with the production rules
```

Change the copied `desk.toml` so that nothing on the Google side of production gets overwritten:

- If you copied `~/.desk.toml`, delete its `workspace` line. The sandbox's own `desk.toml` makes `sandbox/` the workspace and `workspace` there is not read, but the line misleads whoever reads the file.
- Point `[drive]` at a test Drive folder ("Clean up" below).
- To try templates, empty `[slides.templates]` and create them under the test `[drive] desk` with `template.py <theme> --from-base [<source URL>]` (this writes the URL in). `template.py <theme>` rewrites the templates in `[slides.templates]` in place, so leave no production URLs there. To try a production theme, also copy the production `themes/slides/` (`template.py` writes the cover and section divider widths and the background brightness into it).
- Don't run `git init` in `sandbox/` (desk-init asks about it). It would become a nested repository that `git clean` in the worktree doesn't remove.
- `desk-kaizen` is the one skill that doesn't test this worktree: `kaizen.py start` clones GitHub's `main` into `sandbox/.desk/kaizen/<name>/repo`.

With `~/.desk.toml` in place, scripts and hooks run outside `sandbox/` (such as at the worktree root) use the production workspace: its settings, `rules/`, and `.desk/`. Run them in `sandbox/`, or start them with `DESK_CONFIG=` (an empty value skips `~/.desk.toml`; `deck-practices/scripts/desk.py`). Inside `sandbox/`, its own `desk.toml` is found first, so nothing from `~/.desk.toml` mixes in.

## Claude Code

In `sandbox/`, pass the plugin with `--plugin-dir` instead of installing it.

```sh
claude --plugin-dir ..
```

- At startup, the `path` of the plugin in `plugins` points to the worktree, and the 16 `desk-tools:` skills load. Check with the following (it prints the worktree path and the 16 names):

  ```sh
  claude --plugin-dir .. -p ok --model haiku --max-turns 1 --output-format stream-json --verbose 2>/dev/null \
    | python3 -c "import json,sys; e=next(e for e in map(json.loads, sys.stdin) if e.get('subtype')=='init'); print([p['path'] for p in e['plugins'] if p['name']=='desk-tools']); print(sorted(s for s in e['skills'] if s.startswith('desk-tools:')))"
  ```

- Don't install with `claude plugin marketplace add .. --scope project`. `~/.claude/plugins/known_marketplaces.json` holds only one marketplace named `desk-tools`, so it collides with the one added in the production workspace, and removing it also deletes the record of the one added elsewhere.
- `claude -p` children started from there (such as desk-dreaming's `run.sh claude`) don't have the plugin. To check children too, use pi.
- If the worktree is under a folder whose name starts with a dot (such as T3 Code's `~/.t3/worktrees`), conversations run with `claude -p` can't write files in the sandbox, treating them as "sensitive files" (even with `--permission-mode acceptEdits`). To build materials with `claude -p`, copy the sandbox to `/tmp/<name>/` and run `claude --plugin-dir <worktree>` there. Delete it when done.

## Codex

In `sandbox/`, install the worktree into a separate `CODEX_HOME`.

```sh
export CODEX_HOME=/tmp/adf-codex-$(basename "$(dirname "$PWD")") && mkdir -p $CODEX_HOME
codex plugin marketplace add .. && codex plugin add desk-tools@desk-tools
codex debug prompt-input ok | grep -oE 'desk-tools:[a-z-]+: ' | sort -u
```

- Put `CODEX_HOME` outside the worktree. Codex copies the whole worktree (the marketplace root), so inside it, Codex keeps copying itself and stops (`File name too long`).
- Don't run `codex plugin marketplace add ..` with the usual `~/.codex`. Only one marketplace named `desk-tools` can exist, so it collides with the one added in the production workspace.
- Conversations read the copy in `$CODEX_HOME/plugins/cache/desk-tools/desk-tools/local/`. Codex copies even a marketplace added by local path, so after each change, rerun `codex plugin add desk-tools@desk-tools`.
- The separate `CODEX_HOME` has no login. To run conversations, copy `~/.codex/auth.json` (the ChatGPT login), or `model_provider` and `[model_providers.<name>]` from `~/.codex/config.toml`. Session logs also go to `$CODEX_HOME/sessions/`, so desk-dreaming's `sessions.py` (which reads `~/.codex/sessions/`) doesn't see them.
- Hooks don't run until trusted. Trust them with `/hooks` in interactive Codex, or run `codex exec --dangerously-bypass-hook-trust`. Verified: the `sandbox/rules/` marker is injected after Codex runs `sed -n 1,3p ../skills/slides-build/visual.md` (also from inside code mode's `exec`), not again when the same file is read later, and when the skill is invoked as `$desk-tools:desk-doctor`.

## pi

In `sandbox/`, install the worktree as a package.

```sh
pi install -l ..
pi                                     # the first time, save trust with /trust (pi -p children can't ask)
(echo '{"type":"get_commands"}'; sleep 8) | pi --mode rpc --no-session 2>/dev/null \
  | python3 -c "import json,os,sys; r=os.path.realpath('..'); e=next(e for e in map(json.loads, sys.stdin) if e.get('command')=='get_commands'); print(sorted(c['name'] for c in e['data']['commands'] if c.get('sourceInfo',{}).get('path','').startswith(r)))"
```

The last command prints the 16 skills loaded from the worktree.

- The worktree is added to `.pi/settings.json` as `../..` (relative to `.pi/`), and its 16 skills and `extensions/rules.ts` load. `pi -p` children (desk-dreaming's `run.sh pi`, review requests) read the same. Verified by starting `pi -p` in `sandbox/`: slides-build's `SKILL.md` appears with the worktree path, and reading `../skills/slides-build/visual.md` appends `sandbox/rules/slides-build/visual.md`.
- Save trust by opening interactive pi in `sandbox/` and running `/trust`. `pi -p` children can't ask, so do this first. A decision saved for a parent folder applies to its subfolders too: with the home folder trusted, the package loaded in `pi -p` and `--mode rpc` without `--approve`. Trusting the whole folder that holds the worktrees (`~/.t3/worktrees` for T3 Code) stops the prompts, but it also silently loads the extensions of any other repository placed there later (「project trust」 in [pi.md](pi.md)).
- If another skill has the same name, the package's skill loses (「同じ名前のスキルがあるとき」 in [pi.md](pi.md)). Check that `sourceInfo.path` in `get_commands` points to the worktree.

## Check that `rules/` is appended

In `sandbox/`, write a rule file with a one-line marker and `paths: [slides-build/visual.md]`, and have the conversation open `../skills/slides-build/visual.md`. If the marker is appended after it, the hook (Claude Code, Codex) and the extension (pi) work. When a skill is invoked as `/desk-tools:<skill>` (Claude Code) or `$desk-tools:<skill>` (Codex), the rule files whose `paths` match its `SKILL.md` are appended (UserPromptSubmit); in pi, `/skill:<name>` appends them (`before_agent_start`). In Claude Code, `/compact` after such a call shows them again (SessionStart). For rule files without `paths`, open `../skills/deck-practices/start.md` (the list of them is appended), then an outline whose 「使う決まり」 names one (the file is appended). Reading two customer files in parallel in one message shows the customer's `memory.md` once. Claude Code gives the hook the folder the conversation last `cd`'d into as `cwd`, so the hook also looks for the workspace from `CLAUDE_PROJECT_DIR` (the folder the conversation was opened in); to check this, start it with `--add-dir ..` and have the conversation run `cd ../skills` before opening the file (without `--add-dir`, Claude Code resets `cwd` to `sandbox/` after a `cd` out of it, so the fallback is not used). The hook also tells a plugin file from the lines it prints in the tool's output, so opening it by name after `cd` into a skill folder appends the rules too: have the conversation run `cd ../skills/slides-build && sed -n 1,3p visual.md` (in Codex, also `sed -n 1,3p visual.md` with `workdir` set to `../skills/slides-build`). With `claude -p`, allow Bash with `--allowedTools Bash`; with `Bash(cd:*)`, the `cd` out of `sandbox/` is blocked. The hook alone can be checked without opening a conversation:

```sh
printf -- '---\ndescription: 試し\npaths: [slides-build/visual.md]\n---\n目印\n' > rules/marker.md
echo "{\"cwd\":\"$PWD\",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$PWD/../skills/slides-build/visual.md\"}}" \
  | python3 ../hooks/rules_overlay.py claude
```

## Build materials

In a `sandbox/` conversation, go through a scene that uses the changed skill (`/desk-tools:slides-build` in Claude Code, `$desk-tools:slides-build` in Codex, `/skill:slides-build` in pi, and so on), and check with lint and with images of the pages Google drew.

## Render the samples

After changing the JSON page schema or components, run `tests/render/run.py` in `sandbox/`. It builds the samples (every page in `skills/slides-build/samples/json/` and the single-component `component.json`) as a temporary deck in `[drive] internal`, runs lint (locally and after building), takes an image of every page, and writes `sandbox/.desk/render/report.md`, which sets each image beside its checks from `tests/render/expect.json`. After taking the images, it moves the deck to the trash (`--keep` keeps it).

```sh
python3 ../tests/render/run.py            # writes report.md; open the images yourself
python3 ../tests/render/run.py --judge    # then has claude -p look at the images and write OK or NG per page to judge.md
```

The exit status is 1 if lint reports `要修正` or `--judge` reports NG. `--judge` is an LLM's judgment, so open the images of NG pages to confirm. When you add a sample page, add its checks to `expect.json` (`--selftest` checks this).

## Test with fixture prompts

After changing the JSON page schema or the skill descriptions, give a prompt from [fixtures/](fixtures/) to a child agent with no conversation context, have it write the deck, and check the result against 「見るところ」 in each file (modeled on pom's dev-fixtures; 2026-10-16). Selftests can't tell whether the descriptions alone lead to the right components.

```sh
rsync -a --exclude sandbox --exclude .git --exclude docs --exclude tests <worktree>/ /tmp/adf-plugin/   # under a dot folder, claude -p children can't read the plugin either ("Claude Code" above)
cp -R <worktree>/sandbox /tmp/adf-fixture && cd /tmp/adf-fixture
claude --plugin-dir /tmp/adf-plugin -p "$(sed -n '/^```text$/,/^```$/p' <worktree>/docs/fixtures/02-gantt.md | sed '1d;$d')" \
  --permission-mode acceptEdits --disallowedTools WebFetch WebSearch --allowedTools "Bash(python3:*)" "Bash(uv run:*)" "Bash(ls:*)" "Bash(mkdir:*)"
```

Leave `docs/` and `tests/` out of the copy, so the child can't read 「見るところ」 (the checks you grade it by) or `tests/render/expect.json`. A child that can reach the answer key may read it without being told to: Harness² found a Codex run fetching its own task's rubric (2026-10-25 in 「決めたこと」 in README). The fixtures are also public on GitHub, so keep web tools away from the child: `claude -p` inherits the allow rules in your `~/.claude/settings.json` (such as `WebFetch(domain:github.com)`), and `--allowedTools` only adds to them, so deny them with `--disallowedTools`, which wins over allow rules.

Look at the files the child wrote and the lint results, and where it hesitated over how to write something, fix the schema or the descriptions. Make each prompt differ in content from the samples (`skills/slides-build/samples/json/`); otherwise you can't tell whether the child only copied a sample. Delete `/tmp/adf-plugin` and `/tmp/adf-fixture` when done.

To compare a change against `main` on the same fixtures, `kaizen.py probe` in `desk-kaizen` does this for both versions and has a blind child pick one. It compares `.desk/kaizen/<name>/repo` with `base/` (GitHub's `main`, both made by `kaizen.py start`), not the worktree, so commit the change in `repo/` first.

## Try the worktree in the production workspace

To test with the production workspace's rules and materials, start from the workspace root and pass the worktree with launch options. Leave what is installed unchanged.

```sh
cd ~/Documents
claude --plugin-dir <worktree>
pi -ns --skill <worktree>/skills -ne -e <worktree>/extensions/rules.ts
```

- Claude Code loads only the `--plugin-dir` version, even when the plugin is also installed (no duplicates).
- In pi, adding only `--skill` lets the installed package win. With `-ns` (no skill discovery) and `-ne` (no extension discovery), only what you pass loads. Other skills (such as `~/.agents/skills`) and extensions stop loading too.
- Codex has no launch option for passing a plugin without installing it. To test in the production workspace, install into a separate `CODEX_HOME` as in "Codex" above.
- For both Claude Code and pi, the options don't reach child processes. Children read the installed version (the original checkout, if it was installed by that path).

## Clean up

Deleting the worktree deletes `sandbox/`. To recreate the sandbox and keep the worktree, run `rm -rf sandbox`. `git clean -fdx` in the worktree deletes `sandbox/` and the other ignored files (`node_modules/` and so on).

What remains:

- Slides and documents built on Google Drive. Delete the whole test folder set in `[drive]`.
- The `CODEX_HOME` from Codex tests (`/tmp/adf-codex-<worktree name>`). Delete it with `rm -rf`.
- Claude Code memory and session logs (`~/.claude/projects/<sandbox path with / . _ replaced by ->/`) and pi session logs (`~/.pi/agent/sessions/--<sandbox path with / replaced by ->--/`). They are harmless, but delete them now and then.
