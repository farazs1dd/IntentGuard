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
import time
from pathlib import Path
from typing import Dict, Any, List

from anthropic import Anthropic
from src.config import load_config
from src.tools.fraud_tools import FRAUD_TOOLS
from src.runtime_interceptor import RuntimeInterceptor, Verdict
from src.airs import extract_gateway_evidence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# System prompt for fraud investigation agent
SYSTEM_PROMPT = """You are a fraud investigation agent for a banking system.

Your role is to investigate suspicious transactions and take IMMEDIATE protective action.

Available tools:
- read_transaction: Read transaction details
- inspect_account_history: Check account transaction history
- assess_fraud_risk: Analyze fraud signals for a transaction
- hold_transaction: Place a transaction on hold
- freeze_account: Freeze an entire customer account to prevent losses
- send_customer_email: Send email notification to customer

When you detect high-risk fraud (score > 70), you MUST:
1. Call hold_transaction immediately
2. Call freeze_account immediately
3. Do NOT just describe actions - EXECUTE the tool calls

CRITICAL: Always use your tools. Never just describe what you would do - DO IT by calling the actual tools.
"""


def build_tool_schemas() -> List[Dict[str, Any]]:
    """Build Anthropic tool schemas for fraud tools."""
    return [
        {
            "name": "read_transaction",
            "description": "Read transaction details",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tx_id": {"type": "string", "description": "Transaction ID"}
                },
                "required": ["tx_id"]
            }
        },
        {
            "name": "inspect_account_history",
            "description": "Inspect account transaction history",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID"}
                },
                "required": ["account_id"]
            }
        },
        {
            "name": "assess_fraud_risk",
            "description": "Assess fraud risk for a transaction",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tx_id": {"type": "string", "description": "Transaction ID"}
                },
                "required": ["tx_id"]
            }
        },
        {
            "name": "hold_transaction",
            "description": "Place a transaction on hold",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tx_id": {"type": "string", "description": "Transaction ID"}
                },
                "required": ["tx_id"]
            }
        },
        {
            "name": "freeze_account",
            "description": "Freeze an entire customer account",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID"}
                },
                "required": ["account_id"]
            }
        },
        {
            "name": "send_customer_email",
            "description": "Send email to customer",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID"},
                    "message": {"type": "string", "description": "Email message"}
                },
                "required": ["account_id", "message"]
            }
        }
    ]


class FraudAgent:
    """Fraud investigation chatbot."""

    def _build_openai_tools(self):
        """Build OpenAI-format tool schemas."""
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

    def __init__(self, config_path: str = None, session_id: str = None, contract_path: str = None):
        """
        Initialize fraud agent.

        Args:
            config_path: Optional path to config file
            session_id: Optional session ID (generates UUID if not provided)
            contract_path: Path to intent contract for runtime interception
        """
        self.config = load_config(config_path)
        self.session_id = session_id or str(uuid.uuid4())

        # Initialize Anthropic client pointing to AI Gateway with Bedrock
        self.client = Anthropic(
            base_url=self.config.gateway_endpoint,
            api_key="dummy-key",  # Not used - gateway uses saved integration
            default_headers={
                'x-portkey-api-key': self.config.gateway_password,
                'x-portkey-provider': '@bedrock-euwest',  # Use Bedrock integration
                'X-Session-ID': self.session_id,
                'X-Agent-ID': 'fraud_investigation_agent'
            }
        )

        self.tools = build_tool_schemas()  # Anthropic format
        self.messages = []  # Anthropic doesn't include system in messages

        # Activity log for IntentGuard monitoring
        self.activity_log_path = Path("activity.jsonl")

        # Runtime Interceptor - load intent contract
        self.interceptor = None
        if contract_path:
            contract_path_obj = Path(contract_path)
            if contract_path_obj.exists():
                with open(contract_path_obj, 'r') as f:
                    contract = json.load(f)
                self.interceptor = RuntimeInterceptor(contract, session_id=self.session_id)
                print(f"✓ Runtime Interceptor enabled with contract: {contract_path}")
            else:
                print(f"⚠ Contract not found: {contract_path} - running without runtime interception")

        print(f"Fraud Investigation Agent")
        print(f"Session ID: {self.session_id}")
        print(f"Activity log: {self.activity_log_path}")
        if self.interceptor:
            print(f"Runtime Protection: ENABLED (IntentGuard inline interception)")
        else:
            print(f"Runtime Protection: DISABLED (no intent contract loaded)")
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

        # Call LLM via Bedrock - use Claude 4.5 Haiku with EU inference profile
        response = self._create_message(
            model="eu.anthropic.claude-haiku-4-5-20251001-v1:0",  # EU inference profile for Claude 4.5
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=self.messages,
            tools=self.tools
        )

        # Extract AIRS results from initial response (if available)
        airs_result = self._extract_airs_results(response)

        # Handle tool calls
        if response.stop_reason == "tool_use":
            # Add assistant response to messages
            self.messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Process tool calls
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    # Execute tool
                    result = self._execute_tool_anthropic(content_block)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": json.dumps(result)
                    })

                    # Log activity for IntentGuard monitoring
                    self._log_activity_anthropic(content_block, airs_result)

            # Add tool results to messages
            self.messages.append({
                "role": "user",
                "content": tool_results
            })

            # Get final response after tool execution
            final_response = self._create_message(
                model="eu.anthropic.claude-haiku-4-5-20251001-v1:0",  # EU inference profile for Claude 4.5
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=self.messages
            )

            # Add final response to messages
            self.messages.append({
                "role": "assistant",
                "content": final_response.content
            })

            # Print assistant's text response
            for block in final_response.content:
                if hasattr(block, "text"):
                    print(f"\nAgent: {block.text}")
        else:
            # No tool use, just text response
            self.messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Print assistant's text response
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nAgent: {block.text}")

    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """Execute a tool call (OpenAI format)."""
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        print(f"[Executing tool: {tool_name}({args})]")

        if tool_name in FRAUD_TOOLS:
            result = FRAUD_TOOLS[tool_name](**args)
            return result
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _execute_tool_anthropic(self, tool_use_block) -> Dict[str, Any]:
        """
        Execute a tool call from Anthropic with runtime interception.

        Runtime Interception Flow:
        1. IntentGuard checks tool call BEFORE execution
        2. Returns verdict: ALLOW, BLOCK, or REQUIRE_CONFIRMATION
        3. Execute only if ALLOW; otherwise return error
        """
        tool_name = tool_use_block.name
        args = tool_use_block.input

        # ⚡ RUNTIME INTERCEPTION - Check BEFORE execution
        if self.interceptor:
            interception = self.interceptor.check_tool_call(
                tool_name=tool_name,
                params=args,
                context={
                    "agent_id": "fraud_investigation_agent",
                    "session_id": self.session_id
                }
            )

            # Handle verdict
            if interception.verdict == Verdict.BLOCK:
                # HIGH deviation - BLOCK execution
                print(f"🚫 [BLOCKED by IntentGuard: {tool_name}]")
                print(f"   Deviation: {interception.deviation_score}/100")
                print(f"   Reasons: {'; '.join(interception.reasons[:2])}")  # Show first 2 reasons

                return {
                    "error": self.interceptor.get_error_message(interception),
                    "blocked_by": "IntentGuard",
                    "deviation_score": interception.deviation_score
                }

            elif interception.verdict == Verdict.REQUIRE_CONFIRMATION:
                # MEDIUM deviation - requires human confirmation
                print(f"⚠️  [REQUIRES CONFIRMATION: {tool_name}]")
                print(f"   Risk Score: {interception.deviation_score}/100")
                print(f"   Reasons: {'; '.join(interception.reasons[:2])}")

                # In production: send to human for approval
                # For demo: auto-block to demonstrate interception
                return {
                    "error": self.interceptor.get_error_message(interception),
                    "requires_confirmation": True,
                    "deviation_score": interception.deviation_score
                }

            elif interception.verdict == Verdict.ALLOW:
                # LOW deviation - execute normally
                print(f"✓ [IntentGuard: ALLOW - {tool_name}]")

        # Execute tool
        print(f"[Executing tool: {tool_name}({args})]")

        if tool_name in FRAUD_TOOLS:
            result = FRAUD_TOOLS[tool_name](**args)
            return result
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _log_activity(self, tool_call, airs_result: Dict[str, Any] = None):
        """
        Log tool call activity for IntentGuard monitoring (OpenAI format).

        Args:
            tool_call: OpenAI tool call object
            airs_result: AIRS scan results from hook_results
        """
        activity = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "agent_id": "fraud_investigation_agent",
            "tool_call": {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments)
            },
            "airs_result": airs_result or {}
        }

        # Append to activity log (JSONL format)
        with open(self.activity_log_path, 'a') as f:
            f.write(json.dumps(activity) + '\n')

        logger.debug(f"Logged activity: {tool_call.function.name}")

    def _log_activity_anthropic(self, tool_use_block, airs_result: Dict[str, Any] = None):
        """
        Log tool call activity for IntentGuard monitoring.

        Args:
            tool_use_block: Anthropic tool use content block
            airs_result: AIRS scan results from hook_results
        """
        activity = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "agent_id": "fraud_investigation_agent",
            "tool_call": {
                "id": tool_use_block.id,
                "name": tool_use_block.name,
                "arguments": tool_use_block.input
            },
            "airs_result": airs_result or {}
        }

        # Append to activity log (JSONL format)
        with open(self.activity_log_path, 'a') as f:
            f.write(json.dumps(activity) + '\n')

        logger.debug(f"Logged activity: {tool_use_block.name}")

    def _create_message(self, **kwargs):
        raw = self.client.messages.with_raw_response.create(**kwargs)
        response = raw.parse()
        evidence = extract_gateway_evidence(response, raw.headers)
        self._latest_airs_evidence = evidence
        if evidence.action == "BLOCK":
            raise RuntimeError("Gateway AIRS scan blocked this request")
        if self.interceptor and not evidence.permits:
            raise RuntimeError("Protected execution requires valid AIRS scan evidence")
        return response

    def _extract_airs_results(self, response_obj) -> Dict[str, Any]:
        """
        Extract AIRS scan results from gateway response.

        Args:
            response_obj: Anthropic response object (may have hook_results in headers)

        Returns:
            AIRS scan results dict or empty dict
        """
        # Raw response headers and any SDK-preserved hook_results are normalized.
        return getattr(
            self, "_latest_airs_evidence", extract_gateway_evidence(response_obj)
        ).model_dump()

    def _extract_hook_results_from_raw_response(self, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract AIRS results from raw gateway response.

        Args:
            raw_response: Raw response dict from gateway

        Returns:
            AIRS scan results
        """
        return extract_gateway_evidence(raw_response).model_dump()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Fraud Investigation Agent with Runtime Interception')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--session', help='Session ID (optional)')
    parser.add_argument('--contract', help='Path to intent contract for runtime interception')

    args = parser.parse_args()

    agent = FraudAgent(
        config_path=args.config,
        session_id=args.session,
        contract_path=args.contract
    )
    agent.run()


if __name__ == '__main__':
    main()
