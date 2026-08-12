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
