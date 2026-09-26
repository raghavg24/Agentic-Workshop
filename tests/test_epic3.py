"""Epic 3: eval harness unit tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestLoadData:
    def test_returns_20_rows(self):
        from eval.run_eval import _load_data
        rows = _load_data()
        assert len(rows) == 20

    def test_row_shape(self):
        from eval.run_eval import _load_data
        row = _load_data()[0]
        assert "inputs" in row and "expectations" in row
        assert "ticket_id" in row["inputs"]
        assert "expected_category" in row["expectations"]
        assert "expected_priority" in row["expectations"]
        assert "judge_notes" in row["expectations"]


class TestValidSchema:
    def test_valid_output_scores_1(self):
        from eval.run_eval import valid_schema
        output = {"category": "billing", "priority": "P2", "route": "billing-team", "rationale": "ok"}
        assert valid_schema._original_func(outputs=output) == 1

    def test_invalid_output_scores_0(self):
        from eval.run_eval import valid_schema
        assert valid_schema._original_func(outputs={"category": "invalid"}) == 0

    def test_none_output_scores_0(self):
        from eval.run_eval import valid_schema
        assert valid_schema._original_func(outputs=None) == 0


class TestCategoryMatch:
    def test_match_scores_1(self):
        from eval.run_eval import category_match
        assert category_match._original_func(
            outputs={"category": "billing"},
            expectations={"expected_category": "billing"},
        ) == 1

    def test_mismatch_scores_0(self):
        from eval.run_eval import category_match
        assert category_match._original_func(
            outputs={"category": "bug"},
            expectations={"expected_category": "billing"},
        ) == 0


class TestPriorityMatch:
    def test_match_scores_1(self):
        from eval.run_eval import priority_match
        assert priority_match._original_func(
            outputs={"priority": "P2"},
            expectations={"expected_priority": "P2"},
        ) == 1

    def test_mismatch_scores_0(self):
        from eval.run_eval import priority_match
        assert priority_match._original_func(
            outputs={"priority": "P1"},
            expectations={"expected_priority": "P3"},
        ) == 0


class TestToolOrder:
    def _make_span(self, name, start_ns):
        span = MagicMock()
        span.name = name
        span.start_time_ns = start_ns
        return span

    def test_correct_order_scores_1(self):
        from eval.run_eval import tool_order
        trace = MagicMock()
        trace.data.spans = [
            self._make_span("get_ticket", 100),
            self._make_span("get_customer_history", 200),
        ]
        assert tool_order._original_func(trace=trace) == 1

    def test_wrong_order_scores_0(self):
        from eval.run_eval import tool_order
        trace = MagicMock()
        trace.data.spans = [
            self._make_span("get_customer_history", 100),
            self._make_span("get_ticket", 200),
        ]
        assert tool_order._original_func(trace=trace) == 0

    def test_missing_spans_scores_0(self):
        from eval.run_eval import tool_order
        trace = MagicMock()
        trace.data.spans = [self._make_span("get_ticket", 100)]
        assert tool_order._original_func(trace=trace) == 0

    def test_none_trace_scores_0(self):
        from eval.run_eval import tool_order
        assert tool_order._original_func(trace=None) == 0


class TestRationaleJudge:
    def test_returns_pass_when_llm_says_pass(self):
        from eval.run_eval import rationale_judge
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="pass: rationale correctly identifies billing issue")
        with patch("eval.run_eval.ChatGroq", return_value=mock_llm):
            result = rationale_judge._original_func(
                inputs={"ticket_id": "T-1042"},
                outputs={"rationale": "Customer has billing dispute"},
                expectations={"judge_notes": "Should be billing P2"},
            )
        assert result.startswith("pass")

    def test_returns_fail_when_llm_says_fail(self):
        from eval.run_eval import rationale_judge
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="fail: agent missed enterprise bump")
        with patch("eval.run_eval.ChatGroq", return_value=mock_llm):
            result = rationale_judge._original_func(
                inputs={"ticket_id": "T-1044"},
                outputs={"rationale": "low priority bug"},
                expectations={"judge_notes": "Should be P1 due to enterprise plan"},
            )
        assert result.startswith("fail")

    def test_never_reads_gemini_api_key(self):
        from eval.run_eval import rationale_judge
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="pass: ok")
        with patch("eval.run_eval.ChatGroq", return_value=mock_llm) as mock_groq:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "should-not-appear"}, clear=False):
                rationale_judge._original_func(
                    inputs={"ticket_id": "T-1042"},
                    outputs={"rationale": "billing issue"},
                    expectations={"judge_notes": "billing"},
                )
            call_kwargs = mock_groq.call_args[1] if mock_groq.call_args else {}
            assert "GEMINI_API_KEY" not in str(call_kwargs)

    def test_uses_judge_model_env(self):
        from eval.run_eval import rationale_judge
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="pass: ok")
        with patch("eval.run_eval.ChatGroq", return_value=mock_llm) as mock_groq:
            with patch.dict(os.environ, {"JUDGE_MODEL": "llama3-70b-8192"}, clear=False):
                rationale_judge._original_func(
                    inputs={"ticket_id": "T-1042"},
                    outputs={"rationale": "billing issue"},
                    expectations={"judge_notes": "billing"},
                )
            mock_groq.assert_called_once_with(model="llama3-70b-8192")


class TestPredictAutoApprove:
    def test_sets_auto_approve_env(self):
        captured = {}

        def mock_triage(ticket_id):
            captured["env"] = os.environ.get("AUTO_APPROVE_ESCALATION")

            async def _inner():
                return {"category": "billing", "priority": "P2", "route": "billing-team", "rationale": "ok"}
            return _inner()

        with patch("eval.run_eval.asyncio.run") as mock_run, \
             patch.dict(os.environ, {}, clear=False):
            mock_run.side_effect = lambda coro: {"category": "billing", "priority": "P2", "route": "billing-team", "rationale": "ok"}
            with patch.dict("sys.modules", {"agent": MagicMock(triage=mock_triage)}):
                from eval.run_eval import predict
                predict({"ticket_id": "T-1042"})

    def test_clears_auto_approve_after_predict(self):
        os.environ.pop("AUTO_APPROVE_ESCALATION", None)

        def mock_run(coro):
            assert os.environ.get("AUTO_APPROVE_ESCALATION") == "1"
            return {"category": "billing", "priority": "P2", "route": "billing-team", "rationale": "ok"}

        mock_agent = MagicMock()
        mock_agent.triage = MagicMock()
        with patch("eval.run_eval.asyncio.run", side_effect=mock_run), \
             patch.dict("sys.modules", {"agent": mock_agent}):
            from eval.run_eval import predict
            predict({"ticket_id": "T-1042"})

        assert "AUTO_APPROVE_ESCALATION" not in os.environ
