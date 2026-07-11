---
name: daily-leads
description: Daily lite lead run — find 10-20 freshly funded ICP-fit companies (pre-seed through Series B, across US/UK/Canada/UAE/Australia/Europe) using Claude's built-in web search (no API key), verify X or Instagram activity, dedup against the committed registry, and commit results to data/leads/. Use when asked to run the daily leads, find today's leads, or on a scheduled daily-leads firing.
---

# Daily Leads Run (lite mode — no API key)

You are the research engine. Do NOT call the Anthropic API and do NOT expect
`ANTHROPIC_API_KEY` — you do the filtering and enrichment yourself with the
WebSearch tool. Direct HTTP to news sites is blocked in this sandbox; rely on
WebSearch only.

**MINIMUM: 10 qualified leads. Target: 10–20.** Ten is the floor the
business needs — do not stop below it while there is still searching left
to do. Escalate effort until you reach 10:

1. Start with funding announced in the last 1–3 days.
2. Short of 10? Widen to 7 days, then 14, then 30.
3. Still short? Run more collection searches (niche-specific queries,
   site: queries against funding-news sites) and work through candidates
   you haven't researched yet — anything not in `data/processed.csv` is
   fair game, including names earlier runs left unprocessed.
4. Only stop below 10 when you have genuinely exhausted the candidate
   pool (roughly 60+ searches with no fresh names left). Never pad with
   unqualified companies to hit the number — if you end below 10, say so
   plainly in the summary and explain what ran out.

## Step 1 — Find candidates (WebSearch)

Run 8–12 searches (more if below minimum) for companies that announced
funding in the window above. Good query shapes:

- `startup raises seed funding <today's date / this week>`
- `"Series A" OR "Series B" AI startup announcement <month year>`
- `fintech startup raises seed OR Series A <month year>`
- `SaaS startup pre-seed OR seed funding announced this week`
- `site:finsmes.com raises <month year>` and similar for techcrunch.com,
  eu-startups.com, betakit.com, thesaasnews.com
- Region-dedicated queries — at least one each for: UK, Canada
  (site:betakit.com works well), Dubai/UAE (`UAE startup raises`,
  site:wamda.com, site:menabytes.com), Australia
  (`Australian startup raises`, site:startupdaily.net), and Europe
  (site:eu-startups.com, site:tech.eu)

Collect ~30–40 candidate company names with their funding stage/amount,
announcement date, and source URL.

## Step 2 — Dedup

```bash
python pipeline.py check "Name One" "Name Two" ...
```

Drop everything marked `SEEN`. Only research `NEW` names.

## Step 3 — ICP filter

**Stage gate (apply FIRST): Pre-seed, Seed, Series A, or Series B ONLY.**
Reject Series C+, growth/late-stage, mega-rounds, and IPO-track companies
with reason "stage out of scope". Rationale: early-stage companies are
the ones that actually reply to outreach. When a search result is a
roundup, confirm the stage from the original announcement.

In-ICP (keep): SaaS, AI, Tech/Software, Fintech, Trading platforms/
infrastructure, Biotech (AI-software side only — not wet-lab pharma).

HARD exclusions (drop, with reason): gambling/betting; interest-based lending
(BNPL/consumer credit whose core product is interest); alcohol/cannabis;
adult content; Israeli companies. **Target regions — search ALL of these
actively (dedicate collection queries to each): USA, UK, Canada, Dubai/UAE,
Australia, and Europe.** Record the region; do NOT exclude other regions —
just record them.

Resolve each keeper's real brand name and website (search if needed).

## Step 4 — Verify socials (the qualification bar)

For each ICP-fit company, look for BOTH its X (Twitter) handle AND its
Instagram account — check them in the same searches
(`site:x.com <company>`, `site:instagram.com <company>`,
`"<company>" twitter instagram official account`). Check activity within
the **last 30 days** (post dates in results; a same-week funding
announcement from an existing, non-dormant account counts as inferred
activity — flag inferred vs confirmed).

- An active X OR an active Instagram qualifies — they are co-equal
  signals now. Record both handles whenever both exist.
- **Founder X accounts: always search for them** (funding articles quote
  founders; check article bylines/quotes, then `site:x.com <founder name>`).
  Founder X is the preferred outreach channel. BUT a lead with only the
  company's X (or IG) and no findable founder handle still goes in the
  final list — do not drop or hold it back for that.
- A LinkedIn URL alone does NOT qualify. Record the LinkedIn company URL but
  never attempt to check LinkedIn activity.
- **X DM status (best-effort, record as `x_dms`: "open" | "closed" |
  "unknown"):** search snippets can't render the Message button, so only
  mark "open" or "closed" with clear evidence (bio says "DMs open", the
  account invites DMs, press/contact pages point to X DMs). Default to
  "unknown" — do NOT reject a lead for unknown DM status.
- **Contactability (best-effort, never blocking):** aim for two-plus
  contact paths per lead (founder X > company X > Instagram > email).
  If a lead has only the company account after 1-2 extra searches for
  the founder/email, include it anyway and note it in the summary.
- Bonus (never blocking, ~2 searches max each): founder name/title/X/LinkedIn
  (funding articles usually quote founders) and a contact/hello email.

## Step 5 — Record

Write ALL researched companies (qualified and rejected) to a JSON array at
`/tmp/leads_today.json`, then:

```bash
python pipeline.py append --in /tmp/leads_today.json
```

Object schema (leave unknown strings empty, `instagram_active` null if
unknown):

```json
{
  "company": "Acme AI", "website": "https://acme.ai",
  "category": "AI", "region": "US", "funding": "Series A, $12M",
  "announced_date": "2026-07-08", "source": "TechCrunch",
  "source_url": "https://...", "fit_reasoning": "one line",
  "x_handle": "acmeai", "x_active": true, "x_dms": "unknown",
  "linkedin_url": "", "instagram": "", "instagram_active": null,
  "discord": "", "email": "",
  "founder_name": "", "founder_title": "", "founder_x": "", "founder_linkedin": "",
  "qualified": true, "reject_reason": ""
}
```

The command writes `data/leads/<date>.csv`, updates `data/processed.csv`
(the dedup registry), and appends to the Google Sheet if credentials are
configured (it skips the sheet silently if not).

## Step 6 — Commit and report

```bash
git add data/ && git commit -m "Daily leads <date>: N qualified" && git push -u origin claude/ic-funded-leads-pipeline-ejhq0y
```

If the working branch differs from `claude/ic-funded-leads-pipeline-ejhq0y`,
push to the current branch instead. Finish with a short summary: qualified
count vs the 10 minimum, X-active and Instagram-active counts, DM status
breakdown (open/closed/unknown), founder-X-found count (and which leads
are company-account-only), region breakdown, rejects with reasons, and
the CSV path.

## Lessons from prior runs (keep applying these)

- **Roundup articles re-report old news.** Always confirm the ORIGINAL
  announcement date (press release / primary coverage) before treating a
  company as fresh — a "July 9 roundup" often contains June rounds.
- **X verification:** `site:x.com <company or handle>` is the best probe.
  The gold standard is the company's own dated funding tweet. Tweet IDs
  encode time (bigger = newer) — compare against a known-recent ID from the
  same week to judge recency. An account whose newest indexed posts are
  months old (e.g. a Series C the company never tweeted) is NOT active.
- **Record only what you concluded.** If you researched a company and
  couldn't confirm an active social → record as rejected (auditable).
  If you never researched a candidate → do NOT record it; leave it
  unmarked so a future run picks it up fresh.
- **Prioritize consumer and dev-tool companies** — they verify on X far
  more easily than enterprise B2B, so you get more qualified leads per
  search. B2B-heavy days will yield fewer leads; that's fine, never pad.
