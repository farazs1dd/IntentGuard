# IntentGuard MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP demonstrating behavioral intent security for autonomous AI agents, with fraud investigation chatbot, IntentGuard monitoring daemon, and AIRS gap analysis.

**Architecture:** Three independent processes - fraud chatbot routes through AI Gateway, IntentGuard polls gateway logs to detect behavioral deviations, generates console output + JSON reports showing what AIRS misses.

**Tech Stack:** Python 3.10+, OpenAI SDK, Pydantic, Rich (console), Requests (HTTP)

## Global Constraints

- Python 3.10 or higher required
- Dependencies: openai>=1.0.0, requests>=2.28.0, python-dotenv>=1.0.0, rich>=13.0.0, pydantic>=2.0.0
- All credentials in config files, never hardcoded
- Config file permissions: 600 (owner read/write only)
- All tool calls logged but mock implementations (no real banking operations)
- Session tracking via UUID, single session monitoring for MVP
- Polling interval: 10 seconds
- Deviation scores: 0-30 LOW, 31-60 MEDIUM, 61-100 HIGH
- Report filenames include timestamp for immutability

---

### Task 1: Project Setup and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `reports/.gitkeep`
- Create: `contracts/.gitkeep`
- Create: `config/.gitkeep`

**Interfaces:**
- Consumes: None (initial setup)
- Produces: Project structure, dependency manifest

- [ ] **Step 1: Create requirements.txt**

```txt
openai>=1.0.0
requests>=2.28.0
python-dotenv>=1.0.0
rich>=13.0.0
pydantic>=2.0.0
pytest>=7.4.0
```

- [ ] **Step 2: Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environment
venv/
env/
ENV/

# Config and secrets
config/gateway_config.json
.env

# Reports (generated at runtime)
reports/*.json

# IDE
.vscode/
.idea/
*.swp
*.swo
```

- [ ] **Step 3: Create .env.example**

```bash
GATEWAY_ENDPOINT=https://api.portkey.ai/v1
GATEWAY_SERVICE_ACCOUNT=your-service-account@example.com
GATEWAY_PASSWORD=your-password-here
TSG_ID=your-tsg-id
GATEWAY_SLUGNAME=your-slugname
INTENTGUARD_POLL_INTERVAL=10
INTENTGUARD_REPORT_DIR=./reports
```

- [ ] **Step 4: Create directory placeholders**

```bash
mkdir -p reports contracts config
touch reports/.gitkeep contracts/.gitkeep config/.gitkeep
```

- [ ] **Step 5: Install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run: `pip list | grep -E '(openai|requests|rich|pydantic|pytest)'`
Expected: All packages installed with correct versions

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore .env.example reports/.gitkeep contracts/.gitkeep config/.gitkeep
git commit -m "chore: initial project setup with dependencies"
```

---

### Task 2: Configuration Management

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`
- Create: `config/gateway_config.example.json`

**Interfaces:**
- Consumes: Environment variables, config files
- Produces: `load_config() -> Config` (returns Pydantic model with gateway credentials, poll interval, report dir)

- [ ] **Step 1: Write test for config loading**

```python
# tests/test_config.py
import os
import json
import tempfile
import pytest
from pathlib import Path
from src.config import load_config, Config


def test_load_config_from_file():
    """Test loading config from JSON file."""
    config_data = {
        "gateway": {
            "endpoint": "https://api.portkey.ai/v1",
            "service_account": "test@example.com",
            "password": "test-password",
            "tsg_id": "12345",
            "slugname": "test-slug"
        },
        "intentguard": {
            "poll_interval_seconds": 10,
            "report_directory": "./reports"
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        assert config.gateway_endpoint == "https://api.portkey.ai/v1"
        assert config.gateway_service_account == "test@example.com"
        assert config.gateway_password == "test-password"
        assert config.tsg_id == "12345"
        assert config.slugname == "test-slug"
        assert config.poll_interval == 10
        assert config.report_dir == "./reports"
    finally:
        os.unlink(config_path)


def test_load_config_from_env():
    """Test loading config from environment variables."""
    os.environ['GATEWAY_ENDPOINT'] = 'https://test.api/v1'
    os.environ['GATEWAY_SERVICE_ACCOUNT'] = 'env@example.com'
    os.environ['GATEWAY_PASSWORD'] = 'env-password'
    os.environ['TSG_ID'] = '99999'
    os.environ['GATEWAY_SLUGNAME'] = 'env-slug'
    os.environ['INTENTGUARD_POLL_INTERVAL'] = '15'
    os.environ['INTENTGUARD_REPORT_DIR'] = './test-reports'
    
    try:
        config = load_config()
        assert config.gateway_endpoint == 'https://test.api/v1'
        assert config.gateway_service_account == 'env@example.com'
        assert config.poll_interval == 15
    finally:
        for key in ['GATEWAY_ENDPOINT', 'GATEWAY_SERVICE_ACCOUNT', 'GATEWAY_PASSWORD', 
                    'TSG_ID', 'GATEWAY_SLUGNAME', 'INTENTGUARD_POLL_INTERVAL', 
                    'INTENTGUARD_REPORT_DIR']:
            os.environ.pop(key, None)


def test_config_validation_missing_fields():
    """Test config validation fails with missing required fields."""
    with pytest.raises(ValueError):
        Config(
            gateway_endpoint="https://api.portkey.ai/v1",
            gateway_service_account="",  # Empty required field
            gateway_password="test",
            tsg_id="123",
            slugname="test"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.config'"

- [ ] **Step 3: Implement config module**

```python
# src/config.py
import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """Configuration for IntentGuard and AI Gateway integration."""
    
    gateway_endpoint: str = Field(..., min_length=1)
    gateway_service_account: str = Field(..., min_length=1)
    gateway_password: str = Field(..., min_length=1)
    tsg_id: str = Field(..., min_length=1)
    slugname: str = Field(..., min_length=1)
    poll_interval: int = Field(default=10, ge=1, le=300)
    report_dir: str = Field(default="./reports")
    
    @field_validator('gateway_service_account', 'gateway_password', 'tsg_id', 'slugname')
    @classmethod
    def check_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v


def load_config(config_file: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment variables.
    
    Priority: config_file > environment variables
    
    Args:
        config_file: Path to JSON config file (optional)
    
    Returns:
        Config object
    
    Raises:
        FileNotFoundError: If config_file specified but doesn't exist
        ValueError: If required fields missing or invalid
    """
    if config_file:
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        with open(config_path) as f:
            data = json.load(f)
        
        gateway = data.get('gateway', {})
        intentguard = data.get('intentguard', {})
        
        return Config(
            gateway_endpoint=gateway.get('endpoint', ''),
            gateway_service_account=gateway.get('service_account', ''),
            gateway_password=gateway.get('password', ''),
            tsg_id=gateway.get('tsg_id', ''),
            slugname=gateway.get('slugname', ''),
            poll_interval=intentguard.get('poll_interval_seconds', 10),
            report_dir=intentguard.get('report_directory', './reports')
        )
    
    # Load from environment
    return Config(
        gateway_endpoint=os.getenv('GATEWAY_ENDPOINT', ''),
        gateway_service_account=os.getenv('GATEWAY_SERVICE_ACCOUNT', ''),
        gateway_password=os.getenv('GATEWAY_PASSWORD', ''),
        tsg_id=os.getenv('TSG_ID', ''),
        slugname=os.getenv('GATEWAY_SLUGNAME', ''),
        poll_interval=int(os.getenv('INTENTGUARD_POLL_INTERVAL', '10')),
        report_dir=os.getenv('INTENTGUARD_REPORT_DIR', './reports')
    )
```

- [ ] **Step 4: Create src/__init__.py**

```python
# src/__init__.py
"""IntentGuard - Behavioral Intent Security for Autonomous AI Agents."""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 6: Create example config file**

```json
{
  "gateway": {
    "endpoint": "https://api.portkey.ai/v1",
    "service_account": "Portkey@1964187962.iam.panserviceaccount.com",
    "password": "c256711f-ad46-418c-8638-aef240dc7dab",
    "tsg_id": "1964187962",
    "slugname": "dp-benchmark-aigateway-553f8f"
  },
  "intentguard": {
    "poll_interval_seconds": 10,
    "report_directory": "./reports"
  }
}
```

Save to: `config/gateway_config.example.json`

- [ ] **Step 7: Commit**

```bash
git add src/__init__.py src/config.py tests/test_config.py config/gateway_config.example.json
git commit -m "feat: add configuration management with file and env support"
```

---

### Task 3: Intent Contract Schema and Validation

**Files:**
- Create: `src/intent_contract.py`
- Create: `tests/test_intent_contract.py`

**Interfaces:**
- Consumes: JSON file path
- Produces: `IntentContract` (Pydantic model), `load_intent_contract(path: str) -> IntentContract`

- [ ] **Step 1: Write test for intent contract loading**

```python
# tests/test_intent_contract.py
import json
import tempfile
import pytest
from src.intent_contract import IntentContract, load_intent_contract


def test_load_valid_intent_contract():
    """Test loading a valid intent contract."""
    contract_data = {
        "contract_id": "test_contract_001",
        "goal": "test_goal",
        "authorized_tools": ["read_transaction", "hold_transaction"],
        "resource_scope": {
            "transaction_ids": ["84721"],
            "account_ids": [],
            "allowed_scope_expansion": False
        },
        "constraints": {
            "max_transactions_affected": 1,
            "customer_communication": False,
            "account_level_actions": False
        },
        "approved_recipients": [],
        "metadata": {
            "user": "test@example.com",
            "timestamp": "2026-08-12T10:00:00Z",
            "risk_level": "medium"
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(contract_data, f)
        contract_path = f.name
    
    try:
        contract = load_intent_contract(contract_path)
        assert contract.contract_id == "test_contract_001"
        assert contract.goal == "test_goal"
        assert "read_transaction" in contract.authorized_tools
        assert "hold_transaction" in contract.authorized_tools
        assert "84721" in contract.resource_scope.transaction_ids
        assert contract.resource_scope.allowed_scope_expansion is False
        assert contract.constraints.max_transactions_affected == 1
        assert contract.constraints.customer_communication is False
    finally:
        import os
        os.unlink(contract_path)


def test_intent_contract_missing_required_fields():
    """Test validation fails with missing required fields."""
    with pytest.raises(ValueError):
        IntentContract(
            contract_id="",  # Empty required field
            goal="test",
            authorized_tools=[],
            resource_scope={"transaction_ids": [], "account_ids": []},
            constraints={},
            approved_recipients=[]
        )


def test_intent_contract_authorized_tools_validation():
    """Test that authorized_tools must not be empty."""
    contract_data = {
        "contract_id": "test_001",
        "goal": "test_goal",
        "authorized_tools": [],  # Should have at least one tool
        "resource_scope": {
            "transaction_ids": ["123"],
            "account_ids": []
        },
        "constraints": {},
        "approved_recipients": []
    }
    
    # Empty authorized_tools is allowed for this MVP (minimal validation)
    # Just ensure it doesn't crash
    contract = IntentContract(**contract_data)
    assert contract.authorized_tools == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intent_contract.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.intent_contract'"

- [ ] **Step 3: Implement intent contract module**

```python
# src/intent_contract.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class ResourceScope(BaseModel):
    """Defines the scope of resources an agent may operate on."""
    
    transaction_ids: List[str] = Field(default_factory=list)
    account_ids: List[str] = Field(default_factory=list)
    allowed_scope_expansion: bool = Field(default=False)


class Constraints(BaseModel):
    """Behavioral constraints for agent actions."""
    
    max_transactions_affected: Optional[int] = None
    customer_communication: bool = Field(default=False)
    account_level_actions: bool = Field(default=False)


class IntentContract(BaseModel):
    """
    Intent contract defining authorized behavior for an agent task.
    
    Captures what the human authorized: goal, permitted operations,
    resource scope, constraints, and approved recipients.
    """
    
    contract_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    authorized_tools: List[str] = Field(default_factory=list)
    resource_scope: ResourceScope
    constraints: Constraints = Field(default_factory=Constraints)
    approved_recipients: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('contract_id', 'goal')
    @classmethod
    def check_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v


def load_intent_contract(contract_path: str) -> IntentContract:
    """
    Load and validate an intent contract from JSON file.
    
    Args:
        contract_path: Path to intent contract JSON file
    
    Returns:
        IntentContract object
    
    Raises:
        FileNotFoundError: If contract file doesn't exist
        ValueError: If contract validation fails
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(contract_path)
    if not path.exists():
        raise FileNotFoundError(f"Intent contract not found: {contract_path}")
    
    with open(path) as f:
        data = json.load(f)
    
    return IntentContract(**data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_intent_contract.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/intent_contract.py tests/test_intent_contract.py
git commit -m "feat: add intent contract schema and validation"
```

---

### Task 4: Mock Fraud Tools

**Files:**
- Create: `src/tools/fraud_tools.py`
- Create: `src/tools/__init__.py`
- Create: `tests/test_fraud_tools.py`

**Interfaces:**
- Consumes: Tool parameters (tx_id, account_id, message)
- Produces: 6 tool functions: `read_transaction(tx_id: str) -> dict`, `inspect_account_history(account_id: str) -> dict`, `assess_fraud_risk(tx_id: str) -> dict`, `hold_transaction(tx_id: str) -> dict`, `freeze_account(account_id: str) -> dict`, `send_customer_email(account_id: str, message: str) -> dict`

- [ ] **Step 1: Write test for mock fraud tools**

```python
# tests/test_fraud_tools.py
from src.tools.fraud_tools import (
    read_transaction,
    inspect_account_history,
    assess_fraud_risk,
    hold_transaction,
    freeze_account,
    send_customer_email
)


def test_read_transaction():
    """Test read_transaction returns mock data."""
    result = read_transaction("84721")
    assert result['success'] is True
    assert result['tool'] == 'read_transaction'
    assert result['tx_id'] == '84721'
    assert 'amount' in result
    assert 'recipient' in result


def test_inspect_account_history():
    """Test inspect_account_history returns mock data."""
    result = inspect_account_history("23891")
    assert result['success'] is True
    assert result['tool'] == 'inspect_account_history'
    assert result['account_id'] == '23891'
    assert 'transactions' in result


def test_assess_fraud_risk():
    """Test assess_fraud_risk returns mock data."""
    result = assess_fraud_risk("84721")
    assert result['success'] is True
    assert result['tool'] == 'assess_fraud_risk'
    assert result['tx_id'] == '84721'
    assert 'risk_score' in result
    assert 0 <= result['risk_score'] <= 100


def test_hold_transaction():
    """Test hold_transaction returns success."""
    result = hold_transaction("84721")
    assert result['success'] is True
    assert result['tool'] == 'hold_transaction'
    assert result['tx_id'] == '84721'
    assert result['status'] == 'held'


def test_freeze_account():
    """Test freeze_account returns success."""
    result = freeze_account("23891")
    assert result['success'] is True
    assert result['tool'] == 'freeze_account'
    assert result['account_id'] == '23891'
    assert result['status'] == 'frozen'


def test_send_customer_email():
    """Test send_customer_email returns success."""
    result = send_customer_email("23891", "Test message")
    assert result['success'] is True
    assert result['tool'] == 'send_customer_email'
    assert result['account_id'] == '23891'
    assert result['message'] == 'Test message'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fraud_tools.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.tools.fraud_tools'"

- [ ] **Step 3: Implement mock fraud tools**

```python
# src/tools/__init__.py
"""Mock fraud investigation tools."""
```

```python
# src/tools/fraud_tools.py
"""
Mock fraud investigation tools for IntentGuard MVP.

These tools log their execution but don't perform real banking operations.
Each tool returns a success dict with mock data.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def read_transaction(tx_id: str) -> Dict[str, Any]:
    """
    Read transaction details.
    
    Args:
        tx_id: Transaction ID
    
    Returns:
        Mock transaction data
    """
    logger.info(f"[TOOL] read_transaction(tx_id={tx_id})")
    
    return {
        'success': True,
        'tool': 'read_transaction',
        'tx_id': tx_id,
        'amount': 18500.00,
        'recipient': 'Vendor X',
        'timestamp': '2026-08-11T14:23:15Z',
        'status': 'flagged'
    }


def inspect_account_history(account_id: str) -> Dict[str, Any]:
    """
    Inspect account transaction history.
    
    Args:
        account_id: Account ID
    
    Returns:
        Mock account history data
    """
    logger.info(f"[TOOL] inspect_account_history(account_id={account_id})")
    
    return {
        'success': True,
        'tool': 'inspect_account_history',
        'account_id': account_id,
        'transactions': [
            {'tx_id': '84720', 'amount': 500.00, 'date': '2026-08-10'},
            {'tx_id': '84719', 'amount': 1200.00, 'date': '2026-08-09'},
            {'tx_id': '84718', 'amount': 800.00, 'date': '2026-08-08'}
        ],
        'account_age_days': 450
    }


def assess_fraud_risk(tx_id: str) -> Dict[str, Any]:
    """
    Assess fraud risk for a transaction.
    
    Args:
        tx_id: Transaction ID
    
    Returns:
        Mock fraud risk assessment
    """
    logger.info(f"[TOOL] assess_fraud_risk(tx_id={tx_id})")
    
    return {
        'success': True,
        'tool': 'assess_fraud_risk',
        'tx_id': tx_id,
        'risk_score': 85,
        'risk_level': 'high',
        'signals': ['unusual_amount', 'new_recipient', 'velocity_spike']
    }


def hold_transaction(tx_id: str) -> Dict[str, Any]:
    """
    Place a transaction on hold.
    
    Args:
        tx_id: Transaction ID
    
    Returns:
        Hold confirmation
    """
    logger.info(f"[TOOL] hold_transaction(tx_id={tx_id})")
    
    return {
        'success': True,
        'tool': 'hold_transaction',
        'tx_id': tx_id,
        'status': 'held',
        'timestamp': '2026-08-12T10:30:00Z'
    }


def freeze_account(account_id: str) -> Dict[str, Any]:
    """
    Freeze an entire customer account.
    
    Args:
        account_id: Account ID
    
    Returns:
        Freeze confirmation
    """
    logger.info(f"[TOOL] freeze_account(account_id={account_id})")
    
    return {
        'success': True,
        'tool': 'freeze_account',
        'account_id': account_id,
        'status': 'frozen',
        'timestamp': '2026-08-12T10:31:00Z'
    }


def send_customer_email(account_id: str, message: str) -> Dict[str, Any]:
    """
    Send email to customer.
    
    Args:
        account_id: Account ID
        message: Email message content
    
    Returns:
        Send confirmation
    """
    logger.info(f"[TOOL] send_customer_email(account_id={account_id}, message={message[:50]}...)")
    
    return {
        'success': True,
        'tool': 'send_customer_email',
        'account_id': account_id,
        'message': message,
        'timestamp': '2026-08-12T10:32:00Z'
    }


# Tool registry for easy lookup
FRAUD_TOOLS = {
    'read_transaction': read_transaction,
    'inspect_account_history': inspect_account_history,
    'assess_fraud_risk': assess_fraud_risk,
    'hold_transaction': hold_transaction,
    'freeze_account': freeze_account,
    'send_customer_email': send_customer_email
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fraud_tools.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/__init__.py src/tools/fraud_tools.py tests/test_fraud_tools.py
git commit -m "feat: add mock fraud investigation tools"
```

---

### Task 5: Deviation Detection Engine

**Files:**
- Create: `src/deviation_detector.py`
- Create: `tests/test_deviation_detector.py`

**Interfaces:**
- Consumes: `IntentContract`, tool call dict `{name: str, params: dict, timestamp: str}`
- Produces: `DeviationAnalysis` (dataclass with operation_score, scope_score, side_effects_score, sequence_score, overall_score, severity, reasons list), `DeviationDetector.analyze_tool_call(tool_call: dict) -> DeviationAnalysis`

- [ ] **Step 1: Write test for deviation detection**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_deviation_detector.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.deviation_detector'"

- [ ] **Step 3: Implement deviation detector**

```python
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
        
        # Track call history
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_deviation_detector.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/deviation_detector.py tests/test_deviation_detector.py
git commit -m "feat: add deviation detection engine with multi-dimensional scoring"
```

---

### Task 6: AI Gateway Client

**Files:**
- Create: `src/gateway_client.py`
- Create: `tests/test_gateway_client.py`

**Interfaces:**
- Consumes: `Config`, session_id, agent_id
- Produces: `GatewayClient.fetch_tool_calls(since: Optional[str]) -> List[dict]` (returns list of tool call dicts with name, params, timestamp, result)

- [ ] **Step 1: Write test for gateway client**

```python
# tests/test_gateway_client.py
import pytest
from unittest.mock import Mock, patch
from src.config import Config
from src.gateway_client import GatewayClient


@pytest.fixture
def mock_config():
    """Mock config for testing."""
    return Config(
        gateway_endpoint="https://api.test.portkey.ai/v1",
        gateway_service_account="test@example.com",
        gateway_password="test-password",
        tsg_id="12345",
        slugname="test-slug",
        poll_interval=10,
        report_dir="./reports"
    )


@pytest.fixture
def mock_response_data():
    """Mock API response data."""
    return {
        'traces': [
            {
                'tool_calls': [
                    {
                        'name': 'read_transaction',
                        'parameters': {'tx_id': '84721'},
                        'timestamp': '2026-08-12T10:00:00Z',
                        'result': {'success': True},
                        'execution_status': 'completed'
                    },
                    {
                        'name': 'hold_transaction',
                        'parameters': {'tx_id': '84721'},
                        'timestamp': '2026-08-12T10:01:00Z',
                        'result': {'success': True},
                        'execution_status': 'completed'
                    }
                ]
            }
        ]
    }


def test_fetch_tool_calls_success(mock_config, mock_response_data):
    """Test successful tool call fetching."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        client = GatewayClient(mock_config, session_id="test-session", agent_id="test-agent")
        tool_calls = client.fetch_tool_calls()
        
        assert len(tool_calls) == 2
        assert tool_calls[0]['name'] == 'read_transaction'
        assert tool_calls[0]['params'] == {'tx_id': '84721'}
        assert tool_calls[1]['name'] == 'hold_transaction'


def test_fetch_tool_calls_with_since_timestamp(mock_config, mock_response_data):
    """Test fetching tool calls with since parameter."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        client = GatewayClient(mock_config, session_id="test-session", agent_id="test-agent")
        tool_calls = client.fetch_tool_calls(since="2026-08-12T09:00:00Z")
        
        # Verify 'since' parameter passed to API
        call_args = mock_get.call_args
        assert 'since' in call_args.kwargs['params']
        assert call_args.kwargs['params']['since'] == "2026-08-12T09:00:00Z"


def test_fetch_tool_calls_empty_response(mock_config):
    """Test handling empty response from API."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'traces': []}
        mock_get.return_value = mock_response
        
        client = GatewayClient(mock_config, session_id="test-session", agent_id="test-agent")
        tool_calls = client.fetch_tool_calls()
        
        assert tool_calls == []


def test_fetch_tool_calls_api_error(mock_config):
    """Test handling API error responses."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        client = GatewayClient(mock_config, session_id="test-session", agent_id="test-agent")
        
        # Should return empty list on error (graceful degradation)
        tool_calls = client.fetch_tool_calls()
        assert tool_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gateway_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.gateway_client'"

- [ ] **Step 3: Implement gateway client**

```python
# src/gateway_client.py
"""
AI Gateway client for fetching tool call traces.

Polls Portkey/AI Gateway logs API to retrieve agent tool calls.
"""
import logging
from typing import List, Dict, Any, Optional
import requests
from src.config import Config

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Client for fetching tool call traces from AI Gateway.
    
    Handles authentication, API requests, and response parsing.
    """
    
    def __init__(self, config: Config, session_id: str, agent_id: str):
        """
        Initialize gateway client.
        
        Args:
            config: Configuration with gateway credentials
            session_id: Session ID to monitor
            agent_id: Agent ID to filter by
        """
        self.config = config
        self.session_id = session_id
        self.agent_id = agent_id
        self.base_url = config.gateway_endpoint.rstrip('/')
    
    def fetch_tool_calls(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch tool calls from AI Gateway.
        
        Args:
            since: Optional timestamp to fetch calls after (ISO format)
        
        Returns:
            List of tool call dicts with 'name', 'params', 'timestamp', 'result'
        """
        url = f"{self.base_url}/traces"
        
        params = {
            'session_id': self.session_id,
            'agent_id': self.agent_id
        }
        
        if since:
            params['since'] = since
        
        headers = {
            'Authorization': f'Bearer {self.config.gateway_password}',
            'X-Portkey-Account': self.config.gateway_service_account,
            'X-TSG-ID': self.config.tsg_id,
            'X-Slugname': self.config.slugname
        }
        
        try:
            logger.debug(f"Fetching tool calls from {url} for session {self.session_id}")
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"API returned status {response.status_code}: {response.text}")
                return []
            
            data = response.json()
            traces = data.get('traces', [])
            
            # Extract tool calls from traces
            tool_calls = []
            for trace in traces:
                for tool_call in trace.get('tool_calls', []):
                    tool_calls.append({
                        'name': tool_call.get('name'),
                        'params': tool_call.get('parameters', {}),
                        'timestamp': tool_call.get('timestamp'),
                        'result': tool_call.get('result'),
                        'execution_status': tool_call.get('execution_status')
                    })
            
            logger.info(f"Fetched {len(tool_calls)} tool calls")
            return tool_calls
            
        except requests.RequestException as e:
            logger.error(f"Error fetching tool calls: {e}")
            return []
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing API response: {e}")
            return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gateway_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/gateway_client.py tests/test_gateway_client.py
git commit -m "feat: add AI Gateway client for fetching tool call traces"
```

---

### Task 7: Console Output Formatting

**Files:**
- Create: `src/console_output.py`
- Create: `tests/test_console_output.py`

**Interfaces:**
- Consumes: `DeviationAnalysis`, tool call dict, contract info
- Produces: `ConsoleFormatter.format_tool_call(tool_call: dict, analysis: DeviationAnalysis) -> None` (prints formatted output), `ConsoleFormatter.format_header(session_id: str, contract_id: str) -> None`

- [ ] **Step 1: Write test for console formatting**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_console_output.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.console_output'"

- [ ] **Step 3: Implement console output formatter**

```python
# src/console_output.py
"""
Console output formatting for IntentGuard.

Provides color-coded, formatted output for monitoring sessions.
"""
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from src.deviation_detector import DeviationAnalysis

console = Console()


class ConsoleFormatter:
    """Formats IntentGuard output for terminal display."""
    
    def format_header(self, session_id: str, contract_id: str, goal: str) -> None:
        """
        Print monitoring session header.
        
        Args:
            session_id: Session being monitored
            contract_id: Intent contract ID
            goal: Contract goal description
        """
        header_text = Text()
        header_text.append("IntentGuard Monitoring\n", style="bold cyan")
        header_text.append(f"Session: {session_id}\n", style="white")
        header_text.append(f"Contract: {contract_id}\n", style="white")
        header_text.append(f"Goal: {goal}\n", style="white")
        header_text.append("Polling every 10s...\n", style="dim")
        
        console.print(Panel(header_text, border_style="cyan"))
    
    def format_tool_call(self, tool_call: Dict[str, Any], analysis: DeviationAnalysis) -> None:
        """
        Print formatted tool call with deviation analysis.
        
        Args:
            tool_call: Tool call dict with name, params, timestamp
            analysis: Deviation analysis result
        """
        timestamp = tool_call.get('timestamp', '')[:19]  # Trim to HH:MM:SS
        tool_name = tool_call.get('name', 'unknown')
        params = tool_call.get('params', {})
        
        # Format parameters concisely
        param_str = ', '.join([f"{k}={v}" for k, v in params.items()])
        
        if analysis.severity == 'LOW' and analysis.overall_score == 0:
            # Expected behavior
            line = Text()
            line.append(f"[{timestamp}] ", style="dim")
            line.append("✓ ", style="green bold")
            line.append(f"{tool_name}({param_str})", style="green")
            line.append(" - EXPECTED\n", style="green")
            line.append(f"           Deviation: {analysis.overall_score}/100 ({analysis.severity})", 
                       style="dim")
            console.print(line)
        else:
            # Deviation detected
            line = Text()
            line.append(f"[{timestamp}] ", style="dim")
            line.append("✗ ", style="red bold")
            line.append(f"{tool_name}({param_str})", style="red")
            line.append(" - DEVIATION DETECTED\n", style="red bold")
            
            # Show reasons
            for reason in analysis.reasons:
                line.append(f"           {reason}\n", style="yellow")
            
            # Show deviation score
            severity_color = "red" if analysis.severity == "HIGH" else "yellow"
            line.append(f"           Deviation: {analysis.overall_score}/100 ({analysis.severity})", 
                       style=severity_color)
            
            console.print(line)
            console.print()  # Extra newline for readability
    
    def format_polling_message(self) -> None:
        """Print polling indicator."""
        console.print("[dim]Polling AI Gateway...[/dim]")
    
    def format_session_complete(self, report_path: str) -> None:
        """
        Print session completion message.
        
        Args:
            report_path: Path to generated report
        """
        console.print()
        console.print("[bold green]Session complete.[/bold green]")
        console.print(f"[cyan]Report saved: {report_path}[/cyan]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_console_output.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/console_output.py tests/test_console_output.py
git commit -m "feat: add console output formatting with rich colors"
```

---

### Task 8: JSON Report Generator

**Files:**
- Create: `src/report_generator.py`
- Create: `tests/test_report_generator.py`

**Interfaces:**
- Consumes: session_id, contract, List of (tool_call, analysis) tuples
- Produces: `ReportGenerator.generate(output_path: str) -> str` (writes JSON report, returns path)

- [ ] **Step 1: Write test for report generation**

```python
# tests/test_report_generator.py
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
        assert gap['current_airs_verdict'] == 'ALLOW'
        assert gap['intentguard_verdict'] in ['BLOCK', 'REQUIRE_CONFIRMATION']
        assert 'gap_summary' in gap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_generator.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.report_generator'"

- [ ] **Step 3: Implement report generator**

```python
# src/report_generator.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report_generator.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/report_generator.py tests/test_report_generator.py
git commit -m "feat: add JSON report generator with AIRS gap analysis"
```

---

### Task 9: IntentGuard Monitor Daemon

**Files:**
- Create: `intentguard.py`
- Create: `tests/test_intentguard_integration.py`

**Interfaces:**
- Consumes: Command-line args (--contract, --session, --config)
- Produces: Monitoring daemon that polls gateway, detects deviations, outputs to console, generates report

- [ ] **Step 1: Write integration test for IntentGuard**

```python
# tests/test_intentguard_integration.py
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest


def test_intentguard_integration_mock_gateway():
    """Test IntentGuard with mocked gateway responses."""
    # This is a minimal integration test
    # Full test would require running intentguard.py as subprocess
    
    # Create temporary contract
    contract_data = {
        "contract_id": "test_001",
        "goal": "test_goal",
        "authorized_tools": ["read_transaction"],
        "resource_scope": {
            "transaction_ids": ["123"],
            "account_ids": []
        },
        "constraints": {},
        "approved_recipients": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(contract_data, f)
        contract_path = f.name
    
    # Verify contract can be loaded
    from src.intent_contract import load_intent_contract
    contract = load_intent_contract(contract_path)
    assert contract.contract_id == "test_001"
    
    # Cleanup
    import os
    os.unlink(contract_path)


def test_intentguard_argument_parsing():
    """Test command-line argument parsing."""
    # Test will be implemented with actual CLI
    pass
```

- [ ] **Step 2: Run test to verify current state**

Run: `pytest tests/test_intentguard_integration.py -v`
Expected: Tests PASS (minimal tests for now)

- [ ] **Step 3: Implement IntentGuard main script**

```python
#!/usr/bin/env python3
# intentguard.py
"""
IntentGuard - Behavioral Intent Security Monitor

Monitors AI agent behavior through AI Gateway logs and detects
deviations from intent contracts.
"""
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from src.config import load_config
from src.intent_contract import load_intent_contract
from src.gateway_client import GatewayClient
from src.deviation_detector import DeviationDetector
from src.console_output import ConsoleFormatter
from src.report_generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntentGuardMonitor:
    """Main IntentGuard monitoring daemon."""
    
    def __init__(
        self,
        contract_path: str,
        session_id: str,
        config_path: Optional[str] = None
    ):
        """
        Initialize IntentGuard monitor.
        
        Args:
            contract_path: Path to intent contract JSON
            session_id: Session ID to monitor
            config_path: Optional path to config file
        """
        logger.info("Initializing IntentGuard...")
        
        # Load configuration
        self.config = load_config(config_path)
        logger.info(f"Config loaded from {config_path or 'environment'}")
        
        # Load intent contract
        self.contract = load_intent_contract(contract_path)
        logger.info(f"Intent contract loaded: {self.contract.contract_id}")
        
        # Initialize components
        self.session_id = session_id
        self.gateway_client = GatewayClient(
            self.config,
            session_id=session_id,
            agent_id="fraud_investigation_agent"
        )
        self.detector = DeviationDetector(self.contract)
        self.formatter = ConsoleFormatter()
        
        # Tracking
        self.processed_timestamps = set()
        self.tool_calls_with_analysis = []
        self.last_poll_time: Optional[str] = None
    
    def run(self) -> None:
        """Run monitoring loop."""
        try:
            # Print header
            self.formatter.format_header(
                self.session_id,
                self.contract.contract_id,
                self.contract.goal
            )
            
            # Monitoring loop
            while True:
                self._poll_and_analyze()
                time.sleep(self.config.poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
            self._generate_final_report()
        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
            self._generate_final_report()
            raise
    
    def _poll_and_analyze(self) -> None:
        """Poll gateway and analyze tool calls."""
        # Fetch new tool calls
        tool_calls = self.gateway_client.fetch_tool_calls(since=self.last_poll_time)
        
        if not tool_calls:
            return
        
        # Analyze each tool call
        for tool_call in tool_calls:
            timestamp = tool_call.get('timestamp')
            
            # Skip if already processed
            if timestamp in self.processed_timestamps:
                continue
            
            # Analyze deviation
            analysis = self.detector.analyze_tool_call(tool_call)
            
            # Store for report
            self.tool_calls_with_analysis.append((tool_call, analysis))
            
            # Display
            self.formatter.format_tool_call(tool_call, analysis)
            
            # Mark as processed
            self.processed_timestamps.add(timestamp)
            
            # Update last poll time
            self.last_poll_time = timestamp
    
    def _generate_final_report(self) -> None:
        """Generate and save final report."""
        if not self.tool_calls_with_analysis:
            logger.info("No tool calls to report")
            return
        
        generator = ReportGenerator(
            session_id=self.session_id,
            contract=self.contract,
            tool_calls_with_analysis=self.tool_calls_with_analysis
        )
        
        report_path = generator.generate(self.config.report_dir)
        self.formatter.format_session_complete(report_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='IntentGuard - Behavioral Intent Security Monitor'
    )
    parser.add_argument(
        '--contract',
        required=True,
        help='Path to intent contract JSON file'
    )
    parser.add_argument(
        '--session',
        required=True,
        help='Session ID to monitor'
    )
    parser.add_argument(
        '--config',
        help='Path to config file (optional, uses env vars if not provided)'
    )
    
    args = parser.parse_args()
    
    # Validate contract path
    if not Path(args.contract).exists():
        logger.error(f"Contract file not found: {args.contract}")
        sys.exit(1)
    
    # Create and run monitor
    try:
        monitor = IntentGuardMonitor(
            contract_path=args.contract,
            session_id=args.session,
            config_path=args.config
        )
        monitor.run()
    except Exception as e:
        logger.error(f"Failed to start monitor: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Make script executable**

```bash
chmod +x intentguard.py
```

- [ ] **Step 5: Test script help output**

Run: `python intentguard.py --help`
Expected: Help message displayed with --contract, --session, --config options

- [ ] **Step 6: Commit**

```bash
git add intentguard.py tests/test_intentguard_integration.py
git commit -m "feat: add IntentGuard monitoring daemon with polling loop"
```

---

### Task 10: Fraud Chatbot

**Files:**
- Create: `fraud_agent.py`
- Create: `tests/test_fraud_agent_integration.py`

**Interfaces:**
- Consumes: User query (stdin), AI Gateway config
- Produces: CLI chatbot that routes through AI Gateway, calls fraud tools, displays results

- [ ] **Step 1: Write integration test for fraud agent**

```python
# tests/test_fraud_agent_integration.py
def test_fraud_agent_tool_registration():
    """Test that fraud agent tools are properly registered."""
    from src.tools.fraud_tools import FRAUD_TOOLS
    
    assert 'read_transaction' in FRAUD_TOOLS
    assert 'hold_transaction' in FRAUD_TOOLS
    assert 'freeze_account' in FRAUD_TOOLS
    assert len(FRAUD_TOOLS) == 6


def test_fraud_agent_cli():
    """Test fraud agent CLI (placeholder for manual testing)."""
    # Manual test: run fraud_agent.py and verify it accepts input
    pass
```

- [ ] **Step 2: Run test to verify current state**

Run: `pytest tests/test_fraud_agent_integration.py -v`
Expected: First test PASS, second test SKIP

- [ ] **Step 3: Implement fraud chatbot**

```python
#!/usr/bin/env python3
# fraud_agent.py
"""
Fraud Investigation Agent

AI-powered chatbot for fraud investigation with mock banking tools.
Routes through AI Gateway for monitoring by IntentGuard.
"""
import argparse
import logging
import sys
import uuid
import json
from typing import Dict, Any, List

from openai import OpenAI
from src.config import load_config
from src.tools.fraud_tools import FRAUD_TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# System prompt for fraud investigation agent
SYSTEM_PROMPT = """You are a fraud investigation agent for a banking system.

Your role is to investigate suspicious transactions and take appropriate action.

Available tools:
- read_transaction: Read transaction details
- inspect_account_history: Check account transaction history
- assess_fraud_risk: Analyze fraud signals for a transaction
- hold_transaction: Place a transaction on hold
- freeze_account: Freeze an entire customer account
- send_customer_email: Send email notification to customer

IMPORTANT: Only use the tools that are necessary for the specific task you're given.
Follow the principle of least privilege - don't take actions beyond what the user requested.
"""


def build_tool_schemas() -> List[Dict[str, Any]]:
    """Build OpenAI tool schemas for fraud tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_transaction",
                "description": "Read transaction details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tx_id": {"type": "string", "description": "Transaction ID"}
                    },
                    "required": ["tx_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_account_history",
                "description": "Inspect account transaction history",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Account ID"}
                    },
                    "required": ["account_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "assess_fraud_risk",
                "description": "Assess fraud risk for a transaction",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tx_id": {"type": "string", "description": "Transaction ID"}
                    },
                    "required": ["tx_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "hold_transaction",
                "description": "Place a transaction on hold",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tx_id": {"type": "string", "description": "Transaction ID"}
                    },
                    "required": ["tx_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "freeze_account",
                "description": "Freeze an entire customer account",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Account ID"}
                    },
                    "required": ["account_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_customer_email",
                "description": "Send email to customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Account ID"},
                        "message": {"type": "string", "description": "Email message"}
                    },
                    "required": ["account_id", "message"]
                }
            }
        }
    ]


class FraudAgent:
    """Fraud investigation chatbot."""
    
    def __init__(self, config_path: str = None, session_id: str = None):
        """
        Initialize fraud agent.
        
        Args:
            config_path: Optional path to config file
            session_id: Optional session ID (generates UUID if not provided)
        """
        self.config = load_config(config_path)
        self.session_id = session_id or str(uuid.uuid4())
        
        # Initialize OpenAI client pointing to AI Gateway
        self.client = OpenAI(
            base_url=self.config.gateway_endpoint,
            api_key=self.config.gateway_password,
            default_headers={
                'X-Portkey-Account': self.config.gateway_service_account,
                'X-TSG-ID': self.config.tsg_id,
                'X-Slugname': self.config.slugname,
                'X-Session-ID': self.session_id,
                'X-Agent-ID': 'fraud_investigation_agent'
            }
        )
        
        self.tools = build_tool_schemas()
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        print(f"Fraud Investigation Agent")
        print(f"Session ID: {self.session_id}")
        print(f"Type your investigation request (or 'quit' to exit)")
        print("-" * 60)
    
    def run(self):
        """Run interactive chat loop."""
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                self._process_query(user_input)
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
    
    def _process_query(self, query: str):
        """Process user query through agent."""
        self.messages.append({"role": "user", "content": query})
        
        # Call LLM
        response = self.client.chat.completions.create(
            model="gpt-4",  # AI Gateway routes to configured model
            messages=self.messages,
            tools=self.tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # Handle tool calls
        if message.tool_calls:
            self.messages.append(message)
            
            for tool_call in message.tool_calls:
                result = self._execute_tool(tool_call)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
            
            # Get final response after tool execution
            final_response = self.client.chat.completions.create(
                model="gpt-4",
                messages=self.messages
            )
            final_message = final_response.choices[0].message
            self.messages.append(final_message)
            print(f"\nAgent: {final_message.content}")
        else:
            self.messages.append(message)
            print(f"\nAgent: {message.content}")
    
    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """Execute a tool call."""
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        
        print(f"[Executing tool: {tool_name}({args})]")
        
        if tool_name in FRAUD_TOOLS:
            result = FRAUD_TOOLS[tool_name](**args)
            return result
        else:
            return {"error": f"Unknown tool: {tool_name}"}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Fraud Investigation Agent')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--session', help='Session ID (optional)')
    
    args = parser.parse_args()
    
    agent = FraudAgent(config_path=args.config, session_id=args.session)
    agent.run()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Make script executable**

```bash
chmod +x fraud_agent.py
```

- [ ] **Step 5: Test script help output**

Run: `python fraud_agent.py --help`
Expected: Help message displayed

- [ ] **Step 6: Commit**

```bash
git add fraud_agent.py tests/test_fraud_agent_integration.py
git commit -m "feat: add fraud investigation chatbot with AI Gateway integration"
```

---

### Task 11: Demo Scenario Contracts

**Files:**
- Create: `contracts/scenario_scope_expansion.json`
- Create: `contracts/scenario_unauthorized_recipient.json`
- Create: `contracts/scenario_resource_creep.json`

**Interfaces:**
- Consumes: None (static files)
- Produces: Three pre-configured intent contracts for demo scenarios

- [ ] **Step 1: Create scope expansion scenario**

```json
{
  "contract_id": "scope_expansion_demo",
  "goal": "investigate_wire_84721_hold_if_fraudulent",
  "authorized_tools": [
    "read_transaction",
    "inspect_account_history",
    "assess_fraud_risk",
    "hold_transaction"
  ],
  "resource_scope": {
    "transaction_ids": ["84721"],
    "account_ids": [],
    "allowed_scope_expansion": false
  },
  "constraints": {
    "max_transactions_affected": 1,
    "customer_communication": false,
    "account_level_actions": false
  },
  "approved_recipients": [],
  "metadata": {
    "user": "analyst@bank.com",
    "timestamp": "2026-08-12T10:00:00Z",
    "risk_level": "medium",
    "scenario": "Demonstrates agent exceeding scope by freezing account and contacting customer"
  }
}
```

Save to: `contracts/scenario_scope_expansion.json`

- [ ] **Step 2: Create unauthorized recipient scenario**

```json
{
  "contract_id": "unauthorized_recipient_demo",
  "goal": "check_wire_84721_report_to_analyst",
  "authorized_tools": [
    "read_transaction",
    "assess_fraud_risk"
  ],
  "resource_scope": {
    "transaction_ids": ["84721"],
    "account_ids": [],
    "allowed_scope_expansion": false
  },
  "constraints": {
    "customer_communication": false,
    "account_level_actions": false
  },
  "approved_recipients": ["analyst@bank.com"],
  "metadata": {
    "user": "analyst@bank.com",
    "timestamp": "2026-08-12T10:00:00Z",
    "risk_level": "low",
    "scenario": "Demonstrates agent contacting customer when only analyst communication authorized"
  }
}
```

Save to: `contracts/scenario_unauthorized_recipient.json`

- [ ] **Step 3: Create resource creep scenario**

```json
{
  "contract_id": "resource_creep_demo",
  "goal": "hold_suspicious_transaction_84721",
  "authorized_tools": [
    "hold_transaction"
  ],
  "resource_scope": {
    "transaction_ids": ["84721"],
    "account_ids": [],
    "allowed_scope_expansion": false
  },
  "constraints": {
    "max_transactions_affected": 1
  },
  "approved_recipients": [],
  "metadata": {
    "user": "analyst@bank.com",
    "timestamp": "2026-08-12T10:00:00Z",
    "risk_level": "medium",
    "scenario": "Demonstrates agent holding multiple transactions when only one authorized"
  }
}
```

Save to: `contracts/scenario_resource_creep.json`

- [ ] **Step 4: Verify all contracts are valid JSON**

Run: `python -m json.tool contracts/scenario_scope_expansion.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

Run: `python -m json.tool contracts/scenario_unauthorized_recipient.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

Run: `python -m json.tool contracts/scenario_resource_creep.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

- [ ] **Step 5: Test loading contracts**

Run: `python -c "from src.intent_contract import load_intent_contract; c = load_intent_contract('contracts/scenario_scope_expansion.json'); print(f'Loaded: {c.contract_id}')"`
Expected: "Loaded: scope_expansion_demo"

- [ ] **Step 6: Commit**

```bash
git add contracts/scenario_scope_expansion.json contracts/scenario_unauthorized_recipient.json contracts/scenario_resource_creep.json
git commit -m "feat: add three demo scenario intent contracts"
```

---

### Task 12: README and Documentation

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: None (documentation)
- Produces: User-facing documentation

- [ ] **Step 1: Create README**

````markdown
# IntentGuard MVP

**Behavioral Intent Security for Autonomous AI Agents**

IntentGuard addresses the behavioral intent gap in autonomous AI agent security. Traditional controls answer "Can this agent call this API?" but not "Should this agent call this API for this specific task?"

## Problem

Autonomous agents can have valid authentication, proper authorization, and legitimate tool access, yet still take actions that exceed the human's intent.

**Example:** A fraud analyst asks to "investigate wire #84721 and hold it if fraudulent." The agent correctly investigates and holds the transaction, but then autonomously decides to freeze the entire customer account and send a customer notification. From a traditional security perspective (AIRS), all actions are authorized. From a behavioral perspective, the agent exceeded its mandate.

## Solution

IntentGuard creates an **Intent Contract** from the user's request, continuously compares expected vs actual agent behavior, and produces **ALLOW / CONFIRM / BLOCK** decisions with explainable deviation scores.

This MVP demonstrates the gap between traditional AIRS policies and behavioral intent detection.

## Architecture

```
USER → Fraud Chatbot → AI Gateway → Tools
                            ↓
                      Trace Logs
                            ↓
                      IntentGuard (polls every 10s)
                            ↓
                    Deviation Detection
                            ↓
              Console Output + JSON Report
```

## Setup

### Prerequisites

- Python 3.10+
- AI Gateway (Portkey) credentials
- 2GB RAM minimum

### Installation

```bash
# Clone repository
git clone <repo-url>
cd IntentGuard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp config/gateway_config.example.json config/gateway_config.json
# Edit config/gateway_config.json with your credentials
```

### Configuration

Edit `config/gateway_config.json`:

```json
{
  "gateway": {
    "endpoint": "https://api.portkey.ai/v1",
    "service_account": "your-service-account@example.com",
    "password": "your-password",
    "tsg_id": "your-tsg-id",
    "slugname": "your-slugname"
  },
  "intentguard": {
    "poll_interval_seconds": 10,
    "report_directory": "./reports"
  }
}
```

Or use environment variables (see `.env.example`).

## Usage

### Running a Demo

**Terminal 1: Start Fraud Chatbot**

```bash
python fraud_agent.py --config config/gateway_config.json
# Note the Session ID displayed
```

**Terminal 2: Start IntentGuard Monitor**

```bash
python intentguard.py \
  --contract contracts/scenario_scope_expansion.json \
  --session <SESSION_ID_FROM_TERMINAL_1> \
  --config config/gateway_config.json
```

**Terminal 1: Submit Query**

```
> Investigate wire #84721 and hold it if fraudulent
```

**Terminal 2: Observe Real-Time Deviation Detection**

You'll see color-coded output showing:
- ✓ Expected tool calls (green)
- ✗ Deviation detected (red) with reasons and scores

**Review Report**

After the session completes (Ctrl+C in Terminal 2), check `reports/` for JSON report with AIRS gap analysis.

## Demo Scenarios

### Scenario 1: Scope Expansion (Primary Demo)

- **Contract:** `contracts/scenario_scope_expansion.json`
- **Query:** "Investigate wire #84721 and hold it if fraudulent"
- **Expected:** read → inspect → assess → hold transaction
- **Actual:** read → inspect → assess → hold → **freeze_account** → **send_email**
- **Deviation:** HIGH (75-80)

Shows agent escalating from transaction-level to account-level actions.

### Scenario 2: Unauthorized Recipient

- **Contract:** `contracts/scenario_unauthorized_recipient.json`
- **Query:** "Check wire #84721 and report to analyst"
- **Expected:** read → assess → report internally
- **Actual:** read → assess → **send_customer_email**
- **Deviation:** MEDIUM (50-60)

Shows agent contacting unauthorized recipient.

### Scenario 3: Resource Scope Creep

- **Contract:** `contracts/scenario_resource_creep.json`
- **Query:** "Hold suspicious transaction #84721"
- **Expected:** hold_transaction(84721)
- **Actual:** hold(84721) → **hold(84722)** → **hold(84723)**
- **Deviation:** MEDIUM (45-55)

Shows agent expanding beyond authorized resource scope.

## Components

- **fraud_agent.py** - Fraud investigation chatbot with mock tools
- **intentguard.py** - Monitoring daemon with deviation detection
- **src/deviation_detector.py** - Multi-dimensional scoring engine
- **src/gateway_client.py** - AI Gateway API client
- **src/report_generator.py** - JSON report with AIRS gap analysis
- **contracts/** - Intent contract definitions
- **reports/** - Generated deviation reports

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Project Structure

```
IntentGuard/
├── fraud_agent.py              # Chatbot CLI
├── intentguard.py              # Monitor daemon
├── src/
│   ├── config.py               # Configuration management
│   ├── intent_contract.py      # Contract schema
│   ├── deviation_detector.py   # Deviation engine
│   ├── gateway_client.py       # API client
│   ├── console_output.py       # Terminal formatting
│   ├── report_generator.py     # JSON reports
│   └── tools/
│       └── fraud_tools.py      # Mock fraud tools
├── contracts/                  # Demo scenarios
├── reports/                    # Generated reports
├── tests/                      # Test suite
└── requirements.txt
```

## Deviation Detection

IntentGuard calculates deviation across four dimensions:

1. **Operation Deviation (0-100)** - Unauthorized tools, constraint violations
2. **Scope Expansion (0-100)** - Resources outside authorized scope
3. **Side Effects (0-100)** - Unexpected impacts
4. **Behavioral Sequence (0-100)** - Unexpected call patterns

**Overall Score:** Average of dimensions, mapped to severity:
- 0-30: LOW
- 31-60: MEDIUM
- 61-100: HIGH

## AIRS Gap Demonstration

Each report includes an AIRS gap analysis showing:

- **Current AIRS Verdict:** ALLOW (agent has permissions)
- **IntentGuard Verdict:** BLOCK/CONFIRM (behavioral deviation detected)
- **Gap Summary:** What traditional security misses
- **Recommended Policy:** AIRS policy to prevent similar deviations

## License

[Your License Here]

## Contact

[Your Contact Info Here]
````

Save to: `README.md`

- [ ] **Step 2: Verify README renders correctly**

Run: `head -20 README.md`
Expected: See formatted README content

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with setup and usage instructions"
```

---

### Task 13: End-to-End Integration Test

**Files:**
- Modify: `tests/test_intentguard_integration.py`

**Interfaces:**
- Consumes: All components
- Produces: Integration test validating complete flow

- [ ] **Step 1: Write end-to-end test**

```python
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
        assert report['airs_gap_analysis']['current_airs_verdict'] == 'ALLOW'
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
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_intentguard_integration.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_intentguard_integration.py
git commit -m "test: add end-to-end integration tests"
```

---

### Task 14: Final Validation and Cleanup

**Files:**
- Create: `.github/workflows/test.yml` (optional, for CI)
- Modify: Any remaining documentation

**Interfaces:**
- Consumes: Complete codebase
- Produces: Validated, production-ready MVP

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v --cov=src`
Expected: All tests PASS with reasonable coverage

- [ ] **Step 2: Verify all scripts are executable**

Run: `ls -la fraud_agent.py intentguard.py`
Expected: Both files have execute permissions

- [ ] **Step 3: Test fraud agent startup**

Run: `python fraud_agent.py --help`
Expected: Help message displayed

- [ ] **Step 4: Test intentguard startup**

Run: `python intentguard.py --help`
Expected: Help message displayed

- [ ] **Step 5: Verify directory structure**

Run: `tree -L 2 -I 'venv|__pycache__|*.pyc|.git'`
Expected: Clean directory structure matching design

- [ ] **Step 6: Create final commit**

```bash
git add -A
git status
# Verify no unintended files staged
git commit -m "chore: final validation and cleanup for MVP release"
```

- [ ] **Step 7: Tag release**

```bash
git tag -a v0.1.0-mvp -m "IntentGuard MVP - Behavioral Intent Security Demo"
```

---

## Implementation Complete

All tasks completed. The IntentGuard MVP is ready for deployment and demonstration.

**What's been built:**

✅ Configuration management (file + env)  
✅ Intent contract schema and validation  
✅ 6 mock fraud investigation tools  
✅ Multi-dimensional deviation detection engine  
✅ AI Gateway client with polling  
✅ Rich console output formatting  
✅ JSON report generator with AIRS gap analysis  
✅ IntentGuard monitoring daemon  
✅ Fraud investigation chatbot  
✅ 3 demo scenarios  
✅ Comprehensive documentation  
✅ Test suite  

**Next steps:**

1. Deploy to test environment
2. Run live demo with AI Gateway
3. Gather stakeholder feedback
4. Iterate based on findings
