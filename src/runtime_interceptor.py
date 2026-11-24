"""
Runtime Interceptor for IntentGuard

Intercepts tool calls BEFORE execution and returns verdicts:
- ALLOW: Execute normally
- BLOCK: Skip execution, return error
- REQUIRE_CONFIRMATION: High-risk action requiring human approval

Architecture matches Faberlens/AgentTrust runtime enforcement model.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from src.deviation_detector import DeviationDetector, DeviationAnalysis
from src.intent_contract import IntentContract


class Verdict(Enum):
    """Runtime verdict for tool call."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


@dataclass
class InterceptionResult:
    """Result of runtime interception check."""
    verdict: Verdict
    deviation_score: int
    reasons: list[str]
    analysis: Optional[DeviationAnalysis] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "verdict": self.verdict.value,
            "deviation_score": self.deviation_score,
            "reasons": self.reasons,
            "analysis": {
                "severity": self.analysis.severity,
                "overall_score": self.analysis.overall_score,
                "breakdown": {
                    "operation": self.analysis.operation_score,
                    "scope": self.analysis.scope_score,
                    "side_effects": self.analysis.side_effects_score,
                    "sequence": self.analysis.sequence_score
                }
            } if self.analysis else None
        }


class RuntimeInterceptor:
    """
    Runtime interceptor for AI agent tool calls.

    Checks tool calls against intent contract BEFORE execution.
    Returns verdict: ALLOW, BLOCK, or REQUIRE_CONFIRMATION.
    """

    # Verdict thresholds
    BLOCK_THRESHOLD = 70      # Score >= 70: BLOCK
    CONFIRM_THRESHOLD = 40    # Score >= 40: REQUIRE_CONFIRMATION
    # Score < 40: ALLOW

    def __init__(self, contract: Union[IntentContract, Dict[str, Any]], session_id: str = "default"):
        """
        Initialize runtime interceptor.

        Args:
            contract: Intent contract (IntentContract object or dict)
            session_id: Session identifier for logging
        """
        # Convert dict to IntentContract if needed
        if isinstance(contract, dict):
            self.contract = IntentContract(**contract)
        else:
            self.contract = contract

        self.session_id = session_id
        self.detector = DeviationDetector(self.contract)

        # Interception log
        self.interception_log_path = Path("interceptions.jsonl")

    def check_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> InterceptionResult:
        """
        Check tool call against intent contract BEFORE execution.

        Args:
            tool_name: Name of the tool being called
            params: Tool parameters
            context: Additional context (agent_id, timestamp, etc.)

        Returns:
            InterceptionResult with verdict and reasoning
        """
        # Build tool call for analysis
        tool_call = {
            "name": tool_name,
            "params": params,
            "timestamp": time.time()
        }

        # Analyze deviation
        analysis = self.detector.analyze_tool_call(tool_call)

        # Determine verdict based on deviation score
        verdict = self._determine_verdict(analysis)
        # A denied proposal did not execute and must not consume history/quota.
        if verdict != Verdict.ALLOW:
            self.detector.tool_call_history.pop()

        # Calculate max score across dimensions (used for verdict)
        max_score = max(
            analysis.operation_score,
            analysis.scope_score,
            analysis.side_effects_score,
            analysis.sequence_score
        )

        # Build interception result
        result = InterceptionResult(
            verdict=verdict,
            deviation_score=max_score,  # Use max for fail-secure
            reasons=analysis.reasons,
            analysis=analysis
        )

        # Log interception
        self._log_interception(tool_name, params, result, context)

        return result

    def _determine_verdict(self, analysis: DeviationAnalysis) -> Verdict:
        """
        Determine verdict based on deviation analysis.

        Uses MAX score across dimensions - if ANY dimension shows critical
        deviation, that determines the verdict (fail-secure principle).

        Thresholds:
        - Max score >= 70: BLOCK (high deviation - unauthorized action)
        - Max score >= 40: REQUIRE_CONFIRMATION (medium deviation - risky action)
        - Max score < 40: ALLOW (low/expected deviation)

        Args:
            analysis: Deviation analysis result

        Returns:
            Verdict enum
        """
        # Use MAX across dimensions for fail-secure behavior
        # If scope=100 (complete scope expansion), that alone should BLOCK
        max_score = max(
            analysis.operation_score,
            analysis.scope_score,
            analysis.side_effects_score,
            analysis.sequence_score
        )

        if max_score >= self.BLOCK_THRESHOLD:
            return Verdict.BLOCK
        elif max_score >= self.CONFIRM_THRESHOLD:
            return Verdict.REQUIRE_CONFIRMATION
        else:
            return Verdict.ALLOW

    def _log_interception(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: InterceptionResult,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log interception to JSONL file for audit trail.

        Args:
            tool_name: Tool name
            params: Tool parameters
            result: Interception result
            context: Additional context
        """
        entry = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "tool_call": {
                "name": tool_name,
                "params": params
            },
            "interception": result.to_dict(),
            "context": context or {}
        }

        with open(self.interception_log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def get_error_message(self, result: InterceptionResult) -> str:
        """
        Generate user-friendly error message for blocked/confirmation actions.

        Args:
            result: Interception result

        Returns:
            Error message string
        """
        if result.verdict == Verdict.BLOCK:
            return (
                f"Action blocked by IntentGuard (deviation: {result.deviation_score}/100). "
                f"Reasons: {'; '.join(result.reasons)}"
            )
        elif result.verdict == Verdict.REQUIRE_CONFIRMATION:
            return (
                f"Action requires confirmation (risk score: {result.deviation_score}/100). "
                f"Reasons: {'; '.join(result.reasons)}"
            )
        else:
            return ""
