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
