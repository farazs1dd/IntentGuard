"""Campaign routes. Starting work always requires explicit budget consent."""
import json
import time
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.assurance_gateway import (
    Censored,
    GatewayFailure,
    Ledger,
    gateway_identity,
    gateway_readiness,
)
from src.assurance_models import digest
from src.assurance_runtime import identifier
from src.campaign_models import CampaignInput, Consent, PreflightInput, Review


def install_campaign_routes(app):
    def manager():
        return app.state.campaigns

    def ready(*, for_preflight=False):
        result = gateway_readiness(manager().settings, for_preflight=for_preflight)
        if not result["ready"]:
            raise HTTPException(503, {"code": "GATEWAY_NOT_CONFIGURED", **result})

    def verified(owner):
        ready()
        fingerprint = gateway_identity(manager().settings)
        try:
            preflight = manager().store.get("preflight", owner, fingerprint)
        except KeyError:
            preflight = {}
        if preflight.get("status") != "passed":
            raise HTTPException(409, {
                "code": "GATEWAY_PREFLIGHT_REQUIRED",
                "message": "Approve and pass gateway security/tool-call preflight before running a campaign",
            })

    @app.get("/api/gateway")
    async def gateway_info(request: Request):
        service = manager()
        settings = service.settings
        preflight = None
        if settings:
            try:
                preflight = service.store.get("preflight", request.state.owner, gateway_identity(settings))
            except KeyError:
                pass
        return {
            **gateway_readiness(settings), "configuration_error": app.state.gateway_error,
            "endpoint": settings.endpoint if settings else None,
            "fingerprint": gateway_identity(settings) if settings else None,
            "routes": {key: value.model_dump() for key, value in settings.routes.items()} if settings else {},
            "preflight": preflight,
        }

    @app.post("/api/gateway/preflight")
    async def preflight(body: PreflightInput, request: Request):
        ready(for_preflight=True)
        service, owner = manager(), request.state.owner
        if service.settings.endpoint.startswith("http://") and not body.acknowledge_http:
            raise HTTPException(409, {
                "code": "HTTP_TRANSPORT_CONSENT_REQUIRED",
                "message": "This endpoint uses HTTP without TLS. Explicit transport acknowledgement is required before sending credentials.",
            })
        if service.lock.locked():
            raise HTTPException(409, "Another workflow is running")
        async with service.lock:
            settings = service.settings
            fingerprint = gateway_identity(settings)
            budget_id = identifier()
            ledger = Ledger.create(service.store, owner, budget_id, body.limits)
            record = {"id": fingerprint, "budget_id": budget_id, "status": "running",
                      "routes_checked": [], "timestamp": time.time(),
                      "http_transport_acknowledged": body.acknowledge_http}
            service.store.put("preflight", owner, record)
            try:
                for route_name in {settings.target_route, settings.analyst_route, settings.judge_route}:
                    scoped = settings.model_copy(update={"target_route": route_name})
                    gateway = service.gateway_factory(scoped, ledger)
                    gateway.validation_only = True
                    tools = [{"type": "function", "function": {
                        "name": "assurance_echo", "description": "Harmless connection test",
                        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                                       "required": ["text"], "additionalProperties": False},
                    }}]
                    messages = [{"role": "user", "content": "Call assurance_echo with text ping."}]
                    message, _ = await gateway.complete("target", messages, tools=tools)
                    calls = message.get("tool_calls") or []
                    if len(calls) != 1 or calls[0]["function"]["name"] != "assurance_echo":
                        raise GatewayFailure("Gateway route did not complete the expected tool call")
                    if json.loads(calls[0]["function"]["arguments"]) != {"text": "ping"}:
                        raise GatewayFailure("Gateway tool arguments were changed")
                    messages.extend([message, {
                        "role": "tool", "tool_call_id": calls[0]["id"], "content": '{"text":"pong"}',
                    }])
                    final, _ = await gateway.complete("target", messages, tools=tools)
                    if final.get("tool_calls") or not final.get("content"):
                        raise GatewayFailure("Gateway tool-result round trip did not complete")
                    prevented = False
                    try:
                        await gateway.complete("target", [{"role": "user", "content": body.block_probe}])
                    except Censored:
                        latest = next(c for c in service.store.list("gateway_call", owner)
                                      if c["budget_id"] == budget_id)
                        prevented = latest["http_status"] == 446 and any(
                            latest[phase]["status"] == "SCANNED" and latest[phase]["action"] == "BLOCK"
                            for phase in ("input", "output")
                        )
                    if not prevented:
                        raise GatewayFailure("Probe did not prove a synchronous AIRS deny; verify the gateway config")
                    record["routes_checked"].append(route_name)
                record["status"] = "passed"
            except (ValueError, KeyError, TypeError) as exc:
                record.update(status="failed", error=str(exc) if isinstance(exc, GatewayFailure)
                              else "Unexpected gateway contract; no protection claim made")
            record["observed_models"] = sorted({
                call["actual_model"] for call in service.store.list("gateway_call", owner)
                if call["budget_id"] == budget_id and isinstance(call.get("actual_model"), str)
            })
            service.store.put("preflight", owner, record)
            return {**record, "budget": service.store.get("budget", owner, budget_id)}

    @app.post("/api/campaigns")
    async def create(body: CampaignInput, request: Request):
        return manager().public(request.state.owner, manager().create(request.state.owner, body))

    @app.get("/api/campaigns")
    async def campaigns(request: Request):
        return [manager().public(request.state.owner, doc)
                for doc in manager().store.list("campaign", request.state.owner)]

    @app.get("/api/campaigns/{campaign_id}")
    async def campaign(campaign_id: str, request: Request):
        return manager().public(request.state.owner, manager().get(request.state.owner, campaign_id))

    @app.post("/api/campaigns/{campaign_id}/start")
    async def start(campaign_id: str, body: Consent, request: Request):
        manager().get(request.state.owner, campaign_id)
        verified(request.state.owner)
        manager().schedule(request.state.owner, campaign_id)
        return {"id": campaign_id, "status": "queued"}

    @app.post("/api/campaigns/{campaign_id}/cancel")
    async def cancel(campaign_id: str, request: Request):
        return manager().public(request.state.owner, manager().cancel(request.state.owner, campaign_id))

    @app.post("/api/campaigns/{campaign_id}/review")
    async def review(campaign_id: str, body: Review, request: Request):
        return manager().public(request.state.owner, manager().review(request.state.owner, campaign_id, body))

    @app.get("/api/campaigns/{campaign_id}/drift")
    async def drift(campaign_id: str, request: Request):
        service = manager()
        doc = service.get(request.state.owner, campaign_id)
        comp = service.store.get("composition", request.state.owner, doc["composition_id"])
        return {"composition_changed": comp["hash"] != doc["composition_hash"],
                "connector_source_changed": digest(
                    Path(__file__).with_name("sandbox_crm.py").read_text()
                ) != comp["connector_version"],
                "remote_config_note": "Fingerprints track configured references, not undetectable remote edits under the same config ID. Re-run preflight after gateway changes.",
                "gateway_changed": service.settings is None or
                gateway_identity(service.settings) != doc["gateway_fingerprint"]}

    @app.get("/api/campaigns/{campaign_id}/export")
    async def export(campaign_id: str, request: Request):
        service, owner = manager(), request.state.owner
        doc = service.public(owner, service.get(owner, campaign_id))
        doc["gateway_calls"] = [c for c in service.store.list("gateway_call", owner)
                                if c["budget_id"] == campaign_id]
        return JSONResponse(doc, headers={
            "Content-Disposition": f'attachment; filename="campaign-{campaign_id}.json"',
        })
