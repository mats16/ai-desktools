# recipes/

このワークスペースだけの決まり（レシピ）と、それが使うテンプレート・点検。プラグインより優先する（スキル `desk-feedback` の `routing.md` の「Workspace rules」）。分け方・書き方・組み直し方は、スキル `desk-feedback` の `recipes.md`。

## レシピ: `recipes/<名前>/RECIPE.md`

1 つの目的ごとに 1 つのフォルダ。フォルダの名前は目的を英小文字で書く（例: `recipes/product_update/`・`recipes/internal_tools/`）。スキルやプラグインのファイルの名前にはしない。決まりは `RECIPE.md` に書き、頭の frontmatter に、いつ使うかを書く。同じフォルダのほかのファイル（テンプレート・`checks.py`・画像）は、そのレシピの資源で、決まりとしては出さない（hook は名前だけを添える）。`RECIPE.md` のないフォルダは、レシピを集めるだけのフォルダ（3 つほど集まったときに作る。例: `recipes/customer/cxo/RECIPE.md`）。

```markdown
---
description: 製品のアップデートをまとめる資料で、顧客に効くものを選んで説明するとき
targets: [slides, docs]
audience: [顧客向け]
per_material: true
---

- 〜のときは〜する（<短い理由>）。
```

- `description`（要る）: いつ使うか。この 1 行だけで選べるように書く。
- `targets`: `slides`・`docs`・`vids`。`audience`: `顧客向け`・`社内向け`・`コミュニティ向け`。書かなければ全部。
- 出し方は 3 つ。人が書くときは、スキルのことは考えなくてよい。`description` と項目だけを書けば、AI が目的に合うレシピと出し方を決める。
  - `per_material: true`: 資料ごとに選ぶ（資料の種類や場面のレシピ）。作る会話が構成案の頭に `- **使う決まり:** recipes/a/RECIPE.md、recipes/b/RECIPE.md` と書き、構成案を開くたびに hook が出す。
  - 何も書かない: 資料の中身と見た目の、どの資料にも効く決まり。資料を作るどの作業（書く・組む・レビュー）でも hook が出す。
  - `step: gather`: 材料を集めるときだけ要る知識（社内の検索の道具、情報源）。資料の材料集めのほか、ただの調べもの（`Research/`・`references_index.md` を使い、`.md` の名前が入るコマンド。雛形の AGENTS.md の「調べもの」の探し方）でも出す。`step: build`: 組むときだけ要る知識（ロゴやアイコンの取り先、テーマの手順、API の落とし穴）。
- 1 つの `RECIPE.md` は 3,800 字まで（顧客の memory と並べても、最初のレシピは途中で切れない。入りきらないものは、hook がパスを挙げる）。超えそうなら、もっと狭い目的で分ける。
- プラグインの決まりを上書きするときは、上書きする決まりの ID を角括弧なしで `- 〜は〜にする（slides-visual-012 より優先。<短い理由>）。` の形で書く（ID のない節なら「プラグインの〇〇の節より優先」）。
- 決まりは 1 項目ずつ箇条書きにし、ID は付けない（`- 〜のときは〜する（<短い理由>）。`）。日付とユーザーの言葉（原文）は本文に書かず、決まりの台帳（`.desk/ledger.jsonl`）に、このレシピへの指摘として残す。直してから戻し先にこのレシピを書く（`ledger.py route <c-ID> recipes/<名前>/RECIPE.md`）と、台帳が直す前と後の全文を版として残す（`ledger.py why recipes/<名前>/RECIPE.md` で見る。スキル `desk-feedback` の `routing.md` の「Routing corrections」）。

## テンプレート: `recipes/<名前>/templates/<テンプレートの名前>/doc.md`

会社の文書の型（`docs.py init <テンプレートの名前>` が写す）。使う資料のレシピのフォルダに置き、どれをいつ使うかは、そのレシピの `RECIPE.md` に書く（例: 「顧客向けの PoC の計画書は `templates/poc_customer/doc.md`、社内の PoC は `templates/poc_internal/doc.md`」）。テンプレートの名前は `recipes/` の中で重ねない（`docs.py init` は名前で探す）。決まりではないので、frontmatter の description は要らない。

## 点検: `recipes/<名前>/checks.py`

lint が毎回、`recipes/` の下のすべての `checks.py` を読み込む。その点検が見る決まりのレシピのフォルダに置く。スライドの lint（`slides.py lint`・`gslides.py check`）は `slides(p, r)` にスライドの JSON（presentations.get）を、ドキュメントの lint（`docs.py check`）は `doc(doc, r)` にドキュメントの JSON（documents.get）を渡す。持っている関数だけが呼ばれる。どちらも指摘を `r.hits["<規則の名前>"].append("<場所>: <中身>")` で足す。`HARD` に入れた名前は要修正（exit 1）、ほかは要確認。スライドの部品（`lint`）はドキュメントの lint からは読めないので、import は関数の中に書く。

```python
# recipes/brand/checks.py
HARD = {"社名の旧表記"}

def slides(p, r):
    import lint  # スライドの lint の部品（flatten・paras・ptext）
    for i, s in enumerate(p.get("slides", []), 1):
        for e, _ in lint.flatten(s.get("pageElements", [])):
            text = "".join(lint.ptext(x) for x in lint.paras(e.get("shape", {}).get("text")))
            if "旧社名" in text:
                r.hits["社名の旧表記"].append(f"p{i}: 「{text[:20]}」")

def doc(doc, r):
    import doc_lint  # ドキュメントの lint の部品（gdoc_paras・gdoc_text）
    for n, p, _, _ in doc_lint.gdoc_paras(doc):  # 段落の番号、段落、表の番号、表の前の段落か
        if "旧社名" in (text := doc_lint.gdoc_text(p).strip()):
            r.hits["社名の旧表記"].append(f"段落 {n}: 「{text[:20]}」")
```

## 大元に上げる

ほかの人にも効くと分かったものは、desk-dreaming が「プラグインに上げる」提案にし、`desk-kaizen` で Issue を出す。上げた決まりが入っているプラグインに届き、同じ文がここに残っていれば、ここの写しを desk-dreaming が消す（`ledger.py candidates` の「写しを消す」）。

## 顧客の memory: `Customers/<顧客>/memory.md`

顧客ごとの好みは、ここではなく顧客のフォルダに置く（スキル `desk-feedback` の「Customer memory」）。その顧客の資料を開くと、hook が続けて出す。
