# AI Desk Tools

日本語のスライド（Google Slides）とドキュメント（Google Docs）を Slides API・Docs API で直接組み、lint・Google が描いたページの画像・別の目のレビューで確かめて渡す仕組み。会話の記録から、決まりに戻し忘れた指示を拾って決まりを育てていく（desk-dreaming）。

同じソースを、Claude Code と Codex のプラグイン、pi のパッケージから入れられる。

## 中身

スキルは、中身の種類で 6 つの組に分ける。ほかのスキルはスキルの名前で呼び、その中のファイルは指さない（[決めたこと](docs/decisions.md) の 2026-10-31）。スキルで共有するコードは `lib/` に置く。

| 組 | スキル | すること |
|---|---|---|
| 進め方 | `deck-workflow` | 資料を作る・直すときに最初に読む（スライドとドキュメントで共通）。1〜11 の流れと、どの工程でも効くやり方。工程ごとのファイル（`start.md`: 1〜5 の準備と構成、`slides_steps.md`: デッキの 6〜8〔代表の 3 枚、残りのページ、全体を組む〕と、ページを書く子への依頼文 `prompt_pages.md`、`agents.md`: 子の起こし方と待ち方、`materials.md`: 材料集めと出典の台帳、`reuse.md`: 社内のデッキの流用、`drive.md`: Drive への置き方、`deliver.md`: 返す・片付ける、`revise.md`: 返したあとの頼み、`comments.md`: 組んだ資料のコメントから直す・見張る〔`comments.py`、見張りの子への依頼文 `prompt_watch.md`〕） |
| 進め方 | `deck-review` | 返す前の全体のレビュー。会話を渡さない新しいサブエージェント（メインと同じモデルと effort）に頼む。`SKILL.md` はラウンドの流れと手順ごとに開くファイルの表だけで、頼み方は `ask.md`、指摘の確かめと直し方は `fix.md`、直しを子に分けるときは `prompt_fix.md`。子への依頼文は形式ごと（`prompt_slides.md`・`prompt_doc.md`）と出典の照合（`prompt_sources.md`） |
| 知見 | `deck-writing` | どの資料にも効く、中身と言葉の判断の軸と、良い資料とは何をするものかの企画書（鉄則と 6 つに聞き手の立場に合わせることを足したもの、初見の読み手が少ない手間で分かる、言い切る範囲は根拠まで、口に出して通じる言葉、聞き手に要るものだけ）。決まりが決めていないこと（何をつかませるか、どの関係を図で見せるか）を決める。資料の種類ごとの中身・見出し・1 ページの中身・言葉と「文体」・出典の書き方（`content.md`、種類ごとの `content_customer.md`・`content_internal.md`・`content_explain.md`）も持つ |
| 知見 | `deck-design` | どの資料にも効く、見た目（意匠）の知見。デザインの専門家の考え方から出した原則（そのページで最も伝えたいことに最も合うデザインを探る、強調は相対的、同じか、はっきり違うか、効く範囲でいちばん小さい差、空きでまとめる、ひと目で要点）と、そこから出るベストプラクティス（強調の 1 点、分類と強調の色、形はページごとで枠はそろえる〔slides-visual-048・049〕、強調の手段、階層、配色、地、矢印）。指示として残すのは、測れるものは部品と lint に任せることと、何から順に従うかだけ。形式ごとの値と、和文の組み方・AI が作ったように見えるくせは `slides.md`（スライド）・`docs.md`（ドキュメント） |
| 道具 | `slides-build` | Google Slides を、宣言的に書くページの JSON から組む（`slides.py`）・確かめる（`gslides.py check`・`lint.py`）。ページの JSON は `pages.md`、図・矢印・ガント・棒グラフの書き方は `diagrams.md`、コマンドは `commands.md`、テーマは `themes.md`、画像は `images.md`、lint の読み方は `lint.md`、Slides API の落とし穴は `api.md`、pages.py と pptx の古いデッキは `legacy.md`。会社のテンプレートから AI Desk Tools のテンプレート（テーマ）を作る・既定のテーマを替える（`template.md`、3 つの場合は `template_create.md`、暗い本文は `template_dark.md`、書体は `template_fonts.md`。`template.py audit`）。使い回す画像は `assets/`、一通りの書き方を入れた JSON のページの見本は `samples/json/` |
| 道具 | `docs-build` | Google Docs を `build/doc.md` から組む・確かめる（`docs.py`・`doc_lint.py`・`doc_layout.py`）。lint の読み方は `lint.md`、Docs API の落とし穴は `api.md`、テーマのファイルは `themes.md`、テンプレートから書く・作るは `templates.md`。テンプレートはワークスペースのレシピのフォルダ（`recipes/<レシピ>/templates/`） |
| 道具 | `vids-voice` | Google Vids の AI の読み上げ（voiceover）の台本を書く。台本の置き場所は、元の Google Slides の各ページのスピーカーノート。声の長さと間も、Vids の画面でなく台本（字数・audio tags）で直す。資料はノートなしで組み、ノートは頼まれたときだけ、組んだあとに資料全体の台本としてまとめて書く。ノートのある資料も、この手順で書き直す。スライドを読み上げず動画全体の筋を通し、Vids が読む audio tags を入れる。言語によらない決まりは `SKILL.md`、言語に結びつく決まり（文体、字数、読み、記号、ほかのシーンの指し方、タグの置き場所）は `ja.md`・`en.md`（lint は `--lang`）。スライドは組み直さず、ノートだけを書き換える（`speaker_notes.py pull`・`lint`・`push`。前のノートは `build/notes_before_<日付>.json` に控える） |
| 道具 | `vids-build` | ベータ版（Vids の編集の公開の API がまだないので、Vids の画面と同じ内部の呼び出しを使う。呼び出しは 1 つのファイルにまとめてあり、公開の API が出たら、そのファイルだけを差し替える）。動画は、作るとはっきり頼まれたときだけ、組んだ Google Slides から Google Vids で作る。スピーカーノートが変わったら、頼まれなくても、その資料から作った動画の変わったシーンだけを差し替える。ページを足した・消した・直したときは動画を追わせず、頼まれたら作り直す（新しい Vids に作るか、`--vids` で同じ Vids の中身を消して組み直す）（`vids.py create`・`update`・`check`・`voices`・`download`）。動画は資料そのものから作り、動画のための Slides の写しを作らない。全ページをシーンにし、各ページのスピーカーノートを Conversational voice（既定は Elio。audio tags が効く）で読ませる。指定したページだけ AI avatar（Conversational voices で話す 30 体）に読ませることもでき、ページの空いた隅に丸く置く（`vids.py layout` で置き方を決め、円を描いた一覧の画像で確かめる）。動画は Slides と同じフォルダに作る。Vids の編集には公開の API がないので、対象の Google アカウントにログイン済みの Chrome のタブの中から、Vids の画面と同じ内部の呼び出しを使う（`internal_api.md`） |
| 材料 | `customer-profile` | 顧客の profile（`Customers/<顧客>/profile.md`。事業、組織、技術の構成、エンジニアの好みと文化、いまの取り組み）を `[sources]` と公開の情報から作る・取り直す・書き足す。ユーザーが言った行は残す |
| 材料 | `desk-crawl` | 定期に回す集めの作業で、どの先をいつ読むかを決め、回ごとに学ぶ（`crawl.py`）。読む先は Slack のチャンネルと検索、メールの検索、RSS・Atom、web のページと検索、wiki のページ。値打ちの低い先は間を空けて読み（前に読んだ所から取り戻すので落とさない）、取りこぼしの元と新しい先を先に試し、子に浅く読ませて（題・リンク・要約・見えた先）候補を 1 つにまとめる。使う側が返す、使ったものと取りこぼしから学ぶ。何を選ぶか・何を書くか（関心）と、調べて出典を残すことは持たない。記録は `.desk/crawl/<話題>/` |
| 指摘から育てる | `desk-feedback` | ユーザーの修正の指示から学ぶ。その指示が誰にとって正しいか（この資料だけ・この顧客・この人や組織の環境・誰にでも効く知見）を見立て、台帳に見立てごと残し（`ledger.py add --scope`）、それぞれの置き場所（構成案、顧客の memory、レシピ、プラグインへの提案）に、合う形（知見なら原則と理由、個別の事情なら「〜のときは〜する（理由）」、数えられるものは点検）で書く（`SKILL.md`）。記録と戻し先・決まりの ID・hook のレシピの出し方・顧客の memory・決まりの確かめ方は `routing.md`、レシピの分け方と書き方・組み直しは `recipes.md` |
| 指摘から育てる | `desk-dreaming` | 会話の記録と台帳から、決まりを定期的に整理する（戻し忘れた指示を提案にし、重なり・古い記述を片付け、プラグインに上げる案を出す） |
| 指摘から育てる | `desk-kaizen` | プラグインの改善を、過去の資料で前後を比べてから Issue にする（理由・背景・検証の結果・見た目なら画像・変更案の差分）。PR は持ち主が作る |
| 指摘から育てる | `desk-research` | 資料づくりのベストプラクティスの調べ直し。調べた記録（`state.md`・`log/`）はワークスペースの `Research/deck_research/` |
| 環境 | `desk-init` | ワークスペースを作る（desk.toml・references_index.md・drive_folders.md・recipes/ の雛形と資料のフォルダ。AGENTS.md・CLAUDE.md は置かない。どのフォルダに何を置くかも持つ。設定の desk.toml は、ワークスペースか `~/.desk.toml` に置く。あるファイルは上書きしない） |
| 環境 | `desk-doctor` | 前提を確かめる（Python・uv、使っている設定とワークスペース、スキルの重なり、Google の認証、テンプレートと Drive のフォルダ、gh） |
| 環境 | `desk-migrate` | 前の版で作ったワークスペースを今の版へ移す（`rules/` の移動、決まりの ID とパスの書き換え、`rules/` から `recipes/<名前>/RECIPE.md` への移し。先に `.desk/migrate/` に控えを取る）。全体に入れるときは、ワークスペースの `desk.toml` を `~/.desk.toml` に移す（`to-user`）。2026-10-31 のスキルの組み直しで変わった名前とパスも、ワークスペースの文と台帳で書き換える |

```
INSTALL.md                        会話で入れるときに、エージェントが読む手順（README の「会話で入れる」）
.claude-plugin/plugin.json        Claude Code のプラグイン（Codex もこれを読む）
.claude-plugin/marketplace.json   このリポジトリをそのままマーケットプレイスにする
package.json                      pi のパッケージ（pi.skills: ./skills）
skills/                           上の 17 個（Claude Code・Codex・pi で共通）
lib/                              スキルと hook で共有するコード（desk.py・gapi.py・brand.py・textlint.py・sheet.py・ledger.py・refs.py、subtree で取り込んだ yomiyasu/）。スキルではない
hooks/hooks.json                  Claude Code と Codex の hook（プラグインのファイルを読むかスキルを呼んだら、その作業のレシピ〔recipes/〕を、顧客の資料を読んだら memory.md を続けて出す）
hooks/rules_overlay.py            その中身（Claude Code・Codex・pi で共有）
extensions/rules.ts               pi の拡張（同じことを pi の read・bash で）
docs/                             設定のガイド（decisions.md: 決めたこと。todo.md: 残っている課題。claude-code-plugin.md: Claude Code に入れる範囲と確かめ方。codex-plugin.md: Codex に入れる範囲と hook の信頼。pi.md: pi に入れる範囲と確かめ方。development.md: 開発しながら動作を見る）
```

## 会話で入れる

Claude Code・Codex・pi のどれかを開き、次を貼る（どのフォルダで開いた会話でもよい）。

```text
AI Desk Tools を入れて、ワークスペースを作ってください。
手順は https://raw.githubusercontent.com/mats16/ai-desktools/main/INSTALL.md にあります。WebFetch ではなく curl で読み、そのとおりに進めてください。
```

エージェントが [INSTALL.md](INSTALL.md) に従い、ワークスペースにするフォルダと全社の共有テーマのフォルダ、定期の整理を回すか、資料を作る言語を聞き、Python・uv を見て、そのフォルダだけにプラグインを入れる。続けて、入れた `desk-init` と `desk-doctor` の手順で `desk.toml`（Google の認証、テーマ、Drive の置き場所、材料を集める道具）を一緒に埋め、要修正が 0 になるまで進める。最後に、定期の整理（desk-dreaming）を回すなら、エージェントが自分の道具にあるスケジューラー（T3 Code・Claude Code Desktop・Omnigent など）に登録する（なければ、launchd か cron の入れ方を示す）。自分で回すのは、ブラウザが開く Google のログインだけ。終わったら、ワークスペースの直下で会話を開き直す。

## 前の名前から移る

前の名前（`ai-deck-factory`）で入れたものは、新しい名前（`desk-tools`）では引けない。入れていた Claude Code・Codex・pi のどれかを開き、次を貼る（どのフォルダで開いた会話でもよい）。資料・`desk.toml`・`rules/`・`.desk/` は残る。

```text
前の名前（ai-deck-factory）で入れた AI Deck Factory を、新しい名前の AI Desk Tools（desk-tools）に移してください。資料・desk.toml・rules/・.desk/ は消さずに残します。ファイルは WebFetch ではなく curl で読んでください。
1. 前の名前で登録したものを拾う。<ワークスペース> は資料のフォルダ（desk.toml か factory.toml のあるところ）で、分からなければ聞く。次の grep で出たファイル（プラグインの写しのフォルダは除いてある）、crontab -l、自分の道具のスケジューラー（T3 Code・Claude Code Desktop・Omnigent など）の定期の作業のうち ai-deck-factory を含むものを、まとめて見せてから進める。自分の道具で見られないスケジューラー（ほかのアプリのもの）に desk-dreaming を登録したかも、ユーザーに聞く。
   grep -rln --exclude-dir=cache --exclude-dir=marketplaces --exclude-dir=git ai-deck-factory ~/.claude/plugins ~/.claude/settings.json ~/.codex/config.toml ~/.codex/automations ~/.claude/scheduled-tasks ~/Library/LaunchAgents ~/.pi/agent/settings.json <ワークスペース>/.claude <ワークスペース>/.codex <ワークスペース>/.pi <ワークスペース>/AGENTS.md <ワークスペース>/rules 2>/dev/null
2. 前の入れ元が手元の checkout なら、外す前に、その .claude-plugin/marketplace.json の name を見る。desk-tools でなければ（前の版のまま）、何も外さずに見せ、その checkout を mats16/ai-desktools に合わせるか、ほかの入れ元にするかをユーザーに聞く。決まったら、前の名前のプラグインとマーケットプレイスを、入れたときと同じ範囲で外す。https://raw.githubusercontent.com/mats16/ai-desktools/main/docs/ の claude-code-plugin.md・codex-plugin.md・pi.md の「外す」を、desk-tools を ai-deck-factory に替えて使う。pi は settings.json に書かれた入れ元を、そのまま pi remove に渡す（-l の有無も同じにする）。
3. https://raw.githubusercontent.com/mats16/ai-desktools/main/INSTALL.md の 3（プラグインを入れる）と 4 の 2（desk-doctor）を、今のワークスペースで進める。入れる範囲（ユーザー全体かワークスペースだけか）と入れ元（GitHub か手元の checkout）は前と同じにし、INSTALL.md の 3 のコマンドをそれに合わせて替える（手元のパスから入れる書き方は README の「入れ方」）。desk-doctor が「前のバージョンのワークスペース」を出したら、<プラグイン>/skills/desk-migrate/SKILL.md を開いて移す。
4. AGENTS.md・rules/ に残る ai-deck-factory:（コロン付き。/ai-deck-factory:<スキル> や $ai-deck-factory:<スキル>）を desk-tools: に替える（hook は新しい名前でしか拾わない）。コロンのない ai-deck-factory（テンプレートとデッキの目印 ai-deck-factory theme= など）は替えない。
5. 定期の整理（desk-dreaming）を登録していたら、登録した先を <プラグイン>/skills/desk-dreaming/schedule.md の見出しの順にすべて見て、前の登録を消し、INSTALL.md の 5 のとおりに、新しい prompt.txt と run.sh のパスで登録し直す。launchd と cron は自分で書き換えず、消すコマンドと入れるコマンドを示して、ユーザーに回してもらう。自分の道具で見られない登録先は、そのアプリで消して登録し直すよう、渡す 1 行と作業フォルダを添えてユーザーに返す。
6. 1 の grep と crontab -l をもう一度回し、残ったものと、次からの開き方（INSTALL.md の 6）を返す。コロンのない目印と、name が desk-tools の checkout のパスに残る ai-deck-factory は、残ったものに数えない。
```

Drive のフォルダ「AI Deck Factory」は `desk.toml` の URL で引くので、名前は替えなくてよい。

## 入れ方

手で入れるときの手順。Python 3.11 以上と `uv` が要る。Google の認証は下の「Google の認証」。

**Claude Code**

```sh
claude plugin marketplace add https://github.com/mats16/ai-desktools.git   # 手元の checkout なら ~/Projects/ai-desktools
claude plugin install desk-tools@desk-tools
claude plugin update desk-tools@desk-tools               # GitHub から入れたとき、直して commit・push したあと
```

マーケットプレイスが GitHub を指していれば、会話は `~/.claude/plugins/cache/` に写した版を読む。`plugin.json` に版を書いていないので commit の SHA が版になり、push してから `update` で届く。手元のパスで足したなら、会話は checkout をそのまま読むので、保存すれば次の会話から効く（commit も `update` も要らない）。手元で直しながら試すときは `claude --plugin-dir ~/Projects/ai-desktools`（worktree と検証用のワークスペースで試す手順は [docs/development.md](docs/development.md)）。スキルは `/desk-tools:desk-init` のように呼ぶ。資料のフォルダだけで効かせる（`--scope project`）入れ方と、効いている範囲の確かめ方は [docs/claude-code-plugin.md](docs/claude-code-plugin.md)。

**Codex**

```sh
codex plugin marketplace add mats16/ai-desktools   # 手元の checkout なら ~/Projects/ai-desktools
codex plugin add desk-tools@desk-tools     # 直したものを取るときも回し直す（GitHub なら先に codex plugin marketplace upgrade desk-tools）
```

Codex は Claude Code の形（`.claude-plugin/`・`hooks/hooks.json`）をそのまま読む。会話が読むのは `~/.codex/plugins/cache/` の写しで、手元のパスで足しても写すので、直したら `add` を回し直す。hook は、対話の Codex の `/hooks` で信頼するまで動かない。スキルは `$desk-tools:desk-init` のように呼ぶ。資料のフォルダだけで効かせる入れ方（Codex には scope がないので、ユーザーの設定で切り、ワークスペースの `.codex/config.toml` で入れる）と、効いている範囲の確かめ方は [docs/codex-plugin.md](docs/codex-plugin.md)。

**pi**

```sh
pi install ~/Projects/ai-desktools                                # 手元の checkout をそのまま読む（写さない）
pi install git:github.com/mats16/ai-desktools        # git から
```

スキルは `/skill:desk-init` のように呼ぶ。資料のフォルダだけで効かせる（`-l`）入れ方と、project trust、効いている範囲の確かめ方は [docs/pi.md](docs/pi.md)。

入れたら、ワークスペースにするフォルダで `desk-init`、続けて `desk-doctor` を呼ぶ。前の版から更新したら `desk-doctor` を回し、「前のバージョンのワークスペース」が出たら `desk-migrate` で移す（2026-10-24 にスキルの名前・ファイルの分け方・決まりの ID を、2026-10-25 に設定と記録と管理のスキルの名前〔`factory.toml` → `desk.toml`、`.factory/` → `.desk/`、`factory-*` → `desk-*`、`dreaming` → `desk-dreaming` と決まりの ID の `factory-dreaming` → `desk-dreaming`〕を変えた）。

## ワークスペース

資料を置くフォルダ（例: `~/Documents`）。スクリプトと hook は、今いるフォルダから上へたどって最初に見つかった `desk.toml` のフォルダをワークスペースとして扱う。見つからなければ `~/.desk.toml`（環境変数 `DESK_CONFIG` で場所を替えられる）を読み、その `workspace` をワークスペースにする。見つかった 1 つだけを読み、混ぜない（`lib/desk.py`）。`desk-init` が置くもの:

- `desk.toml`（`~/.desk.toml` に置くときは、ワークスペースには置かない）: 人ごとに変わる値（資料を作る言語〔`[desk] default_language`。書かなければ `ja`〕、認証、テンプレート〔`[slides.templates]`: テーマの名前 = テンプレートの URL〕と社名、Drive の置き場所、材料を集める道具〔`[sources]`: 社内の検索・チャット・会議の記録・wiki など〕、レビューの進め方〔`[review]`: 構成を決めたあとを誰が見るか、`/deck-review` のラウンドの上限〕、返したあとにコメントを見張る期間〔`[feedback.google_comments] watch_hours`。0 か書かなければ見張らない〕）。テンプレートは `slides-build/scripts/template.py navy --from-base`（`white`・`blue` も）で作ると URL が書き込まれる。元にするテンプレートは `desk.toml` に持たず、`--from-base <元の URL>` で渡す。渡さなければ、白紙の pptx（`slides-build/assets/blank.pptx`）を Google Slides に変換して上げ、そこから作る。会社で配るテーマは全社の共有テーマのフォルダ（`[drive] shared_themes`）に置き、使う人は `slides.py themes` で見つけて `slides.py theme <url>` で写す（`slides-build/themes.md`）。
- `themes/slides/<名前>.json`: テーマのファイル（`kind: theme`。色・書体・著作権表示・表紙と扉のパターンと、使い分けの `description`。エージェントが `slides.py themes` の一覧から資料ごとに選ぶ）。組み込みの navy・white・blue はプラグインの `slides-build/themes/` にあり、同じ名前のファイルを置くとそちらが勝つ。desk-init は置かない（会社のテーマを作るとき〔`slides-build` の `template.md`〕と、共有のテーマを写すときにできる）。
- `recipes/<名前>/RECIPE.md`: 資料を作る・材料を集めるときだけ要る、このワークスペースの決まり（レシピ）。頭の frontmatter に、いつ使うか（`description`）を書く。作るもの（`targets`）と資料の種類（`audience`）で絞り、出し方（資料ごとに選ぶ `per_material: true`、材料集めの `step: gather`、組むときの `step: build`、書かなければどの作業でも）を書く。同じフォルダに、使うテンプレート（`templates/`）と点検（`checks.py`）を置く（下の「決まりの置き場所と育て方」）。
- `Customers/<顧客>/memory.md`: その顧客の資料への好み（どう作るか。相手が何者かは `profile.md`）（顧客の memory）。その顧客の資料の `構成案*.md` などを開くと、hook が続けて出す。
- `Customers/<顧客>/profile.md`: その顧客の事業・組織・技術の構成・エンジニアの好み（顧客の profile。行ごとに出典と日付）。`customer-profile` が作り、顧客向けの資料の作り始めに読む。30 日より古ければ取り直す。
- `Customers/`・`Internal/`・`Research/`、`references_index.md`・`drive_folders.md`: 資料と台帳。資料のフォルダの `references.md`（出典の台帳。出典ごとに S の ID。資料に結びつかない出典は `Research/references.md`）と構成案の「出典の表」（ページに出す事実の台帳。事実ごとに F の ID）は `lib/refs.py` が足し、確かめる。全体の索引 `references_index.md` は、`refs.py index` がすべての `references.md` から作り直す（手で直さない）。`drive_folders.md` は Google Drive の置き場所と上げた資料で、手で足す。`Research/deck_research/` は `desk-research` の調べ直しの記録（`state.md`・`log/`。代表の 3 枚の選び方の記録も）。
- `.desk/`: スクリプトが書く記録。`ledger.jsonl`（決まりの台帳。修正の指示、決まりの ID ごとの出典と再発、desk-dreaming の提案・適用・却下とプラグインへの提案の Issue、判断待ちと答え、deck-review の指摘の結果。`lib/ledger.py` が読み書きする）、`lint_runs.jsonl`（`lint.py --stats` が読む）、`spec_raw.jsonl`（JSON のページの形の外の書き方の数。`slides.py stats` が読む）、`dreaming/last_run`・`dreaming/log/`・`dreaming/backup/`、`profile/`（`customer-profile` が取り直す前の顧客の profile）、`comments.json`（`deck-workflow` の `comments.py` が前に取った時刻・送った返信・見張りの起点・見張りの知らせのコメントを残す）、`crawl/<話題>/`（`desk-crawl` の読む先の台帳 `sources.json`、回の記録 `runs.jsonl`、その回の読み方 `plan.json`）。

自分だけの画像は `assets/` に置く。`slides.asset()` はここを先に探し、なければ `slides-build/assets/` を使う。

ワークスペースの直下の `AGENTS.md`・`CLAUDE.md` は、プラグインもスキルも前提にしない（[決めたこと](docs/decisions.md) の 2026-10-31）。`desk-init` は置かず、スクリプトも読まず、修正の指示も戻さない。持ち主が自分で置くのは止めない。ただ、エージェントはこれをどの会話にも、スキルより強く読み込むので、書いた決まりは、資料を作らない作業にも効く。資料を作るための決まりはレシピに書く。2026-10-31 までの `desk-init` が置いた写しは、`desk-doctor` が「前の雛形の AGENTS.md」として知らせ、`desk-migrate` の手順で持ち主と一緒にレシピへ移す。

## 書体

テーマに書けば変えられる。書かなければ既定の書体で組む。

| 使うところ | 書く場所 | 既定 | 書ける書体 |
|---|---|---|---|
| スライドの本文 | テーマのファイル（`themes/slides/<名前>.json`）の `font`（`template.py` がマスターに書く） | Noto Sans JP | 下の「本文の書体」の 18 個（`lib/brand.py` の `JP_FONTS`）と、欧文の DM Sans（`FONT_EM`）。ほかは `slides.py lint` と `template.py` が止める |
| スライドのコード | テーマのファイルの `mono` | Cascadia Mono | Google Fonts の等幅の書体。リガチャのある書体（`LIGATURE_MONO`）は止める |
| ドキュメントの本文 | ドキュメントのテーマのファイル（`themes/docs/<名前>.json`）の `font` | Noto Sans JP | スライドの本文と同じ |
| ドキュメントのコード | ドキュメントのテーマのファイルの `mono` | Cascadia Mono | スライドのコードと同じ |

- **文字の幅の見込みは、測った書体のものを使う。** `slides.py` の `em_width` は、本文の英数字を `FONT_EM` の幅（Noto Sans JP Regular の `ASCII_EM`、DM Sans の `DM_SANS_EM`。太字はそれぞれの Bold の `ASCII_BOLD_EM`・`DM_SANS_BOLD_EM`）で、コードを `MONO_EM`（Cascadia Mono、0.586 em）で見込む。測っていない書体は Noto Sans JP の幅で見込み、折り返しの見込み（組むときの警告、`d.card` の高さ、lint の行数）がずれるので、Google が描いたページの画像で見る。
- **Google Fonts にない名前は、API が受け付けて黙って別の書体で描く。** 書いたら見本のページ（`template.py <名前>`、ドキュメントはそのテーマの文書）を組み、画像で確かめる。
- lint の「書体が … でない」「等幅の … に和文」は、テーマの書体と比べる。

**本文の書体（和文あり）:** 2026-10-07 に、テンプレートを複製した試しのデッキで同じ文を書体ごとに描き、Google Slides で描けることを確かめた。Google Docs で組んでいるのは Noto Sans JP だけで、ほかは Docs では確かめていない。印象ごとの選び方は `slides-build/template_fonts.md`。

| 分け | 書体 |
|---|---|
| ゴシック | Noto Sans JP（既定）、IBM Plex Sans JP、BIZ UDPGothic、BIZ UDGothic、Zen Kaku Gothic New、M PLUS 1p、M PLUS 2、LINE Seed JP、Murecho、Sawarabi Gothic |
| 丸ゴシック | M PLUS Rounded 1c、Zen Maru Gothic、Kosugi Maru |
| 明朝 | Noto Serif JP、BIZ UDPMincho、Shippori Mincho、Zen Old Mincho |
| 手書き風 | Klee One |
| 描けない（明朝と欧文のセリフ体になる。`template.py` の `NO_RENDER`） | Noto Sans CJK JP、Hiragino Sans、Yu Gothic |

**本文の書体（欧文）:** DM Sans だけ書ける。和文の字がなく、Google Slides は和文を別のゴシックで描く（どの書体になるかは選べない）。2026-10-15 に、Google Fonts の版（可変）の英数字の幅を測り、Google Slides が字の大きさによらず opsz 14 の版で描くことを、12・18・30pt で描いた画像で確かめた。

**コードの等幅の書体:** 2026-10-09 に調べた。等幅には和文の字形がないので、和文は本文の書体のまま、英数字の続きにだけ付ける。

| 分け | 書体 |
|---|---|
| Google Slides で描いたページの画像で確かめた | Cascadia Mono（既定。リガチャなし） |
| リガチャがないことを、Google Fonts の版を HarfBuzz で組んで確かめた（Google が描いたページでは見ていない） | Source Code Pro、Fira Mono、IBM Plex Mono、Roboto Mono |
| リガチャが出る（`->` が矢印 1 字になる。`mono` に書くと止める） | JetBrains Mono（Google Slides で出た）、Fira Code、Cascadia Code |
| Google Fonts にない（Arial で描かれる） | Iosevka、Hack、SF Mono、Menlo、Commit Mono、Monaspace |

## 決まりの置き場所と育て方

修正の指示は、ワークスペースの決まり（レシピ）と点検に戻す。大元（プラグイン）を直すべきものだけを Issue にし、持ち主が Issue から直す。決まりに層はない。プラグインの決まりは、スキルと lint の仕組みで効く。ワークスペースの決まりは、hook が要る場面で出したものを読み、資料に合うものだけを当てる。プラグインと食い違えばワークスペースが勝ち、ワークスペースどうしなら条件が狭いほう（顧客の memory、場面や資料の種類を絞ったレシピ、どの資料にも効くレシピの順）が勝つ。同じ狭さなら聞く。

| 決まり | 置き場所 | 中身 | 誰が変えるか |
|---|---|---|---|
| 顧客の memory | `Customers/<顧客>/memory.md` | その顧客の資料への好み（どう作るか。相手が何者かは `profile.md`） | 作る会話がその場で書く。desk-dreaming は提案する。2 社以上で同じ趣旨ならレシピに寄せる |
| ワークスペース | `recipes/<名前>/RECIPE.md`（frontmatter のあるレシピ）と、そのフォルダの `checks.py`・テンプレート | その人・その組織の決まりと点検、修正の指示で育つもの | 作る会話がその場で戻す。desk-dreaming は、会話から拾ったものは推奨を付けて提案し、返事で当てる。重なり・古い記述の片付けのうち、決まりを丸ごと消すだけのものは当ててから知らせる。経緯は決まりの台帳（`.desk/ledger.jsonl`）に残す（git は前提にしない） |
| プラグイン | `skills/`（入った場所は読むだけ） | 誰が使っても同じ決まり、点検、スクリプト、テンプレート | `desk-kaizen` で Issue。持ち主が直してマージしたら `update` で届く |

- **決まりの本文と経緯を分ける。** 決まりは 1 項目ごとに ID（プラグインは書いてあるファイルのパスから `[slides-visual-<番号>]` のように、ワークスペースは `[ws-slides-visual-<番号>]`）と短い理由だけを書く。日付・ユーザーの言葉・どの資料か・ユーザーが決めたかは、ワークスペースの決まりの台帳に ID でつなぐ（`ledger.py why <ID>`）。資料・顧客の数から、ワークスペースに寄せるか、プラグインに上げるかを決める。
- **レシピは frontmatter で出す。** `recipes/<名前>/RECIPE.md` の頭に、`description`（いつ使うか。要る）、`targets`（`slides`・`docs`・`vids`）、`audience`（`顧客向け`・`社内向け`・`コミュニティ向け`）と出し方を書く。1 つの `RECIPE.md` は 3,800 字まで。`step` を書かないレシピは、資料を作るどの作業でも（資料づくりのスキルのファイルを開いたとき〔Claude Code は Read・Bash・Skill、Codex は Bash、pi は read・bash〕と、資料のファイルを開いたとき）、`step: gather` は材料を集めるとき（調べもので `Research/`・`references_index.md` を使うときも。`.md` の名前が入るコマンドだけ。Claude Code と pi は `.md` のないコマンドで hook を起こさないので、Codex もそろえる）、`step: build` は組むときに、hook が続けて出す。どのプラグインのファイルがどの作業かは `desk.py` の `TRIGGERS` が持つので、書く人はプラグインのファイルを知らなくてよい。コマンドで呼んだスキル（`/desk-tools:<スキル>`・`$desk-tools:<スキル>`・pi の `/skill:<名前>`）は、その SKILL.md を開いたのと同じに扱い、Claude Code では自動のコンパクションのあとにも出し直す。`per_material: true` のレシピは資料ごとに選ぶ。作る会話が、hook の出す一覧（`deck-workflow/start.md` を開いたときと、「使う決まり」のない構成案を開いたとき）から選び、構成案の頭の「使う決まり」に書く。そのあとは、資料の `構成案*.md`・`社内メモ_*.md`・`references.md` を開くたびに、顧客の `memory.md` と一緒に先に出す。フォルダのほかのファイル（テンプレート・点検）は、名前だけを添える。前の版の `rules/` は出さず、資料を始めるときに desk-migrate で移すよう知らせる。
- **次の一手は台帳が出す。** `ledger.py candidates` が、決まりごとの数から、下ろす（点検か作る手順へ）・書き直す・条件を足す・上げる・写しを消す・上書きを見直すを出す。境目（2 本以上の資料、2 社以上の顧客）はスクリプトが持ち、desk-dreaming は趣旨と提案の文を考える。
- **当てたことは、効いた証拠ではない。** `ledger.py add`・`review` が、資料ごとに、そのときのハーネス（プラグインと `recipes/`）の指紋を残す。`ledger.py effects` が、文を変えた決まりごとに、前と後に作った資料での指摘の数を比べ、効いた・変わらない・害が出た・指摘なし（前も後も出ていない）・まだ分からない・混ざっている（同じファイルのほかの決まりも同じときに変わった）を出す。desk-dreaming は、変わらないものを点検か作る手順に下ろす案にし、害が出たものを判断待ちにする。
- **点検もワークスペースで育てる。** `recipes/` の下のすべての `checks.py`（見る決まりのレシピのフォルダに置く）の `slides(p, r)` をスライドの lint（`slides.py lint`・`gslides.py check`）が、`doc(doc, r)` をドキュメントの lint（`docs.py check`）が毎回呼ぶ。`HARD` に入れた名前は要修正。書き方は `desk-init/templates/recipes/README.md`。
- **大元に上げる。** ほかの人にも効くものは、desk-dreaming が「プラグインに上げる」提案にし、`desk-kaizen` で出す。
  1. 元のリポジトリを `.desk/kaizen/` に clone して変更案を書く（手元に checkout や fork は要らない）。
  2. 過去の資料で確かめる。lint は前の版と変えた版をかけ比べ、見た目は正本から両方の版で仮に組み直してページの画像を並べる。決まりと手順の文（`skills/` の md）を変えたら、同じ依頼（`docs/fixtures` の試しと、過去の資料の再演）を両方の版で子に書かせ、版を伏せた子に成果物だけを見て選ばせる（`kaizen.py probe`。Google は使わない）。
  3. 理由・背景・検証の結果・画像・変更案の差分を入れた Issue を作る。Issue には資料の名前・URL・本文を出さず、「資料 1」の番号と規則ごとの数の変化、ユーザーが選んだ画像だけを載せる。ブランチは push しない。
  4. 持ち主が Issue を読んで入れるかを決め、ほかのコードと合わせて直して PR にする（simplify・レビューも持ち主がする）。
  5. 直しが届いたら、レシピの写しを消す。
- `desk-research` の調べ直しの結果も、`desk-kaizen` で Issue にする（変更案に入れるのはスキルの直しと `sources.md`。調べた記録はワークスペースに残す）。

## Google の認証

API を直接呼ぶ（MCP は使わない）。トークンは `lib/gapi.py` が次の順に取る。gcloud も、ほかの Google のスキルも、動かすときには要らない。

1. 環境変数 `GOOGLE_OAUTH_ACCESS_TOKEN`（ほかの仕組みで取ったトークンを渡すとき）
2. `authorized_user` の認証情報の JSON（`GOOGLE_APPLICATION_CREDENTIALS`、なければ gcloud の ADC のファイル）の refresh_token。作るのは `gcloud auth application-default login --scopes=…`（`desk-doctor` がコマンドを出す）

gcloud の既定の OAuth クライアントで作った認証情報は、`google.quota_project` がないと 403 になる。

## 決めたこと・残っている課題

ユーザーが決めたことは [docs/decisions.md](docs/decisions.md)、後回しにしたことは [docs/todo.md](docs/todo.md) に書く。

## 入れていないもの

`databricks-updates`（毎朝のアップデートのまとめ）と `pi-compaction-report`（pi の運用レポート）は、使う人のチャット・フォルダ・セッションに結びついた個人の定期の作業なので入れていない。`databricks-updates` のうち、どこを読むかを集めて学ぶ部分は、話題を持たない `source-scout` として入れ（[決めたこと](docs/decisions.md) の 2026-10-26）、2026-10-29 に `desk-crawl` に作り直した（同じく 2026-10-29）。分類・書き方・投稿先は、ワークスペースの側に残す。

## ライセンス

MIT（[LICENSE](LICENSE)）。
