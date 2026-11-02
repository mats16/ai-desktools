# Image assets

`gcp/` holds the images a document can place with `asset("gcp/<name>.png")` (for example `![BigQuery](gcp/bigquery.png){width=40}` in doc.md). They are byte-identical copies of the assets of `google-slides`, which owns them: add or replace an image there, then run `tests/skills/check.py --sync` in the plugin repository. Do not add files here.

Where each image comes from, the use it allows, and the trademark terms are in the asset ledger of `google-slides` (`google-slides` → images). A workspace's own images go in the workspace's `assets/`, which `asset()` reads first.
