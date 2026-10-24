# AI Desk Tools を直すときの決まり

このリポジトリ（GitHub の `mats16/ai-desktools`）は、AI Desk Tools のプラグイン（Claude Code・Codex）とパッケージ（pi）の元。中身・入れ方・ワークスペースの作りは [README.md](README.md)、開発の手順の詳しいことは [docs/development.md](docs/development.md)。

**`sandbox/` の下で開いた会話には、このファイルは効かない。** そこは利用者として動作を見る検証用のワークスペースで、このファイルは親のフォルダから読まれているだけ。`sandbox/` の `AGENTS.md`（factory-init の雛形）に従い、プラグインの利用者として振る舞う。

## 名前

- **リポジトリは `mats16/ai-desktools`、プラグイン・マーケットプレイス・pi のパッケージの名前は `desk-tools`。** スキルは `desk-tools:slides-build` のように呼び、入れるときは `desk-tools@desk-tools`。文の中の製品名は「AI Desk Tools」。前の名前（`ai-deck-factory`・「AI Deck Factory」）は、README の「決めたこと」の過去の記録、前の名前で入れたものを移す話（README の「残っている課題」）、前の版のものを指すところ（元の pptx の丸み〔`slides-visual-018`〕など）に残す。新しい名前に直さない。
- **Google Slides のテンプレートとデッキに書き込む目印（`ai-deck-factory theme=`・`ai-deck-factory layout=`・`ai-deck-factory bar`）は、名前に合わせて替えない。** 作ってあるテンプレートとデッキが、この文字列で読まれるため。

## 中身

| 場所 | 中身 |
| --- | --- |
| `skills/<スキル>/` | 15 個のスキル（`SKILL.md`、場面ごとのファイル、`scripts/`）。3 つのエージェントがどれも読む |
| `hooks/` | `rules_overlay.py`（ワークスペースの `rules/` を続けて出す）と、それを Claude Code・Codex から呼ぶ `hooks.json` |
| `extensions/rules.ts` | pi の拡張。`rules_overlay.py` を呼ぶ |
| `.claude-plugin/` | プラグインとマーケットプレイスの定義。Codex もこれを読む |
| `tests/render/` | 見本を組んで画像で見る（`run.py`、ページごとの見るところ `expect.json`） |
| `docs/` | 入れ方と開発の手順。`docs/fixtures/` は依頼文で試すときの依頼文 |
| README の「決めたこと」「残っている課題」 | ユーザーが決めたことと、後回しにしたこと |

README は 20 万字あり、ほとんどが「決めたこと」。通して読まず、直すスキルの名前や決まりの ID（`deck-review-011` など）で `grep -n` して、関わる項だけ読む。

## 直したら確かめる

どれも `sandbox/` で回す（作り方は下の「sandbox で確かめる」）。結果は PR の「過去資料での検証」にそのまま貼る。

| 直したもの | 確かめ方 |
| --- | --- |
| スクリプト（`hooks/`・`skills/*/scripts/`・`tests/`） | `--selftest` を Python 3.11 で通す（下の 2）。すべて `selftest ok` になる |
| 見た目に効く部品（`slides.py`・`template.py`・`docs.py`） | テンプレートの見本を組み直して画像で見る（`slides-build/themes.md`・`docs-build/templates.md`） |
| JSON のページの形と部品 | `python3 ../tests/render/run.py --judge` で見本を全部組み、全ページの画像を `expect.json` と比べる。形にキーを足したら見本にも、見本のページを足したら `expect.json` にも足す（selftest が見る） |
| 部品や書き方の説明 | `docs/fixtures/` の依頼文を会話を持たない子に渡し、説明だけで正しい部品を選べるかを見る（[docs/development.md](docs/development.md) の「依頼文で試す」） |
| スキル・hook・拡張のふるまい | 会話で開いて、直したスキルを使う場面を通す（[docs/development.md](docs/development.md) の「Claude Code」「Codex」「pi」「`rules/` が続けて出るかを見る」） |

## 直すときの決まり

- **Claude Code・Codex・pi で同じソースを使う。** Codex は Claude Code の形（`.claude-plugin/`・`hooks/hooks.json`）をそのまま読むので、Codex のための別のファイルは置かない。`rules/` を出す仕組みを直すなら、`hooks/hooks.json` と `extensions/rules.ts` の両方を見る。どれか 1 つだけに効く直しにしない。
- **スクリプトは標準ライブラリだけで書く。** Pillow などが要るものだけ、先頭の `# /// script` に依存を書いて `uv run` で回す。Python は 3.11 以上で動かす。
- **`SKILL.md` の本文は 5,000 トークン以内にする。** Claude Code はコンパクションのあと、呼んだスキルの先頭 5,000 トークンだけを付け直すため。場面でしか要らない節（ある場合だけの手順、失敗したとき、別の呼び出しで使う手順）は、`SKILL.md` の表から 1 段で指すファイルに出す。ほかのファイルからしか辿れないファイルは作らない（入れ子の先は一部だけ読まれやすい）。分けたら `factory-migrate/scripts/migrate.py` の `SPLIT` に足す（README の「決めたこと」の 2026-10-24）。
- **ほかのスキルのファイルとスクリプトのメッセージから、`SKILL.md` から分けたファイルを開かせるときは、「`../<スキル>/SKILL.md` を開いてから、その `<ファイル>`」と書く。** hook は開いたパスと同じ `rules/<スキル>/<ファイル>` しか出さないので、分けたファイルを直に開くと、`rules/<スキル>/SKILL.md` に書いてあるワークスペースの上書きが出ない。決まりの出典として番号で指すだけのところ（「`dreaming/run.md` の 5 で見る」）とスクリプトのコメントは、そのままでよい。
- **スキルを足す・外す・名前を変えるときは、数と名前の出てくるところをそろえる。** README の表、`docs/` の「15 個」、`deck-practices` などから指しているパス。
- **ユーザーが決めたことは、README の「決めたこと」に日付とユーザーの発言（原文）で残す。** 後回しにしたものは「残っている課題」に書く。
- **PR の本文は `.github/pull_request_template.md` の節で書く。** 回したコマンドと結果はそのまま貼り、「レビューで見てほしいところ」にファイル:行と確信のない判断を書く。レビューする人も AI も、そこから読む。
- **日本語で書くところは、平易な和文で、言い切りの「〜する」。** 漢語やカタカナ語より、やさしい言い方を選ぶ（「検証」より「確かめる」、「ルール」より「決まり」）。例外: `/deck-review` を回す単位は「ラウンド」（README の「決めたこと」の 2026-10-19）。

## 言葉の使い分け

AI が読む指示は英語、人が読むものと日本語に結びつく決まりは日本語にする（README の「決めたこと」の 2026-10-20）。

- **英語で書く:** `skills/` の md（`SKILL.md` の `description` と見出し、子への依頼文 `prompt_*.md` を含む）のうち、手順、工程の順、子の頼み方、ファイルとフォルダの扱い、コマンドとスクリプトの説明、確かめ方、意味が一意に定まる決まり（位置・大きさ・間・色とコントラスト・部品と JSON のキー・揃え方・矢印・表・画像・API の落とし穴・Drive の置き場所）。`description` は 1000 字以内にする。
- **日本語のまま書く:**
  - 日本語の表記の決まり（文体、表記、用語と訳語、和欧間のスペース、約物、改行と折り返しの位置、全角の字数の目安）。
  - 資料作りのニュアンスが絡む決まり（主張や見出しの言い方、顧客への言葉の調子、聞き手がどう受け取るか、話の運び、何を言う・言わないか）。
  - 例、ユーザーの発言、そのまま書き写す文字列（`構成案.md` などのファイル名、構成案に書く節の名前〔「書き方の決め」など〕、lint の札〔`要修正`・`要確認`〕、台帳の値、スクリプトや人が読む表の列の名前、「要判断」の印）。
  - 利用者や Issue に出す出力の型（dreaming の報告、Issue の本文、profile.md の骨組み、doc.md の例）。
  - 人が読むもの: README.md、`docs/`、このファイル、`docs/fixtures/` の依頼文、`skills/factory-init/templates/`（ワークスペースの人が直す）、PR・Issue・commit の本文。スクリプトのメッセージとコメントも、今は日本語のまま（README の「残っている課題」）。
- **決まり（箇条 1 つ）ごとに、言いたいことの中心で決める。** 迷ったら日本語のままにする。1 つの文の中で混ぜない。英語の文に入れる日本語の例・値・節の名前は、「」か `` ` `` で囲む（「AGENTS.md の「修正の指示」」ではなく「「修正の指示」 in AGENTS.md」）。囲まなくてよいのは、出典の札（（見た目 1-7）など）と固有名詞（人名・書名・社名・書体名）だけ。
- **言葉を替えても、決まりの ID（`[slides-visual-027]` など）と節の番号は変えない。** ほかのファイルの節は英語の見出しで指し（`deck-practices/SKILL.md` の "Working practices"）、番号は `§4` と書く。日本語のまま残るファイル（README・`docs/`・ワークスペースの `AGENTS.md`）の節は、日本語の見出しのまま指す。日本語のファイル（雛形・スクリプトのメッセージ）から英語にしたファイルの節を指すときも、英語の見出しで指す（README の「決めたこと」の過去の記録は直さない）。
- **子への依頼文に、答えの言葉（「日本語で答える」など）を書かない。** なくてもモデルが選ぶ。要るのは、決まりの文・ユーザーの発言・出典を写すときに、元の言葉のまま写す指示のほう。
- **英語は、平易な命令形の短い文にし、理由（because …）を残す。** 用語は今のスキルにそろえる（構成案 → the outline、子 → child agent、指摘 → finding、修正の指示 → correction、扉 → section divider、一覧の画像 → contact sheet、レビューの観点 → aspect など）。

## 公開のリポジトリ

`origin`（GitHub の `mats16/ai-desktools`）は公開している。

- 顧客の名前、資料の名前・URL・本文、社内だけの情報を、commit・PR・Issue に入れない。例には「顧客向けの資料」「（顧客）」「資料 1」を使う。
- 元の checkout（`git worktree list` の 1 行目）は `main` のままにする。ほかのワークスペースに手元のパスで入れたプラグインはそこを読むので、直すのは worktree でする。

## sandbox で確かめる

worktree の直下に検証用のワークスペース `sandbox/` を置き、worktree のプラグインを入れずに渡して確かめる。`sandbox/` は `.gitignore` で無視しているので commit に入らず、worktree を消せば一緒に消える。会話で開いて確かめる手順（Claude Code・Codex・pi、`rules/` が続けて出るか、資料を作って確かめる、消す）は [docs/development.md](docs/development.md)。

1. **作る。** worktree の直下で回す。

   ```sh
   python3 skills/factory-init/scripts/init.py sandbox
   cd sandbox
   python3 ../skills/factory-doctor/scripts/doctor.py --local   # Google の API は見ない
   ```

   雛形の `factory.toml` のままでは、Google に組む作業はできない（doctor の要修正が残る）。組んで確かめるときは、本番のワークスペースの `factory.toml` を写し、`[drive]` を検証用の Drive のフォルダに替える（本番のものを書き換えないため。docs/development.md の「作る」）。`sandbox/` で `git init` はしない。

2. **selftest を回す。** `sandbox/` で回す（`template.py` は `factory.toml` を探す）。Python は最低の版の 3.11 にそろえる。

   ```sh
   for f in ../hooks/*.py ../skills/*/scripts/*.py ../tests/*/*.py; do
     grep -q -e --selftest "$f" && echo "$f: $(uv run -q --python 3.11 "$f" --selftest 2>&1 | tail -1)"
   done
   ```

   すべて `selftest ok` になる。PR と `main` への push では、GitHub Actions（`.github/workflows/selftest.yml`）が Ubuntu で sandbox を作り、2 を回す。

3. **消す。** worktree の直下に戻ってから `rm -rf sandbox`（worktree ごと消すなら要らない）。Google Drive に組んだものと Codex の `CODEX_HOME` は残るので、docs/development.md の「消す」に従って消す。
