"""Stage 3 — ICP filter: one Claude call per batch of raw candidates."""

import json

import config
from .claude_client import call_claude, parse_json_block
from .dedup import normalize_name
from .models import RawRecord, RunStats

_PROMPT_TEMPLATE = """You are qualifying recently funded companies for Impact Creatives, \
a social-media growth agency. For EACH company below, use web search as needed to \
resolve the actual brand/product name and website, then judge ICP fit.

IN-ICP categories (is_icp_fit true only if the company clearly belongs to one):
{niches}

HARD EXCLUSIONS — mark is_icp_fit false with the reason if ANY apply:
{exclusions}

Notes:
- Names from SEC Form D filings are legal entities (e.g. "Acme Labs Inc.") — resolve \
to the real consumer-facing brand name and website. If you cannot confidently identify \
the company at all, mark is_icp_fit false with reasoning "could not resolve company".
- Region: classify as US | UK | Canada | Other. Do NOT exclude on region alone.
- funding_stage_or_amount: stage and/or amount if known (e.g. "Seed, $4M").

Companies to evaluate:
{companies}

Respond with ONLY a JSON array, one object per company, in the SAME ORDER as listed, \
using exactly this schema:
[
  {{
    "company": "<name as listed above>",
    "resolved_brand_name": "",
    "website": "",
    "is_icp_fit": true,
    "category": "SaaS | AI | Tech/Software | Fintech | Trading platform | Biotech (AI software)",
    "region": "US | UK | Canada | Other",
    "funding_stage_or_amount": "",
    "reasoning_one_line": ""
  }}
]
No prose before or after the JSON."""


def filter_batch(batch: list[RawRecord], stats: RunStats) -> list[dict]:
    """Return one result dict per input record (aligned by index).

    Records the model couldn't be matched to get a synthetic not-fit result
    so the caller can still mark them processed.
    """
    companies_text = "\n".join(
        f"{i + 1}. {rec.company_name_raw}"
        f" | source: {rec.source}"
        f" | announced: {rec.announced_date or 'unknown'}"
        + (f" | amount: {rec.amount_if_stated}" if rec.amount_if_stated else "")
        + (f" | headline: {rec.headline_text}" if rec.headline_text else "")
        for i, rec in enumerate(batch)
    )
    prompt = _PROMPT_TEMPLATE.format(
        niches="\n".join(f"- {n}" for n in config.NICHES),
        exclusions="\n".join(f"- {e}" for e in config.EXCLUSIONS),
        companies=companies_text,
    )

    text = call_claude(prompt, stats, config.FILTER_MAX_SEARCHES, "icp_filter")
    parsed = parse_json_block(text)
    if not isinstance(parsed, list):
        print("    [filter] could not parse JSON from model; skipping batch")
        parsed = []

    return _align(batch, parsed)


def _align(batch: list[RawRecord], parsed: list) -> list[dict]:
    """Align model output to input records, by order and then by name."""
    fallback = {
        "is_icp_fit": False,
        "reasoning_one_line": "no result returned by filter model",
        "resolved_brand_name": "",
        "website": "",
        "category": "",
        "region": "",
        "funding_stage_or_amount": "",
    }
    results: list[dict] = []
    by_name = {
        normalize_name(str(item.get("company", ""))): item
        for item in parsed
        if isinstance(item, dict)
    }
    for i, rec in enumerate(batch):
        item = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else None
        if item is None or normalize_name(str(item.get("company", ""))) != rec.dedup_key:
            item = by_name.get(rec.dedup_key, item)
        results.append(dict(fallback, **item) if isinstance(item, dict) else dict(fallback))
    return results
