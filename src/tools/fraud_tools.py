"""
Mock fraud investigation tools for IntentGuard MVP.

These tools log their execution but don't perform real banking operations.
Each tool returns a success dict with mock data.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def read_transaction(tx_id: str) -> Dict[str, Any]:
    """
    Read transaction details.

    Args:
        tx_id: Transaction ID

    Returns:
        Mock transaction data
    """
    logger.info(f"[TOOL] read_transaction(tx_id={tx_id})")

    return {
        'success': True,
        'tool': 'read_transaction',
        'tx_id': tx_id,
        'amount': 18500.00,
        'recipient': 'Vendor X',
        'timestamp': '2026-08-11T14:23:15Z',
        'status': 'flagged'
    }


def inspect_account_history(account_id: str) -> Dict[str, Any]:
    """
    Inspect account transaction history.

    Args:
        account_id: Account ID

    Returns:
        Mock account history data
    """
    logger.info(f"[TOOL] inspect_account_history(account_id={account_id})")

    return {
        'success': True,
        'tool': 'inspect_account_history',
        'account_id': account_id,
        'transactions': [
            {'tx_id': '84720', 'amount': 500.00, 'date': '2026-08-10'},
            {'tx_id': '84719', 'amount': 1200.00, 'date': '2026-08-09'},
            {'tx_id': '84718', 'amount': 800.00, 'date': '2026-08-08'}
        ],
        'account_age_days': 450
    }


def assess_fraud_risk(tx_id: str) -> Dict[str, Any]:
    """
    Assess fraud risk for a transaction.

    Args:
        tx_id: Transaction ID

    Returns:
        Mock fraud risk assessment
    """
    logger.info(f"[TOOL] assess_fraud_risk(tx_id={tx_id})")

    return {
        'success': True,
        'tool': 'assess_fraud_risk',
        'tx_id': tx_id,
        'risk_score': 85,
        'risk_level': 'high',
        'signals': ['unusual_amount', 'new_recipient', 'velocity_spike']
    }


def hold_transaction(tx_id: str) -> Dict[str, Any]:
    """
    Place a transaction on hold.

    Args:
        tx_id: Transaction ID

    Returns:
        Hold confirmation
    """
    logger.info(f"[TOOL] hold_transaction(tx_id={tx_id})")

    return {
        'success': True,
        'tool': 'hold_transaction',
        'tx_id': tx_id,
        'status': 'held',
        'timestamp': '2026-08-12T10:30:00Z'
    }


def freeze_account(account_id: str) -> Dict[str, Any]:
    """
    Freeze an entire customer account.

    Args:
        account_id: Account ID

    Returns:
        Freeze confirmation
    """
    logger.info(f"[TOOL] freeze_account(account_id={account_id})")

    return {
        'success': True,
        'tool': 'freeze_account',
        'account_id': account_id,
        'status': 'frozen',
        'timestamp': '2026-08-12T10:31:00Z'
    }


def send_customer_email(account_id: str, message: str) -> Dict[str, Any]:
    """
    Send email to customer.

    Args:
        account_id: Account ID
        message: Email message content

    Returns:
        Send confirmation
    """
    logger.info(f"[TOOL] send_customer_email(account_id={account_id}, message={message[:50]}...)")

    return {
        'success': True,
        'tool': 'send_customer_email',
        'account_id': account_id,
        'message': message,
        'timestamp': '2026-08-12T10:32:00Z'
    }


# Tool registry for easy lookup
FRAUD_TOOLS = {
    'read_transaction': read_transaction,
    'inspect_account_history': inspect_account_history,
    'assess_fraud_risk': assess_fraud_risk,
    'hold_transaction': hold_transaction,
    'freeze_account': freeze_account,
    'send_customer_email': send_customer_email
}
