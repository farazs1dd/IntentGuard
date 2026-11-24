"""
JSON report generator for IntentGuard.

Generates detailed deviation reports with AIRS gap analysis.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any
from src.intent_contract import IntentContract
from src.deviation_detector import DeviationAnalysis
from src.airs import normalize_scan, ScanEvidence


class ReportGenerator:
    """Generates JSON reports from monitoring sessions."""

    def __init__(
        self,
        session_id: str,
        contract: IntentContract,
        tool_calls_with_analysis: List[Tuple[Dict[str, Any], DeviationAnalysis]]
    ):
        """
        Initialize report generator.

        Args:
            session_id: Monitoring session ID
            contract: Intent contract used
            tool_calls_with_analysis: List of (tool_call, analysis) tuples
        """
        self.session_id = session_id
        self.contract = contract
        self.tool_calls_with_analysis = tool_calls_with_analysis

    def generate(self, output_dir: str) -> str:
        """
        Generate JSON report.

        Args:
            output_dir: Directory to save report

        Returns:
            Path to generated report file
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
        filename = f"{self.session_id}_{timestamp}.json"
        output_path = Path(output_dir) / filename

        report = self._build_report()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        return str(output_path)

    def _build_report(self) -> Dict[str, Any]:
        """Build complete report structure."""
        total_actions = len(self.tool_calls_with_analysis)
        deviations = sum(1 for _, analysis in self.tool_calls_with_analysis
                        if analysis.overall_score > 0)
        expected_actions = total_actions - deviations

        # Calculate overall deviation score (max of all analyses)
        overall_deviation = max(
            (analysis.overall_score for _, analysis in self.tool_calls_with_analysis),
            default=0
        )

        if overall_deviation <= 30:
            verdict = 'LOW'
        elif overall_deviation <= 60:
            verdict = 'MEDIUM'
        else:
            verdict = 'HIGH'

        return {
            'session_id': self.session_id,
            'contract_id': self.contract.contract_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_actions': total_actions,
                'expected_actions': expected_actions,
                'deviations': deviations,
                'overall_deviation_score': overall_deviation,
                'verdict': verdict
            },
            'timeline': self._build_timeline(),
            'airs_gap_analysis': self._build_airs_gap_analysis(overall_deviation, verdict),
            'recommended_actions': self._build_recommendations()
        }

    def _build_timeline(self) -> List[Dict[str, Any]]:
        """Build timeline of tool calls with analysis."""
        timeline = []

        for tool_call, analysis in self.tool_calls_with_analysis:
            entry = {
                'timestamp': tool_call.get('timestamp'),
                'tool': tool_call.get('name'),
                'params': tool_call.get('params', {}),
                'result': tool_call.get('result', {}),
                'expected': analysis.overall_score == 0,
                'deviation_score': analysis.overall_score,
                'reasons': analysis.reasons
            }

            if analysis.overall_score > 0:
                entry['deviation_breakdown'] = {
                    'operation_deviation': analysis.operation_score,
                    'scope_expansion': analysis.scope_score,
                    'side_effects': analysis.side_effects_score,
                    'behavioral_sequence': analysis.sequence_score
                }

            timeline.append(entry)

        return timeline

    def _build_airs_gap_analysis(self, overall_deviation: int, verdict: str) -> Dict[str, Any]:
        """Build AIRS gap analysis section."""
        maximum = max(
            (max(a.operation_score, a.scope_score, a.side_effects_score, a.sequence_score)
             for _, a in self.tool_calls_with_analysis), default=0
        )
        intentguard_verdict = 'BLOCK' if maximum >= 70 else \
                             'REQUIRE_CONFIRMATION' if maximum >= 40 else 'ALLOW'
        scans = [
            normalize_scan(call['airs_result'], 'gateway')
            if call.get('airs_result') else ScanEvidence()
            for call, _ in self.tool_calls_with_analysis
        ]
        observed = (
            'BLOCK' if any(s.action == 'BLOCK' for s in scans)
            else 'ALLOW' if scans and all(s.permits for s in scans)
            else 'UNKNOWN'
        )
        return {
            'current_airs_verdict': observed,
            'current_airs_reasoning': 'Observed scan evidence only; absent scans are unknown.',
            'scan_evidence': [s.model_dump() for s in scans],
            'intentguard_verdict': intentguard_verdict,
            'intentguard_reasoning': 'Local intent-contract evaluation, independent of AIRS.',
            'gap_summary': 'Compare AIRS threat verdicts with local intent decisions. '
                          'Unknown scans do not establish a protection gap.'
        }

    def _build_recommendations(self) -> List[str]:
        """Build recommended actions list."""
        recommendations = []

        for tool_call, analysis in self.tool_calls_with_analysis:
            if analysis.overall_score > 60:
                tool_name = tool_call.get('name')
                params = tool_call.get('params', {})
                param_str = ', '.join([f"{k}={v}" for k, v in params.items()])
                recommendations.append(
                    f"Review {tool_name}({param_str}) - verify if action was appropriate"
                )

        if recommendations:
            recommendations.append(
                "Review local action policies and AIRS profile settings independently"
            )

        return recommendations
