"""Tests must never load a developer's saved gateway credentials or routing."""
import pytest


@pytest.fixture(autouse=True)
def isolate_gateway_configuration(monkeypatch):
    monkeypatch.setenv("GATEWAY_ASSURANCE_CONFIG", "")
