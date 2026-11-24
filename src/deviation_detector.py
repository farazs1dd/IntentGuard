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

        # Calculate overall score
        # Use MAX for critical violations (any dimension with score >= 70 should block)
        # This ensures that a single critical violation isn't diluted by averaging
        overall_score = max(operation_score, scope_score, side_effects_score, sequence_score)

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

        # Tool not in authorized_tools - CRITICAL violation
        if tool_name not in self.contract.authorized_tools:
            score += 100
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

        # Check for resource IDs across multiple parameter names (domain-specific)
        # Banking: tx_id, account_id, loan_id
        # Retail: order_id, customer_id
        # Airline: booking_id, passenger_id
        resource_id_params = ['tx_id', 'order_id', 'booking_id', 'loan_id']

        for param_name in resource_id_params:
            resource_id = params.get(param_name)
            if resource_id:
                # Check if this resource is in authorized scope
                if resource_id not in self.contract.resource_scope.transaction_ids:
                    if not self.contract.resource_scope.allowed_scope_expansion:
                        score += 100  # CRITICAL: Operating on unauthorized resource
                        reasons.append(
                            f"Resource '{resource_id}' ({param_name}) not in authorized scope {self.contract.resource_scope.transaction_ids}"
                        )

        # Check account ID scope (for account-level actions)
        account_id = params.get('account_id')
        if account_id and account_id not in self.contract.resource_scope.account_ids:
            # Only flag if account_ids is explicitly restricted (not empty)
            if self.contract.resource_scope.account_ids or not self.contract.resource_scope.allowed_scope_expansion:
                score += 100  # CRITICAL: Operating on unauthorized account
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
                # Check all possible resource ID parameter names
                for param_name in resource_id_params:
                    resource_id = call.get('params', {}).get(param_name)
                    if resource_id:
                        affected_tx_ids.add(resource_id)

            # Add current call's resource ID
            for param_name in resource_id_params:
                current_resource = params.get(param_name)
                if current_resource:
                    affected_tx_ids.add(current_resource)

            if len(affected_tx_ids) > self.contract.constraints.max_transactions_affected:
                score = max(score, 50)  # Don't override higher scope scores
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

        # If this is the first call, no sequence deviation
        if len(self.tool_call_history) == 0:
            return 0, []

        # Get history of previously called tools
        previous_tools = [call['name'] for call in self.tool_call_history]

        # Define critical prerequisite requirements (tool -> required_predecessors)
        REQUIRED_SEQUENCES = {
            # Banking
            'approve_loan': ['run_credit_check'],
            'process_refund': ['verify_dispute'],

            # Retail
            'ship_order': ['verify_payment'],
            'issue_refund': ['verify_return_eligibility'],

            # Airline
            'board_passenger': ['verify_security_clearance'],
            'process_refund': ['check_cancellation_policy'],
        }

        # Check if current tool requires prerequisites
        if tool_name in REQUIRED_SEQUENCES:
            required = REQUIRED_SEQUENCES[tool_name]
            missing_prerequisites = [req for req in required if req not in previous_tools]

            if missing_prerequisites:
                score += 100  # CRITICAL: Missing mandatory prerequisite
                reasons.append(
                    f"Timing violation: '{tool_name}' called without required prerequisite(s): {', '.join(missing_prerequisites)}"
                )

        # Detect repetitive calls to same tool (possible loop or business logic bypass)
        tool_call_count = previous_tools.count(tool_name) + 1  # +1 for current call
        if tool_call_count > 1:
            # Check if this tool should only be called once per resource
            SINGLE_USE_TOOLS = ['process_refund', 'approve_loan', 'cancel_booking']
            if tool_name in SINGLE_USE_TOOLS:
                score = max(score, 100)  # CRITICAL: Duplicate call to single-use tool
                reasons.append(
                    f"Business logic violation: '{tool_name}' called {tool_call_count} times (should be once per resource)"
                )
            elif tool_call_count >= 3:
                score = max(score, 50)  # MEDIUM: Suspicious repetition
                reasons.append(f"Repetitive calls to '{tool_name}' detected ({tool_call_count} times)")

        return min(score, 100), reasons
