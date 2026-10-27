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

# 会話に読み込まれるスキル: ワークスペースでは desk-tools:* の 16 個、ほかのフォルダでは 0
cd <ワークスペース> && claude -p ok --model haiku --max-turns 1 --output-format stream-json --verbose \
  | python3 -c "import json,sys; e=next(e for e in map(json.loads, sys.stdin) if e.get('subtype')=='init'); print(sorted(s for s in e['skills'] if s.startswith('desk-tools:')))"
```

2026-10-12 に `~/adf-plugin-test` で確かめた結果:

| フォルダ | `plugin list` の enabled | 読み込まれたスキル |
|---|---|---|
| `~/adf-plugin-test`（入れたフォルダ） | true | `desk-tools:` の 16 個（customer-profile、deck-comments、deck-practices、deck-research、deck-review、docs-build、desk-dreaming、desk-doctor、desk-init、desk-kaizen、desk-migrate、slides-build、slides-template、source-scout、vids-build、vids-voice） |
| `~/Documents` | false | `.agents/skills` の 6 つ（`desk-tools:` が付かない。プラグインのものではない） |
| `/tmp` | false | なし |
| `~/adf-plugin-test/Internal`（入れたフォルダのサブフォルダ） | false | なし |

プロジェクトは、Claude Code を開いたフォルダそのもの（git の根元や親のフォルダの `.claude/settings.json` は見ない）。サブフォルダで開くとプラグインは読み込まれず、スキルも hook も効かない。ワークスペースの直下で開き、資料のフォルダへはそこから移る。`.agents/skills`・`.claude/skills` に置いたスキルは親のフォルダからも読まれるので、`~/Documents/Internal/<資料>/build` で開いても使える。ここが前の入れ方との違い。

## ワークスペースを作る

同じフォルダで Claude Code を開き、スキルを呼ぶ。

```
/desk-tools:desk-init
/desk-tools:desk-doctor
```

doctor の要修正が 0 になれば使える。ワークスペースの決まり（`rules/` の下の、frontmatter に `description` のある .md）は、frontmatter の `paths` に当たるプラグインのファイルを Read で開くと hook が続けて出す（2026-10-12 に、そのときの同じパスの `rules/deck-practices/visual.md` で確かめた。サブフォルダで開いた会話では出ない）。`paths` のない決まりは、構成案の頭の「使う決まり」に書いたものを、構成案を開くと出す。`/desk-tools:<スキル>` で呼んだときは、道具を通らずに SKILL.md が入るので、UserPromptSubmit の hook が、その SKILL.md に `paths` が当たる決まりを出す（2026-10-20 に確かめた）。自動のコンパクションのあと、Claude Code は呼んだスキルの SKILL.md を付け直すので、SessionStart（`compact`）の hook がその決まりを出し直す（2026-10-25 に `/compact` で確かめた）。frontmatter の `paths`、`deck-practices/start.md` を開いたときの一覧、構成案の「使う決まり」は、2026-10-27 に sandbox の会話の記録で確かめた（Read と `/desk-tools:deck-review`）。スキルは `desk-tools:` を付けた名前で呼ぶ（`/desk-tools:slides-build` など）。

## 注意

- **同じ名前のスキルを二重に入れない。** ワークスペースの `.agents/skills/` や `.claude/skills/` に slides-build などがあると、プラグインのスキルと両方が読み込まれる（`slides-build` と `desk-tools:slides-build`）。doctor が「スキルの重なり」として要確認に出すので、どちらかを外す。
- **直したプラグインを届ける。** 手元のパスで足したなら、保存して会話を開き直すだけでよい。GitHub から入れたなら、`plugin.json` に版を書いていないので commit の SHA が版になる。push してから `claude plugin update desk-tools@desk-tools --scope project` で届け、会話を開き直す。
- **手元で直しながら試す。** 入れずに `claude --plugin-dir ~/Projects/ai-desktools` で開いてもよい。その会話だけで効き、入れてあるものより優先される。worktree で直して検証用のワークスペースで試す手順は [development.md](development.md)。

## 外す

```sh
cd <ワークスペース>
claude plugin uninstall desk-tools@desk-tools --scope project
claude plugin marketplace remove desk-tools --scope project
```
