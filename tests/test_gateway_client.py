"""Tests the current local activity log reader rather than a fictional trace API."""
import json
from types import SimpleNamespace

from src.gateway_client import GatewayClient


def make_client(tmp_path):
    client = GatewayClient(SimpleNamespace(), "session-a", "agent-a")
    client.activity_log_path = tmp_path / "activity.jsonl"
    return client


def entry(timestamp, session="session-a", agent="agent-a"):
    return {"session_id": session, "agent_id": agent, "timestamp": timestamp,
            "tool_call": {"name": "read_transaction", "arguments": {"tx_id": "84721"}},
            "airs_result": {"action": "allow", "scan_id": "fixture-scan"}}


def test_fetch_tool_calls_success(tmp_path):
    client = make_client(tmp_path)
    client.activity_log_path.write_text(
        "\n".join(json.dumps(e) for e in [entry(1), entry(2), entry(3, session="other")]) + "\n")
    calls = client.fetch_tool_calls()
    assert len(calls) == 2
    assert calls[0]["params"] == {"tx_id": "84721"}
    assert calls[0]["airs_result"]["scan_id"] == "fixture-scan"
    assert client.fetch_tool_calls() == []


def test_fetch_tool_calls_with_since_timestamp(tmp_path):
    client = make_client(tmp_path)
    client.activity_log_path.write_text(json.dumps(entry(1)) + "\n" + json.dumps(entry(2)) + "\n")
    assert [c["timestamp"] for c in client.fetch_tool_calls(since=1)] == [2]
    with client.activity_log_path.open("a") as stream:
        stream.write(json.dumps(entry(3)) + "\n")
    assert [c["timestamp"] for c in client.fetch_tool_calls()] == [3]


def test_missing_log(tmp_path):
    assert make_client(tmp_path).fetch_tool_calls() == []


def test_invalid_lines_and_agent_filter(tmp_path):
    client = make_client(tmp_path)
    client.activity_log_path.write_text(
        "not-json\n" + json.dumps(entry(1, agent="other")) + "\n" + json.dumps(entry(2)) + "\n")
    assert len(client.fetch_tool_calls()) == 1
