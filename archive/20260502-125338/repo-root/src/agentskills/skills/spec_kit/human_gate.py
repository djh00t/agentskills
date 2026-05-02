"""Human checkpoint interfaces for clarification and approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agentskills.contracts.spec_kit_models import (
    ApprovalDecision,
    ClarificationQuestion,
)


class HumanGate(Protocol):
    """Defines required human interactions for the workflow."""

    def ask(self, question: ClarificationQuestion) -> str:
        """Asks a clarification question and returns the response."""

    def approve(self, summary: str) -> ApprovalDecision:
        """Requests publication approval and returns the decision."""


@dataclass
class CliHumanGate:
    """Implements interactive CLI prompts for human checkpoints."""

    approver: str = "human"

    def ask(self, question: ClarificationQuestion) -> str:
        """Prompts for clarification response in interactive mode."""
        return input(f"{question.prompt}\n> ").strip()

    def approve(self, summary: str) -> ApprovalDecision:
        """Prompts for yes/no approval in interactive mode."""
        response = input(f"Approve publication? {summary} [y/N]\n> ").strip().lower()
        return ApprovalDecision(
            approved=response == "y",
            approver=self.approver,
            notes=("approved via CLI" if response == "y" else "rejected via CLI"),
        )
