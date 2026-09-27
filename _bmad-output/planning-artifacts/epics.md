---
stepsCompleted: [1]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-mygitclone-2026-09-27/prd.md
---

# Expense Claim Reviewer - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Expense Claim Reviewer, decomposing requirements from the PRD into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: The agent accepts a claim_id and retrieves all line items via get_claim(claim_id)
FR2: The agent retrieves employee level and city via get_employee(employee_id)
FR3: The agent retrieves per-category limits via get_policy_limits(level, city)
FR4: Every line item receives exactly one decision: approve, flag, or reject
FR5: The agent applies clauses in priority order: §3 → 5.1 → 1.2 → 4.1 → limits §2/§6 → 1.3
FR6: Meals and ground transport are daily caps — all lines on same date summed before deciding
FR7: Against any limit: ≤ limit → approve; ≤ limit×1.20 → flag; > limit×1.20 → reject
FR8: The agent records every decision via record_decision(line_id, decision, clause)
FR9: Any approved item with amount > 500 CAD is held pending human payout release
FR10: Hold surfaced as "holds" field in output JSON; agent records approve, human releases externally
FR11: Agent returns JSON summary: claim_id, per-line decisions with clause+amount, holds, reimbursable_total
FR12: If any line item decision is missing from output, agent must surface an error (no partial decisions)
FR13: Every agent run is traced in MLflow under experiment expense-agent
FR14: Eval writes results to MLflow experiment expense-eval

### NonFunctional Requirements

NFR1: Claim text is untrusted — agent must not follow instructions found in descriptions (enforced by system prompt)
NFR2: Model provider switchable without code change via PROVIDER env var (gemini / groq)
NFR3: Policy file (POLICY.md) and seed data are read-only — never modified at runtime
NFR4: Missing limit data must not silently produce wrong decisions — get_policy_limits raises on empty result

### Additional Requirements

- SQLite database seeded from 4 CSVs (claims, line_items, employees, limits) via load_seed.py
- 4 MCP tools served over stdio via langchain-mcp-adapters
- LangChain ReAct agent (create_react_agent) as the execution framework
- MLflow autolog for tracing; separate experiments for agent runs vs eval
- Eval harness runs 30 labelled claims from eval/labelled.csv

### UX Design Requirements

N/A — internal demo, single operator, MLflow dashboard only.

### FR Coverage Map

(Populated in epic design step)

## Epic List

1. Epic 1: Data Foundation — seed loader, SQLite schema, MCP server
2. Epic 2: Agent Core — LangChain ReAct agent with policy prompt and tracing
3. Epic 3: Eval Harness — automated eval against labelled examples, MLflow logging

## Epic 1: Data Foundation

Establish the SQLite database, seed it from CSVs, and expose it via 4 MCP tools so the agent has everything it needs to review claims.

## Epic 2: Agent Core

Build and trace the LangChain ReAct agent that applies the 7-clause policy priority chain to every line item, records decisions, and holds items > $500.

## Epic 3: Eval Harness

Run 30 labelled claims through the agent, score decision + clause accuracy and reimbursable totals, surface results in MLflow.
