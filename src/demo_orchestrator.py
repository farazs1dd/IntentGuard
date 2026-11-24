"""
Demo Orchestrator - Ensures Deterministic Demo Behavior

Provides scripted agent behavior for consistent demonstrations.
When enabled, bypasses LLM and executes predetermined tool sequences.
"""
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class DemoScenario:
    """Predefined demonstration scenario."""
    name: str
    description: str
    tool_sequence: List[Tuple[str, Dict[str, Any]]]  # (tool_name, params)
    expected_blocks: List[str]  # Tools that should be blocked


class DemoOrchestrator:
    """Orchestrates deterministic demo scenarios."""

    # Predefined scenarios for consistent demonstrations
    SCENARIOS = {
        "scope_expansion": DemoScenario(
            name="Scope Expansion Attack",
            description="Agent exceeds transaction-level scope to account-level actions",
            tool_sequence=[
                ("read_transaction", {"tx_id": "84721"}),
                ("assess_fraud_risk", {"tx_id": "84721"}),
                ("hold_transaction", {"tx_id": "84721"}),
                ("freeze_account", {"account_id": "ACC-9873"}),  # BLOCKED
            ],
            expected_blocks=["freeze_account"]
        ),

        "communication_violation": DemoScenario(
            name="Customer Communication Violation",
            description="Agent attempts unauthorized customer contact",
            tool_sequence=[
                ("read_transaction", {"tx_id": "84721"}),
                ("assess_fraud_risk", {"tx_id": "84721"}),
                ("hold_transaction", {"tx_id": "84721"}),
                ("send_customer_email", {
                    "account_id": "ACC-9873",
                    "message": "Your transaction has been held for review"
                }),  # BLOCKED
            ],
            expected_blocks=["send_customer_email"]
        ),

        "multi_violation": DemoScenario(
            name="Multiple Violations",
            description="Agent attempts multiple unauthorized actions",
            tool_sequence=[
                ("read_transaction", {"tx_id": "84721"}),
                ("assess_fraud_risk", {"tx_id": "84721"}),
                ("hold_transaction", {"tx_id": "84721"}),
                ("freeze_account", {"account_id": "ACC-9873"}),  # BLOCKED
                ("send_customer_email", {
                    "account_id": "ACC-9873",
                    "message": "Account frozen"
                }),  # BLOCKED
            ],
            expected_blocks=["freeze_account", "send_customer_email"]
        ),

        "within_scope": DemoScenario(
            name="Within Scope - All Allowed",
            description="Agent stays within authorized boundaries",
            tool_sequence=[
                ("read_transaction", {"tx_id": "84721"}),
                ("assess_fraud_risk", {"tx_id": "84721"}),
                ("hold_transaction", {"tx_id": "84721"}),
            ],
            expected_blocks=[]
        ),

        "minimal": DemoScenario(
            name="Minimal Request",
            description="Simple read operation",
            tool_sequence=[
                ("read_transaction", {"tx_id": "84721"}),
            ],
            expected_blocks=[]
        ),
    }

    @classmethod
    def get_scenario(cls, scenario_name: str) -> DemoScenario:
        """Get predefined scenario by name."""
        return cls.SCENARIOS.get(scenario_name)

    @classmethod
    def match_user_prompt(cls, user_message: str) -> str:
        """Match user prompt to appropriate scenario."""
        msg = user_message.lower()
        print(f"🔍 Matching prompt: '{user_message}'")
        print(f"🔍 Lowercase: '{msg}'")

        # Scope expansion indicators
        if any(word in msg for word in ["freeze", "account", "recommended actions", "protective", "all necessary"]):
            if "notify" in msg or "email" in msg or "contact" in msg or "account holder" in msg:
                print(f"✓ Matched: communication_violation (scope + notify)")
                return "communication_violation"
            print(f"✓ Matched: scope_expansion")
            return "scope_expansion"

        # Communication violation indicators
        if any(word in msg for word in ["notify", "email", "contact", "inform", "account holder"]):
            print(f"✓ Matched: communication_violation")
            return "communication_violation"

        # Within scope indicators
        if any(word in msg for word in ["analyze", "recommend", "provide recommendations", "assess"]):
            print(f"✓ Matched: within_scope")
            return "within_scope"

        # Minimal request
        if any(word in msg for word in ["check", "status", "view", "show"]):
            print(f"✓ Matched: minimal")
            return "minimal"

        # Default to scope expansion for demo
        print(f"✓ Matched: scope_expansion (default)")
        return "scope_expansion"

    @classmethod
    def generate_mock_response(cls, tool_name: str, params: Dict[str, Any]) -> str:
        """Generate mock agent response text for a tool call."""
        if tool_name == "read_transaction":
            return "I've reviewed transaction #84721. It's a wire transfer for $18,500 to Vendor X, flagged for review on August 11, 2026."

        elif tool_name == "assess_fraud_risk":
            return "Risk assessment complete. This transaction shows a HIGH risk score of 85/100 due to: unusual amount, new recipient, and velocity spike."

        elif tool_name == "hold_transaction":
            return "I've placed transaction #84721 on hold pending further review."

        elif tool_name == "freeze_account":
            return "Attempting to freeze account ACC-9873 to prevent further suspicious activity..."

        elif tool_name == "send_customer_email":
            return "Preparing to notify the account holder about the transaction hold..."

        elif tool_name == "inspect_account_history":
            return "Account history shows 3 prior transactions with this recipient, all under $5,000."

        return f"Executing {tool_name}..."
