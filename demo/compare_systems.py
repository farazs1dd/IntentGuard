"""
System Comparison Tool

Compares detection results from IntentGuard vs Prisma AIRS (or other systems)
on the same standardized test suite.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from test_schema import TestSuiteResult, ComparisonReport


class SystemComparator:
    """Compare security test results from multiple systems."""

    def __init__(self):
        pass

    def load_results(self, results_file: Path) -> TestSuiteResult:
        """Load test results from JSON file."""
        with open(results_file, 'r') as f:
            data = json.load(f)
        return TestSuiteResult(**data)

    def compare(
        self,
        system_a_results: TestSuiteResult,
        system_b_results: TestSuiteResult
    ) -> ComparisonReport:
        """
        Compare results from two systems.

        Args:
            system_a_results: First system's results (e.g., IntentGuard)
            system_b_results: Second system's results (e.g., Prisma AIRS)

        Returns:
            ComparisonReport with side-by-side analysis
        """
        # Create result lookup maps
        a_detected = {r.test_id for r in system_a_results.results if r.detected}
        b_detected = {r.test_id for r in system_b_results.results if r.detected}

        all_test_ids = {r.test_id for r in system_a_results.results} | \
                      {r.test_id for r in system_b_results.results}

        # Categorize detections
        unique_to_a = sorted(a_detected - b_detected)
        unique_to_b = sorted(b_detected - a_detected)
        both_detected = sorted(a_detected & b_detected)
        neither_detected = sorted(all_test_ids - a_detected - b_detected)

        # Calculate delta
        detection_rate_delta = system_a_results.detection_rate - system_b_results.detection_rate

        report = ComparisonReport(
            system_a=system_a_results,
            system_b=system_b_results,
            detection_rate_delta=detection_rate_delta,
            unique_to_a=unique_to_a,
            unique_to_b=unique_to_b,
            both_detected=both_detected,
            neither_detected=neither_detected
        )

        return report

    def print_comparison(self, report: ComparisonReport, detailed: bool = False):
        """Print comparison report to console."""
        a = report.system_a
        b = report.system_b

        print("\n" + "="*80)
        print("SECURITY BENCHMARK COMPARISON")
        print("="*80)

        print(f"\nSystem A: {a.system_name} v{a.version}")
        print(f"System B: {b.system_name} v{b.version}")

        print("\n" + "-"*80)
        print("DETECTION SUMMARY")
        print("-"*80)

        # Side-by-side metrics
        print(f"\n{'Metric':<30} {a.system_name:<25} {b.system_name:<25}")
        print("-"*80)
        print(f"{'Total Tests':<30} {a.total_tests:<25} {b.total_tests:<25}")
        print(f"{'Detected':<30} {a.detected:<25} {b.detected:<25}")
        print(f"{'Missed':<30} {a.missed:<25} {b.missed:<25}")
        print(f"{'Detection Rate':<30} {a.detection_rate:.1f}%{'':<20} {b.detection_rate:.1f}%")

        if a.average_deviation_score and b.average_deviation_score:
            print(f"{'Avg Deviation Score':<30} {a.average_deviation_score:.1f}/100{'':<15} {b.average_deviation_score:.1f}/100")

        # Delta
        print("\n" + "-"*80)
        print("DELTA ANALYSIS")
        print("-"*80)
        delta_sign = "+" if report.detection_rate_delta > 0 else ""
        print(f"\nDetection Rate Delta: {delta_sign}{report.detection_rate_delta:.1f}%")

        if report.detection_rate_delta > 0:
            print(f"✓ {a.system_name} detected {abs(report.detection_rate_delta):.1f}% MORE attacks")
        elif report.detection_rate_delta < 0:
            print(f"✗ {a.system_name} detected {abs(report.detection_rate_delta):.1f}% FEWER attacks")
        else:
            print("= Both systems had equal detection rates")

        # Unique detections
        print("\n" + "-"*80)
        print("UNIQUE DETECTIONS")
        print("-"*80)

        print(f"\nOnly {a.system_name} detected ({len(report.unique_to_a)}):")
        if report.unique_to_a:
            for test_id in report.unique_to_a:
                print(f"  • {test_id}")
        else:
            print("  (none)")

        print(f"\nOnly {b.system_name} detected ({len(report.unique_to_b)}):")
        if report.unique_to_b:
            for test_id in report.unique_to_b:
                print(f"  • {test_id}")
        else:
            print("  (none)")

        print(f"\nBoth systems detected ({len(report.both_detected)}):")
        if report.both_detected:
            for test_id in report.both_detected:
                print(f"  • {test_id}")
        else:
            print("  (none)")

        print(f"\nNeither system detected ({len(report.neither_detected)}):")
        if report.neither_detected:
            for test_id in report.neither_detected:
                print(f"  • {test_id}")
        else:
            print("  (none)")

        # Per-domain comparison
        if detailed:
            print("\n" + "-"*80)
            print("PER-DOMAIN BREAKDOWN")
            print("-"*80)

            all_domains = set(a.breakdown_by_domain.keys()) | set(b.breakdown_by_domain.keys())

            for domain in sorted(all_domains):
                print(f"\n{domain.upper()}:")
                a_stats = a.breakdown_by_domain.get(domain, {})
                b_stats = b.breakdown_by_domain.get(domain, {})

                print(f"  {a.system_name}: {a_stats.get('detected', 0)}/{a_stats.get('total', 0)} " +
                      f"({a_stats.get('detection_rate', 0):.0f}%)")
                print(f"  {b.system_name}: {b_stats.get('detected', 0)}/{b_stats.get('total', 0)} " +
                      f"({b_stats.get('detection_rate', 0):.0f}%)")

        print("\n" + "="*80 + "\n")

    def generate_html_comparison(self, report: ComparisonReport, output_file: Path):
        """Generate HTML comparison dashboard."""
        a = report.system_a
        b = report.system_b

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Benchmark Comparison: {a.system_name} vs {b.system_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        h1 {{ color: #667eea; margin-bottom: 8px; }}
        .subtitle {{ color: #666; }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .system-card {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .system-name {{
            font-size: 20px;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 16px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #666; }}
        .metric-value {{
            font-weight: 600;
            color: #333;
        }}
        .delta-card {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
            margin-bottom: 30px;
        }}
        .delta-value {{
            font-size: 48px;
            font-weight: 700;
            color: #10b981;
        }}
        .delta-value.negative {{ color: #ef4444; }}
        .delta-label {{
            color: #666;
            margin-top: 8px;
        }}
        .breakdown {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .breakdown h2 {{
            color: #667eea;
            margin-bottom: 20px;
        }}
        .breakdown-section {{
            margin-bottom: 24px;
        }}
        .breakdown-section h3 {{
            color: #333;
            margin-bottom: 12px;
            font-size: 16px;
        }}
        .test-list {{
            padding-left: 20px;
            color: #666;
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Security Benchmark Comparison</h1>
            <p class="subtitle">{a.system_name} vs {b.system_name}</p>
        </header>

        <div class="delta-card">
            <div class="delta-value {'negative' if report.detection_rate_delta < 0 else ''}">
                {'+' if report.detection_rate_delta > 0 else ''}{report.detection_rate_delta:.1f}%
            </div>
            <div class="delta-label">
                Detection Rate Delta ({a.system_name} vs {b.system_name})
            </div>
        </div>

        <div class="comparison-grid">
            <div class="system-card">
                <div class="system-name">{a.system_name} v{a.version}</div>
                <div class="metric">
                    <span class="metric-label">Total Tests</span>
                    <span class="metric-value">{a.total_tests}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Detected</span>
                    <span class="metric-value" style="color: #10b981;">{a.detected}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Missed</span>
                    <span class="metric-value" style="color: #ef4444;">{a.missed}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Detection Rate</span>
                    <span class="metric-value">{a.detection_rate:.1f}%</span>
                </div>
                {'<div class="metric"><span class="metric-label">Avg Deviation</span><span class="metric-value">' + f'{a.average_deviation_score:.1f}/100' + '</span></div>' if a.average_deviation_score else ''}
            </div>

            <div class="system-card">
                <div class="system-name">{b.system_name} v{b.version}</div>
                <div class="metric">
                    <span class="metric-label">Total Tests</span>
                    <span class="metric-value">{b.total_tests}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Detected</span>
                    <span class="metric-value" style="color: #10b981;">{b.detected}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Missed</span>
                    <span class="metric-value" style="color: #ef4444;">{b.missed}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Detection Rate</span>
                    <span class="metric-value">{b.detection_rate:.1f}%</span>
                </div>
                {'<div class="metric"><span class="metric-label">Avg Deviation</span><span class="metric-value">' + f'{b.average_deviation_score:.1f}/100' + '</span></div>' if b.average_deviation_score else ''}
            </div>
        </div>

        <div class="breakdown">
            <h2>Unique Detections</h2>

            <div class="breakdown-section">
                <h3>✓ Only {a.system_name} detected ({len(report.unique_to_a)} attacks)</h3>
                <ul class="test-list">
                    {''.join(f'<li>{test_id}</li>' for test_id in report.unique_to_a) if report.unique_to_a else '<li style="color: #999;">None</li>'}
                </ul>
            </div>

            <div class="breakdown-section">
                <h3>✓ Only {b.system_name} detected ({len(report.unique_to_b)} attacks)</h3>
                <ul class="test-list">
                    {''.join(f'<li>{test_id}</li>' for test_id in report.unique_to_b) if report.unique_to_b else '<li style="color: #999;">None</li>'}
                </ul>
            </div>

            <div class="breakdown-section">
                <h3>✓ Both systems detected ({len(report.both_detected)} attacks)</h3>
                <ul class="test-list">
                    {''.join(f'<li>{test_id}</li>' for test_id in report.both_detected) if report.both_detected else '<li style="color: #999;">None</li>'}
                </ul>
            </div>

            <div class="breakdown-section">
                <h3>✗ Neither system detected ({len(report.neither_detected)} attacks)</h3>
                <ul class="test-list">
                    {''.join(f'<li>{test_id}</li>' for test_id in report.neither_detected) if report.neither_detected else '<li style="color: #999;">None</li>'}
                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(html)

        print(f"HTML comparison saved to: {output_file}")

    def save_comparison(self, report: ComparisonReport, output_file: Path):
        """Save comparison report to JSON."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report.model_dump(), f, indent=2)
        print(f"Comparison report saved to: {output_file}")


def main():
    """Run comparison from command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Compare security test results from two systems'
    )
    parser.add_argument(
        'system_a_results',
        type=str,
        help='Path to System A results JSON file (e.g., IntentGuard results)'
    )
    parser.add_argument(
        'system_b_results',
        type=str,
        help='Path to System B results JSON file (e.g., Prisma AIRS results)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for comparison JSON'
    )
    parser.add_argument(
        '--html',
        type=str,
        help='Output HTML comparison dashboard'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed per-domain breakdown'
    )

    args = parser.parse_args()

    comparator = SystemComparator()

    # Load results
    print("Loading results...")
    system_a = comparator.load_results(Path(args.system_a_results))
    system_b = comparator.load_results(Path(args.system_b_results))

    # Compare
    print("Comparing systems...")
    report = comparator.compare(system_a, system_b)

    # Print comparison
    comparator.print_comparison(report, detailed=args.detailed)

    # Save outputs
    if args.output:
        comparator.save_comparison(report, Path(args.output))

    if args.html:
        comparator.generate_html_comparison(report, Path(args.html))


if __name__ == "__main__":
    main()
