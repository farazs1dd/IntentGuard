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
