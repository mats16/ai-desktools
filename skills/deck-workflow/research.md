# Research requests

Open this for a research request that makes no material (「〇〇を調べて」). Research for one material goes in that material's folder instead (`references.md` and `社内メモ_*.md`; "Ledger" in [materials.md](materials.md)).

Do not stop at answering in the reply. Leave the result in `Research/<topic>_<YYYYMMDD>.md`, so the same thing is not researched twice.

- **Search first.** `grep -rln <word> Research/ references_index.md` finds earlier research and the sources used before. If one covers the request, read it, research only what is missing, and add to the same file (the date and what changed under 「更新」 at the end).
- **What to write:** the request in the user's words, the conclusion in a few lines at the top, the evidence and its sources (URL and the date you checked), what you confirmed apart from what you inferred, and what is still unconfirmed. If it holds internal-only information, write 【社内】 at the top (「社外秘と顧客の情報」 in `deck-writing`).
- **After writing or adding, copy it to Drive.** `python3 <deck-workflow folder>/scripts/drive_put.py research Research/<topic>_<YYYYMMDD>.md` converts it to Google Docs and uploads it to `Research` under `drive.desk` in `desk.toml` (created if missing). A file with the same name is overwritten, so the URL stays the same. The first time, add `- 上げた: Research/<topic>_<YYYYMMDD>.md → [<YYYYMMDD>_<topic>](URL)（初めて上げた日）` under the `Research` line of `drive_folders.md` (add the line if missing). The copy is a record for people to read in a browser. The md here is the original, and you search and read it here. Do not edit or comment on the Drive copy, because the next upload erases the edits and leaves the comments without their anchor.
- **Sources** that can help other materials: `python3 <plugin>/lib/refs.py add Research <URL> --use <what it is good for>` (`Research/references.md`). `refs.py` rebuilds the overall index `references_index.md` from every folder's `references.md`, so do not edit the index by hand.
