"""Stage 4 — social enrichment + activity check for ICP-fit companies."""

import config
from .claude_client import call_claude, parse_json_block
from .models import Lead, RunStats

_PROMPT_TEMPLATE = """Find the social profiles and contact info for this recently \
funded company. Use web search to verify.

Company: {company}
Website: {website}
Category: {category}
Funding context: {funding} — {headline}

Rules:
- x_active: true ONLY if the company's X (Twitter) account has posted within the \
last 30 days — verify via web search of the handle's recent posts. This is the \
priority signal; check it carefully.
- instagram_active: best-effort; null if you cannot tell.
- linkedin_url: company page URL only — do NOT attempt to check LinkedIn activity.
- Founder fields are a bonus, never required. Check the funding announcement \
(founders are usually quoted), the company's /about page, X bios, or Crunchbase. \
If not found after ~2 search attempts, leave blank and move on.
- email: a contact/hello email from the site or press releases; blank if not found.
- Leave any field you cannot find as "" (or null for instagram_active).
- x_handle should be the bare handle without the @ (e.g. "acmehq").

Respond with ONLY this JSON object, no prose:
{{
  "x_handle": "", "x_active": false,
  "linkedin_url": "",
  "instagram": "", "instagram_active": null,
  "discord": "",
  "email": "",
  "founder_name": "", "founder_title": "",
  "founder_x": "", "founder_linkedin": ""
}}"""


def enrich(lead: Lead, stats: RunStats) -> Lead:
    """Fill social/contact fields on the lead in place and return it."""
    prompt = _PROMPT_TEMPLATE.format(
        company=lead.company,
        website=lead.website or "unknown — find it",
        category=lead.category,
        funding=lead.funding or "recently funded",
        headline=lead.raw.headline_text,
    )
    text = call_claude(prompt, stats, config.ENRICH_MAX_SEARCHES, "enrich")
    data = parse_json_block(text)
    if not isinstance(data, dict):
        print(f"    [enrich] could not parse JSON for {lead.company}")
        return lead

    lead.x_handle = str(data.get("x_handle") or "").lstrip("@")
    lead.x_active = bool(data.get("x_active"))
    lead.linkedin_url = str(data.get("linkedin_url") or "")
    lead.instagram = str(data.get("instagram") or "")
    ig_active = data.get("instagram_active")
    lead.instagram_active = bool(ig_active) if ig_active is not None else None
    lead.discord = str(data.get("discord") or "")
    lead.email = str(data.get("email") or "")
    lead.founder_name = str(data.get("founder_name") or "")
    lead.founder_title = str(data.get("founder_title") or "")
    lead.founder_x = str(data.get("founder_x") or "").lstrip("@")
    lead.founder_linkedin = str(data.get("founder_linkedin") or "")
    return lead


def is_qualified(lead: Lead) -> bool:
    """Qualification bar: at least one confirmed-active social.

    X is the priority signal — an active X alone qualifies. Instagram
    activity is the best-effort backup. A LinkedIn URL alone does NOT
    qualify (no activity check is possible).
    """
    return lead.x_active or bool(lead.instagram_active)
