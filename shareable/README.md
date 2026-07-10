# Shareable Daily-Leads Setup

Give a friend (or another Claude account) the same daily lead machine.
The ICP is a placeholder in every file — customize it per business.

## What's in here

- **`DAILY-LEADS-PROMPT.md`** — a fully self-contained prompt. Works in
  plain claude.ai chat, Claude Code terminal, or Claude Code web. No code,
  no repo, no API key — just Claude with web search. Fill in the CONFIG
  block (ICP placeholder) and paste it.

## Three ways to run it

### 1. Plain claude.ai chat (simplest — any paid plan)
Fill in the CONFIG block of `DAILY-LEADS-PROMPT.md`, paste it into a new
chat. Leads come back as a table. For repeat runs, keep using the same
chat/Project so Claude remembers what it already delivered, or paste your
running list of past leads so nothing repeats.

### 2. Claude Code (terminal or web) — one-off runs
Same prompt, same result, but Claude Code can also save the results to CSV
files and keep a dedup registry if you point it at a folder/repo.

### 3. Claude Code web — fully automatic daily runs (this repo's setup)
This is what runs for Impact Creatives:
1. Fork/clone this repo (or copy `pipeline.py`, `config.py`, `ic_pipeline/`,
   and `.claude/skills/daily-leads/` into your own repo).
2. Edit the ICP: `config.py` (`NICHES`, `EXCLUSIONS`, `NEWS_QUERIES`) and
   `.claude/skills/daily-leads/SKILL.md` (filter + stage-gate sections).
3. Open the repo in Claude Code on the web and say:
   *"Create a daily routine at [time] that runs the /daily-leads skill in a
   fresh session and sends me a push notification with the summary."*
4. Leads land in `data/leads/<date>.csv` every morning, deduped against
   `data/processed.csv` automatically.

## Scaling up later (optional, costs money)

- **Claude Max** — same setup, bigger daily usage allowance = more
  leads/searches per run.
- **API mode** — add an `ANTHROPIC_API_KEY` and run `python pipeline.py run`
  for high-volume batches (150-200 leads); see the main repo README.
- **Google Sheet output** — add `SHEET_ID` + `GOOGLE_CREDENTIALS_JSON`
  (free) and every run also appends to a Google Sheet.

## Honest limitations

- **X DM status is best-effort.** Search engines can't see the Message
  button on an X profile, so the `X DMs` column says "open"/"closed" only
  when there's clear evidence and "unknown" otherwise. That's why every
  lead requires two contact paths (company X / founder X / email) — spot-
  check DMs manually for the day's batch before writing outreach.
- **X activity verification is strict.** B2B companies with quiet X
  accounts get rejected even if they're great fits — check the rejected
  list occasionally; some are worth manual review.
