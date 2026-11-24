"""
Dynamic Intent Analyzer for IntentGuard

Automatically analyzes user intent and generates authorization contracts on-the-fly.
Detects ANY scope expansion, not just curated scenarios.
"""
import re
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass
from anthropic import Anthropic


@dataclass
class IntentAnalysis:
    """Result of intent analysis."""
    user_request: str
    detected_intent: str
    authorized_tools: List[str]
    resource_scope: Dict[str, List[str]]
    constraints: Dict[str, Any]
    confidence: float
    reasoning: str


class DynamicIntentAnalyzer:
    """
    Analyzes user requests and generates intent contracts dynamically.

    Uses LLM to understand intent and determine appropriate authorization scope.
    Works with ANY tools/skills, not just predefined scenarios.
    """

    def __init__(self, available_tools: List[Dict[str, Any]], api_key: Optional[str] = None):
        """
        Initialize analyzer.

        Args:
            available_tools: List of tool definitions with name, description, parameters
            api_key: Optional Anthropic API key for intent analysis
        """
        self.available_tools = available_tools
        self.tool_map = {tool['name']: tool for tool in available_tools}

        if api_key:
            self.client = Anthropic(api_key=api_key)
        else:
            self.client = None

    def analyze_intent(self, user_request: str) -> IntentAnalysis:
        """
        Analyze user request and determine authorization scope.

        Args:
            user_request: The user's natural language request

        Returns:
            IntentAnalysis with authorized tools, resources, and constraints
        """
        # If LLM available, use it for analysis
        if self.client:
            return self._analyze_with_llm(user_request)
        else:
            return self._analyze_with_rules(user_request)

    def _analyze_with_llm(self, user_request: str) -> IntentAnalysis:
        """Use LLM to analyze intent and determine authorization."""

        # Build tool catalog for LLM
        tool_catalog = "\n".join([
            f"- {tool['name']}: {tool.get('description', 'No description')}"
            for tool in self.available_tools
        ])

        prompt = f"""Analyze this user request and determine what tools should be authorized.

USER REQUEST: "{user_request}"

AVAILABLE TOOLS:
{tool_catalog}

Determine:
1. The core intent/goal of the request
2. Which tools are NECESSARY to fulfill this specific request
3. What resources (IDs, accounts, etc.) are in scope
4. What constraints should apply (e.g., no customer contact, no account-level actions)

Respond in JSON format:
{{
  "detected_intent": "Brief description of what user wants",
  "authorized_tools": ["tool1", "tool2"],
  "resource_scope": {{"transaction_ids": ["84721"], "account_ids": []}},
  "constraints": {{"customer_communication": false, "account_level_actions": false}},
  "reasoning": "Explanation of authorization decisions"
}}

Be conservative - only authorize tools DIRECTLY needed for this specific request."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse LLM response
            import json
            response_text = response.content[0].text

            # Extract JSON (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            analysis_data = json.loads(response_text.strip())

            return IntentAnalysis(
                user_request=user_request,
                detected_intent=analysis_data.get("detected_intent", "Unknown"),
                authorized_tools=analysis_data.get("authorized_tools", []),
                resource_scope=analysis_data.get("resource_scope", {}),
                constraints=analysis_data.get("constraints", {}),
                confidence=0.9,
                reasoning=analysis_data.get("reasoning", "LLM-based analysis")
            )

        except Exception as e:
            print(f"LLM analysis failed: {e}, falling back to rule-based")
            return self._analyze_with_rules(user_request)

    def _analyze_with_rules(self, user_request: str) -> IntentAnalysis:
        """Fallback rule-based intent analysis."""
        request_lower = user_request.lower()

        # Extract resource IDs
        transaction_ids = re.findall(r'(?:wire|transaction|tx)\s*#?(\d+)', request_lower)
        account_ids = re.findall(r'(?:account|acct)\s*#?([A-Z0-9-]+)', user_request)

        # Determine authorized tools based on keywords
        authorized_tools = []

        # Read operations
        if any(word in request_lower for word in ['investigate', 'review', 'check', 'analyze', 'look at']):
            authorized_tools.extend(['read_transaction', 'inspect_account_history', 'assess_fraud_risk'])

        # Write operations - be conservative
        if 'hold' in request_lower and transaction_ids:
            authorized_tools.append('hold_transaction')

        # Determine constraints
        constraints = {
            "customer_communication": False,
            "account_level_actions": False,
            "max_transactions_affected": 1 if transaction_ids else 0
        }

        # Detect intent
        if 'investigate' in request_lower or 'review' in request_lower:
            intent = "Investigation and analysis"
        elif 'hold' in request_lower:
            intent = "Transaction hold"
        elif 'report' in request_lower:
            intent = "Reporting and documentation"
        else:
            intent = "General inquiry"

        return IntentAnalysis(
            user_request=user_request,
            detected_intent=intent,
            authorized_tools=list(set(authorized_tools)),
            resource_scope={
                "transaction_ids": transaction_ids,
                "account_ids": account_ids
            },
            constraints=constraints,
            confidence=0.7,
            reasoning="Rule-based analysis from keywords and patterns"
        )

    def detect_scope_expansion(
        self,
        tool_name: str,
        params: Dict[str, Any],
        authorized_tools: List[str],
        resource_scope: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Detect if a tool call represents scope expansion.

        Args:
            tool_name: Name of tool being called
            params: Tool parameters
            authorized_tools: List of authorized tool names
            resource_scope: Authorized resource IDs

        Returns:
            Dict with expansion_detected, expansion_type, and details
        """
        expansions = []

        # Check 1: Unauthorized tool
        if tool_name not in authorized_tools:
            expansions.append({
                "type": "unauthorized_tool",
                "severity": "high",
                "detail": f"Tool '{tool_name}' not in authorized set: {authorized_tools}"
            })

        # Check 2: Resource scope expansion
        for param_name, param_value in params.items():
            # Check transaction IDs
            if 'tx' in param_name.lower() or 'transaction' in param_name.lower():
                tx_ids = resource_scope.get('transaction_ids', [])
                if tx_ids and str(param_value) not in tx_ids:
                    expansions.append({
                        "type": "resource_scope_expansion",
                        "severity": "medium",
                        "detail": f"Transaction ID '{param_value}' not in authorized scope: {tx_ids}"
                    })

            # Check account IDs
            if 'account' in param_name.lower() or 'acct' in param_name.lower():
                acct_ids = resource_scope.get('account_ids', [])
                if acct_ids and str(param_value) not in acct_ids:
                    expansions.append({
                        "type": "resource_scope_expansion",
                        "severity": "high",
                        "detail": f"Account ID '{param_value}' not in authorized scope: {acct_ids}"
                    })

        # Check 3: Tool category expansion (e.g., read-only -> write)
        tool_categories = self._categorize_tool(tool_name)
        authorized_categories = set()
        for auth_tool in authorized_tools:
            authorized_categories.update(self._categorize_tool(auth_tool))

        unauthorized_categories = tool_categories - authorized_categories
        if unauthorized_categories:
            expansions.append({
                "type": "capability_expansion",
                "severity": "high",
                "detail": f"Tool requires capabilities not authorized: {unauthorized_categories}"
            })

        return {
            "expansion_detected": len(expansions) > 0,
            "expansion_count": len(expansions),
            "expansions": expansions,
            "overall_severity": max([e['severity'] for e in expansions], default='none')
        }

    def _categorize_tool(self, tool_name: str) -> Set[str]:
        """Categorize tool by capability (read, write, communication, etc.)."""
        categories = set()
        tool_lower = tool_name.lower()

        # Read operations
        if any(word in tool_lower for word in ['read', 'get', 'fetch', 'inspect', 'assess', 'view']):
            categories.add('read')

        # Write operations
        if any(word in tool_lower for word in ['write', 'update', 'create', 'modify', 'hold', 'freeze']):
            categories.add('write')

        # Delete operations
        if any(word in tool_lower for word in ['delete', 'remove', 'cancel']):
            categories.add('delete')

        # Communication
        if any(word in tool_lower for word in ['send', 'email', 'notify', 'message', 'alert']):
            categories.add('communication')

        # Account-level
        if 'account' in tool_lower and any(word in tool_lower for word in ['freeze', 'close', 'suspend']):
            categories.add('account_level')

        return categories
