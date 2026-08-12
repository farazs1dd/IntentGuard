# tests/test_fraud_tools.py
from src.tools.fraud_tools import (
    read_transaction,
    inspect_account_history,
    assess_fraud_risk,
    hold_transaction,
    freeze_account,
    send_customer_email
)


def test_read_transaction():
    """Test read_transaction returns mock data."""
    result = read_transaction("84721")
    assert result['success'] is True
    assert result['tool'] == 'read_transaction'
    assert result['tx_id'] == '84721'
    assert 'amount' in result
    assert 'recipient' in result


def test_inspect_account_history():
    """Test inspect_account_history returns mock data."""
    result = inspect_account_history("23891")
    assert result['success'] is True
    assert result['tool'] == 'inspect_account_history'
    assert result['account_id'] == '23891'
    assert 'transactions' in result


def test_assess_fraud_risk():
    """Test assess_fraud_risk returns mock data."""
    result = assess_fraud_risk("84721")
    assert result['success'] is True
    assert result['tool'] == 'assess_fraud_risk'
    assert result['tx_id'] == '84721'
    assert 'risk_score' in result
    assert 0 <= result['risk_score'] <= 100


def test_hold_transaction():
    """Test hold_transaction returns success."""
    result = hold_transaction("84721")
    assert result['success'] is True
    assert result['tool'] == 'hold_transaction'
    assert result['tx_id'] == '84721'
    assert result['status'] == 'held'


def test_freeze_account():
    """Test freeze_account returns success."""
    result = freeze_account("23891")
    assert result['success'] is True
    assert result['tool'] == 'freeze_account'
    assert result['account_id'] == '23891'
    assert result['status'] == 'frozen'


def test_send_customer_email():
    """Test send_customer_email returns success."""
    result = send_customer_email("23891", "Test message")
    assert result['success'] is True
    assert result['tool'] == 'send_customer_email'
    assert result['account_id'] == '23891'
    assert result['message'] == 'Test message'
