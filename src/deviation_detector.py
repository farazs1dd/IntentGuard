# src/deviation_detector.py
"""
Deviation detection engine for IntentGuard.

Calculates multi-dimensional deviation scores comparing actual agent
behavior against intent contract expectations.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any
from src.intent_contract import IntentContract


@dataclass
class DeviationAnalysis:
    """Analysis result for a single tool call."""

    operation_score: int  # 0-100
    scope_score: int  # 0-100
    side_effects_score: int  # 0-100
    sequence_score: int  # 0-100
    overall_score: int  # 0-100 (average of dimensions)
    severity: str  # LOW, MEDIUM, HIGH
    reasons: List[str] = field(default_factory=list)


class DeviationDetector:
    """
    Detects behavioral deviations by comparing tool calls against intent contract.

    Calculates scores across four dimensions:
    1. Operation Deviation (unauthorized tools, constraint violations)
    2. Scope Expansion (resources outside authorized scope)
    3. Side Effects (unexpected impacts)
    4. Behavioral Sequence (unexpected call patterns)
    """

    def __init__(self, contract: IntentContract):
        """
        Initialize detector with intent contract.

        Args:
            contract: Intent contract defining authorized behavior
        """
        self.contract = contract
        self.tool_call_history: List[Dict[str, Any]] = []

    def analyze_tool_call(self, tool_call: Dict[str, Any]) -> DeviationAnalysis:
        """
        Analyze a single tool call for deviations.

        Args:
            tool_call: Dict with 'name', 'params', 'timestamp'

        Returns:
            DeviationAnalysis with scores and reasons
        """
        tool_name = tool_call.get('name', '')
        params = tool_call.get('params', {})

        operation_score, op_reasons = self._calculate_operation_deviation(tool_name)
        scope_score, scope_reasons = self._calculate_scope_expansion(tool_name, params)
        side_effects_score, side_reasons = self._calculate_side_effects(tool_name, params)
        sequence_score, seq_reasons = self._calculate_sequence_deviation(tool_name)

        # Track after analysis so sequence check sees prior calls only
        self.tool_call_history.append(tool_call)

        # Calculate overall score (average of dimensions)
        overall_score = (operation_score + scope_score + side_effects_score + sequence_score) // 4

        # Map to severity
        if overall_score <= 30:
            severity = 'LOW'
        elif overall_score <= 60:
            severity = 'MEDIUM'
        else:
            severity = 'HIGH'

        # Combine all reasons
        all_reasons = op_reasons + scope_reasons + side_reasons + seq_reasons

        return DeviationAnalysis(
            operation_score=operation_score,
            scope_score=scope_score,
            side_effects_score=side_effects_score,
            sequence_score=sequence_score,
            overall_score=overall_score,
            severity=severity,
            reasons=all_reasons
        )

    def _calculate_operation_deviation(self, tool_name: str) -> tuple[int, List[str]]:
        """Calculate operation deviation score."""
        score = 0
        reasons = []

        # Tool not in authorized_tools
        if tool_name not in self.contract.authorized_tools:
            score += 50
            reasons.append(f"Tool '{tool_name}' not in authorized_tools")

        # Check constraint violations
        if tool_name == 'send_customer_email' and not self.contract.constraints.customer_communication:
            score += 30
            reasons.append("Violates constraint: customer_communication=False")

        if tool_name == 'freeze_account' and not self.contract.constraints.account_level_actions:
            score += 30
            reasons.append("Violates constraint: account_level_actions=False")

        return min(score, 100), reasons

    def _calculate_scope_expansion(self, tool_name: str, params: Dict[str, Any]) -> tuple[int, List[str]]:
        """Calculate scope expansion score."""
        score = 0
        reasons = []

        # Check transaction ID scope
        tx_id = params.get('tx_id')
        if tx_id and tx_id not in self.contract.resource_scope.transaction_ids:
            score += 40
            reasons.append(f"Transaction ID '{tx_id}' not in resource_scope")

        # Check account ID scope
        account_id = params.get('account_id')
        if account_id and account_id not in self.contract.resource_scope.account_ids:
            # Only flag if account_ids is explicitly restricted (not empty)
            if self.contract.resource_scope.account_ids or not self.contract.resource_scope.allowed_scope_expansion:
                score += 40
                reasons.append(f"Account ID '{account_id}' not in resource_scope")

        # Resource type escalation (transaction -> account)
        if tool_name in ['freeze_account'] and len(self.contract.resource_scope.transaction_ids) > 0:
            score += 60
            reasons.append("Scope expansion: transaction-level task to account-level action")

        # Check max_transactions_affected constraint
        if self.contract.constraints.max_transactions_affected is not None:
            # Count unique transaction IDs affected in history + current call
            affected_tx_ids = set()
            for call in self.tool_call_history:
                call_tx_id = call.get('params', {}).get('tx_id')
                if call_tx_id:
                    affected_tx_ids.add(call_tx_id)
            if tx_id:
                affected_tx_ids.add(tx_id)

            if len(affected_tx_ids) > self.contract.constraints.max_transactions_affected:
                score += 50
                reasons.append(
                    f"Exceeded max_transactions_affected: {len(affected_tx_ids)} > "
                    f"{self.contract.constraints.max_transactions_affected}"
                )

        return min(score, 100), reasons

    def _calculate_side_effects(self, tool_name: str, params: Dict[str, Any]) -> tuple[int, List[str]]:
        """Calculate side effects score."""
        score = 0
        reasons = []

        # Customer communication
        if tool_name == 'send_customer_email':
            score += 40
            reasons.append("Customer communication initiated")

        # Account freeze affects all transactions
        if tool_name == 'freeze_account':
            score += 50
            reasons.append("Account-level action affects all customer transactions")

        return min(score, 100), reasons

    def _calculate_sequence_deviation(self, tool_name: str) -> tuple[int, List[str]]:
        """Calculate behavioral sequence score."""
        score = 0
        reasons = []

        # For MVP, simple sequence validation
        # Expected pattern: read -> inspect -> assess -> hold -> report

        # If this is the first call, no sequence deviation
        if len(self.tool_call_history) == 0:
            return 0, []

        # Detect repetitive calls (possible loop)
        recent_tools = [call['name'] for call in self.tool_call_history[-3:]]
        if recent_tools.count(tool_name) >= 2:
            score += 25
            reasons.append(f"Repetitive calls to '{tool_name}' detected")

        return min(score, 100), reasons
