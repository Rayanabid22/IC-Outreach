"""Stage 5 — Google Sheets output via a service account (gspread)."""

import json
import os

import gspread

import config
from .models import LEADS_HEADERS, PROCESSED_HEADERS, REJECTED_HEADERS


def _service_account():
    """credentials.json on disk, or the GOOGLE_CREDENTIALS_JSON env var."""
    if os.path.exists(config.CREDENTIALS_FILE):
        return gspread.service_account(filename=config.CREDENTIALS_FILE)
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if raw:
        return gspread.service_account_from_dict(json.loads(raw))
    raise SystemExit(
        "No Google credentials found: place the service-account key at "
        f"{config.CREDENTIALS_FILE} or set GOOGLE_CREDENTIALS_JSON to its "
        "full JSON contents (see README)."
    )


class SheetWriter:
    def __init__(self):
        if not config.SHEET_ID:
            raise SystemExit(
                "SHEET_ID is not set. Export SHEET_ID=<your sheet id> or set it "
                "in config.py (see README for setup)."
            )
        gc = _service_account()
        self.sheet = gc.open_by_key(config.SHEET_ID)
        self.leads = self._ensure_tab(config.LEADS_TAB, LEADS_HEADERS)
        self.processed = self._ensure_tab(config.PROCESSED_TAB, PROCESSED_HEADERS)
        self.rejected = self._ensure_tab(config.REJECTED_TAB, REJECTED_HEADERS)

    def _ensure_tab(self, title: str, headers: list[str]):
        try:
            ws = self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=title, rows=1000, cols=len(headers) + 2)
        first_row = ws.row_values(1)
        if not first_row:
            ws.append_row(headers, value_input_option="RAW")
        return ws

    def load_processed_keys(self) -> set[str]:
        """Keys already recorded in the Processed tab (column A)."""
        values = self.processed.col_values(1)
        return set(values[1:])  # skip header

    def append_leads(self, rows: list[list]):
        if rows:
            self.leads.append_rows(rows, value_input_option="RAW")

    def append_processed(self, rows: list[list]):
        if rows:
            self.processed.append_rows(rows, value_input_option="RAW")

    def append_rejected(self, rows: list[list]):
        if rows:
            self.rejected.append_rows(rows, value_input_option="RAW")
