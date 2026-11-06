# Exchange Sector Monitor

A read-only mirror of the Exchange Sector Monitor: news, financial results, operating data, history since 2015, business models and technology profiles for about 48 exchange groups, post-trade infrastructures (CCPs, CSDs) and market-data and index providers.

- **Live site:** https://aterentievfiles.github.io/Exchange-Sector-Monitor/
- **Data:** [`data.json`](data.json) — one file with every collection (`companies`, `news`, `events`, `series`, `mix`, `tech`) plus the last update `status`.
- **Updates:** refreshed every weekday morning (Moscow time) by an automated research run. The original lives on claude.ai; this repo is a copy.

News summaries are written in our own words and link to their original sources. Figures are as reported by the companies, in reporting currency; check the linked source before relying on any number.

## Files

| File | What it is |
|---|---|
| `index.html` | The monitor page. Off claude.ai, it loads `data.json` and runs read-only. |
| `data.json` | Snapshot of the knowledge base, keyed by collection and document id. |
| `.nojekyll` | Tells GitHub Pages to serve files as they are. |
