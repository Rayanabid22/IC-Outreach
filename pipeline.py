#!/usr/bin/env python3
"""IC Funded Leads Pipeline.

Usage:
    python pipeline.py run [--window 14] [--target 200] [--dry-run]

Finds companies funded in the last 7 days (auto-widening to 30 if needed),
filters them to Impact Creatives' ICP with Claude + web search, verifies at
least one social is active (X priority), and appends qualified leads to the
Google Sheet.
"""

import argparse
import sys
from datetime import date, datetime
from urllib.parse import urlparse

import config
from ic_pipeline.collectors import collect
from ic_pipeline.dedup import SeenStore, normalize_name
from ic_pipeline.enrich import enrich, is_qualified
from ic_pipeline.icp_filter import filter_batch
from ic_pipeline.models import Lead, RawRecord, RunStats


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _domain(url: str) -> str:
    try:
        return (urlparse(url if "//" in url else f"https://{url}").netloc or "").lower()
    except ValueError:
        return ""


def run(window: int | None, target: int, dry_run: bool):
    if not config.ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY is not set — export it and re-run.")

    stats = RunStats()
    today = date.today().isoformat()

    # Sheet connection (skipped entirely in dry-run mode).
    writer = None
    if not dry_run:
        from ic_pipeline.sheets import SheetWriter

        writer = SheetWriter()

    # Dedup store: local SQLite, merged with the sheet's Processed tab.
    seen = SeenStore(config.SEEN_DB)
    if writer is not None:
        try:
            seen.import_keys(writer.load_processed_keys())
        except Exception as exc:
            print(f"[dedup] warning: could not read Processed tab: {exc}")

    # Fixed window if --window given; otherwise the auto-widening schedule.
    if window:
        windows = [min(window, config.MAX_WINDOW_DAYS)]
    else:
        windows = [w for w in config.WINDOW_STEPS if w <= config.MAX_WINDOW_DAYS]

    qualified: list[Lead] = []
    rejected_rows: list[list] = []
    processed_rows: list[list] = []
    processed_this_run: set[str] = set()

    for w in windows:
        stats.window_used = w
        stats.windows_tried.append(w)

        raw = collect(w)
        stats.raw_collected += len(raw)

        fresh = [
            r for r in raw
            if r.dedup_key not in processed_this_run and not seen.is_seen(r.dedup_key)
        ]
        stats.after_dedup += len(fresh)
        print(f"[stage 2] {len(fresh)} candidates remain after dedup "
              f"(window {w}d)")

        for batch_num, batch in enumerate(_chunks(fresh, config.FILTER_BATCH_SIZE), 1):
            print(f"[stage 3] ICP filter batch {batch_num} "
                  f"({len(batch)} companies)...")
            results = filter_batch(batch, stats)

            for rec, res in zip(batch, results):
                key = rec.dedup_key
                processed_this_run.add(key)
                company = str(res.get("resolved_brand_name") or rec.company_name_raw)
                # Also block the resolved brand's key, so e.g. "Fintech
                # startup Ramp" and "Ramp" can't both get processed.
                resolved_key = normalize_name(company)
                if resolved_key and resolved_key != key:
                    processed_this_run.add(resolved_key)
                website = str(res.get("website") or "")
                reasoning = str(res.get("reasoning_one_line") or "")

                def mark(outcome, _k=key, _rk=resolved_key, _c=company, _d=_domain(website)):
                    seen.mark(_k, _c, _d, outcome)
                    if _rk and _rk != _k:
                        seen.mark(_rk, _c, _d, outcome)
                    processed_rows.append([_k, _c, _d, today, outcome])

                if not res.get("is_icp_fit"):
                    stats.rejected_not_icp += 1
                    mark("not-icp")
                    rejected_rows.append(
                        [today, company, rec.source, f"Not ICP: {reasoning}"]
                    )
                    continue

                stats.icp_fit += 1
                lead = Lead(
                    raw=rec,
                    company=company,
                    website=website,
                    category=str(res.get("category") or ""),
                    region=str(res.get("region") or ""),
                    funding=str(res.get("funding_stage_or_amount") or rec.amount_if_stated),
                    fit_reasoning=reasoning,
                )
                print(f"[stage 4] Enriching {lead.company}...")
                enrich(lead, stats)

                if is_qualified(lead):
                    qualified.append(lead)
                    stats.qualified += 1
                    if lead.founder_name:
                        stats.founders_found += 1
                    mark("qualified")
                    print(f"    -> QUALIFIED ({stats.qualified}/{target})"
                          + (f" X: @{lead.x_handle}" if lead.x_handle else ""))
                else:
                    stats.rejected_no_socials += 1
                    mark("no-active-socials")
                    rejected_rows.append(
                        [today, company, rec.source,
                         "ICP fit but no confirmed-active social found"]
                    )

                if stats.qualified >= target:
                    break
            if stats.qualified >= target:
                break

        if stats.qualified >= target:
            break
        if w != windows[-1]:
            print(f"[widen] Only {stats.qualified}/{target} qualified at "
                  f"{w}d — widening window...")

    # ---------------------------------------------------------------
    # Stage 5 — write
    # ---------------------------------------------------------------
    lead_rows = [lead.to_sheet_row(today) for lead in qualified]
    if dry_run:
        print("\n[dry-run] Rows that WOULD be appended to the Leads tab:")
        for row in lead_rows:
            print("  " + " | ".join(str(cell) for cell in row))
        print(f"\n[dry-run] {len(rejected_rows)} rows would go to Rejected, "
              f"{len(processed_rows)} to Processed.")
    else:
        print(f"[stage 5] Appending {len(lead_rows)} leads to the sheet...")
        writer.append_leads(lead_rows)
        writer.append_processed(processed_rows)
        writer.append_rejected(rejected_rows)

    seen.close()
    _print_summary(stats, target, len(lead_rows), dry_run)


def _print_summary(stats: RunStats, target: int, written: int, dry_run: bool):
    founder_rate = (
        f"{stats.founders_found / stats.qualified:.0%}" if stats.qualified else "n/a"
    )
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"  Window used:            {stats.window_used} days "
          f"(tried: {', '.join(str(w) + 'd' for w in stats.windows_tried)})")
    print(f"  Raw collected:          {stats.raw_collected}")
    print(f"  After dedup:            {stats.after_dedup}")
    print(f"  ICP-fit:                {stats.icp_fit}")
    print(f"  Socially active:        {stats.qualified} (target was {target})")
    print(f"  Rejected (not ICP):     {stats.rejected_not_icp}")
    print(f"  Rejected (no socials):  {stats.rejected_no_socials}")
    print(f"  Written to sheet:       {written}"
          + (" (dry run — nothing written)" if dry_run else ""))
    print(f"  Founder found rate:     {founder_rate}")
    print(f"  API calls:              {stats.api_calls} "
          f"({stats.input_tokens:,} in / {stats.output_tokens:,} out tokens, "
          f"{stats.web_searches} web searches)")
    print(f"  Est. API cost:          ${stats.cost_estimate():.2f}")
    if stats.qualified < target:
        print(f"\n  NOTE: target of {target} not met at "
              f"{config.MAX_WINDOW_DAYS} days — the run completed with the "
              f"real count above (no padding).")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run the full pipeline")
    run_parser.add_argument("--window", type=int, default=None,
                            help="force a fixed window in days (disables auto-widening)")
    run_parser.add_argument("--target", type=int, default=config.TARGET_LEADS,
                            help=f"qualified-lead target (default {config.TARGET_LEADS})")
    run_parser.add_argument("--dry-run", action="store_true",
                            help="print results instead of writing to the sheet")
    args = parser.parse_args()

    if args.command == "run":
        started = datetime.now()
        run(args.window, args.target, args.dry_run)
        print(f"Done in {(datetime.now() - started).total_seconds() / 60:.1f} min.")


if __name__ == "__main__":
    main()
