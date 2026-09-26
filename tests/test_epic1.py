"""Epic 1: schema validation and seed loader tests."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from schema import TriageDecision


class TestTriageDecision:
    def test_valid_decision(self):
        d = TriageDecision(category="billing", priority="P2", route="billing-team", rationale="Double charge.")
        assert d.category == "billing"
        assert d.priority == "P2"
        assert d.route == "billing-team"

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            TriageDecision(category="unknown", priority="P1", route="bug-team", rationale="x")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            TriageDecision(category="bug", priority="P5", route="bug-team", rationale="x")

    def test_invalid_route_rejected(self):
        with pytest.raises(ValidationError):
            TriageDecision(category="bug", priority="P1", route="nowhere", rationale="x")

    def test_missing_rationale_rejected(self):
        with pytest.raises(ValidationError):
            TriageDecision(category="bug", priority="P1", route="bug-team")

    @pytest.mark.parametrize("cat", ["billing", "bug", "access", "performance", "how-to"])
    def test_all_categories_accepted(self, cat):
        d = TriageDecision(category=cat, priority="P3", route=f"{cat}-team", rationale="ok")
        assert d.category == cat


class TestLoadSeed:
    def test_loads_tickets_and_customers(self, tmp_path, monkeypatch):
        import load_seed

        db = tmp_path / "test.db"
        monkeypatch.setattr(load_seed, "DB_PATH", db)
        load_seed.main()

        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets")]
            customers = [dict(r) for r in conn.execute("SELECT * FROM customers")]

        assert len(tickets) > 0
        assert "ticket_id" in tickets[0]
        assert "customer_id" in tickets[0]
        assert len(customers) > 0
        assert "customer_id" in customers[0]
        assert "plan" in customers[0]

    def test_idempotent(self, tmp_path, monkeypatch):
        import load_seed

        db = tmp_path / "test.db"
        monkeypatch.setattr(load_seed, "DB_PATH", db)
        load_seed.main()
        load_seed.main()

        with sqlite3.connect(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

        seed_count = sum(1 for _ in open(Path(__file__).parent.parent / "seed" / "tickets.csv")) - 1
        assert count == seed_count

    def test_ticket_t1042_present(self, tmp_path, monkeypatch):
        import load_seed

        db = tmp_path / "test.db"
        monkeypatch.setattr(load_seed, "DB_PATH", db)
        load_seed.main()

        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT customer_id FROM tickets WHERE ticket_id = 'T-1042'").fetchone()

        assert row is not None
        assert row[0] == "C-77"
