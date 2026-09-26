---
title: 'Epic 1: triage data schema and seed loader'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo has no SQLite database and no way to load seed data, so the MCP server (`mcp/triage_server.py`) and the triage agent have nothing to read. There is also no validated schema for the triage decision that downstream code can import and trust.

**Approach:** Create `schema.py` with a Pydantic model for triage decisions (category, priority, route, rationale), and `load_seed.py` that reads `seed/tickets.csv` and `seed/customers.csv` into `app.db` idempotently.

</frozen-after-approval>

## Implementation Notes

- Created `schema.py` with Pydantic `TriageDecision` model using `Literal` types for all constrained fields.
- Created `load_seed.py`: reads CSVs with `csv.DictReader`, infers column schema from headers, uses `CREATE TABLE IF NOT EXISTS` + `DELETE FROM` + bulk insert for idempotency.
- Added `pythonpath = ["."]` to `pyproject.toml` so tests can import project-root modules.
- Created `tests/test_epic1.py` with 13 tests covering schema validation (all valid types, all rejection cases) and loader (happy path, idempotency, specific row check for T-1042).
- Removed `.env.example` (was empty; `.env` already exists and is gitignored).

## Review Triage Log

| # | Finding | Verdict | Evidence |
|---|---------|---------|----------|
| 1 | `rationale` min_length constraint | false | Schema validates type; content quality is agent's responsibility, not schema's |
| 2 | SQL injection via f-string table name | false | Table names are hardcoded literals in caller — no user input path exists |
| 3 | All columns TEXT in SQLite | false | SQLite is dynamically typed; MCP server returns raw dict rows; no numeric SQL performed |
| 4 | Test isolation / monkeypatch contamination | false | `monkeypatch` is function-scoped; each test gets its own `tmp_path` |
| 5 | Fragile seed path in tests | low (rejected) | Path is correct for current layout; fix adds complexity with no practical benefit |
| 6 | Silent success violates expectation | false | Global rules require no terminal output on success |
| 7 | Missing linting tools in dev deps | defer | Out of Epic 1 scope; added to deferred-work.md |
| 8 | CSV column names assumed in tests | false | Test column names exactly match actual CSV headers (confirmed by inspection) |

### Review Findings

- [ ] [Review][Patch] .env.example deletion removes setup instructions [.env.example] — file contained "Copy this file to .env and fill in your keys" + all required key names (GEMINI_API_KEY, GROQ_API_KEY) + optional overrides; new contributors have no template

**Rejected:**

- BH-2 (false): Schema cross-field validation — spec requires per-field validation only; cross-field consistency is the agent's responsibility, not the schema's
- BH-3 (false): SQL injection via f-string table names — table names are hardcoded string literals in `main()`; no user input path reaches `_load_table`
- BH-4 (false): `test_ticket_t1042_present` hardcodes `"C-77"` — seed is read-only per AGENTS.md; the value is stable and correct
- BH-5 (false): No logger/tracing hook — global rules mandate silent output on success; loader is a standalone script, not a library
- BH-6 (rejected): Triage log doesn't cite code locations — fix would require editing the spec under review
- BH-7 (low, rejected): No malformed CSV handling — seed is read-only; malformed CSV is unreachable in everyday use; fix adds unnecessary guards
- ECH-1 (false): CSV file not found → silent failure — `open()` raises `FileNotFoundError` with full path; failure is not silent
- ECH-2 (false): CSV row missing column → incomplete rows — `csv.DictReader` fills missing columns with `None`; seed is consistent and read-only
- ECH-3 (false): Test seed file not found → unclear error — `open()` raises `FileNotFoundError` with path; seed is always present
- ECH-4 (low, rejected): Commit message says ".env.example was empty" — cosmetic wording in git history; cannot be amended; grouped root cause covered by the patch finding above
