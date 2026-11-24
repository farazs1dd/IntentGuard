"""Tests for JSON report generator."""
import json
import tempfile
import os
from pathlib import Path
from src.intent_contract import IntentContract, ResourceScope, Constraints
from src.deviation_detector import DeviationAnalysis
from src.report_generator import ReportGenerator


def test_generate_report():
    """Test JSON report generation."""
    contract = IntentContract(
        contract_id="test_001",
        goal="test_goal",
        authorized_tools=["read_transaction"],
        resource_scope=ResourceScope(transaction_ids=["123"]),
        constraints=Constraints()
    )

    tool_calls_with_analysis = [
        (
            {'name': 'read_transaction', 'params': {'tx_id': '123'}, 'timestamp': '2026-08-12T10:00:00Z'},
            DeviationAnalysis(0, 0, 0, 0, 0, 'LOW', [])
        ),
        (
            {'name': 'freeze_account', 'params': {'account_id': '456'}, 'timestamp': '2026-08-12T10:01:00Z'},
            DeviationAnalysis(80, 60, 50, 20, 52, 'MEDIUM', ['Tool not authorized'])
        )
    ]

    generator = ReportGenerator(
        session_id="test-session",
        contract=contract,
        tool_calls_with_analysis=tool_calls_with_analysis
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = generator.generate(tmpdir)

        assert Path(output_path).exists()

        with open(output_path) as f:
            report = json.load(f)

        assert report['session_id'] == 'test-session'
        assert report['contract_id'] == 'test_001'
        assert report['summary']['total_actions'] == 2
        assert report['summary']['expected_actions'] == 1
        assert report['summary']['deviations'] == 1
        assert len(report['timeline']) == 2
        assert 'airs_gap_analysis' in report


def test_report_airs_gap_analysis():
    """Test AIRS gap analysis in report."""
    contract = IntentContract(
        contract_id="test_001",
        goal="test_goal",
        authorized_tools=["read_transaction"],
        resource_scope=ResourceScope(transaction_ids=["123"]),
        constraints=Constraints()
    )

    tool_calls_with_analysis = [
        (
            {'name': 'freeze_account', 'params': {'account_id': '456'}, 'timestamp': '2026-08-12T10:00:00Z'},
            DeviationAnalysis(80, 60, 50, 20, 75, 'HIGH', ['Unauthorized tool'])
        )
    ]

    generator = ReportGenerator(
        session_id="test-session",
        contract=contract,
        tool_calls_with_analysis=tool_calls_with_analysis
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = generator.generate(tmpdir)

        with open(output_path) as f:
            report = json.load(f)

        gap = report['airs_gap_analysis']
        assert gap['current_airs_verdict'] == 'UNKNOWN'
        assert gap['intentguard_verdict'] in ['BLOCK', 'REQUIRE_CONFIRMATION']
        assert 'gap_summary' in gap
