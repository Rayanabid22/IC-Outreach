"""Configuration for the IC Funded Leads Pipeline.

Everything Rayan is likely to tweak lives here: news queries, niches,
exclusions, targets, and batch sizes. Secrets (API key) come from the
environment; the Google Sheet ID can come from either.
"""

import os

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# Rough pricing used only for the end-of-run cost estimate (per PRD stage 6).
PRICE_INPUT_PER_MTOK = 3.00     # USD per 1M input tokens (claude-sonnet-4-6)
PRICE_OUTPUT_PER_MTOK = 15.00   # USD per 1M output tokens
PRICE_PER_1000_SEARCHES = 10.00 # USD per 1,000 web searches

# ---------------------------------------------------------------------------
# Google Sheet
# ---------------------------------------------------------------------------
SHEET_ID = os.environ.get("SHEET_ID", "")  # or paste the ID here directly
CREDENTIALS_FILE = "credentials.json"      # service-account key (gitignored)
LEADS_TAB = "Leads"
PROCESSED_TAB = "Processed"
REJECTED_TAB = "Rejected"

# ---------------------------------------------------------------------------
# Run targets / windows
# ---------------------------------------------------------------------------
TARGET_LEADS = 175
START_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 30
# Auto-widening schedule when the qualified count falls short of target.
WINDOW_STEPS = [7, 14, 21, 30]

# ---------------------------------------------------------------------------
# Stage 1 — collection sources
# ---------------------------------------------------------------------------
# SEC requires a descriptive User-Agent on all requests.
SEC_USER_AGENT = "ImpactCreatives research contact@theimpactcreatives.com"

# How many individual Form D filings to fetch in detail (offering amount,
# state, industry) per run. The index itself is always fetched in full.
EDGAR_MAX_DETAIL_FETCH = 150

# Polite delay between requests to EDGAR / RSS hosts (seconds).
REQUEST_DELAY_SECONDS = 0.6

# Google News RSS queries — edit freely, one plain-text query per line.
NEWS_QUERIES = [
    '"raises" "seed" SaaS',
    '"Series A" AI startup',
    '"announces funding" software',
    '"raises" fintech startup',
    '"raises" "seed" AI',
    '"Series A" fintech',
    '"raises" biotech AI',
    '"raises" trading platform',
    '"secures funding" SaaS',
    '"pre-seed" startup software',
    # Region-dedicated queries (target regions: USA, UK, Canada,
    # Dubai/UAE, Australia, Europe)
    '"raises" UAE OR Dubai startup',
    '"raises" Australian startup software',
    '"raises" Canadian startup software',
    '"raises" European startup SaaS',
]

# Static RSS feeds (name -> url).
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/category/venture/feed/",
    "Finsmes": "https://www.finsmes.com/feed",
    "EU-Startups": "https://www.eu-startups.com/feed/",
    "BetaKit": "https://betakit.com/feed/",
}

# ---------------------------------------------------------------------------
# Stage 3 — ICP definition (fed verbatim into the Claude filter prompt)
# ---------------------------------------------------------------------------
NICHES = [
    "SaaS",
    "AI",
    "Tech/Software",
    "Fintech",
    "Trading platform (actual trading platforms / trading infrastructure)",
    "Biotech (AI-software side only — not wet-lab pharma)",
]

EXCLUSIONS = [
    "Gambling or betting of any kind",
    "Interest-based lending products (BNPL / consumer credit whose core product is interest)",
    "Alcohol or cannabis",
    "Adult content",
    "Israeli companies (consistent with the existing lead tracker rule)",
]

# ---------------------------------------------------------------------------
# Batch sizes / search budgets
# ---------------------------------------------------------------------------
FILTER_BATCH_SIZE = 15        # raw companies per Claude ICP-filter call
FILTER_MAX_SEARCHES = 20      # web-search budget per filter call
ENRICH_MAX_SEARCHES = 8       # web-search budget per enrichment call

# ---------------------------------------------------------------------------
# Local state
# ---------------------------------------------------------------------------
SEEN_DB = "seen.db"
LOG_DIR = "logs"
