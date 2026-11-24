# tests/test_intentguard_integration.py
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from src.config import Config
from src.intent_contract import load_intent_contract, IntentContract, ResourceScope, Constraints
from src.gateway_client import GatewayClient
from src.deviation_detector import DeviationDetector
from src.report_generator import ReportGenerator


def test_end_to_end_deviation_detection():
    """Test complete flow from contract to report."""

    # 1. Create intent contract
    contract = IntentContract(
        contract_id="e2e_test",
        goal="test_investigation",
        authorized_tools=["read_transaction", "hold_transaction"],
        resource_scope=ResourceScope(
            transaction_ids=["84721"],
            account_ids=[]
        ),
        constraints=Constraints(
            max_transactions_affected=1,
            customer_communication=False,
            account_level_actions=False
        )
    )

    # 2. Simulate tool calls (some authorized, some not)
    tool_calls = [
        {'name': 'read_transaction', 'params': {'tx_id': '84721'},
         'timestamp': '2026-08-12T10:00:00Z', 'result': {}},
        {'name': 'hold_transaction', 'params': {'tx_id': '84721'},
         'timestamp': '2026-08-12T10:01:00Z', 'result': {}},
        {'name': 'freeze_account', 'params': {'account_id': '23891'},
         'timestamp': '2026-08-12T10:02:00Z', 'result': {}},
    ]

    # 3. Run deviation detection
    detector = DeviationDetector(contract)
    analyses = [detector.analyze_tool_call(tc) for tc in tool_calls]

    # 4. Verify detections
    assert analyses[0].severity == 'LOW'  # Authorized
    assert analyses[1].severity == 'LOW'  # Authorized
    assert analyses[2].severity in ['MEDIUM', 'HIGH']  # Deviation
    assert analyses[2].operation_score > 0

    # 5. Generate report
    tool_calls_with_analysis = list(zip(tool_calls, analyses))
    generator = ReportGenerator(
        session_id="e2e_test_session",
        contract=contract,
        tool_calls_with_analysis=tool_calls_with_analysis
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = generator.generate(tmpdir)

        # 6. Verify report
        assert Path(report_path).exists()

        with open(report_path) as f:
            report = json.load(f)

        assert report['summary']['total_actions'] == 3
        assert report['summary']['deviations'] >= 1
        assert 'airs_gap_analysis' in report
        assert report['airs_gap_analysis']['current_airs_verdict'] == 'UNKNOWN'
        assert report['airs_gap_analysis']['intentguard_verdict'] in ['BLOCK', 'REQUIRE_CONFIRMATION']


def test_load_demo_scenarios():
    """Test that all demo scenario contracts can be loaded."""
    scenarios = [
        'contracts/scenario_scope_expansion.json',
        'contracts/scenario_unauthorized_recipient.json',
        'contracts/scenario_resource_creep.json'
    ]

    for scenario_path in scenarios:
        if Path(scenario_path).exists():
            contract = load_intent_contract(scenario_path)
            assert contract.contract_id
            assert contract.goal
        else:
            pytest.skip(f"Scenario file not found: {scenario_path}")
