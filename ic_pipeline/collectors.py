"""Stage 1 — collect raw funding-event candidates from free public sources.

Sources:
  1. SEC EDGAR Form D filings (full-text search API + per-filing XML detail)
  2. Google News RSS (queries from config.NEWS_QUERIES)
  3. TechCrunch venture feed, Finsmes, EU-Startups, BetaKit (config.RSS_FEEDS)
"""

import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests

import config
from .models import RawRecord

_session = requests.Session()


def _polite_get(url: str, headers: dict | None = None, **kwargs) -> requests.Response | None:
    """GET with rate limiting and exponential backoff on 429/5xx."""
    delay = config.REQUEST_DELAY_SECONDS
    for attempt in range(4):
        time.sleep(delay if attempt == 0 else min(2 ** attempt * 2, 30))
        try:
            resp = _session.get(url, headers=headers, timeout=30, **kwargs)
        except requests.RequestException as exc:
            print(f"    [collect] request error {url}: {exc}")
            continue
        if resp.status_code == 200:
            return resp
        if resp.status_code in (429, 500, 502, 503):
            continue
        print(f"    [collect] HTTP {resp.status_code} for {url}")
        return None
    return None


# ---------------------------------------------------------------------------
# 1. SEC EDGAR Form D
# ---------------------------------------------------------------------------

_EDGAR_HEADERS = {"User-Agent": config.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
# Names that are almost certainly pooled investment funds, not startups.
_FUND_NAME_RE = re.compile(
    r"\b(fund|feeder|offshore|spv|series [ivx0-9]+ (?:lp|llc)|capital partners)\b", re.I
)


def collect_edgar(window_days: int) -> list[RawRecord]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=window_days)
    records: list[RawRecord] = []
    seen_ids: set[str] = set()

    # Full-text search index for Form D within the date range, paginated.
    for page_from in range(0, 400, 10):
        url = (
            "https://efts.sec.gov/LATEST/search-index"
            f"?q=%22Form%20D%22&forms=D&dateRange=custom"
            f"&startdt={start.isoformat()}&enddt={end.isoformat()}&from={page_from}"
        )
        resp = _polite_get(url, headers=_EDGAR_HEADERS)
        if resp is None:
            break
        try:
            hits = resp.json().get("hits", {}).get("hits", [])
        except ValueError:
            break
        if not hits:
            break
        for hit in hits:
            source = hit.get("_source", {})
            hit_id = hit.get("_id", "")
            if not hit_id or hit_id in seen_ids:
                continue
            seen_ids.add(hit_id)
            names = source.get("display_names") or []
            if not names:
                continue
            match = re.match(r"^(.*?)\s*\(CIK\s*(\d+)\)", names[0])
            entity = match.group(1).strip() if match else names[0].strip()
            cik = match.group(2) if match else ""
            if _FUND_NAME_RE.search(entity):
                continue
            records.append(
                RawRecord(
                    company_name_raw=entity,
                    source="SEC EDGAR Form D",
                    source_url=(
                        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                        f"&CIK={cik}&type=D" if cik else "https://efts.sec.gov"
                    ),
                    announced_date=source.get("file_date", ""),
                    headline_text=f"Form D filing by {entity}",
                )
            )
            # stash detail info for the enrichment fetch below
            records[-1]._edgar = (cik, hit_id)  # type: ignore[attr-defined]

    _fetch_edgar_details(records)
    print(f"  [collect] EDGAR Form D: {len(records)} candidates")
    return records


def _fetch_edgar_details(records: list[RawRecord]):
    """Best-effort fetch of each filing's XML for amount/state/industry.

    Drops obvious pooled-investment-fund filings in place.
    """
    fetched = 0
    keep: list[RawRecord] = []
    for rec in records:
        cik, hit_id = getattr(rec, "_edgar", ("", ""))
        if not cik or ":" not in hit_id or fetched >= config.EDGAR_MAX_DETAIL_FETCH:
            keep.append(rec)
            continue
        accession, filename = hit_id.split(":", 1)
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{filename}"
        )
        resp = _polite_get(url, headers=_EDGAR_HEADERS)
        fetched += 1
        if resp is None:
            keep.append(rec)
            continue
        xml = resp.text
        industry = _xml_tag(xml, "industryGroupType")
        if industry and "pooled investment" in industry.lower():
            continue  # a fund vehicle, not a startup
        amount = _xml_tag(xml, "totalOfferingAmount")
        if amount and amount.replace(".", "").isdigit():
            rec.amount_if_stated = f"${float(amount):,.0f}"
        state = _xml_tag(xml, "stateOrCountryDescription")
        if state:
            rec.headline_text += f" ({state})"
        keep.append(rec)
    records[:] = keep


def _xml_tag(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}>([^<]+)</{tag}>", xml)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# 2 + 3. RSS feeds (Google News + static funding feeds)
# ---------------------------------------------------------------------------

_FUNDING_KEYWORDS = re.compile(
    r"\b(raises|raised|secures|secured|lands|closes|closed|nabs|bags|banks|"
    r"scores|funding|series [a-e]\b|seed round|pre-seed|seed funding|"
    r"million|billion|\$\d)", re.I,
)

_COMPANY_RE = re.compile(
    r"^(?P<name>[^,:;|]{2,70}?)\s+(?:has\s+|have\s+|just\s+)?"
    r"(?:raises|raised|secures|secured|lands|landed|closes|closed|nabs|"
    r"nabbed|bags|bagged|banks|banked|scores|scored|gets|got|receives|"
    r"received|picks up|pulls in|announces|snags|snagged|collects)\b",
    re.I,
)

_AMOUNT_RE = re.compile(
    r"([$€£]\s?\d+(?:[\.,]\d+)?\s*(?:million|billion|mn|bn|m|b|k)?)", re.I
)


def _parse_feed_entries(feed_name: str, url: str, cutoff: datetime) -> list[RawRecord]:
    records = []
    time.sleep(config.REQUEST_DELAY_SECONDS)
    try:
        parsed = feedparser.parse(url, agent="ImpactCreatives-pipeline/1.0")
    except Exception as exc:
        print(f"    [collect] feed error {feed_name}: {exc}")
        return records

    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue
            date_str = pub_dt.date().isoformat()
        else:
            date_str = ""

        title = (entry.get("title") or "").strip()
        # Google News appends " - Publisher" to titles.
        title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
        if not title or not _FUNDING_KEYWORDS.search(title):
            continue

        match = _COMPANY_RE.match(title)
        if not match:
            continue
        name = match.group("name").strip().strip("'\"“”‘’")
        # Drop generic non-company leads ("This startup raises ...").
        if re.match(r"^(the|this|a|an|these|why|how|what)\b", name, re.I):
            continue

        amount_match = _AMOUNT_RE.search(title)
        records.append(
            RawRecord(
                company_name_raw=name,
                source=feed_name,
                source_url=entry.get("link", ""),
                announced_date=date_str,
                amount_if_stated=amount_match.group(1) if amount_match else "",
                headline_text=title,
            )
        )
    return records


def collect_rss(window_days: int) -> list[RawRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    records: list[RawRecord] = []

    for query in config.NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + f"+when:{window_days}d&hl=en-US&gl=US&ceid=US:en"
        )
        found = _parse_feed_entries(f"Google News ({query})", url, cutoff)
        records.extend(found)

    for name, url in config.RSS_FEEDS.items():
        found = _parse_feed_entries(name, url, cutoff)
        records.extend(found)

    print(f"  [collect] RSS feeds: {len(records)} candidates")
    return records


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def collect(window_days: int) -> list[RawRecord]:
    print(f"[stage 1] Collecting candidates from the last {window_days} days...")
    records = collect_rss(window_days) + collect_edgar(window_days)

    # In-batch dedup by normalized name, newest first.
    records.sort(key=lambda r: r.announced_date or "", reverse=True)
    unique: dict[str, RawRecord] = {}
    for rec in records:
        key = rec.dedup_key
        if key and key not in unique:
            unique[key] = rec
    result = list(unique.values())
    print(f"[stage 1] {len(records)} raw -> {len(result)} unique candidates")
    return result
