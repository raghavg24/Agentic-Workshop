---
title: Expense Claim Reviewer — MVP PRD
status: final
created: 2026-09-27
updated: 2026-09-27
---

# Expense Claim Reviewer — MVP PRD

## Problem

Finance reviews every expense claim by hand. It takes a week, and two reviewers frequently disagree on the same claim. The process is slow, inconsistent, and does not scale.

## Goal

An agent that reviews each line item against the expense policy, records a consistent decision with the exact policy clause, and holds large approved items for human payout release.

## User

Single operator: Finance team lead. Internal demo scope — no external users, no UI beyond the MLflow dashboard where the operator reads traces and decision JSON.

## Success Metrics

| # | Metric | Target |
|---|---|---|
| 1 | Decision accuracy (label match) | ≥ 90% on 30 labelled claims |
| 2 | Clause accuracy (cited clause match) | ≥ 90% on 30 labelled claims |
| 3 | Reimbursable total accuracy per claim | Within $0.02 |
| 4 | Human gate triggered correctly | 100% of approved items > $500 held |

**Counter-metric:** False reject rate on valid claims — must stay below 10%.

## Scope

**In:** Review line items, cite clause, record decisions, hold items > $500 for human release.  
**Out:** Paying anyone, emailing employees, any UI beyond the MLflow dashboard. Human payout release is an external manual step — the agent only records the hold.

## Functional Requirements

### FR-1 Claim ingestion
- **FR-1.1** The agent accepts a `claim_id` and retrieves all line items via `get_claim(claim_id)`.
- **FR-1.2** The agent retrieves employee level and city via `get_employee(employee_id)`.
- **FR-1.3** The agent retrieves per-category limits via `get_policy_limits(level, city)`.

### FR-2 Line-item decision
- **FR-2.1** Every line item receives exactly one decision: `approve`, `flag`, or `reject`.
- **FR-2.2** The agent applies clauses in priority order: §3 (never-reimbursable) → 5.1 (duplicate) → 1.2 (stale >60 days) → 4.1 (IT pre-approval) → limits §2/§6 → 1.3 (missing receipt).
- **FR-2.3** Meals and ground transport are daily caps: all lines on the same date are summed before deciding; each line on that day receives the day's decision.
- **FR-2.4** Against any limit: ≤ limit → approve; ≤ limit × 1.20 → flag; > limit × 1.20 → reject.
- **FR-2.5** The agent records every decision via `record_decision(line_id, decision, clause)`.

### FR-3 Human gate
- **FR-3.1** Any line item with `decision = approve` and `amount > 500 CAD` is held pending human payout release.
- **FR-3.2** The hold is surfaced as a structured field in the agent's output JSON (`"holds": ["L-XXXX"]`). The agent records `approve`; a human releases the payout externally via the `expense_decisions` table.

### FR-4 Output
- **FR-4.1** The agent returns a JSON summary: `claim_id`, per-line decisions with clause and amount, list of holds, and `reimbursable_total` (sum of approved-only amounts).
- **FR-4.2** If any line item decision is missing from the output (claim processed but line absent from decisions), the agent must surface an error — partial decisions are not acceptable.

### FR-5 Tracing
- **FR-5.1** Every agent run is traced in MLflow under experiment `expense-agent`.
- **FR-5.2** The eval writes results to MLflow experiment `expense-eval`.

## Non-Functional Requirements

| # | Requirement | Target |
|---|---|---|
| 1 | Claim text is untrusted — the agent must not follow instructions found in descriptions | Enforced by system prompt |
| 2 | Model provider switchable without code change | `PROVIDER` env var (gemini / groq) |
| 3 | Policy file (`POLICY.md`) and seed data are read-only | Never modified at runtime |
| 4 | Missing limit data must not silently produce wrong decisions | `get_policy_limits` raises on empty result; agent surfaces error |

## Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | Human gate is a dead end — Finance has no defined release mechanism | High: $500+ items never paid | Define release as reading `expense_decisions` where `decision='approve'` and `line_id` in holds; document in operator runbook |
| 2 | Silent partial decisions — missing city/level or LLM timeout leaves decisions table incomplete | High: incorrect reimbursable total, audit failure | FR-4.2 completeness check; `get_policy_limits` raises on empty result (NFR-4) |
| 3 | Daily aggregation correctness — 4 eval misses suggest model reasoning gap on multi-line daily sums | Medium: accuracy below 90% threshold on holdout set | Investigate prompt gap before demo; add explicit daily-sum example to system prompt |

## Open Questions

| # | Question | Owner | Revisit |
|---|---|---|---|
| 1 | Daily aggregation misses (CL-2003, 2008, 2015, 2020): prompt gap or model reasoning? | Dev | Before demo |
| 2 | Holdout claims CL-2031–2040 scored live at demo — are labels pre-loaded? | PM | Before demo |
