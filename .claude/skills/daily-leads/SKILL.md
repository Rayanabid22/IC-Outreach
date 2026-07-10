---
name: daily-leads
description: Daily lite lead run — find 10-20 freshly funded ICP-fit companies using Claude's built-in web search (no API key), verify X activity, dedup against the committed registry, and commit results to data/leads/. Use when asked to run the daily leads, find today's leads, or on a scheduled daily-leads firing.
---

# Daily Leads Run (lite mode — no API key)

You are the research engine. Do NOT call the Anthropic API and do NOT expect
`ANTHROPIC_API_KEY` — you do the filtering and enrichment yourself with the
WebSearch tool. Direct HTTP to news sites is blocked in this sandbox; rely on
WebSearch only.

**Target: 10–20 qualified leads.** Never pad — a short honest list beats a
padded one. Stop early once you hit 20.

## Step 1 — Find candidates (WebSearch)

Run 8–12 searches for companies that announced funding in the **last 1–3
days** (widen to 7 days only if you can't find enough). Good query shapes:

- `startup raises seed funding <today's date / this week>`
- `"Series A" AI startup announcement <month year>`
- `fintech startup raises seed <month year>`
- `SaaS startup funding announced this week`
- `site:finsmes.com raises <month year>` and similar for techcrunch.com,
  eu-startups.com, betakit.com, thesaasnews.com
- One or two UK/EU/Canada-flavored queries

Collect ~30–40 candidate company names with their funding stage/amount,
announcement date, and source URL.

## Step 2 — Dedup

```bash
python pipeline.py check "Name One" "Name Two" ...
```

Drop everything marked `SEEN`. Only research `NEW` names.

## Step 3 — ICP filter

In-ICP (keep): SaaS, AI, Tech/Software, Fintech, Trading platforms/
infrastructure, Biotech (AI-software side only — not wet-lab pharma).

HARD exclusions (drop, with reason): gambling/betting; interest-based lending
(BNPL/consumer credit whose core product is interest); alcohol/cannabis;
adult content; Israeli companies. Region: prefer US/UK/Canada but do NOT
exclude others — just record the region.

Resolve each keeper's real brand name and website (search if needed).

## Step 4 — Verify socials (the qualification bar)

For each ICP-fit company, search for its X (Twitter) handle and check the
account has posted within the **last 30 days** (search `site:x.com <handle>`
or `"<company>" twitter recent posts`; look at post dates in results).

- Active X alone qualifies. If X can't be confirmed active, Instagram
  confirmed-active also qualifies (best effort).
- A LinkedIn URL alone does NOT qualify. Record the LinkedIn company URL but
  never attempt to check LinkedIn activity.
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
  "category": "AI", "region": "US", "funding": "Seed, $5M",
  "announced_date": "2026-07-08", "source": "TechCrunch",
  "source_url": "https://...", "fit_reasoning": "one line",
  "x_handle": "acmeai", "x_active": true,
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
count, X-active count, founder-found count, rejects with reasons, and the
CSV path.

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
