# Checking a rewritten rule file against the user's decisions (step 4j of the scheduled cleanup)

The parent of desk-dreaming gives everything below the line to one child agent per rewritten file at step 4j of [run.md](run.md). Replace `{file}` with the workspace file, and paste under "Inputs": the current text, the new text, and the decisions (from `ledger.py why {file}`: each finding marked 「ユーザーが決めた」, and each 「手で直した」 version with its diff from `ledger.py pending --status all`). The child only checks. The parent proposes the file only when the child returns 「通す」.

---

You check that a rewrite of the rule file `{file}` in an AI Desk Tools workspace kept what the user decided. Someone else wrote the new text. Do not suggest improvements to it. Judge only whether each decision below still holds in the new text, because a rewrite that silently drops or weakens a decision overturns the user, and every later material follows the rule file.

## Inputs

- **Current text** of `{file}`.
- **New text** of `{file}`.
- **Decisions:** each finding the user decided (c-ID, date, the user's words verbatim, what was fixed), and each 「手で直した」 version (P-ID and the lines it added or changed). For a 「手で直した」 version from before the migration, you get instead the text a proposal had applied that the user later edited: find the wording that took its place in the current text, and check that wording.

## How to check

For each decision, find where the new text says it, and mark it:

- **残っている:** the new text still makes a material come out the same way under that decision. Different wording is fine.
- **変わった:** it is there but narrower, wider, or weaker. For example, a condition was added or dropped, 「〜する」 became 「〜してもよい」, an example became the rule, or it moved under a heading that limits it to some materials.
- **消えた:** the current text says it, and the new text does not.
- **前からない:** neither the current text nor the new text says it (another file or the plugin may already hold it). This rewrite did not drop it, so it does not stop the rewrite. Say where you think the rule now is, if you can see it, so the parent can link the finding there.

A later decision of the user can replace an earlier one. Mark the earlier one 残っている only if the later decision is in the new text, and name the later c-ID.

Then list the items of the current text that are missing from the new text and are not explained by any finding or decision (silent deletions). An item merged into another item is not missing if its content is there. Silent deletions stop the rewrite too, because the user approves it from the change per finding and would not see them.

## Output

Return only this, in the order of the decisions. Copy the user's words and the rule text in their original language.

```markdown
- c-0012: 残っている — 新しい文「<引用>」
- c-0031: 変わった — 前「<引用>」→ 新しい「<引用>」（<何が変わったか>）
- P0040: 消えた — 前「<引用>」
- c-0416: 前からない — 前の文にも新しい文にもない（<今ある場所の見当。分からなければ「不明」>）
## 黙って消えた項目
- 「<前の文の引用>」（なければ「なし」）
## 判定
止める（変わった・消えた・黙って消えた項目が 1 件以上。前からないは数えない）／通す
```
