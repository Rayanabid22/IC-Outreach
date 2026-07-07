# IC Funded Leads Pipeline

Finds companies funded in the last 7 days (auto-widening to 30 if needed),
filters them to Impact Creatives' ICP using Claude with web search, verifies
their socials are active (X is the priority signal), optionally finds
founders, and appends qualified leads to the existing Google Sheet.

Target: 150–200 leads per run when the data supports it. The pipeline never
pads with unqualified rows — every row in `Leads` has at least one
confirmed-active social.

## Quick start

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...
export SHEET_ID=<your google sheet id>

python pipeline.py run
```

Optional flags:

| Flag | Effect |
|---|---|
| `--window 14` | Force a fixed collection window in days (disables auto-widening) |
| `--target 200` | Override the qualified-lead target (default 175) |
| `--dry-run` | Print results instead of writing to the sheet (no Google auth needed) |

## One-time Google Sheets setup

1. Create a Google Cloud project → enable the **Google Sheets API**.
2. Create a **service account** in that project → create a JSON key →
   download it as `credentials.json` into this directory (it's gitignored).
   Alternatively (e.g. for cloud runs), set the env var
   `GOOGLE_CREDENTIALS_JSON` to the full JSON contents of the key file.
3. Open the target Google Sheet → **Share** → add the service account's
   email (`...@...iam.gserviceaccount.com`) as **Editor**.
4. Put the Sheet ID (the long string in the sheet URL between `/d/` and
   `/edit`) in the `SHEET_ID` env var, or paste it into `config.py`.

The pipeline creates/maintains three tabs automatically:

- **Leads** — qualified leads (18 columns: Date Added, Company, Website,
  Category, Region, Funding, Announced Date, Source, X Handle, X Active,
  LinkedIn, Instagram, Discord, Email, Founder, Founder X,
  Founder LinkedIn, Fit Reasoning)
- **Processed** — every company ever evaluated, keyed on normalized name.
  Used for cross-run dedup (merged with the local `seen.db`).
- **Rejected** — dropped companies with the reason, for auditing the filter.

## How it works

1. **Collect** — SEC EDGAR Form D filings (full-text search + per-filing
   XML for amounts/state), Google News RSS queries, TechCrunch venture
   feed, Finsmes, EU-Startups, and BetaKit. Starts with a 7-day window.
2. **Dedup** — normalized company name keyed in a local SQLite `seen.db`,
   synced with the sheet's `Processed` tab. Anything processed in a prior
   run is skipped regardless of outcome, so repeat runs stay fresh and
   re-running the same day never creates duplicate rows.
3. **ICP filter** — batched Claude calls (`claude-sonnet-4-6` with web
   search, 15 companies per call). Resolves Form D legal entities to real
   brand names/websites, classifies category and region, and applies the
   hard exclusions (gambling, interest-based lending, alcohol/cannabis,
   adult content, Israeli companies). Region is recorded but never a hard
   exclusion.
4. **Social enrichment** — one Claude call per ICP-fit company: X handle +
   30-day activity check (verified via web search), LinkedIn URL (no
   activity check — LinkedIn blocks scraping and we don't attempt it),
   Instagram best-effort, Discord, contact email, and founder info as a
   bonus. Qualification bar: at least one confirmed-active social; an
   active X alone qualifies. No active socials → logged to `Rejected`.
5. **Write** — qualified leads appended to `Leads`; audit rows to
   `Processed` and `Rejected`.
6. **Summary** — window used, funnel counts, founder-found rate, and a
   rough API cost estimate printed to the terminal.

If the qualified count is below target after a window, the pipeline
automatically widens: 7 → 14 → 21 → 30 days. If the target still can't be
met at 30 days, the run completes anyway and the summary states the real
count.

## Configuration

Everything editable lives in `config.py`:

- `NEWS_QUERIES` — Google News search queries (add/remove niches freely)
- `RSS_FEEDS` — static feeds
- `NICHES` / `EXCLUSIONS` — the ICP definition fed to the filter prompt
- `TARGET_LEADS`, `START_WINDOW_DAYS`, `MAX_WINDOW_DAYS`, `WINDOW_STEPS`
- `FILTER_BATCH_SIZE`, `FILTER_MAX_SEARCHES`, `ENRICH_MAX_SEARCHES`
- `SEC_USER_AGENT` — SEC requires a descriptive User-Agent
- `CLAUDE_MODEL` and the pricing constants used for the cost estimate

## Operational notes

- Every Claude API response is logged to `logs/` for debugging.
- EDGAR and RSS requests are rate-limited (~1–2 req/sec) with exponential
  backoff on 429s.
- `seen.db` is the primary dedup store; delete it only if you also clear
  the `Processed` tab (it re-syncs from the tab on each non-dry run).
- Explicit non-goals: no LinkedIn scraping/automation, no outreach sending
  (this produces the sheet only), no IC HQ integration in v1.
