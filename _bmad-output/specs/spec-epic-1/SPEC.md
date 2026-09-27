---
id: SPEC-epic-1
companions: []
sources:
  - ../../planning-artifacts/prds/prd-mygitclone-2026-09-27/prd.md
  - ../../planning-artifacts/epics.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Epic 1: Data Foundation

## Why

The expense claim reviewer agent cannot run without a seeded database and working MCP tools. Finance's consistency problem is solved by the agent, but the agent is blind without access to claims, employee levels, city limits, and a place to record decisions. This epic establishes that foundation — the SQLite schema, the seed loader, and the 4 MCP tools — so every downstream epic has a stable, testable data layer to build on.

## Capabilities

- **CAP-1**
  - **intent:** Operator can run `load_seed.py` once to populate a local SQLite database from 4 CSVs (`claims`, `line_items`, `employees`, `limits`) and create the `expense_decisions` write target.
  - **success:** `load_seed.py` exits 0; all 5 tables exist; row counts match the source CSVs; re-run is idempotent (`INSERT OR REPLACE`).

- **CAP-2**
  - **intent:** Agent can call 4 MCP tools over stdio — `get_claim`, `get_employee`, `get_policy_limits`, `record_decision` — and receive correct data or a hard error on bad input.
  - **success:** Each tool returns the correct shape against the seeded DB; `get_policy_limits` raises `ValueError` when the level/city combination is absent; `record_decision` rejects any value outside `{approve, flag, reject}`; all 4 tools callable from `langchain-mcp-adapters` without error.

- **CAP-3**
  - **intent:** Eval harness can read `eval/labelled.csv` (30 labelled claims, 1 row per line item) as the ground-truth oracle for decision and clause accuracy.
  - **success:** `labelled.csv` is present, parseable, and covers all line items in `CL-2001`–`CL-2030`; the file is never written to at runtime.

## Constraints

- `seed/` CSVs and `eval/labelled.csv` are read-only — load_seed.py reads them; nothing writes them at runtime.
- `get_policy_limits` must raise on an empty query result — silent wrong decisions are not acceptable.
- DB path is derived from `__file__` in both `load_seed.py` and `mcp_server.py` so they resolve correctly from any working directory.
- MCP server transport is stdio (`FastMCP`); no HTTP, no separate process lifecycle to manage.

## Non-goals

- Populating `expense_decisions` with any pre-existing decisions — the table starts empty.
- Any migration tooling — seed is a one-time load; schema changes require a manual DB delete and re-seed.
- Exposing the database directly over an API or web interface.

## Success signal

`uv run python load_seed.py` exits 0 and prints row counts matching the CSVs. A separate smoke-test script calls all 4 MCP tools against the seeded DB and receives correct responses with no unhandled exceptions.
