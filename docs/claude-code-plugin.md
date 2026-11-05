# Claude Code にプラグインとして入れる

AI Desk Tools を Claude Code のプラグインとして入れ、ワークスペースを作るまでの手順。pi で使う手順は [pi.md](pi.md)。

## 入れる範囲（scope）を決める

| scope | 書き込まれる場所 | 効く範囲 |
|---|---|---|
| `user`（既定） | `~/.claude/settings.json` | どのフォルダの会話でも |
| `project` | `<フォルダ>/.claude/settings.json` | そのフォルダ（プロジェクト）の会話だけ。git に入れれば、同じリポジトリを使う人にも効く |
| `local` | `<フォルダ>/.claude/settings.local.json` | そのフォルダで、自分だけ |

資料のフォルダだけで使うなら `project` にする。ほかのフォルダの会話にスキルが出てこない。

## 入れる（project）

ワークスペースにするフォルダで回す。

```sh
cd <ワークスペース>
claude plugin marketplace add https://github.com/mats16/ai-desktools.git --scope project   # 手元の checkout なら ~/Projects/ai-desktools
claude plugin install desk-tools@desk-tools --scope project
```

`<ワークスペース>/.claude/settings.json` に次が書き込まれる。

```json
{
  "extraKnownMarketplaces": {
    "desk-tools": { "source": { "source": "directory", "path": "/Users/<you>/Projects/ai-desktools" } }
  },
  "enabledPlugins": { "desk-tools@desk-tools": true }
}
```

- `~/.claude/settings.json` は変わらない。
- `~/.claude/plugins/` の `known_marketplaces.json`（マーケットプレイスの一覧）と `installed_plugins.json`（`scope: project` と `projectPath` が付く）には行が足される。どちらも記録だけで、ほかのフォルダでプラグインが有効になるわけではない。
- マーケットプレイスを手元のパスで足すと、会話はその checkout からプラグインを読む（起動したときの `plugins` の `path` が checkout を指す）。`install`・`update` は `~/.claude/plugins/cache/` に commit ごとの写しを作り、`installed_plugins.json` の `installPath` もそこを指すが、会話は読まない。commit していない変更も次の会話から効き、checkout を動かすとプラグインは読まれなくなる（写しには戻らない）。GitHub を指していれば、会話は写しを読む（2026-10-12 に Claude Code 2.1.295 で確かめた）。

## そのフォルダだけで効いているかを確かめる

```sh
# 一覧: ワークスペースでは enabled が true、ほかのフォルダでは false
for d in <ワークスペース> /tmp; do
  (cd $d && claude plugin list --json) | python3 -c "import json,sys; [print(p['id'], p['scope'], p['enabled']) for p in json.load(sys.stdin) if p['id']=='desk-tools@desk-tools']"
done

# 会話に読み込まれるスキル: ワークスペースでは desk-tools:* がプラグインの `skills/` と同じ数、ほかのフォルダでは 0
cd <ワークスペース> && claude -p ok --model haiku --max-turns 1 --output-format stream-json --verbose \
  | python3 -c "import json,sys; e=next(e for e in map(json.loads, sys.stdin) if e.get('subtype')=='init'); print(sorted(s for s in e['skills'] if s.startswith('desk-tools:')))"
```

2026-10-12 に `~/adf-plugin-test` で確かめた結果（そのときの 19 個。2026-10-31 にスキルを組み直して 17 個に、2026-11-02 に vids-voice を google-vids に寄せて 16 個になった。2026-11-04 に道具のスキルを build-* と改め、2026-11-05 に desk-doctor を desk-init に入れて 15 個になった）:

| フォルダ | `plugin list` の enabled | 読み込まれたスキル |
|---|---|---|
| `~/adf-plugin-test`（入れたフォルダ） | true | `desk-tools:` の 19 個（customer-profile、deck-comments、deck-design、deck-practices、deck-research、deck-review、deck-writing、docs-build、desk-crawl、desk-dreaming、desk-doctor、desk-init、desk-kaizen、desk-migrate、desk-recipes、slides-build、slides-template、vids-build、vids-voice） |
| `~/Documents` | false | `.agents/skills` の 6 つ（`desk-tools:` が付かない。プラグインのものではない） |
| `/tmp` | false | なし |
| `~/adf-plugin-test/Internal`（入れたフォルダのサブフォルダ） | false | なし |

プロジェクトは、Claude Code を開いたフォルダそのもの（git の根元や親のフォルダの `.claude/settings.json` は見ない）。サブフォルダで開くとプラグインは読み込まれず、スキルが効かない。ワークスペースの直下で開き、資料のフォルダへはそこから移る。`.agents/skills`・`.claude/skills` に置いたスキルは親のフォルダからも読まれるので、`~/Documents/Internal/<資料>/build` で開いても使える。ここが前の入れ方との違い。

## 一覧に説明が載っているかを確かめる

Claude Code は、会話の先頭に出すスキルの一覧をコンテキストの 1%（既定）までに収める。入れてあるスキルが多いと、呼び出した回数が少ないスキルから説明が落ち、名前だけになる（[公式ドキュメント](https://code.claude.com/docs/en/skills) の "Skill descriptions are cut short"）。名前だけのスキルは、モデルが場面から選びにくい。2026-11-05 にこの端末（スキル 111 個）で確かめたところ、desk-tools の 15 個のうち build-docs・build-vids・customer-profile・desk-crawl・desk-init・desk-kaizen・desk-migrate の 7 個が名前だけだった（Codex と pi は 15 個とも説明が載る）。

```sh
# 名前だけになっている desk-tools のスキルを聞く（none なら全部載っている）
cd <ワークスペース> && claude -p 'In your system prompt there is a list "The following skills are available for use with the Skill tool". Answer with one line only: "without: " then the desk-tools: skill names that appear with no description (or "none").' --model haiku --max-turns 1
```

名前だけのものがあれば、設定で予算を広げるか、使わないスキルを一覧から外す。`/context` の Skills の行と `/doctor` でも、一覧の大きさと内訳が見られる。

- 予算を広げる: `.claude/settings.json`（または `~/.claude/settings.json`）に `"skillListingBudgetFraction": 0.05` を足す（5%。既定は 0.01）。確かめるだけなら `claude --settings '{"skillListingBudgetFraction":0.05}'`、または環境変数 `SLASH_COMMAND_TOOL_CHAR_BUDGET=100000`（文字数の固定値）でもよい。2026-11-05 にどちらでも 15 個とも説明が載った。
- 使わないスキルを外す: 同じ設定の `skillOverrides` で、ほかのプラグインのスキルを `"name-only"` や `"off"` にする。

## ワークスペースを作る

同じフォルダで Claude Code を開き、スキルを呼ぶ。

```
/desk-tools:desk-init
```

doctor の要修正が 0 になれば使える。ワークスペースの決まり（レシピ。`recipes/<名前>/RECIPE.md` で、frontmatter に `description` のあるもの）は、hook では出さない（2026-11-04 にやめた）。資料を作るスキルの手順の中で、エージェントが `desk.py recipes` で一覧を見て、その作業に当たるものを自分で開く（`desk-feedback` の `routing.md` の「Workspace rules」）。スキルは `desk-tools:` を付けた名前で呼ぶ（`/desk-tools:build-slides` など）。

## 注意

- **同じ名前のスキルを二重に入れない。** ワークスペースの `.agents/skills/` や `.claude/skills/` に build-slides などがあると、プラグインのスキルと両方が読み込まれる（`build-slides` と `desk-tools:build-slides`）。doctor が「スキルの重なり」として要確認に出すので、どちらかを外す。
- **直したプラグインを届ける。** 手元のパスで足したなら、保存して会話を開き直すだけでよい。GitHub から入れたなら、`plugin.json` に版を書いていないので commit の SHA が版になる。push してから `claude plugin update desk-tools@desk-tools --scope project` で届け、会話を開き直す。
- **手元で直しながら試す。** 入れずに `claude --plugin-dir ~/Projects/ai-desktools` で開いてもよい。その会話だけで効き、入れてあるものより優先される。worktree で直して検証用のワークスペースで試す手順は [development.md](development.md)。

## 外す

```sh
cd <ワークスペース>
claude plugin uninstall desk-tools@desk-tools --scope project
claude plugin marketplace remove desk-tools --scope project
```
