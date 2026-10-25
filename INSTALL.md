# AI Desk Tools を会話で入れる（エージェントが読む手順）

README の「会話で入れる」のプロンプトを貼られたエージェントが従う手順。プラグインを入れ、ワークスペースを作り、desk-doctor で確かめるまでを、1 つの会話で進める。手で入れる手順は README の「入れ方」。

このファイルは curl で読む（`curl -fsSL https://raw.githubusercontent.com/mats16/ai-desktools/main/INSTALL.md`）。WebFetch のように要約して返す道具では、コマンドと手順が欠ける。

## 決まり

- **この会話には、まだスキルがない。** 入れたスキルは次の会話から読み込まれる。この会話では `/desk-tools:desk-init`・`$desk-tools:desk-init`・`/skill:desk-init` を呼ばずに、入れた場所の `SKILL.md` を開いて従う（4）。
- **ワークスペースだけに入れる。** `~/.claude/settings.json`・`~/.pi/agent/settings.json` は変えない。Codex は入れる範囲がないので、`~/.codex/config.toml` で切ってワークスペースの `.codex/config.toml` で入れる（3）。ほかのフォルダの会話にはスキルが出ない。
- **ユーザーが決めることは聞いてから進める。** 場所、ツールを入れるか、`desk.toml` の値。ブラウザが開くログイン（`gcloud auth application-default login`）は、ユーザーに回してもらう。
- **あるファイルは上書きしない。** desk-init の `init.py` も上書きしない。
- 手順の `<ワークスペース>` と `<プラグイン>` は、1 と 3 で決まったパスに置き換える。スクリプトは今いるフォルダから `desk.toml` を探すので、ワークスペースのコマンドは `cd <ワークスペース> &&` を付けて回す。

## 1. 聞く

自分が Claude Code・Codex・pi のどれかは聞かない（自分で分かる）。次の 5 つをまとめて聞く（Claude Code なら AskUserQuestion。1 回に 4 つまでなので、1〜4 を聞いてから 5 を聞く）。

1. **ワークスペースにするフォルダ。** 資料（`Customers/`・`Internal/`・`Research/`）と `desk.toml` を置く。候補に、今の会話のフォルダと `~/Documents` を出す。なければ作る。すでに `desk.toml` か `AGENTS.md` があれば、足りないものだけ置くことを伝える。
2. **全社の共有テーマのフォルダ。** 会社でスライドのテーマ（テンプレート）を配っていれば、その Google Drive のフォルダの URL。なければ「ない」。プロンプトに URL が書いてあれば聞かずに使う。4 で `desk.toml` の `[drive] shared_themes` に書く。
3. **定期の整理（desk-dreaming）を回すか。** 会話の記録から、決まりに戻し忘れた指示を毎日拾うもの。選ぶのは「毎日 5:00 に回す（推奨）」「時刻を変える」「回さない」。どのスケジューラーに登録するかは聞かない（5 で、今の環境から決める）。
4. **資料を返したあと、付いたコメントを見張るか。** 人にコメントを頼んだあと、付いたコメントで直すもの。最後のコメント（なければ見張り始め）から決めた時間、新しいコメントがなければ見張りを終える。見張りは、資料を作った会話が開いているあいだだけ動く。選ぶのは「見張らない（既定）」「24 時間」「72 時間」「時間を決める」。見張らなくても、「コメントを見て直して」「コメントを見張って」と頼めば、そのときに取る。4 で `desk.toml` の `[feedback.google_comments] watch_hours` に書く（見張らないなら 0 のまま）。
5. **資料を作る言語。** 頼むときに言語を言わなかった資料は、この言語で作る（本文、スピーカーノート、納品物の名前まで）。選ぶのは「日本語（既定）」「English」「ほかの言語」。資料ごとに言えば、そのときだけほかの言語にできる。4 で `desk.toml` の `[desk] default_language` に書く（`ja`・`en` など）。

## 2. 前提を見る

```sh
python3 --version   # 3.11 以上
uv --version
git --version
```

足りないものは、入れ方を示し、ユーザーが良いと言ったら入れる。

- uv: `brew install uv`（macOS）か `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.11 以上: `brew install python@3.12` など。`python3` が古いままなら、このあとの `python3` を `uv run --python 3.11` に替えて回す。

## 3. プラグインを入れる

**Claude Code**

```sh
cd <ワークスペース>
claude plugin marketplace list --json | python3 -c "import json,sys; [print(m) for m in json.load(sys.stdin) if m['name']=='desk-tools']"   # もうあるか
claude plugin marketplace add https://github.com/mats16/ai-desktools.git --scope project
claude plugin install desk-tools@desk-tools --scope project
claude plugin list --json | python3 -c "import json,sys; [print(p.get('readFromFolder') or p['installPath']) for p in json.load(sys.stdin) if p['id']=='desk-tools@desk-tools' and p['enabled']]"
```

- 1 つめで `desk-tools` が出たら、`add` は飛ばす（名前は 1 つしか持てない。足すと前のものとぶつかる）。出た入れ元（`path`・`url`・`repo`）が、ここで入れるもの（GitHub）と違うときは、そのことと、ほかのワークスペースもその入れ元を読んでいることを伝え、そのまま使うかをユーザーに聞く。入れ元を勝手に替えない。
- 最後に出たパスが `<プラグイン>`。手元のパスから入れたなら checkout（`readFromFolder`）、GitHub から入れたなら写し（`installPath`）。

**Codex**

```sh
cd <ワークスペース>
codex plugin marketplace list --json | python3 -c "import json,sys; [print(m) for m in json.load(sys.stdin)['marketplaces'] if m['name']=='desk-tools']"   # もうあるか
codex plugin marketplace add mats16/ai-desktools
codex plugin add desk-tools@desk-tools --json | python3 -c "import json,sys; print(json.load(sys.stdin)['installedPath'])"
python3 -c 'import os,pathlib; p=pathlib.Path(os.environ.get("CODEX_HOME","~/.codex")).expanduser()/"config.toml"; k="[plugins.\"desk-tools@desk-tools\"]\nenabled = true"; s=p.read_text(); assert k in s, "見つからない"; p.write_text(s.replace(k, k[:-4]+"false"))'
mkdir -p .codex && { grep -qs 'desk-tools@desk-tools' .codex/config.toml || printf '\n[plugins."desk-tools@desk-tools"]\nenabled = true\n' >> .codex/config.toml; }
```

- 1 つめで出たときは、Claude Code と同じく `marketplace add` を飛ばし、入れ元（`marketplaceSource`）が違えばユーザーに聞く。
- 3 つめに出たパスが `<プラグイン>`（`~/.codex/plugins/cache/` の写し）。
- 4 つめでユーザーの設定の `enabled` を切り、5 つめでワークスペースだけで入れる。4 つめが止まったら、`~/.codex/config.toml` の `[plugins."desk-tools@desk-tools"]` を見せ、`enabled = false` にしてもらう（切らないと、どのフォルダの会話にもスキルが出る）。5 つめは、ワークスペースの `.codex/config.toml` にもう `desk-tools@desk-tools` があれば足さないので、そのときは中身を見て `enabled = true` かを確かめる。ワークスペースの `.codex/config.toml` は、そのフォルダを信頼したときだけ読まれる。
- hook は、次に対話の Codex をワークスペースで開いたとき、`/hooks` で `desk-tools` の 2 つを信頼してもらう（6 で伝える。信頼するまで `rules/` が出ない。`<プラグイン>/docs/codex-plugin.md`）。

**pi**

```sh
cd <ワークスペース>
pi install -l git:github.com/mats16/ai-desktools
```

`<プラグイン>` は `<ワークスペース>/.pi/git/github.com/mats16/ai-desktools`。

どれも `<プラグイン>/skills/desk-init/SKILL.md` があることを確かめる。

## 4. ワークスペースを作る

1. `<プラグイン>/skills/desk-init/SKILL.md` を開き、その手順に従う。「このスキルのフォルダ」は `<プラグイン>/skills/desk-init`、ほかのスキルのフォルダは `<プラグイン>/skills/<スキル>`。手順の 1（場所と設定の置き場所）は、ここの 1 で聞いたので飛ばす。設定はワークスペースの直下の `desk.toml` に置く（`init.py <ワークスペース>`。プラグインをワークスペースだけに入れるので、`--user` は付けない）。3 の `[drive] shared_themes` は、ここの 1 の 2 で聞いた値を書く。`[feedback.google_comments] watch_hours` は、ここの 1 の 4 で選んだ時間を書く（見張らないなら雛形の 0 のまま）。`[desk] default_language` は、ここの 1 の 5 で選んだ言語を書く（日本語なら雛形の `ja` のまま）。3 の `[slides] default_theme`（既定のテンプレート）は、テンプレートを作り、共有のテーマを `slides.py theme <url>` で写したあとで、`<プラグイン>/skills/slides-template/SKILL.md` の「Choosing the default theme」に従って選択式で聞く（1 では聞かない。何を選べるかは、そろってから分かる）。
2. desk-init の最後の手順（6 の「Check」）は、`<プラグイン>/skills/desk-doctor/SKILL.md` を開いて従う。要修正が 0 になるまで直す。Google のログインのように、ユーザーが回すものが残ったら、回してもらってから doctor をもう一度回す。

## 5. 定期の整理を登録する

1 の 3 で「回さない」なら飛ばす。渡すのは `<プラグイン>/skills/desk-dreaming/prompt.txt` の 1 行で、作業フォルダは `<ワークスペース>`、時刻は 1 の 3 で決めたもの。登録のしかたの詳しいことは `<プラグイン>/skills/desk-dreaming/schedule.md`（以下、schedule.md）。pi で回すときは、T3 Code の中でも手で入れるときも、先に対話の pi でワークスペースの trust を `/trust` で保存してもらう（人のいない回は trust を聞けず、保存していないとスキルが読まれない。`<プラグイン>/docs/pi.md`）。

1. **自分の道具にスケジューラーがあれば、それに登録する。** 道具の一覧から、定期の回を作る道具を探す（見えなければ「schedule」「scheduled task」で道具を探す）。使えるのは、次をすべて満たすものだけ。
   - 会話を閉じても、アプリを開き直しても残る。Claude Code の `/loop` のように、会話の中だけで動くものは使わない。
   - この PC で、`<ワークスペース>` を作業フォルダにして回る。クラウドや、回ごとに作るサンドボックス・git の worktree で回るものは使わない（ワークスペースのファイルと会話の記録を読めない）。
   - 人がいなくても、権限の確認で止まらない。

   時刻は手元の時間帯で書く（UTC が既定の道具もある）。2 つ以上あれば、この会話を動かしているアプリのものにする（T3 Code の中なら T3 Code）。よく使うものの値と注意は schedule.md にある（T3 Code の `schedule_task` は 1、Claude Code Desktop は 2、Omnigent の `sys_scheduled_task_create` は 4）。schedule.md にない道具でも、上を満たせば使い、登録した値を 6 で返す。
2. **なければ、手で入れてもらう。** Claude Code・Codex の CLI と pi には、会話を閉じても残るスケジューラーがない。launchd（macOS）か cron で `run.sh` を回す設定（schedule.md の 5）を、`<ワークスペース>`・run.sh のパス・時刻・引数（Claude Code なら `claude`、Codex なら `codex`、pi なら `pi`）を埋めて示し、入れる・すぐ回す・止めるのコマンドを添える。`~/Library/LaunchAgents/` と crontab は、エージェントが書かない（会話の外で毎日動くものを足すので、ユーザーが中身を見て入れる）。Claude Code Desktop を使っているなら、その Routines で作ってもよいことも添える（schedule.md の 2）。

登録したら、すぐ回して確かめる（道具の「すぐ回す」、launchd は `kickstart`）。権限の確認が出たら、ユーザーに許してもらう（次からは聞かれないようにする）。初めての回は 7 日前からの会話を見る。この回から 12 時間以内の次の回は、重ねないために止まる（desk-dreaming の run.md の 0）ので、6 で伝える。

## 6. 終える

次をまとめて返す。

- 置いたもの（init.py の「置いた」「残した」）と、`desk.toml` で埋めた値・空のままの値。既定のテーマ。資料を作る言語。コメントを見張る時間（見張らないなら、そう書く）。
- 定期の整理を登録したスケジューラーと時刻。手で入れてもらうものが残っていれば、その手順。
- doctor の結果。残った要確認と、ユーザーが回すもの。
- 次からの開き方。**ワークスペースの直下で開く**（サブフォルダで開くと、プラグインのスキルも hook も読み込まれない）。
  - Claude Code: `cd <ワークスペース> && claude`。スキルは `/desk-tools:slides-build` のように呼ぶ。
  - Codex: `cd <ワークスペース> && codex`。初めてはフォルダを信頼し、`/hooks` で `desk-tools` の hook を信頼する。スキルは `$desk-tools:slides-build` のように呼ぶ。
  - pi: `cd <ワークスペース> && pi`。初めては `/trust` で信頼を保存する（保存しないと、パッケージのスキルが出ない。desk-dreaming の定期の回も読めない）。スキルは `/skill:slides-build` のように呼ぶ。
- 最初の資料は「〇〇向けの提案のスライドを作って」のように頼めばよい（スキル `deck-practices` から始まる）。

## うまくいかないとき

- **同じ名前のスキルがある。** ワークスペースの `.agents/skills/`・`.claude/skills/` に slides-build などがあると、二重に読まれる（pi ではプラグインのものが負ける）。doctor の「スキルの重なり」に出るので、どちらを使うかをユーザーに聞く。
- **入れる範囲、確かめ方、外し方。** Claude Code は `<プラグイン>/docs/claude-code-plugin.md`、Codex は `<プラグイン>/docs/codex-plugin.md`、pi は `<プラグイン>/docs/pi.md`。
