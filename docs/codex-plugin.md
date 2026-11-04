# Codex にプラグインとして入れる

AI Desk Tools を Codex（CLI と、ChatGPT のデスクトップアプリの Codex）のプラグインとして、1 つのワークスペースだけで効くように入れる手順。2026-10-20 に Codex CLI 0.162.1 で確かめた。Claude Code で使う手順は [claude-code-plugin.md](claude-code-plugin.md)、pi は [pi.md](pi.md)。

Codex は Claude Code の形をそのまま読む。マーケットプレイスは `.claude-plugin/marketplace.json`、プラグインは `.claude-plugin/plugin.json`。Codex のための別のファイルは置いていない。hook は持たない（2026-11-04 にやめた。ワークスペースのレシピは、スキルの手順の中でエージェントが自分で開く）ので、`/hooks` で信頼するものはない。

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

- ワークスペースの `.codex/config.toml` は、そのフォルダを信頼したときだけ読まれる。初めて Codex を開くと聞かれ、決めたことは `~/.codex/config.toml` の `[projects."<ワークスペース>"] trust_level = "trusted"` に残る。信頼しないと、スキルが出ない。
- 会話が読むのは、入れたときの写し（`~/.codex/plugins/cache/desk-tools/desk-tools/local/`）。手元のパスで足しても写す（Claude Code と違い、checkout をそのまま読まない）。

## そのフォルダだけで効いているかを確かめる

```sh
# 会話に出るスキル（モデルは呼ばない）: ワークスペースでは 12、ほかのフォルダでは 0
for d in <ワークスペース> /tmp; do
  (cd $d && codex debug prompt-input ok 2>/dev/null) | grep -oE 'desk-tools:[a-z-]+: ' | sort -u | wc -l
done

```

2026-10-20 に検証用のワークスペースで確かめた結果（そのときの 19 個とパス。2026-10-31 にスキルを組み直して 17 個になり、`slides-build/visual.md` は `deck-design/slides.md` になった。2026-11-02 に、道具のスキルの名前を `google-*` にし、vids-voice を google-vids に寄せて 16 個になった。2026-11-04 に `build-*` と改め、2026-11-05 に desk-doctor を desk-init に入れて 15 個になった）:

| フォルダ | 出たスキル |
|---|---|
| ワークスペース（信頼した） | `desk-tools:` の 19 個 |
| ワークスペースのサブフォルダ | 19 個（親の `.codex/config.toml` も読まれる） |
| `/tmp` | 0 |

## ワークスペースを作る

同じフォルダで Codex を開き、スキルを呼ぶ（`$` を打つと選べる）。

```
$desk-tools:desk-init
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
