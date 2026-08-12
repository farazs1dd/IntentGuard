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
