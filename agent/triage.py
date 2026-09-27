"""LangChain triage agent — Epic 2."""

import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from schema import TriageDecision

_POLICY = (Path(__file__).parent.parent / "TRIAGE_POLICY.md").read_text()
_MCP_SERVER = str(Path(__file__).parent.parent / "mcp" / "triage_server.py")


def _make_model():
    provider = os.environ.get("PROVIDER", "").lower()
    model_name = os.environ.get("MODEL", "")
    if provider == "groq":
        return ChatGroq(model=model_name or "openai/gpt-oss-120b")
    return ChatGoogleGenerativeAI(model=model_name or "gemini-3.8-flash")


@tool
def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Escalate this ticket to a human. Call this when the final priority is P1 and the customer is on the Enterprise plan."""
    return f"Escalation approved for {ticket_id}: {reason}"


async def triage(ticket_id: str) -> dict:
    client = MultiServerMCPClient({
        "triage": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [_MCP_SERVER],
        }
    })
    mcp_tools = await client.get_tools()

    auto_approve = os.environ.get("AUTO_APPROVE_ESCALATION", "").lower() in ("1", "true", "yes")
    checkpointer = MemorySaver()
    middleware = (
        []
        if auto_approve
        else [HumanInTheLoopMiddleware(interrupt_on={"escalate_to_human": True})]
    )

    agent = create_agent(
        model=_make_model(),
        tools=[*mcp_tools, escalate_to_human],
        system_prompt=_POLICY,
        checkpointer=checkpointer,
        middleware=middleware,
        response_format=TriageDecision,
    )

    for attempt in range(2):
        config = {"configurable": {"thread_id": f"{ticket_id}-{attempt}"}}
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": f"Triage ticket {ticket_id}."}]},
                config=config,
            )

            if not auto_approve and "__interrupt__" in result:
                answer = input(f"\n[ESCALATION] Approve escalation for {ticket_id}? [yes/no]: ").strip().lower()
                result = await agent.ainvoke(
                    Command(resume={"decisions": [{"type": "approve" if answer == "yes" else "reject"}]}),
                    config=config,
                )

            structured = result.get("structured_response")
            if isinstance(structured, TriageDecision):
                return structured.model_dump()
            raise ValueError(f"No structured response returned (keys: {list(result.keys())})")

        except (ValidationError, ValueError) as exc:
            if attempt == 1:
                raise RuntimeError(f"Triage failed for {ticket_id} after 2 attempts: {exc}") from exc

    raise RuntimeError(f"Triage failed for {ticket_id}")
