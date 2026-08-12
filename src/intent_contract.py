# src/intent_contract.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class ResourceScope(BaseModel):
    """Defines the scope of resources an agent may operate on."""

    transaction_ids: List[str] = Field(default_factory=list)
    account_ids: List[str] = Field(default_factory=list)
    allowed_scope_expansion: bool = Field(default=False)


class Constraints(BaseModel):
    """Behavioral constraints for agent actions."""

    max_transactions_affected: Optional[int] = None
    customer_communication: bool = Field(default=False)
    account_level_actions: bool = Field(default=False)


class IntentContract(BaseModel):
    """
    Intent contract defining authorized behavior for an agent task.

    Captures what the human authorized: goal, permitted operations,
    resource scope, constraints, and approved recipients.
    """

    contract_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    authorized_tools: List[str] = Field(default_factory=list)
    resource_scope: ResourceScope
    constraints: Constraints = Field(default_factory=Constraints)
    approved_recipients: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('contract_id', 'goal')
    @classmethod
    def check_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v


def load_intent_contract(contract_path: str) -> IntentContract:
    """
    Load and validate an intent contract from JSON file.

    Args:
        contract_path: Path to intent contract JSON file

    Returns:
        IntentContract object

    Raises:
        FileNotFoundError: If contract file doesn't exist
        ValueError: If contract validation fails
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(contract_path)
    if not path.exists():
        raise FileNotFoundError(f"Intent contract not found: {contract_path}")

    with open(path) as f:
        data = json.load(f)

    return IntentContract(**data)
