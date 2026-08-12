# tests/test_intentguard_integration.py
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest


def test_intentguard_integration_mock_gateway():
    """Test IntentGuard with mocked gateway responses."""
    # This is a minimal integration test
    # Full test would require running intentguard.py as subprocess

    # Create temporary contract
    contract_data = {
        "contract_id": "test_001",
        "goal": "test_goal",
        "authorized_tools": ["read_transaction"],
        "resource_scope": {
            "transaction_ids": ["123"],
            "account_ids": []
        },
        "constraints": {},
        "approved_recipients": []
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(contract_data, f)
        contract_path = f.name

    # Verify contract can be loaded
    from src.intent_contract import load_intent_contract
    contract = load_intent_contract(contract_path)
    assert contract.contract_id == "test_001"

    # Cleanup
    import os
    os.unlink(contract_path)


def test_intentguard_argument_parsing():
    """Test command-line argument parsing."""
    # Test will be implemented with actual CLI
    pass
