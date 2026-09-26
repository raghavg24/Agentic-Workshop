"""Load seed/tickets.csv and seed/customers.csv into app.db.

Usage: uv run python load_seed.py
Running this command twice gives the same database.
"""

import csv
import sqlite3
from pathlib import Path

_BASE = Path(__file__).parent
DB_PATH = _BASE / "app.db"
_SEED_DIR = _BASE / "seed"


def _load_table(conn: sqlite3.Connection, table: str, csv_path: Path) -> None:
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    cols = list(rows[0].keys())
    col_defs = ", ".join(f"{c} TEXT" for c in cols)
    placeholders = ", ".join("?" * len(cols))
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})")
    conn.execute(f"DELETE FROM {table}")
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [[row[c] for c in cols] for row in rows],
    )


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        _load_table(conn, "tickets", _SEED_DIR / "tickets.csv")
        _load_table(conn, "customers", _SEED_DIR / "customers.csv")


if __name__ == "__main__":
    main()
