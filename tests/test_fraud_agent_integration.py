# tests/test_fraud_agent_integration.py
def test_fraud_agent_tool_registration():
    """Test that fraud agent tools are properly registered."""
    from src.tools.fraud_tools import FRAUD_TOOLS

    assert 'read_transaction' in FRAUD_TOOLS
    assert 'hold_transaction' in FRAUD_TOOLS
    assert 'freeze_account' in FRAUD_TOOLS
    assert len(FRAUD_TOOLS) == 6


def test_fraud_agent_cli():
    """Test fraud agent CLI (placeholder for manual testing)."""
    # Manual test: run fraud_agent.py and verify it accepts input
    pass
