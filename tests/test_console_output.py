# tests/test_console_output.py
from io import StringIO
import sys
from src.console_output import ConsoleFormatter
from src.deviation_detector import DeviationAnalysis


def test_format_header(capsys):
    """Test header formatting."""
    formatter = ConsoleFormatter()
    formatter.format_header("test-session-123", "fraud_inv_001", "investigate_transaction")

    captured = capsys.readouterr()
    assert "test-session-123" in captured.out
    assert "fraud_inv_001" in captured.out


def test_format_tool_call_expected(capsys):
    """Test formatting expected tool call (no deviation)."""
    formatter = ConsoleFormatter()

    tool_call = {
        'name': 'read_transaction',
        'params': {'tx_id': '84721'},
        'timestamp': '2026-08-12T10:00:00Z'
    }

    analysis = DeviationAnalysis(
        operation_score=0,
        scope_score=0,
        side_effects_score=0,
        sequence_score=0,
        overall_score=0,
        severity='LOW',
        reasons=[]
    )

    formatter.format_tool_call(tool_call, analysis)

    captured = capsys.readouterr()
    assert "read_transaction" in captured.out
    assert "84721" in captured.out
    assert "EXPECTED" in captured.out or "✓" in captured.out


def test_format_tool_call_deviation(capsys):
    """Test formatting tool call with deviation."""
    formatter = ConsoleFormatter()

    tool_call = {
        'name': 'freeze_account',
        'params': {'account_id': '23891'},
        'timestamp': '2026-08-12T10:01:00Z'
    }

    analysis = DeviationAnalysis(
        operation_score=80,
        scope_score=100,
        side_effects_score=50,
        sequence_score=70,
        overall_score=75,
        severity='HIGH',
        reasons=[
            "Tool 'freeze_account' not in authorized_tools",
            "Scope expansion: transaction-level task to account-level action"
        ]
    )

    formatter.format_tool_call(tool_call, analysis)

    captured = capsys.readouterr()
    assert "freeze_account" in captured.out
    assert "DEVIATION" in captured.out or "✗" in captured.out
    assert "HIGH" in captured.out
