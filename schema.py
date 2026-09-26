"""Triage decision schema — Epic 1."""

from typing import Literal

from pydantic import BaseModel

Category = Literal["billing", "bug", "access", "performance", "how-to"]
Priority = Literal["P1", "P2", "P3", "P4"]
Route = Literal["billing-team", "bug-team", "access-team", "performance-team", "how-to-team"]


class TriageDecision(BaseModel):
    category: Category
    priority: Priority
    route: Route
    rationale: str
