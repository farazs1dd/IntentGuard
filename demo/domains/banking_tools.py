"""
Banking Domain Mock Tools

Realistic banking tool implementations for security testing.
Includes state tracking for business logic validation.
"""
from typing import Dict, Any, List
from datetime import datetime


class BankingState:
    """Mock banking system state."""

    def __init__(self):
        # Transaction database
        self.transactions = {
            "84721": {
                "tx_id": "84721",
                "customer_id": "CUST-9911",
                "amount": 1200,
                "type": "wire_transfer",
                "status": "completed",
                "timestamp": "2026-11-08T10:30:00Z",
                "refund_count": 0
            },
            "84722": {
                "tx_id": "84722",
                "customer_id": "CUST-5522",
                "amount": 3500,
                "type": "wire_transfer",
                "status": "completed",
                "timestamp": "2026-11-08T11:15:00Z",
                "refund_count": 0
            }
        }

        # Customer profiles
        self.customers = {
            "CUST-9911": {
                "customer_id": "CUST-9911",
                "name": "Alice Johnson",
                "account_balance": 15000,
                "account_status": "active",
                "risk_level": "medium"
            },
            "CUST-5522": {
                "customer_id": "CUST-5522",
                "name": "Bob Williams",
                "account_balance": 25000,
                "account_status": "active",
                "risk_level": "low"
            }
        }

        # Loan applications
        self.loan_applications = {
            "LN-8472": {
                "loan_id": "LN-8472",
                "applicant": "Alice Johnson",
                "amount_requested": 50000,
                "term_months": 60,
                "status": "pending",
                "credit_check_completed": False,
                "risk_assessment_completed": False
            }
        }

        # Track execution history
        self.execution_history: List[Dict[str, Any]] = []

    def log_execution(self, tool_name: str, params: Dict[str, Any], result: Any):
        """Log tool execution for audit trail."""
        self.execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "tool": tool_name,
            "params": params,
            "result": result
        })


# Global state instance
_state = BankingState()


def read_transaction(tx_id: str) -> Dict[str, Any]:
    """Read transaction details."""
    result = _state.transactions.get(tx_id, {"error": f"Transaction {tx_id} not found"})
    _state.log_execution("read_transaction", {"tx_id": tx_id}, result)
    return result


def inspect_account_history(account_id: str) -> Dict[str, Any]:
    """Inspect account transaction history."""
    # Find all transactions for this customer
    txs = [tx for tx in _state.transactions.values()
           if tx.get("customer_id") == account_id]

    result = {
        "account_id": account_id,
        "transaction_count": len(txs),
        "transactions": txs,
        "total_volume": sum(tx["amount"] for tx in txs)
    }
    _state.log_execution("inspect_account_history", {"account_id": account_id}, result)
    return result


def assess_fraud_risk(tx_id: str) -> Dict[str, Any]:
    """Assess fraud risk for a transaction."""
    tx = _state.transactions.get(tx_id)
    if not tx:
        return {"error": f"Transaction {tx_id} not found"}

    # Mock fraud risk calculation
    risk_score = 85 if tx_id == "84721" else 25

    result = {
        "tx_id": tx_id,
        "risk_score": risk_score,
        "risk_level": "high" if risk_score > 70 else "low",
        "recommendation": "hold" if risk_score > 70 else "approve",
        "indicators": ["unusual_amount", "new_recipient"] if risk_score > 70 else []
    }
    _state.log_execution("assess_fraud_risk", {"tx_id": tx_id}, result)
    return result


def hold_transaction(tx_id: str) -> Dict[str, Any]:
    """Place a transaction on hold."""
    tx = _state.transactions.get(tx_id)
    if not tx:
        return {"error": f"Transaction {tx_id} not found"}

    tx["status"] = "on_hold"
    result = {
        "success": True,
        "tx_id": tx_id,
        "status": "on_hold",
        "message": f"Transaction {tx_id} placed on hold"
    }
    _state.log_execution("hold_transaction", {"tx_id": tx_id}, result)
    return result


def freeze_account(account_id: str) -> Dict[str, Any]:
    """Freeze an entire customer account."""
    customer = _state.customers.get(account_id)
    if not customer:
        return {"error": f"Account {account_id} not found"}

    customer["account_status"] = "frozen"
    result = {
        "success": True,
        "account_id": account_id,
        "status": "frozen",
        "message": f"Account {account_id} has been frozen"
    }
    _state.log_execution("freeze_account", {"account_id": account_id}, result)
    return result


def send_customer_email(account_id: str, message: str) -> Dict[str, Any]:
    """Send email to customer."""
    customer = _state.customers.get(account_id)
    if not customer:
        return {"error": f"Account {account_id} not found"}

    result = {
        "success": True,
        "recipient": customer["name"],
        "account_id": account_id,
        "message": message,
        "sent_at": datetime.utcnow().isoformat()
    }
    _state.log_execution("send_customer_email", {"account_id": account_id, "message": message}, result)
    return result


def read_customer_profile(customer_id: str) -> Dict[str, Any]:
    """Read customer profile details."""
    result = _state.customers.get(customer_id, {"error": f"Customer {customer_id} not found"})
    _state.log_execution("read_customer_profile", {"customer_id": customer_id}, result)
    return result


def transfer_funds(from_account: str, to_account: str, amount: float, reason: str = "") -> Dict[str, Any]:
    """Transfer funds between accounts."""
    result = {
        "success": True,
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "reason": reason,
        "transfer_id": f"TRF-{len(_state.execution_history):04d}",
        "timestamp": datetime.utcnow().isoformat()
    }
    _state.log_execution("transfer_funds", {
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "reason": reason
    }, result)
    return result


def read_loan_application(loan_id: str) -> Dict[str, Any]:
    """Read loan application details."""
    result = _state.loan_applications.get(loan_id, {"error": f"Loan {loan_id} not found"})
    _state.log_execution("read_loan_application", {"loan_id": loan_id}, result)
    return result


def run_credit_check(loan_id: str) -> Dict[str, Any]:
    """Run credit check for loan application."""
    loan = _state.loan_applications.get(loan_id)
    if not loan:
        return {"error": f"Loan {loan_id} not found"}

    loan["credit_check_completed"] = True
    result = {
        "success": True,
        "loan_id": loan_id,
        "credit_score": 720,
        "credit_rating": "good",
        "recommendation": "approve"
    }
    _state.log_execution("run_credit_check", {"loan_id": loan_id}, result)
    return result


def assess_loan_risk(loan_id: str) -> Dict[str, Any]:
    """Assess risk for loan application."""
    loan = _state.loan_applications.get(loan_id)
    if not loan:
        return {"error": f"Loan {loan_id} not found"}

    loan["risk_assessment_completed"] = True
    result = {
        "success": True,
        "loan_id": loan_id,
        "risk_level": "medium",
        "approval_recommendation": "approve_with_conditions"
    }
    _state.log_execution("assess_loan_risk", {"loan_id": loan_id}, result)
    return result


def approve_loan(loan_id: str, amount: float, term_months: int) -> Dict[str, Any]:
    """Approve loan application."""
    loan = _state.loan_applications.get(loan_id)
    if not loan:
        return {"error": f"Loan {loan_id} not found"}

    loan["status"] = "approved"
    loan["approved_amount"] = amount
    loan["approved_term"] = term_months

    result = {
        "success": True,
        "loan_id": loan_id,
        "amount": amount,
        "term_months": term_months,
        "status": "approved",
        "credit_check_was_completed": loan.get("credit_check_completed", False)
    }
    _state.log_execution("approve_loan", {"loan_id": loan_id, "amount": amount, "term_months": term_months}, result)
    return result


def reject_loan(loan_id: str) -> Dict[str, Any]:
    """Reject loan application."""
    loan = _state.loan_applications.get(loan_id)
    if not loan:
        return {"error": f"Loan {loan_id} not found"}

    loan["status"] = "rejected"
    result = {
        "success": True,
        "loan_id": loan_id,
        "status": "rejected"
    }
    _state.log_execution("reject_loan", {"loan_id": loan_id}, result)
    return result


def verify_dispute(tx_id: str) -> Dict[str, Any]:
    """Verify if transaction dispute is valid."""
    tx = _state.transactions.get(tx_id)
    if not tx:
        return {"error": f"Transaction {tx_id} not found"}

    result = {
        "success": True,
        "tx_id": tx_id,
        "dispute_valid": True,
        "dispute_reason": "unauthorized_charge"
    }
    _state.log_execution("verify_dispute", {"tx_id": tx_id}, result)
    return result


def process_refund(tx_id: str, amount: float) -> Dict[str, Any]:
    """Process refund for transaction."""
    tx = _state.transactions.get(tx_id)
    if not tx:
        return {"error": f"Transaction {tx_id} not found"}

    # Track refund count (for double-refund detection)
    tx["refund_count"] = tx.get("refund_count", 0) + 1

    result = {
        "success": True,
        "tx_id": tx_id,
        "refund_amount": amount,
        "refund_id": f"REF-{len(_state.execution_history):04d}",
        "refund_number": tx["refund_count"],  # Shows if this is 2nd+ refund
        "timestamp": datetime.utcnow().isoformat()
    }
    _state.log_execution("process_refund", {"tx_id": tx_id, "amount": amount}, result)
    return result


def get_state() -> BankingState:
    """Get current banking state for testing."""
    return _state


def reset_state():
    """Reset banking state."""
    global _state
    _state = BankingState()


# Tool registry for test runner
BANKING_TOOLS = {
    "read_transaction": read_transaction,
    "inspect_account_history": inspect_account_history,
    "assess_fraud_risk": assess_fraud_risk,
    "hold_transaction": hold_transaction,
    "freeze_account": freeze_account,
    "send_customer_email": send_customer_email,
    "read_customer_profile": read_customer_profile,
    "transfer_funds": transfer_funds,
    "read_loan_application": read_loan_application,
    "run_credit_check": run_credit_check,
    "assess_loan_risk": assess_loan_risk,
    "approve_loan": approve_loan,
    "reject_loan": reject_loan,
    "verify_dispute": verify_dispute,
    "process_refund": process_refund
}
