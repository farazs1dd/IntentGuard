"""
Activity log reader for fetching tool call traces.

Reads activity log written by fraud agent to retrieve tool calls and AIRS results.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.config import Config

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Client for reading tool call activity from local activity log.

    Reads activity.jsonl file written by fraud agent containing tool calls
    and AIRS scan results from AI Gateway responses.
    """

    def __init__(self, config: Config, session_id: str, agent_id: str):
        """
        Initialize activity log reader.

        Args:
            config: Configuration (not used for file-based monitoring)
            session_id: Session ID to monitor
            agent_id: Agent ID to filter by
        """
        self.config = config
        self.session_id = session_id
        self.agent_id = agent_id
        self.activity_log_path = Path("activity.jsonl")
        self.last_read_position = 0

    def fetch_tool_calls(self, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Fetch tool calls from activity log.

        Args:
            since: Optional timestamp to fetch calls after

        Returns:
            List of tool call dicts with 'name', 'params', 'timestamp', 'airs_result'
        """
        if not self.activity_log_path.exists():
            logger.debug(f"Activity log not found: {self.activity_log_path}")
            return []

        tool_calls = []

        try:
            with open(self.activity_log_path, 'r') as f:
                # Seek to last read position
                f.seek(self.last_read_position)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        activity = json.loads(line)

                        # Filter by session and agent
                        if activity.get('session_id') != self.session_id:
                            continue
                        if activity.get('agent_id') != self.agent_id:
                            continue

                        # Filter by timestamp if provided
                        if since and activity.get('timestamp', 0) <= since:
                            continue

                        # Extract tool call data
                        tool_call_data = activity.get('tool_call', {})
                        tool_calls.append({
                            'name': tool_call_data.get('name'),
                            'params': tool_call_data.get('arguments', {}),
                            'timestamp': activity.get('timestamp'),
                            'airs_result': activity.get('airs_result', {}),
                            'session_id': activity.get('session_id'),
                            'agent_id': activity.get('agent_id')
                        })

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in activity log: {e}")
                        continue

                # Update last read position
                self.last_read_position = f.tell()

            logger.info(f"Fetched {len(tool_calls)} new tool calls from activity log")
            return tool_calls

        except IOError as e:
            logger.error(f"Error reading activity log: {e}")
            return []
