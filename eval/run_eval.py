"""Eval harness for the triage agent — Epic 3.

Usage: uv run python eval/run_eval.py
"""

import asyncio
import csv
import json
import os
from pathlib import Path

import mlflow
import mlflow.genai
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from mlflow.genai import scorer

load_dotenv()

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("triage-agent")
mlflow.langchain.autolog()

_DATA = Path(__file__).parent / "labelled_tickets.csv"
_REPORT = Path(__file__).parent / "latest_report.json"


def _load_data() -> list[dict]:
    rows = []
    with open(_DATA) as f:
        for row in csv.DictReader(f):
            rows.append({
                "inputs": {"ticket_id": row["ticket_id"]},
                "expectations": {
                    "expected_category": row["expected_category"],
                    "expected_priority": row["expected_priority"],
                    "judge_notes": row["judge_notes"],
                },
            })
    return rows


@mlflow.trace(name="triage_ticket", span_type="AGENT")
def predict(ticket_id: str) -> dict:
    os.environ["AUTO_APPROVE_ESCALATION"] = "1"
    try:
        from agent import triage
        return asyncio.run(triage(ticket_id))
    finally:
        os.environ.pop("AUTO_APPROVE_ESCALATION", None)


@scorer
def valid_schema(outputs) -> int:
    from pydantic import ValidationError
    from schema import TriageDecision
    try:
        TriageDecision.model_validate(outputs or {})
        return 1
    except (ValidationError, TypeError):
        return 0


@scorer
def category_match(outputs, expectations) -> int:
    return 1 if (outputs or {}).get("category") == (expectations or {}).get("expected_category") else 0


@scorer
def priority_match(outputs, expectations) -> int:
    return 1 if (outputs or {}).get("priority") == (expectations or {}).get("expected_priority") else 0


@scorer
def tool_order(trace) -> int:
    if trace is None:
        return 0
    spans = trace.data.spans
    ticket_starts = [s.start_time_ns for s in spans if s.name == "get_ticket"]
    customer_starts = [s.start_time_ns for s in spans if "get_customer_history" in s.name]
    if not ticket_starts or not customer_starts:
        return 0
    return 1 if min(ticket_starts) < min(customer_starts) else 0


@scorer
def rationale_judge(inputs, outputs, expectations) -> str:
    rationale = (outputs or {}).get("rationale", "")
    judge_notes = (expectations or {}).get("judge_notes", "")
    ticket_id = (inputs or {}).get("ticket_id", "")
    judge_model = os.environ.get("JUDGE_MODEL", "openai/gpt-oss-120b")
    llm = ChatGroq(model=judge_model)
    prompt = (
        f"Ticket: {ticket_id}\n"
        f"Agent rationale: {rationale}\n"
        f"Expected behavior: {judge_notes}\n\n"
        "Does the rationale match the expected behavior? "
        "Reply with 'pass: <one-line reason>' or 'fail: <one-line reason>'."
    )
    content = llm.invoke(prompt).content.strip()
    # Return first line only (e.g. "pass: correct billing category identified")
    return content.split("\n")[0]


def _count_escalations(experiment_name: str, run_id: str) -> int:
    """Count auto-approved escalations by finding escalate_to_human spans in traces."""
    client = mlflow.MlflowClient()
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        return 0
    traces = client.search_traces(
        experiment_ids=[exp.experiment_id],
        filter_string=f"tags.`mlflow.sourceRun` = '{run_id}'",
    )
    count = 0
    for _, row in traces.iterrows():
        trace = mlflow.get_trace(row["trace_id"])
        count += sum(1 for s in trace.data.spans if s.name == "escalate_to_human")
    return count


def _total_tokens(experiment_name: str, run_id: str) -> int:
    """Sum llm.token_count.total across all spans in all traces for this run."""
    client = mlflow.MlflowClient()
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        return 0
    traces = client.search_traces(
        experiment_ids=[exp.experiment_id],
        filter_string=f"tags.`mlflow.sourceRun` = '{run_id}'",
    )
    total = 0
    for _, row in traces.iterrows():
        trace = mlflow.get_trace(row["trace_id"])
        for span in trace.data.spans:
            total += int((span.attributes or {}).get("llm.token_count.total", 0))
    return total


def _scorer_means(results) -> dict[str, float | None]:
    """Extract per-scorer means from mlflow.genai.evaluate results."""
    scorer_names = ("valid_schema", "category_match", "priority_match", "tool_order", "rationale_judge")
    metrics = results.metrics if hasattr(results, "metrics") else {}
    means: dict[str, float | None] = {}
    for name in scorer_names:
        # mlflow reports means under various key patterns depending on version
        val = (
            metrics.get(f"{name}/mean")
            or metrics.get(f"mean/{name}")
            or metrics.get(name)
        )
        if val is None and hasattr(results, "tables"):
            # Fall back: compute from results table
            table = results.tables.get("eval_results")
            if table is not None and name in table.columns:
                col = table[name]
                if name == "rationale_judge":
                    val = col.apply(lambda v: 1 if str(v).startswith("pass") else 0).mean()
                else:
                    val = col.mean()
        means[name] = round(float(val), 4) if val is not None else None
    return means


def main() -> None:
    data = _load_data()
    scorers = [valid_schema, category_match, priority_match, tool_order, rationale_judge]

    with mlflow.start_run() as run:
        run_id = run.info.run_id
        results = mlflow.genai.evaluate(
            data=data,
            scorers=scorers,
            predict_fn=predict,
        )

    means = _scorer_means(results)
    total_tokens = _total_tokens("triage-agent", run_id)
    escalation_count = _count_escalations("triage-agent", run_id)

    report = {
        "scorer_means": means,
        "total_tokens": total_tokens,
        "escalation_count": escalation_count,
    }
    _REPORT.write_text(json.dumps(report, indent=2))

    print("\n=== Eval Results ===")
    for k, v in means.items():
        print(f"  {k}: {v}")
    print(f"  total_tokens: {total_tokens}")
    print(f"  escalations_auto_approved: {escalation_count}")
    print(f"\nReport written to {_REPORT}")


if __name__ == "__main__":
    main()
