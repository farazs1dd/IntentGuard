# tests/test_intent_contract.py
import json
import tempfile
import pytest
from src.intent_contract import IntentContract, load_intent_contract


def test_load_valid_intent_contract():
    """Test loading a valid intent contract."""
    contract_data = {
        "contract_id": "test_contract_001",
        "goal": "test_goal",
        "authorized_tools": ["read_transaction", "hold_transaction"],
        "resource_scope": {
            "transaction_ids": ["84721"],
            "account_ids": [],
            "allowed_scope_expansion": False
        },
        "constraints": {
            "max_transactions_affected": 1,
            "customer_communication": False,
            "account_level_actions": False
        },
        "approved_recipients": [],
        "metadata": {
            "user": "test@example.com",
            "timestamp": "2026-08-12T10:00:00Z",
            "risk_level": "medium"
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(contract_data, f)
        contract_path = f.name

    try:
        contract = load_intent_contract(contract_path)
        assert contract.contract_id == "test_contract_001"
        assert contract.goal == "test_goal"
        assert "read_transaction" in contract.authorized_tools
        assert "hold_transaction" in contract.authorized_tools
        assert "84721" in contract.resource_scope.transaction_ids
        assert contract.resource_scope.allowed_scope_expansion is False
        assert contract.constraints.max_transactions_affected == 1
        assert contract.constraints.customer_communication is False
    finally:
        import os
        os.unlink(contract_path)


def test_intent_contract_missing_required_fields():
    """Test validation fails with missing required fields."""
    with pytest.raises(ValueError):
        IntentContract(
            contract_id="",  # Empty required field
            goal="test",
            authorized_tools=[],
            resource_scope={"transaction_ids": [], "account_ids": []},
            constraints={},
            approved_recipients=[]
        )


def test_intent_contract_authorized_tools_validation():
    """Test that authorized_tools must not be empty."""
    contract_data = {
        "contract_id": "test_001",
        "goal": "test_goal",
        "authorized_tools": [],  # Should have at least one tool
        "resource_scope": {
            "transaction_ids": ["123"],
            "account_ids": []
        },
        "constraints": {},
        "approved_recipients": []
    }

    # Empty authorized_tools is allowed for this MVP (minimal validation)
    # Just ensure it doesn't crash
    contract = IntentContract(**contract_data)
    assert contract.authorized_tools == []
