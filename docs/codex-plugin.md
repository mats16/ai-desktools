# Codex にプラグインとして入れる

AI Desk Tools を Codex（CLI と、ChatGPT のデスクトップアプリの Codex）のプラグインとして、1 つのワークスペースだけで効くように入れる手順。2026-10-20 に Codex CLI 0.162.1 で確かめた。Claude Code で使う手順は [claude-code-plugin.md](claude-code-plugin.md)、pi は [pi.md](pi.md)。

Codex は Claude Code の形をそのまま読む。マーケットプレイスは `.claude-plugin/marketplace.json`、プラグインは `.claude-plugin/plugin.json`、hook は `hooks/hooks.json`（`${CLAUDE_PLUGIN_ROOT}` も Codex が埋める）。Codex のための別のファイルは置いていない。

## 入れる

ワークスペースにするフォルダで回す。

```sh
cd <ワークスペース>
codex plugin marketplace add mats16/ai-desktools   # 手元の checkout なら ~/Projects/ai-desktools
codex plugin add desk-tools@desk-tools
```

`~/.codex/config.toml` に次が書き込まれる。Codex には入れる範囲（scope）がなく、このままでは、どのフォルダの会話にもスキルが出る。

```toml
[marketplaces.desk-tools]
source_type = "git"
source = "https://github.com/mats16/ai-desktools.git"

[plugins."desk-tools@desk-tools"]
enabled = true
```

ワークスペースだけで効かせるには、ユーザーの設定で切り、ワークスペースの `.codex/config.toml` で入れる。

```sh
python3 -c 'import os,pathlib; p=pathlib.Path(os.environ.get("CODEX_HOME","~/.codex")).expanduser()/"config.toml"; k="[plugins.\"desk-tools@desk-tools\"]\nenabled = true"; s=p.read_text(); assert k in s, "見つからない"; p.write_text(s.replace(k, k[:-4]+"false"))'
mkdir -p .codex && { grep -qs 'desk-tools@desk-tools' .codex/config.toml || printf '\n[plugins."desk-tools@desk-tools"]\nenabled = true\n' >> .codex/config.toml; }
```

- ワークスペースの `.codex/config.toml` は、そのフォルダを信頼したときだけ読まれる。初めて Codex を開くと聞かれ、決めたことは `~/.codex/config.toml` の `[projects."<ワークスペース>"] trust_level = "trusted"` に残る。信頼しないと、スキルも hook も出ない。
- 会話が読むのは、入れたときの写し（`~/.codex/plugins/cache/desk-tools/desk-tools/local/`）。手元のパスで足しても写す（Claude Code と違い、checkout をそのまま読まない）。

## hook を信頼する

プラグインの hook（`recipes/` のレシピと顧客の `memory.md` を続けて出すもの）は、信頼するまで動かない。対話の Codex で `/hooks` を開き、`desk-tools` の 5 つ（PostToolUse の Read・Bash・Skill、UserPromptSubmit、SessionStart）を信頼する。Read と Skill は Claude Code のためのもので、Codex では起きない。SessionStart（`compact`）は、Claude Code でコンパクションのあとに付け直されるスキルの上書きを出し直すためのもので、Codex では何も出さない（Codex はコンパクションで、呼んだスキルの中身も hook の差し込みも消す）。

- 信頼は hook の中身のハッシュに付く。`hooks/hooks.json` が変わった版を取ると、信頼し直すまで止まる（起動のときに `/hooks` を開くよう知らせが出る）。
- `codex exec`（desk-dreaming の `run.sh codex`、レビューの子）は聞けない。先に対話の Codex で信頼しておく。
- Codex はファイルをシェル（`cat`・`sed` など）で読むので、PostToolUse は `Bash` で効く。`$desk-tools:slides-build` のように呼んだスキルは、道具を使わずに SKILL.md が入るので、UserPromptSubmit がプロンプトから拾って、その SKILL.md を開いたときと同じレシピを出す（2026-10-27 に、そのときの形〔frontmatter の `paths`〕で、`sed` で開いたもの・一覧・構成案の「使う決まり」と、`$desk-tools:deck-review` を、会話の記録の developer のメッセージで確かめた）。
- Codex は `hooks.json` の `if`（Claude Code が `.md` に触れない Read・Bash で hook を起こさないための条件）を読まないので、Bash のたびに hook が起き、出すものがなければすぐ終わる。Codex は hook の差し込みが約 2,500 トークン（和文で約 3,300 字）を超えるとファイルに逃がして頭と末尾だけを見せるので、`additionalContextLimit` を 0 にして逃がさない。量は hook が 9,000 字までに抑える（README の「決めたこと」の 2026-10-25）。

## そのフォルダだけで効いているかを確かめる

```sh
# 会話に出るスキル（モデルは呼ばない）: ワークスペースでは 12、ほかのフォルダでは 0
for d in <ワークスペース> /tmp; do
  (cd $d && codex debug prompt-input ok 2>/dev/null) | grep -oE 'desk-tools:[a-z-]+: ' | sort -u | wc -l
done

# hook と信頼: PostToolUse の Read・Bash・Skill、UserPromptSubmit、SessionStart が trusted で出る
cd <ワークスペース> && (printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"t","version":"0"}}}' '{"jsonrpc":"2.0","method":"initialized"}' '{"jsonrpc":"2.0","id":2,"method":"hooks/list","params":{}}'; sleep 5) \
  | codex app-server 2>/dev/null \
  | python3 -c "import json,sys; r=next(e for e in map(json.loads, sys.stdin) if e.get('id')==2); [print(h['eventName'], h.get('matcher'), h['trustStatus']) for d in r['result']['data'] for h in d['hooks'] if h.get('pluginId')=='desk-tools@desk-tools']"
```

2026-10-20 に検証用のワークスペースで確かめた結果（そのときの 19 個とパス。2026-10-31 にスキルを組み直して 17 個になり、`slides-build/visual.md` は `deck-design/slides.md` になった）:

| フォルダ | 出たスキル | hook |
|---|---|---|
| ワークスペース（信頼した） | `desk-tools:` の 19 個 | `sed -n 1,3p ../skills/slides-build/visual.md` のあとと、`$desk-tools:desk-doctor` で呼んだときに、ワークスペースの決まりの目印が差し込まれた（2026-10-27 の `rules/` の形で） |
| ワークスペースのサブフォルダ | 19 個（親の `.codex/config.toml` も読まれる） | |
| `/tmp` | 0 | |

## ワークスペースを作る

同じフォルダで Codex を開き、スキルを呼ぶ（`$` を打つと選べる）。

```
$desk-tools:desk-init
$desk-tools:desk-doctor
```

doctor の要修正が 0 になれば使える。

## 直したプラグインを届ける

写しを読むので、取り直すまで変わらない。

```sh
codex plugin marketplace upgrade desk-tools   # GitHub から入れたとき。手元のパスなら要らない
codex plugin add desk-tools@desk-tools   # 写し直す
```

`codex plugin add` は、ユーザーの設定の `enabled` を `true` に戻す。上の「入れる」の `python3 -c …` をもう一度回して切る。

## 外す

```sh
codex plugin remove desk-tools@desk-tools
codex plugin marketplace remove desk-tools
```

ワークスペースの `.codex/config.toml` の `[plugins."desk-tools@desk-tools"]` も消す。ワークスペースのファイル（`desk.toml`・`recipes/`・`.desk/`）と、個人の設定の `~/.desk.toml` は残る。
