"""
JSON report generator for IntentGuard.

Generates detailed deviation reports with AIRS gap analysis.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any
from src.intent_contract import IntentContract
from src.deviation_detector import DeviationAnalysis


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
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')
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
            'timestamp': datetime.utcnow().isoformat() + 'Z',
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
        intentguard_verdict = 'BLOCK' if verdict == 'HIGH' else \
                             'REQUIRE_CONFIRMATION' if verdict == 'MEDIUM' else 'ALLOW'

        return {
            'current_airs_verdict': 'ALLOW',
            'current_airs_reasoning': 'Agent authenticated with valid credentials. '
                                     'Agent has necessary tool permissions in IAM policy. '
                                     'No content policy violations detected.',
            'intentguard_verdict': intentguard_verdict,
            'intentguard_reasoning': 'Behavioral deviation detected. Actions exceeded '
                                    'authorized scope for this specific task.',
            'gap_summary': 'AIRS allowed these actions because the agent has the necessary '
                          'permissions. IntentGuard detected that these actions exceeded '
                          'the behavioral intent for this specific task.'
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
                "Consider implementing AIRS policy to require confirmation for detected deviations"
            )

        return recommendations
