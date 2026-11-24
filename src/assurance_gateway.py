"""Non-streaming, provider-neutral gateway transport. No direct-provider fallback."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

from src.airs import ScanEvidence, extract_gateway_evidence
from src.assurance_models import digest
from src.assurance_store import register_secret
from src.campaign_models import GatewaySettings, Limits, Route

DEFAULT_GATEWAY_CONFIG = Path(__file__).resolve().parents[1] / "config/gateway_assurance.json"


class GatewayFailure(ValueError):
    """Safe messages only: never include SDK exceptions, headers or response bodies."""


class EvidenceUnavailable(GatewayFailure):
    pass


class Censored(GatewayFailure):
    pass


class BudgetExceeded(GatewayFailure):
    pass


def load_gateway_settings():
    path = os.getenv("GATEWAY_ASSURANCE_CONFIG")
    if path == "":
        return None
    if path is None:
        default = DEFAULT_GATEWAY_CONFIG
        if not default.exists():
            return None
        path = str(default)
    try:
        location = Path(path).resolve()
        settings = GatewaySettings.model_validate_json(location.read_text())
        if settings.credential_file:
            reference = Path(settings.credential_file)
            if not reference.is_absolute():
                reference = location.parent / reference
            settings = settings.model_copy(update={"credential_file": str(reference.resolve())})
        return settings
    except (OSError, ValueError):
        raise GatewayFailure("Invalid gateway config; use the documented non-secret config schema") from None


def resolve_gateway_credential(settings):
    """Resolve only at the trusted host; never put this value into a public model."""
    from_env = os.getenv(settings.credential_env)
    if from_env:
        register_secret(from_env)
        return from_env
    if settings.credential_file:
        try:
            gateway = json.loads(Path(settings.credential_file).read_text()).get("gateway", {})
            key = gateway.get("password")
            if isinstance(key, str) and key.strip():
                register_secret(key)
                return key
        except (OSError, ValueError, AttributeError):
            pass
    raise GatewayFailure("Gateway credential unavailable in the configured environment or protected credential file")


def gateway_identity(settings):
    """Bind verification to effective credentials without persisting their value."""
    try:
        credential_identity = digest(resolve_gateway_credential(settings))
    except GatewayFailure:
        credential_identity = None
    return digest({"configuration": settings.model_dump(), "credential_identity": credential_identity})


def gateway_readiness(settings, *, for_preflight=False):
    if settings is None:
        return {"available": False, "ready": False, "preflight_ready": False,
                "missing": ["GATEWAY_ASSURANCE_CONFIG"],
                "message": "Configure an operator-owned gateway settings file."}
    missing = []
    if os.getenv("MVP_ENABLE_LIVE") != "1":
        missing.append("MVP_ENABLE_LIVE=1")
    try:
        resolve_gateway_credential(settings)
    except GatewayFailure:
        missing.append("gateway credential reference")
    connection_missing = list(missing)
    coverage_missing = []
    for flag in ("input_scope_verified", "synchronous_guardrails_verified",
                 "response_cache_disabled_verified"):
        if not getattr(settings, flag):
            missing.append(flag)
            coverage_missing.append(flag)
    return {"available": True, "ready": not (connection_missing if for_preflight else missing),
            "preflight_ready": not connection_missing, "missing": missing,
            "verification_pending": coverage_missing,
            "transport": "http" if settings.endpoint.startswith("http://") else "https",
            "transport_warning": "HTTP sends gateway credentials and payloads without TLS. Use only the explicitly approved development connection."
            if settings.endpoint.startswith("http://") else None,
            "message": "Gateway unavailable: configure " + ", ".join(connection_missing)
            if connection_missing else
            "Portkey connection configured; preflight can run. Confirm scan scope, synchronous guardrails and response-cache policy before protected campaigns."
            if coverage_missing else "Gateway configured; preflight approval is still required."}


class Ledger:
    """Reserved requests include uncertainty and upstream attempts, not just successes."""
    def __init__(self, store, owner, identifier):
        self.store, self.owner, self.id = store, owner, identifier

    @classmethod
    def create(cls, store, owner, identifier, limits):
        store.put("budget", owner, {
            "id": identifier, "limits": limits.model_dump(), "requests": 0,
            "input_tokens": 0, "output_tokens": 0, "usd": 0,
            "cost_known": True, "entries": [], "overrun": False,
        })
        return cls(store, owner, identifier)

    def reserve(self, payload, route: Route, attempts):
        # UTF-8 bytes plus protocol allowance is deliberately conservative.
        input_bound = len(json.dumps(payload, ensure_ascii=False).encode()) + 4096
        output_bound = payload["max_tokens"]
        known = route.input_usd_per_million is not None and route.output_usd_per_million is not None
        price = ((input_bound * route.input_usd_per_million +
                  output_bound * route.output_usd_per_million) / 1_000_000 * attempts
                 if known else 0)
        reservation = str(uuid4())

        def reserve(data):
            limits = Limits.model_validate(data["limits"])
            if data["overrun"] or data["requests"] + attempts > limits.max_requests:
                raise BudgetExceeded("Request budget exhausted; explicit new campaign approval required")
            if (data["input_tokens"] + input_bound * attempts > limits.max_input_tokens or
                    data["output_tokens"] + output_bound * attempts > limits.max_output_tokens):
                raise BudgetExceeded("Token budget exhausted; no request dispatched")
            if limits.max_usd is not None:
                if not known or not data["cost_known"]:
                    raise BudgetExceeded("Dollar cap requires effective rates for every route")
                if data["usd"] + price > limits.max_usd:
                    raise BudgetExceeded("Cost reservation exceeds approved dollar cap")
            data["requests"] += attempts
            data["input_tokens"] += input_bound * attempts
            data["output_tokens"] += output_bound * attempts
            data["usd"] += price
            data["cost_known"] = data["cost_known"] and known
            data["entries"].append({
                "id": reservation, "status": "reserved", "input_tokens": input_bound * attempts,
                "output_tokens": output_bound * attempts, "usd": price, "attempts": attempts,
                "model": route.model, "timestamp": time.time(),
            })
        self.store.update("budget", self.owner, self.id, reserve)
        return reservation

    def settle(self, reservation, usage, route):
        def reconcile(data):
            entry = next(e for e in data["entries"] if e["id"] == reservation)
            if entry["status"] != "reserved":
                raise BudgetExceeded("Reservation already reconciled")
            # Undocumented/missing counts and hidden retries retain the full reservation.
            counts = [usage.get("prompt_tokens"), usage.get("completion_tokens")]
            if (entry["attempts"] != 1 or
                    any(type(n) is not int or n < 0 for n in counts)):
                entry["status"] = "uncertain"
                return
            input_used, output_used = counts
            data["overrun"] = input_used > entry["input_tokens"] or output_used > entry["output_tokens"]
            known = route.input_usd_per_million is not None and route.output_usd_per_million is not None
            cost = ((input_used * route.input_usd_per_million +
                     output_used * route.output_usd_per_million) / 1_000_000 if known else 0)
            data["input_tokens"] += input_used - entry["input_tokens"]
            data["output_tokens"] += output_used - entry["output_tokens"]
            data["usd"] += cost - entry["usd"]
            entry.update(status="measured", input_tokens=input_used,
                         output_tokens=output_used, usd=cost)
            limits = data["limits"]
            data["overrun"] = data["overrun"] or (
                data["input_tokens"] > limits["max_input_tokens"] or
                data["output_tokens"] > limits["max_output_tokens"] or
                limits["max_usd"] is not None and data["usd"] > limits["max_usd"]
            )
        self.store.update("budget", self.owner, self.id, reconcile)


def phase_evidence(body, headers, phase):
    try:
        hooks = body.get("hook_results", {})
        if headers.get("x-portkey-hook-results"):
            hooks = json.loads(headers["x-portkey-hook-results"])
        if not isinstance(hooks, dict):
            raise TypeError
        subset = {"hook_results": {phase: hooks.get(phase, [])}}
        evidence = extract_gateway_evidence(subset)
        # Explicit scan identity is required for protected gateway assurance.
        if evidence.status == "SCANNED" and not (evidence.scan_id or evidence.report_id):
            return ScanEvidence(status="ERROR", source="gateway", error="Missing scan identity")
        return evidence
    except (ValueError, TypeError, AttributeError):
        return ScanEvidence(status="ERROR", source="gateway", error="Malformed gateway evidence")


class Gateway:
    def __init__(self, settings, ledger, *, client=None):
        self.settings, self.ledger = settings, ledger
        self.client = client
        self.validation_only = False

    async def complete(self, role, messages, *, tools=None):
        settings = self.settings
        ready = gateway_readiness(settings, for_preflight=self.validation_only)
        if not ready["ready"]:
            raise GatewayFailure(ready["message"])
        route = settings.routes[getattr(settings, f"{role}_route")]
        ledger_data = self.ledger.store.get("budget", self.ledger.owner, self.ledger.id)
        payload = {
            "model": route.model, "messages": messages, "stream": False,
            "max_tokens": ledger_data["limits"]["output_per_request"],
        }
        if tools:
            payload["tools"] = tools
        if len(json.dumps(payload).encode()) > 250_000:
            raise BudgetExceeded("Model context exceeds the approved request size; no silent truncation")
        credential = resolve_gateway_credential(settings)
        reservation = self.ledger.reserve(payload, route, settings.upstream_attempts)
        headers = {
            settings.auth_header: credential,
            "x-portkey-trace-id": reservation,
            "x-portkey-strict-open-ai-compliance": "false",
            "x-portkey-cache-force-refresh": "true",
        }
        if route.config_id:
            headers["x-portkey-config"] = route.config_id
        if route.provider:
            headers["x-portkey-provider"] = route.provider
        try:
            if self.client:
                response = await self.client.post(
                    settings.endpoint + "/chat/completions", headers=headers, json=payload
                )
            else:
                async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
                    response = await client.post(
                        settings.endpoint + "/chat/completions", headers=headers, json=payload
                    )
            if len(response.content) > 2_000_000:
                raise GatewayFailure("Gateway response exceeds supported size")
            body = response.json()
            if not isinstance(body, dict):
                raise GatewayFailure("Gateway response is not an object")
        except (httpx.HTTPError, ValueError):
            # Reservation is intentionally retained after timeouts or malformed replies.
            raise GatewayFailure("Gateway request failed; reserved usage retained") from None
        usage = body.get("usage")
        self.ledger.settle(reservation, usage if isinstance(usage, dict) else {}, route)
        evidence = {
            "input": phase_evidence(body, response.headers, "before_request_hooks").model_dump(),
            "output": phase_evidence(body, response.headers, "after_request_hooks").model_dump(),
            "http_status": response.status_code, "request_id": reservation,
            "actual_model": body.get("model"),
        }
        self.ledger.store.put("gateway_call", self.ledger.owner, {
            "id": reservation, "budget_id": self.ledger.id, "role": role, **evidence,
        })
        if response.status_code == 446 or any(
            value["action"] == "BLOCK" for key, value in evidence.items() if key in {"input", "output"}
        ):
            raise Censored("Request prevented by gateway security; target behavior was not observed")
        if response.status_code not in (200, 246):
            raise GatewayFailure(f"Gateway returned HTTP {response.status_code}")
        if not all(ScanEvidence.model_validate(evidence[p]).permits for p in ("input", "output")):
            raise EvidenceUnavailable("Both synchronous AIRS input and output evidence are required")
        if body.get("model") not in route.expected_models:
            raise GatewayFailure("Gateway model changed or fallback occurred; comparison invalid")
        choices = body.get("choices", [])
        if (not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict)
                or choices[0].get("finish_reason") not in ("stop", "tool_calls")):
            raise GatewayFailure("Incomplete or unsupported gateway response")
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            raise GatewayFailure("Malformed model message")
        return message, evidence

    @property
    def fingerprint(self):
        return gateway_identity(self.settings)
