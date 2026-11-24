"""Observed AIRS evidence. Absence of a scan is never an allow verdict."""
# The legacy fraud CLI still imports this module on Python 3.9.
# ruff: noqa: UP045
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ScanEvidence(BaseModel):
    status: Literal["SCANNED", "NOT_SCANNED", "ERROR"] = "NOT_SCANNED"
    action: Literal["ALLOW", "BLOCK", "UNKNOWN"] = "UNKNOWN"
    source: str = "none"
    scan_id: Optional[str] = None
    report_id: Optional[str] = None
    profile_name: Optional[str] = None
    detections: dict = Field(default_factory=dict)
    latency_ms: float = 0
    error: Optional[str] = None
    checks: list[dict] = Field(default_factory=list)

    @property
    def permits(self):
        return self.status == "SCANNED" and self.action == "ALLOW"


def as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    for method in ("model_dump", "to_dict"):
        if hasattr(value, method):
            return getattr(value, method)()
    return {}


def normalize_scan(value: Any, source="airs") -> ScanEvidence:
    data = as_dict(value)
    if data.get("status") in {"SCANNED", "NOT_SCANNED", "ERROR"}:
        return ScanEvidence.model_validate(data)
    action = str(data.get("action", "")).upper()
    if action not in {"ALLOW", "BLOCK"}:
        return ScanEvidence(status="ERROR", source=source,
                            error="Scan response has no recognized action")
    return ScanEvidence(
        status="SCANNED", action=action, source=source,
        scan_id=data.get("scan_id"), report_id=data.get("report_id"),
        profile_name=data.get("profile_name"),
        detections={k: data[k] for k in (
            "prompt_detected", "response_detected", "tool_detected", "category"
        ) if k in data},
    )


def extract_gateway_evidence(response: Any, headers=None) -> ScanEvidence:
    """Read AIRS check payloads, not gateway/IAM success or invented metadata."""
    data = as_dict(response)
    hooks = data.get("hook_results", {})
    if headers:
        encoded = headers.get("x-portkey-hook-results")
        if encoded:
            try:
                hooks = json.loads(encoded)
            except (ValueError, TypeError):
                return ScanEvidence(status="ERROR", source="gateway",
                                    error="Malformed gateway hook evidence")
    if not isinstance(hooks, dict):
        return ScanEvidence(status="ERROR", source="gateway",
                            error="Invalid gateway hook evidence")
    scans = []
    for phase in ("before_request_hooks", "after_request_hooks"):
        phase_hooks = hooks.get(phase, [])
        if not isinstance(phase_hooks, list):
            return ScanEvidence(status="ERROR", source="gateway", error="Invalid hook list")
        for hook in phase_hooks:
            if not isinstance(hook, dict):
                continue
            checks = hook.get("checks", [])
            if not isinstance(checks, list):
                return ScanEvidence(status="ERROR", source="gateway", error="Invalid checks list")
            for check in checks:
                if not isinstance(check, dict):
                    continue
                if "prisma-airs" in str(check.get("id", "")).lower():
                    scans.append(normalize_scan(check.get("data"), "gateway"))
    if not scans:
        return ScanEvidence(source="gateway")
    # An explicit block wins, otherwise every observed check must be valid.
    for scan in scans:
        if scan.action == "BLOCK":
            return scan.model_copy(update={"checks": [s.model_dump() for s in scans]})
    for scan in scans:
        if not scan.permits:
            return scan.model_copy(update={"checks": [s.model_dump() for s in scans]})
    return scans[-1].model_copy(update={"checks": [s.model_dump() for s in scans]})


class OfflineScanner:
    """Fixture runs do not impersonate a real security service."""
    required = False

    async def scan(self, **kwargs):
        return ScanEvidence(source="offline_fixture")

    async def close(self):
        pass


class AIRSScanner:
    required = True

    def __init__(self):
        # Upstream errors may log raw response bodies. Expose sanitized evidence instead.
        sdk_logger = logging.getLogger("aisecurity")
        sdk_logger.setLevel(logging.CRITICAL + 1)
        sdk_logger.propagate = False
        # Imports are lazy so the fixture workflow needs no SDK or credentials.
        import aisecurity
        from aisecurity.generated_openapi_client.models.ai_profile import AiProfile
        from aisecurity.scan.asyncio.scanner import Scanner

        if not os.getenv("PANW_AI_SEC_API_KEY"):
            raise ValueError("Set PANW_AI_SEC_API_KEY for live AIRS scans")
        profile = os.getenv("PANW_AI_SEC_PROFILE")
        if not profile:
            raise ValueError("Set PANW_AI_SEC_PROFILE for live AIRS scans")
        endpoint = os.getenv("PANW_AI_SEC_ENDPOINT",
                             "https://service.api.aisecurity.paloaltonetworks.com")
        allowed = {
            "https://service.api.aisecurity.paloaltonetworks.com",
            "https://service-de.api.aisecurity.paloaltonetworks.com",
            "https://service-in.api.aisecurity.paloaltonetworks.com",
            "https://service-sg.api.aisecurity.paloaltonetworks.com",
        }
        if endpoint not in allowed:
            raise ValueError("Select an official regional AIRS endpoint")
        aisecurity.init(api_key=os.environ["PANW_AI_SEC_API_KEY"],
                        api_endpoint=endpoint, num_retries=1)
        self.profile = AiProfile(profile_name=profile)
        self.scanner = Scanner()

    async def scan(self, *, prompt=None, response=None, tool_event=None):
        import asyncio

        from aisecurity.generated_openapi_client.models.tool_event import ToolEvent
        from aisecurity.scan.models.content import Content

        start = time.monotonic()
        try:
            content = Content(
                prompt=prompt, response=response,
                tool_event=ToolEvent.model_validate(tool_event) if tool_event else None,
            )
            result = await asyncio.wait_for(
                self.scanner.sync_scan(ai_profile=self.profile, content=content),
                timeout=30,
            )
            evidence = normalize_scan(result)
        except Exception as exc:  # noqa: BLE001 -- external SDK failures must fail closed without payload logging
            # SDK exceptions can contain headers/payloads: never persist str(exc).
            evidence = ScanEvidence(status="ERROR", source="airs",
                                    error=f"AIRS scan failed ({type(exc).__name__})")
        evidence.latency_ms = round((time.monotonic() - start) * 1000, 2)
        return evidence

    async def close(self):
        await self.scanner.close()
