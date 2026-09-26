"""Epic 2: triage agent unit and integration tests."""

import asyncio
import os

import pytest
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock


class TestModelSelection:
    def test_default_is_gemini(self):
        from agent.triage import _make_model
        from langchain_google_genai import ChatGoogleGenerativeAI

        with patch.dict(os.environ, {"PROVIDER": ""}, clear=False):
            model = _make_model()
        assert isinstance(model, ChatGoogleGenerativeAI)

    def test_groq_provider_returns_groq(self):
        from agent.triage import _make_model
        from langchain_groq import ChatGroq

        with patch.dict(os.environ, {"PROVIDER": "groq"}, clear=False):
            model = _make_model()
        assert isinstance(model, ChatGroq)

    def test_model_env_overrides_default_gemini(self):
        from agent.triage import _make_model
        from langchain_google_genai import ChatGoogleGenerativeAI

        with patch.dict(os.environ, {"PROVIDER": "", "MODEL": "gemini-2.0-flash"}, clear=False):
            model = _make_model()
        assert isinstance(model, ChatGoogleGenerativeAI)

    def test_model_env_overrides_default_groq(self):
        from agent.triage import _make_model
        from langchain_groq import ChatGroq

        with patch.dict(os.environ, {"PROVIDER": "groq", "MODEL": "llama3-8b-8192"}, clear=False):
            model = _make_model()
        assert isinstance(model, ChatGroq)


class TestEscalateToHumanTool:
    def test_tool_name(self):
        from agent.triage import escalate_to_human
        assert escalate_to_human.name == "escalate_to_human"

    def test_tool_accepts_ticket_id_and_reason(self):
        from agent.triage import escalate_to_human
        result = escalate_to_human.invoke({"ticket_id": "T-1044", "reason": "P1 Enterprise"})
        assert "T-1044" in result
        assert "approved" in result.lower()


def _integration_enabled() -> bool:
    load_dotenv()
    return os.environ.get("INTEGRATION_TESTS", "").lower() in ("1", "true") and bool(
        os.environ.get("GEMINI_API_KEY")
    )


@pytest.mark.skipif(not _integration_enabled(), reason="set INTEGRATION_TESTS=1 and GEMINI_API_KEY to run")
class TestTriageIntegration:
    def test_t1042_billing_p2(self):
        load_dotenv()
        decision = asyncio.run(triage_ticket("T-1042"))
        assert decision["category"] == "billing"
        assert decision["priority"] == "P2"
        assert decision["route"] == "billing-team"
        assert decision["rationale"]

    def test_t1099_ignores_embedded_instruction(self):
        load_dotenv()
        decision = asyncio.run(triage_ticket("T-1099"))
        assert decision["category"] == "bug"
        assert decision["priority"] == "P4"

    def test_auto_approve_no_stdin_block(self):
        load_dotenv()
        with patch.dict(os.environ, {"AUTO_APPROVE_ESCALATION": "1"}, clear=False):
            decision = asyncio.run(triage_ticket("T-1044"))
        assert decision["category"] == "access"


async def triage_ticket(ticket_id: str) -> dict:
    from agent import triage
    return await triage(ticket_id)
