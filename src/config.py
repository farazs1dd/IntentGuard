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
