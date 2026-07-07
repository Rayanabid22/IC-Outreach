"""Stage 2 — dedup across runs.

Primary store is a local SQLite database (seen.db). On each run we also
sync any keys found in the sheet's Processed tab, so the dedup survives
moving between machines.
"""

import re
import sqlite3
from datetime import date

# Legal-entity suffixes stripped when normalizing company names.
_LEGAL_SUFFIXES = (
    r"\b(incorporated|inc|llc|l\.l\.c|ltd|limited|corp|corporation|co|"
    r"plc|gmbh|s\.a|sa|bv|b\.v|ab|as|oy|pte|pty|lp|l\.p|llp|holdings|"
    r"technologies|technology|labs|group)\b\.?"
)


def normalize_name(name: str) -> str:
    """Normalize a company name into a dedup key."""
    key = (name or "").lower().strip()
    key = re.sub(r"[,\.]", " ", key)
    # Strip trailing legal suffixes repeatedly ("Acme Labs Inc" -> "acme").
    prev = None
    while prev != key:
        prev = key
        key = re.sub(_LEGAL_SUFFIXES + r"\s*$", "", key).strip()
    key = re.sub(r"[^a-z0-9]+", "", key)
    return key


class SeenStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS seen (
                key TEXT PRIMARY KEY,
                company TEXT,
                domain TEXT,
                first_seen TEXT,
                outcome TEXT
            )"""
        )
        self.conn.commit()

    def is_seen(self, key: str) -> bool:
        if not key:
            return True  # unparseable names are never processed
        row = self.conn.execute(
            "SELECT 1 FROM seen WHERE key = ?", (key,)
        ).fetchone()
        return row is not None

    def mark(self, key: str, company: str, domain: str, outcome: str):
        if not key:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO seen (key, company, domain, first_seen, outcome)"
            " VALUES (?, ?, ?, ?, ?)",
            (key, company, domain, date.today().isoformat(), outcome),
        )
        self.conn.commit()

    def import_keys(self, keys):
        """Merge keys from the sheet's Processed tab (cross-machine sync)."""
        for key in keys:
            if key:
                self.conn.execute(
                    "INSERT OR IGNORE INTO seen (key, company, domain, first_seen, outcome)"
                    " VALUES (?, '', '', '', 'from-sheet')",
                    (key,),
                )
        self.conn.commit()

    def close(self):
        self.conn.close()
