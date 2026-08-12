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
