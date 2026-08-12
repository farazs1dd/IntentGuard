# tests/test_deviation_detector.py
import pytest
from src.intent_contract import IntentContract, ResourceScope, Constraints
from src.deviation_detector import DeviationDetector, DeviationAnalysis


@pytest.fixture
def basic_contract():
    """Basic intent contract for testing."""
    return IntentContract(
        contract_id="test_001",
        goal="investigate_transaction",
        authorized_tools=["read_transaction", "assess_fraud_risk", "hold_transaction"],
        resource_scope=ResourceScope(
            transaction_ids=["84721"],
            account_ids=[],
            allowed_scope_expansion=False
        ),
        constraints=Constraints(
            max_transactions_affected=1,
            customer_communication=False,
            account_level_actions=False
        ),
        approved_recipients=[]
    )


def test_authorized_tool_call_no_deviation(basic_contract):
    """Test that authorized tool call within scope has no deviation."""
    detector = DeviationDetector(basic_contract)

    tool_call = {
        'name': 'read_transaction',
        'params': {'tx_id': '84721'},
        'timestamp': '2026-08-12T10:00:00Z'
    }

    analysis = detector.analyze_tool_call(tool_call)
    assert analysis.overall_score == 0
    assert analysis.severity == 'LOW'
    assert len(analysis.reasons) == 0


def test_unauthorized_tool_deviation(basic_contract):
    """Test that unauthorized tool call is detected."""
    detector = DeviationDetector(basic_contract)

    tool_call = {
        'name': 'freeze_account',
        'params': {'account_id': '23891'},
        'timestamp': '2026-08-12T10:01:00Z'
    }

    analysis = detector.analyze_tool_call(tool_call)
    assert analysis.operation_score >= 50
    assert analysis.overall_score > 0
    assert 'not in authorized_tools' in ' '.join(analysis.reasons).lower()


def test_scope_expansion_deviation(basic_contract):
    """Test that resource scope expansion is detected."""
    detector = DeviationDetector(basic_contract)

    tool_call = {
        'name': 'hold_transaction',
        'params': {'tx_id': '84722'},  # Different transaction
        'timestamp': '2026-08-12T10:02:00Z'
    }

    analysis = detector.analyze_tool_call(tool_call)
    assert analysis.scope_score >= 40
    assert 'scope' in ' '.join(analysis.reasons).lower()


def test_constraint_violation_deviation(basic_contract):
    """Test that constraint violations are detected."""
    detector = DeviationDetector(basic_contract)

    tool_call = {
        'name': 'send_customer_email',
        'params': {'account_id': '23891', 'message': 'test'},
        'timestamp': '2026-08-12T10:03:00Z'
    }

    analysis = detector.analyze_tool_call(tool_call)
    assert analysis.operation_score >= 30  # Constraint violation
    assert 'customer_communication' in ' '.join(analysis.reasons).lower() or \
           'constraint' in ' '.join(analysis.reasons).lower()


def test_severity_mapping():
    """Test severity mapping based on overall score."""
    contract = IntentContract(
        contract_id="test_001",
        goal="test",
        authorized_tools=["read_transaction"],
        resource_scope=ResourceScope(transaction_ids=["123"]),
        constraints=Constraints()
    )

    detector = DeviationDetector(contract)

    # Create analysis with different scores
    low_analysis = DeviationAnalysis(
        operation_score=0, scope_score=0, side_effects_score=0,
        sequence_score=0, overall_score=20, severity='LOW', reasons=[]
    )
    assert low_analysis.severity == 'LOW'

    medium_analysis = DeviationAnalysis(
        operation_score=50, scope_score=40, side_effects_score=30,
        sequence_score=20, overall_score=45, severity='MEDIUM', reasons=[]
    )
    assert medium_analysis.severity == 'MEDIUM'

    high_analysis = DeviationAnalysis(
        operation_score=80, scope_score=70, side_effects_score=60,
        sequence_score=50, overall_score=75, severity='HIGH', reasons=[]
    )
    assert high_analysis.severity == 'HIGH'
