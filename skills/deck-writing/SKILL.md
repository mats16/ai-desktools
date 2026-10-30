---
name: deck-writing
description: The brief and the writing axes for materials (decks, documents) - what a good material does, the user's iron rule, and four axes for what the rules leave open in content and wording (what the reader must grasp, which relationships must be seen, how far to claim, which words, what this audience needs). Read before writing an outline or pages, before reviewing, and when a choice of content or wording is not decided by a rule. How things look is in deck-design. deck-practices opens both first; child agents that write pages or review get both paths.
---

# The brief and the writing axes

This file holds the brief that every material serves, and the axes for content and wording. How a page looks (hierarchy, emphasis, color, composition) is in `../deck-design/SKILL.md`. The rules in the other skills decide what can be counted and what the user decided; decide what they leave open with these axes. Do not turn an axis into a fixed pattern ("always add a diagram"), because a pattern applied to every page stops serving the page.

Order when things conflict: the workspace rules (`AGENTS.md`, `recipes/`, the customer's `memory.md`) → the user decisions written as rules in the other skills → these axes. The outline's 「書き方の決め」 is the parent's decision, not the user's: write it from these axes, and when a line of it pulls against an axis, follow the line and write the conflict under 「親に返すこと」 (children) or fix the line (parent).

## The brief: what a good material does

読み手が、各ページの言いたいことを細部より先につかみ、信じ、ほかの人に言い直せる。どの選択も、これに近づくかで決める。

鉄則は「営業色を出さずに、お客様の目線で情報を整理するところから入る。課題や問題意識について目線をそろえることは、提案の中身より重要」。顧客向けの提案だけでなく、社内向けの資料にも、顧客も来るコミュニティ向けの技術資料にも当てはめる。ワークスペースの AGENTS.md の「いい資料の考え方」は、この企画書と deck-writing-004 の要点で、どの会話でも見えるようにそちらにも置いてある。

## The writing axes

1. [deck-writing-001] **初見の読み手が、いちばん少ない手間で要点をつかめる。** 読み手がその話を初めて聞く前提で、何を先に言えば分かるか、どの関係（仕組み・通り道・層・置き場所）は目で見えないと伝わらないかを決める。見えないと伝わる関係は、図で見せる（ページが増えてもよい。どう描くかは deck-design）。一方で、図だけにしない。要旨を押さえた文は、図と同じだけ要る。文字と図の釣り合いは、そのページの中身で決める。分かりにくいときは、言い換える、関係を図にする、ページを分ける、の順に考え、字を小さくして詰めない。
2. [deck-writing-002] **言い切る範囲は、根拠の範囲まで。** 見出しやリードの範囲と数の言葉（「だけ」「すべて」「N つ」「できる」）は、出典の表の行とページの中の項目に合わせる。出典どうしが食い違うとき、相手の環境やデータを確かめていないときは、安全な範囲で言い切るか、何次第かを見出しかリードに書く。相手の道具にもあることは、あると書いたうえで違いを言う。
3. [deck-writing-003] **口に出して通じる、具体の言葉で書く。** 字を詰めるために、何を測った数か・何と何の組み合わせかを略さない。「データソース」「SIEM」のような総称だけでなく、具体の製品や仕組みの名前を書く。製品の名前は正式な名前で、似た製品と取り違えない。略語は初出で正式な名前を添える。直訳の言い回しは、日本語の資料として自然な言い方にする。
4. [deck-writing-004] **聞き手から見て要るものだけを載せる。**
   - **主役は聞き手。** 聞き手の状況と問いから始め、自社や機能の紹介から始めない。見出しの主語は、聞き手の業務・データ・判断・つまずきにする。製品は、問いに答える手段としてあとで出す。
   - **問いを先にそろえる。** 中身に入る前に、なぜこの話なのか、何が問題なのかを聞き手と共有する。問いは聞き手が実際に持っているものを拾い、出典を控える（顧客なら会議の記録と社内のチャット、社内ならチャットに来る質問、コミュニティなら GitHub の Issue やよくある質問、自分たちで試した経験）。こちらの見立てには「仮説」と書く。聞き手が言っていないことを、言ったように書かない。
   - **課題は影響まで書く。煽らない。** 「何に困っているか」だけでなく、それで何が起きるか（時間、コスト、リスク、逃す機会）まで書く。変える価値があるかどうかは、影響を見て決まる。数字は出典のあるものだけを使う。「このままでは〜」「乗り遅れる」のように不安をあおる言い方はしない。決めかねている相手には逆効果になる。
   - **聞き手の見方をなぞるだけにしない。** 聞き手の目線に立つことは、聞き手の言い分を繰り返すことではない。聞き手がまだ持っていない見方（論点の整理、比べ方、見落としやすいリスク）を足すのが SA の仕事。ただし、その見方が特定の製品でしか答えられない形になってはいけない。
   - **公平に書く。** 他社の製品や OSS、今の仕組みでできることは、できると書く。重なるところは重なると言う。自社の製品の向かないところや、プレビューのところも書く。問いと課題を整理したページは、結論が自社の製品にならなかったとしても聞き手の役に立つ内容にする。売るための前振りに見えたら逆効果。
   - **見解ははっきり言う。** 選択肢を並べて終わらせない。推奨か使い分け（「〜なら A、〜なら B」）を、理由と一緒に書く。比べる軸と選択肢は絞る（情報を増やすより、判断を整理する手伝いのほうが役に立つ）。
   - **聞き手の立場と技術の程度に合わせる。** 上から目線、守りに入りすぎた但し書き、こちらの都合（自分だけが使う道具、社内の仮説、聞き手に要らない案内の仕方）を載せない。

## The boundary with deck-design

This file decides what the reader must grasp, which relationships must be seen, and how much of the page is text. deck-design decides how that is shown: the form, the hierarchy, and the emphasis. For 「文字が多いので図にして」, the decision to show a relationship is axis 1 here; how the figure is composed is deck-design.

## How to use the axes

- **Maker (parent and page-writing children):** before writing a page, write the one sentence it says and what the reader must grasp first (axis 1). Before handing it back, read it as a first-time reader of the stated audience.
- **Reviewer:** judge every aspect in the review request by the axes here and in deck-design, starting with axis 1, because it is what the user corrects most and reviewers flag least. When a finding comes from an axis rather than a rule, end the proposed fix with the axis ID (such as 「（deck-writing-002）」); the parent moves it to the 「決まり」 column.
