"""Shared record types passed between pipeline stages."""

from dataclasses import dataclass, field


@dataclass
class RawRecord:
    """Stage 1 output: one funding-event candidate from a public source."""

    company_name_raw: str
    source: str
    source_url: str
    announced_date: str          # ISO date string, best effort
    amount_if_stated: str = ""
    headline_text: str = ""

    @property
    def dedup_key(self) -> str:
        from .dedup import normalize_name

        return normalize_name(self.company_name_raw)


@dataclass
class Lead:
    """A fully qualified lead ready to be appended to the sheet."""

    raw: RawRecord
    # Stage 3 (ICP filter) fields
    company: str = ""
    website: str = ""
    category: str = ""
    region: str = ""
    funding: str = ""
    fit_reasoning: str = ""
    # Stage 4 (enrichment) fields
    x_handle: str = ""
    x_active: bool = False
    linkedin_url: str = ""
    instagram: str = ""
    instagram_active: bool | None = None
    discord: str = ""
    email: str = ""
    founder_name: str = ""
    founder_title: str = ""
    founder_x: str = ""
    founder_linkedin: str = ""

    def to_sheet_row(self, date_added: str) -> list:
        return [
            date_added,
            self.company,
            self.website,
            self.category,
            self.region,
            self.funding,
            self.raw.announced_date,
            self.raw.source,
            self.x_handle,
            "TRUE" if self.x_active else "FALSE",
            self.linkedin_url,
            self.instagram,
            self.discord,
            self.email,
            (f"{self.founder_name} ({self.founder_title})".strip()
             if self.founder_title else self.founder_name),
            self.founder_x,
            self.founder_linkedin,
            self.fit_reasoning,
        ]


LEADS_HEADERS = [
    "Date Added", "Company", "Website", "Category", "Region",
    "Funding (stage/amount)", "Announced Date", "Source", "X Handle",
    "X Active", "LinkedIn", "Instagram", "Discord", "Email", "Founder",
    "Founder X", "Founder LinkedIn", "Fit Reasoning",
]

PROCESSED_HEADERS = ["Key", "Company", "Domain", "Date Processed", "Outcome"]

REJECTED_HEADERS = ["Date", "Company", "Source", "Reason"]


@dataclass
class RunStats:
    """Counters for the Stage 6 summary."""

    window_used: int = 0
    raw_collected: int = 0
    after_dedup: int = 0
    icp_fit: int = 0
    qualified: int = 0
    rejected_not_icp: int = 0
    rejected_no_socials: int = 0
    founders_found: int = 0
    # API accounting
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0
    windows_tried: list = field(default_factory=list)

    def cost_estimate(self) -> float:
        import config

        return (
            self.input_tokens / 1_000_000 * config.PRICE_INPUT_PER_MTOK
            + self.output_tokens / 1_000_000 * config.PRICE_OUTPUT_PER_MTOK
            + self.web_searches / 1000 * config.PRICE_PER_1000_SEARCHES
        )
