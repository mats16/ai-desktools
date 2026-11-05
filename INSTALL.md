# AI Desk Tools を会話で入れる（エージェントが読む手順）

README の「会話で入れる」のプロンプトを貼られたエージェントが従う手順。プラグインを、ユーザーが選んだ範囲（ワークスペースだけか全体か）に入れ、ワークスペースを作り、desk-init の doctor で確かめるまでを、1 つの会話で進める。手で入れる手順は README の「入れ方」。

このファイルは curl で読む（`curl -fsSL https://raw.githubusercontent.com/mats16/ai-desktools/main/INSTALL.md`）。WebFetch のように要約して返す道具では、コマンドと手順が欠ける。

## 決まり

- **この会話には、まだスキルがない。** 入れたスキルは次の会話から読み込まれる。この会話では `/desk-tools:desk-init`・`$desk-tools:desk-init`・`/skill:desk-init` を呼ばずに、入れた場所の `SKILL.md` を開いて従う（4）。
- **入れる範囲は、ユーザーが選ぶ（1 の 2）。** 「ワークスペースだけ」なら、`~/.claude/settings.json`・`~/.pi/agent/settings.json` は変えない。Codex は入れる範囲がないので、`~/.codex/config.toml` で切ってワークスペースの `.codex/config.toml` で入れる（3）。ほかのフォルダの会話にはスキルが出ない。「全体」なら、ユーザーの設定に入れ、設定を `~/.desk.toml` に置く（4）。どのフォルダで開いた会話にもスキルが出て、資料と記録はワークスペースにたまる。
- **ユーザーが決めることは聞いてから進める。** 場所、ツールを入れるか、`desk.toml` の値。ブラウザが開くログイン（`gcloud auth application-default login`）は、ユーザーに回してもらう。
- **あるファイルは上書きしない。** desk-init の `init.py` も上書きしない。
- 手順の `<ワークスペース>` と `<プラグイン>` は、1 と 3 で決まったパスに置き換える。スクリプトは今いるフォルダから `desk.toml` を探すので、ワークスペースのコマンドは `cd <ワークスペース> &&` を付けて回す。

## 1. 聞く

自分が Claude Code・Codex・pi のどれかは聞かない（自分で分かる）。

**先に、もう入れてあるかを見る。**

- Claude Code: `claude plugin list --json` に `desk-tools@desk-tools` があるか（あればその `scope` と `enabled`）。`claude plugin marketplace list --json` に `desk-tools` があるか（ほかのワークスペースに入れたものも、ここに出る）。
- Codex: `$CODEX_HOME/config.toml`（`CODEX_HOME` がなければ `~/.codex/config.toml`）に `[plugins."desk-tools@desk-tools"]` か `[marketplaces.desk-tools]` があるか（あれば `enabled`）。
- pi: `pi list` の User packages に `ai-desktools` があるか。ほかのフォルダに `pi install -l` で入れたものは `pi list` に出ないので、前にどこかへ入れたかをユーザーにも聞く。
- どれでも: `~/.desk.toml`（`DESK_CONFIG` があればそのパス）があるか（あればその `workspace`）。

見つかったものによって、次のどれかにする（上から順に見て、最初に当たったもの）。

- **もう全体に入っている**（Claude Code の `scope` が `user` で `enabled` が `true`、pi の User packages、Codex は `enabled = true` で `~/.desk.toml` もある）: 3（プラグインを入れる）だけ飛ばし、ほかはこの手順のとおり進める。2 は聞かずに「全体」とし、そのことを伝える。`<プラグイン>` は今入っているもののパス（Claude Code は 3 の最後のコマンドで出るもの、Codex は `codex plugin add desk-tools@desk-tools --json` の `installedPath`〔全体ならユーザーの設定はそのままでよい〕、pi は `${PI_CODING_AGENT_DIR:-~/.pi/agent}/git/github.com/mats16/ai-desktools`（pi の保存先。`PI_CODING_AGENT_DIR` がなければ `~/.pi/agent`））。Claude Code では、入れ元（`claude plugin marketplace list --json` の `desk-tools`）が GitHub でなければ、そのことも伝える。`~/.desk.toml` があれば、1 の 1 の候補の先頭にその `workspace` を出す。ほかのフォルダを選んだら、そこは 2 つめのワークスペースになり、設定はそのフォルダの `desk.toml`（4 の `init.py` を `--user` なしで回す）。ほかのワークスペースにもワークスペースだけで入れてあれば、そこではスキルが二重に読まれることも伝える。
- **ほかに何かある**（ほかのワークスペースに入れたもの、Codex の設定の行、`~/.desk.toml`）: 2 は聞かずに「ワークスペースだけ」で進め、そのことを伝える。ワークスペースだけの入れ方は、ほかのワークスペースに入れてあっても重ねて使える。全体にしたければ、先に今のものを外してから（「うまくいかないとき」の外し方）この手順をやり直す。ワークスペースだけに入れたものが残ったまま全体に入れると、そこでスキルが二重に読まれる。全体に入れたものに、Codex でワークスペースだけを重ねると、ユーザーの設定を切るので全体のものが消える。
- **何もない**: 下の 2 も聞く。

`~/.desk.toml` だけがある（プラグインを外したあとに残った）ときは、「ほかに何かある」と同じにする。全体にしたいと言われたら、1 の 1 を `~/.desk.toml` の `workspace` のフォルダにすれば、全体で進めてよい（設定はそのまま使う）。

「ほかに何かある」ときは、前の入れ方から範囲を読み分けて、替えたり合わせたりはしない（読み分けが外れやすい。Codex の `enabled` は直したものを届けると `true` に戻る）。

次の 6 つ（2 を聞かないときは 5 つ）をまとめて聞く（Claude Code なら AskUserQuestion。1 回に 4 つまでなので、4 つを聞いてから残りを聞く）。

1. **ワークスペースにするフォルダ。** 資料（`Customers/`・`Internal/`・`Research/`）を置く（ワークスペースだけに入れるなら `desk.toml` も）。候補に、今の会話のフォルダと `~/Documents` を出す。なければ作る。すでに `desk.toml` があれば、足りないものだけ置くことを伝える（下の 2 で「全体」を選んだら、その `desk.toml` は手順 4 で `~/.desk.toml` に移す）。
2. **入れる範囲。** 選ぶのは「ワークスペースだけ（既定）」「全体」。違いを添えて聞く。
   - ワークスペースだけ: ワークスペースの直下で開いた会話にだけスキルが出る。ほかのフォルダの会話（開発など）には出ない。設定はワークスペースの `desk.toml`。
   - 全体: どのフォルダで開いた会話にもスキルが出る。設定は `~/.desk.toml` に置き、その `workspace` をワークスペースにするので、どこで頼んでも資料・決まり・記録はワークスペースにたまる。`~/.desk.toml` が指すワークスペースは 1 つだけ。ワークスペースの外で開いた会話は、ワークスペースに書くたびに権限の確認が出ることがある。定期の整理（desk-dreaming）が拾うのは、ワークスペースの中で開いた会話だけ。
3. **全社の共有テーマのフォルダ。** 会社でスライドのテーマ（テンプレート）を配っていれば、その Google Drive のフォルダの URL。なければ「ない」。プロンプトに URL が書いてあれば聞かずに使う。4 で `desk.toml` の `[drive] shared_themes` に書く。
4. **定期の整理（desk-dreaming）を回すか。** 会話の記録から、決まりに戻し忘れた指示を毎日拾うもの。選ぶのは「毎日 5:00 に回す（推奨）」「時刻を変える」「回さない」。どのスケジューラーに登録するかは聞かない（手順 5 で、今の環境から決める）。
5. **資料を返したあと、付いたコメントを見張るか。** 人にコメントを頼んだあと、付いたコメントで直すもの。最後のコメント（なければ見張り始め）から決めた時間、新しいコメントがなければ見張りを終える。見張りは、資料を作った会話が開いているあいだだけ動く。選ぶのは「見張らない（既定）」「24 時間」「72 時間」「時間を決める」。見張らなくても、「コメントを見て直して」「コメントを見張って」と頼めば、そのときに取る。4 で `desk.toml` の `[feedback.google_comments] watch_hours` に書く（見張らないなら 0 のまま）。
6. **資料を作る言語。** 頼むときに言語を言わなかった資料は、この言語で作る（本文、スピーカーノート、納品物の名前まで）。選ぶのは「日本語（既定）」「English」「ほかの言語」。資料ごとに言えば、そのときだけほかの言語にできる。4 で `desk.toml` の `[desk] default_language` に書く（`ja`・`en` など）。

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
claude plugin marketplace add https://github.com/mats16/ai-desktools.git --scope <範囲>
claude plugin install desk-tools@desk-tools --scope <範囲>
claude plugin list --json | python3 -c "import json,sys; [print(p.get('readFromFolder') or p['installPath']) for p in json.load(sys.stdin) if p['id']=='desk-tools@desk-tools' and p['enabled']]"
```

- `<範囲>` は、ワークスペースだけなら `project`、全体なら `user`。
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
- 全体なら、4 つめと 5 つめは回さない（ユーザーの設定の `enabled = true` のままで、どのフォルダの会話にも出る）。
- ワークスペースだけなら、4 つめでユーザーの設定の `enabled` を切り、5 つめでワークスペースだけで入れる。4 つめが止まったら、`~/.codex/config.toml` の `[plugins."desk-tools@desk-tools"]` を見せ、`enabled = false` にしてもらう（切らないと、どのフォルダの会話にもスキルが出る）。5 つめは、ワークスペースの `.codex/config.toml` にもう `desk-tools@desk-tools` があれば足さないので、そのときは中身を見て `enabled = true` かを確かめる。ワークスペースの `.codex/config.toml` は、そのフォルダを信頼したときだけ読まれる。

**pi**

```sh
cd <ワークスペース>
pi install -l git:github.com/mats16/ai-desktools   # ワークスペースだけ
pi install git:github.com/mats16/ai-desktools      # 全体
```

`<プラグイン>` は、ワークスペースだけなら `<ワークスペース>/.pi/git/github.com/mats16/ai-desktools`、全体なら `${PI_CODING_AGENT_DIR:-~/.pi/agent}/git/github.com/mats16/ai-desktools`（pi の保存先。`PI_CODING_AGENT_DIR` がなければ `~/.pi/agent`）。

どれも `<プラグイン>/skills/desk-init/SKILL.md` があることを確かめる。

## 4. ワークスペースを作る

1. `<プラグイン>/skills/desk-init/SKILL.md` を開き、その手順に従う。「このスキルのフォルダ」は `<プラグイン>/skills/desk-init`、ほかのスキルのフォルダは `<プラグイン>/skills/<スキル>`。手順の 1（場所と設定の置き場所）は、ここの 1 で聞いたので飛ばす。
   - **設定の置き場所。** プラグインの範囲（ここの 1 の 2）とは別に、このワークスペースの設定をどこに置くかで決める。ワークスペースだけなら、ワークスペースの直下の `desk.toml`（`init.py <ワークスペース>`）。全体で `~/.desk.toml` がまだないか、その `workspace` がこのフォルダなら、`~/.desk.toml`（`init.py <ワークスペース> --user`）。このときワークスペースにもう `desk.toml` があれば、`<プラグイン>/skills/desk-migrate/SKILL.md` の `to-user` で `~/.desk.toml` に移してから回す。全体でも、`~/.desk.toml` がほかのフォルダを指していれば（2 つめのワークスペース）、このフォルダの `desk.toml`（`init.py <ワークスペース>`。`to-user` は回さず、`~/.desk.toml` は変えない）。このあとの `desk.toml` は、ここで決めた設定のファイルのこと（6 でもそれを返す）。
   - **`init.py` が止まったら**（設定がもうほかの場所にある）、そのメッセージを伝え、ユーザーと決めてから、示された手で直してもう一度回す。ただし `~/.desk.toml` の `workspace` は書き替えない（書き替えると、前のワークスペースがどの会話からも使われなくなる）。メッセージがその手を挙げても、ユーザーには出さない。
   - **書く値。** 3 の `[drive] shared_themes` は、ここの 1 の 3 で聞いた値。`[feedback.google_comments] watch_hours` は、ここの 1 の 5 で選んだ時間（見張らないなら雛形の 0 のまま）。`[desk] default_language` は、ここの 1 の 6 で選んだ言語（日本語なら雛形の `ja` のまま）。設定にもう値があり、ここの 1 の答えと違えば、どちらにするかを聞く（聞かずに上書きしない）。
   - **既定のテーマ。** 3 の `[slides] default_theme`（既定のテンプレート）は、テンプレートを作り、共有のテーマを `slides.py theme <url>` で写したあとで、`<プラグイン>/skills/build-slides/template.md` の「Choosing the default theme」に従って選択式で聞く（1 では聞かない。何を選べるかは、そろってから分かる）。
2. desk-init の最後の手順（6 の「Check」）は、`<プラグイン>/skills/desk-init/doctor.md` を開いて従う。要修正が 0 になるまで直す。Google のログインのように、ユーザーが回すものが残ったら、回してもらってから doctor をもう一度回す。

## 5. 定期の整理を登録する

1 の 4 で「回さない」なら飛ばす。渡すのは `<プラグイン>/skills/desk-dreaming/prompt.txt` の 1 行で、作業フォルダは `<ワークスペース>`、時刻は 1 の 4 で決めたもの。登録のしかたの詳しいことは `<プラグイン>/skills/desk-dreaming/schedule.md`（以下、schedule.md）。ワークスペースだけに入れた pi で回すときは、T3 Code の中でも手で入れるときも、先に対話の pi でワークスペースの trust を `/trust` で保存してもらう（人のいない回は trust を聞けず、保存していないとスキルが読まれない。`<プラグイン>/docs/pi.md`）。

1. **自分の道具にスケジューラーがあれば、それに登録する。** 道具の一覧から、定期の回を作る道具を探す（見えなければ「schedule」「scheduled task」で道具を探す）。使えるのは、次をすべて満たすものだけ。
   - 会話を閉じても、アプリを開き直しても残る。Claude Code の `/loop` のように、会話の中だけで動くものは使わない。
   - この PC で、`<ワークスペース>` を作業フォルダにして回る。クラウドや、回ごとに作るサンドボックス・git の worktree で回るものは使わない（ワークスペースのファイルと会話の記録を読めない）。
   - 人がいなくても、権限の確認で止まらない。

   時刻は手元の時間帯で書く（UTC が既定の道具もある）。2 つ以上あれば、この会話を動かしているアプリのものにする（T3 Code の中なら T3 Code）。よく使うものの値と注意は schedule.md にある（T3 Code の `schedule_task` は 1、Claude Code Desktop は 2、Omnigent の `sys_scheduled_task_create` は 4）。schedule.md にない道具でも、上を満たせば使い、登録した値を 6 で返す。
2. **なければ、手で入れてもらう。** Claude Code・Codex の CLI と pi には、会話を閉じても残るスケジューラーがない。launchd（macOS）か cron で `run.sh` を回す設定（schedule.md の 5）を、`<ワークスペース>`・run.sh のパス・時刻・引数（Claude Code なら `claude`、Codex なら `codex`、pi なら `pi`）を埋めて示し、入れる・すぐ回す・止めるのコマンドを添える。`~/Library/LaunchAgents/` と crontab は、エージェントが書かない（会話の外で毎日動くものを足すので、ユーザーが中身を見て入れる）。Claude Code Desktop を使っているなら、その Routines で作ってもよいことも添える（schedule.md の 2）。

登録したら、すぐ回して確かめる（道具の「すぐ回す」、launchd は `kickstart`）。権限の確認が出たら、ユーザーに許してもらう（次からは聞かれないようにする）。初めての回は 7 日前からの会話を見る。この回から 12 時間以内の次の回は、重ねないために止まる（desk-dreaming の run.md の 0）ので、6 で伝える。

## 6. 終える

次をまとめて返す。

- 入れた範囲（ワークスペースだけか全体か）と設定のファイル（`<ワークスペース>/desk.toml` か `~/.desk.toml`）。
- 置いたもの（init.py の「置いた」「残した」）と、`desk.toml` で埋めた値・空のままの値。既定のテーマ。資料を作る言語。コメントを見張る時間（見張らないなら、そう書く）。
- 定期の整理を登録したスケジューラーと時刻。手で入れてもらうものが残っていれば、その手順。
- doctor の結果。残った要確認と、ユーザーが回すもの。
- 次からの開き方。ワークスペースだけに入れたなら、**ワークスペースの直下で開く**（サブフォルダで開くと、プラグインのスキルが読み込まれない）。全体に入れたなら、どのフォルダで開いてもよい。ただ、1 の 2 の注意（権限の確認、定期の整理が拾う会話）があるので、資料を作るときはワークスペースで開くと迷わない。
  - Claude Code: `cd <ワークスペース> && claude`。スキルは `/desk-tools:build-slides` のように呼ぶ。
  - Codex: `cd <ワークスペース> && codex`。ワークスペースだけに入れたなら、初めてはフォルダを信頼する（ワークスペースの `.codex/config.toml` が読まれる）。スキルは `$desk-tools:build-slides` のように呼ぶ。
  - pi: `cd <ワークスペース> && pi`。ワークスペースだけに入れたなら、初めては `/trust` で信頼を保存する（保存しないと、パッケージのスキルが出ない。desk-dreaming の定期の回も読めない）。スキルは `/skill:build-slides` のように呼ぶ。
- 最初の資料は「〇〇向けの提案のスライドを作って」のように頼めばよい（スキル `deck-workflow` から始まる）。

## うまくいかないとき

- **同じ名前のスキルがある。** ワークスペースの `.agents/skills/`・`.claude/skills/` に build-slides などがあると、二重に読まれる（pi ではプラグインのものが負ける）。doctor の「スキルの重なり」に出るので、どちらを使うかをユーザーに聞く。
- **入れる範囲、確かめ方、外し方。** Claude Code は `<プラグイン>/docs/claude-code-plugin.md`、Codex は `<プラグイン>/docs/codex-plugin.md`、pi は `<プラグイン>/docs/pi.md`。どれもワークスペースだけに入れた形で書いてある。全体に入れたなら、確かめる・直したものを届ける・外すのどれも、次のように読み替える。Claude Code は `--scope project` を `--scope user` に替える。Codex は、ユーザーの設定の `enabled` を切る `python3 -c …` を回さず、ワークスペースの `.codex/config.toml` の行もない。pi は `-l` を付けない。ほかのフォルダでもスキルが出るのが正しい。外しても `~/.desk.toml` は残り、どのフォルダのスクリプトもそのワークスペースを使い続けるので、使わないなら消すかをユーザーに聞く。
