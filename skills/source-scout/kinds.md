# How to read each kind of source

The child agents read this file (`prompt_collect.md` points here). A source id is `<kind>:<ref>`. The tool for each kind is the one named in `[sources]` of `desk.toml` (`chat`, `search`, `wiki`); the examples below use the Slack, Gmail, and Glean MCP servers. Topic-specific markers and noise go into the source's notes (`scout.py set … note=…` or `lessons`), not here.

| Kind | Ref | Read with |
|---|---|---|
| `slack` | channel ID (`C0123456789`) | `slack_read_channel` and `slack_read_thread` |
| `slack-search` | query (`japaneast`, `"data residency"`) | `slack_search_public_and_private` |
| `gmail` | Gmail query (`label:product-news`, `subject:"[GA]"`) | `gmail_search`, then `gmail_message_get` for picked mails |
| `feed` | RSS or Atom URL | `scout.py feeds` (the main agent runs it; no child agent) |
| `wiki` | page or space (`confluence:<page ID>`) | the wiki tool, or the search tool with a wiki filter |
| `web` | page URL (a changelog or a list page with no feed) | fetch the page and compare with the items already published |

## Slack

- Use `response_format: "detailed"`, because the concise format has no `Message TS`, reply count, or reactions, and links cannot be built without the ts. A post link is `https://<workspace>.slack.com/archives/<channel ID>/p<ts without the dot>`; a reply adds `?thread_ts=<parent ts>`.
- With `oldest`, results come oldest first, one page at a time. Pass `cursor` from `pagination_info` until none is returned (`limit` 100).
- Read channels one by one. Parallel reads and batch calls (`conversations.history` in parallel, `slack_batch_read_api_call`) timed out and dropped the MCP connection.
- A forwarded post (x-post) has no body; the result says to use `slack_read_thread`. Open the original and report it as `origin`.
- `filter` markers that worked for product announcements: strong (pick even when phrased as a question) `<!channel>`, `<!here>`, `PSA`, `Heads up`, `:tada:`, `:announcement:`, `:rocket:`, `:mega:`; weak (pick only when not a question) `now available`, `generally available`, `is now GA`, `Public Preview`, `Private Preview`, `deprecat`, `EOL`, `retire`, `rolling out`, or 10+ reactions. A question starts with `Hi`, `Hey`, `Quick question`, contains `I have a customer`, or ends with `?`. Check markers in the first 600 characters only, because footers carry unrelated links.
- In environments with code mode (pi), read and filter inside one script and print only the picked posts, so that full channel text does not enter the context.
- **New channels.** For an explore group, also run `slack_search_channels` with words such as `preview`, `beta`, `announce`, `launch`, plus new product names seen today. Results are ordered by relevance, not by date, so read up to 6 pages per word and keep channels whose `Creator: <name> - <YYYY-MM-DD>` is within the window. Report them with `"via": "watch"` and `created`. Skip incident, escalation, customer-deal, and temporary channels.

## Search queries (`slack-search`, `gmail`)

- Filter by date in the query (`after:<day before the window start>` for Slack, because `after:` excludes that day; `after:<epoch seconds> before:<epoch seconds>` for Gmail).
- Open the thread or message of each hit before picking it; pick a Slack question only when someone who owns the product answered it.
- Gmail: group incident mails by their incident number and read only the latest follow-up. Skip personal notices, calendar invites, and external newsletters. Do not copy mail bodies; report the subject, the list it came to, the date, and a summary.

## Wiki and contact pages

- When a product or feature in today's candidates has no known channel, search the wiki for `<product> slack channel`. Preview sign-up pages, FAQs, and user guides often say "reach out through #…". Report the channel with `"via": "wiki"` and the product name in `why`, so it is not looked up again.

## Duplicates across sources

- The same news often appears in several sources (a forward, a cross-post, a digest bot, a mail to a list, a public release note). Report it once per source you saw it in, with the same `url` when possible and the others in `urls`. `scout.py merge` joins them by URL and keeps every source in `seen_in`, which is how the sources that only repeat others are found.
