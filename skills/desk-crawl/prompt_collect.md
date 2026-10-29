You collect updates for the topic `{topic}` from one group of sources (group `{group}`). Read only; do not write files, post, or reply anywhere.

## Goal

{goal}

## Window

From {since} to {until}. Each source below has its own start ("read from"): a source that could not be read last time, or that was skipped for a few runs because it rarely pays, starts where it was last read, so nothing is lost. Do not read before that start.

## Sources

{explore}

{sources}

Notes under a source are lessons from earlier runs about how to read it (markers that worked, noise to skip, tool pitfalls). Follow them. Open `{skill}`, then its `kinds.md`, for how to read each kind (`slack`, `slack-search`, `gmail-search`, `web`, `web-search`, `confluence`) and the tool pitfalls.

Topic notes (apply to every source):

{notes}

## How to read

- Read every top-level post or message in the window, unless a note says how to narrow it (markers for a busy channel). For a `*-search` source, run the query in its id over the window. For a digest (a bot summary, a newsletter), open the original post of each item you pick, because digests are AI summaries and can be wrong.
- Open threads of picked posts that have replies, because conditions, corrections, and dates are often in the replies.
- For a forwarded or cross-posted post, open the original and report the original as `origin`.
- Pick only what serves the goal. Skip questions without an answer, chat, logistics, HR, and individual customer cases. Do not copy customer names or personal names into summaries; write 「ある顧客」.
- If a post links to a channel, page, or list not in your sources (`#channel`, "join #…", "questions go to …"), report it in `discovered`.
- Keep each tool call under 270 seconds. Read sources one by one, not in parallel, because parallel reads time out.

## Return

Return one JSON object, and nothing else:

```json
{"reads": [{"source": "<id>", "name": "<name>", "ok": true, "since": "<start you used>", "until": "{until}", "scanned": 12, "picked": 2}],
 "candidates": [{"title": "<one line: what changed, for whom, conditions>", "url": "<link to the post or page>", "urls": ["<other links to the same news>"],
                 "seen_in": ["<every source id in this group where you saw it>"], "origin": "<source id of the original post, if it is outside this group>",
                 "public_url": "<public docs, blog, or release note URL, if any>", "published": "<ISO time>", "summary": "<2-3 sentences, with stage and dates in the source's words>"}],
 "discovered": [{"source": "<kind>:<ref>", "name": "<name>", "via": "forward|mention|search|thread|watch|wiki", "created": "<YYYY-MM-DD if shown>", "why": "<one line>"}],
 "lessons": [{"source": "<id or *>", "text": "<one short imperative sentence that would make the next read cheaper or more accurate>"}],
 "votes": [{"note": "<note id>", "helpful": true}]}
```

- `reads`: one entry per source in your group. If a source fails (timeout, no access, tool error), set `"ok": false` and `"error"`; do not guess its content.
- `lessons`: only new and concrete ones (a marker, a noise pattern, a pagination or tool fact). Do not restate the notes above.
- `votes`: for a note above that clearly helped (`true`) or misled you (`false`) this time, such as a note or marker that would have made you skip an item you picked anyway. Leave out notes that did not matter.
- Copy titles, stages, and dates in the original language of the source.
