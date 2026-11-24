"""Single-user localhost API. Run one worker; documents are owner-scoped."""
import asyncio
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.airs import AIRSScanner, OfflineScanner
from src.assurance_campaign import Campaigns
from src.assurance_evaluator import Evaluator
from src.assurance_gateway import (
    GatewayFailure,
    gateway_identity,
    gateway_readiness,
    load_gateway_settings,
)
from src.assurance_models import (
    Action,
    ApprovalInput,
    Composition,
    EvaluationInput,
    RuntimeInput,
    StrictModel,
    digest,
)
from src.assurance_runtime import AssuranceRuntime, identifier
from src.assurance_store import Store, redact
from src.campaign_api import install_campaign_routes
from src.sandbox_crm import TOOLS

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "assurance_owner"


def live_readiness():
    required = ("ANTHROPIC_API_KEY", "PANW_AI_SEC_API_KEY", "PANW_AI_SEC_PROFILE")
    enabled = os.getenv("MVP_ENABLE_LIVE") == "1"
    missing = ([] if enabled else ["MVP_ENABLE_LIVE=1"]) + [
        name for name in required if not os.getenv(name)
    ]
    return {
        "enabled": enabled,
        "credentials_configured": all(os.getenv(name) for name in required),
        "ready": not missing,
        "missing": missing,
        "message": (
            "Live services are configured; connectivity has not been verified."
            if not missing else
            "Live mode is unavailable. Configure " + ", ".join(missing) +
            " in the server environment and restart, or select an Offline fixture composition."
        ),
    }


class PromptInput(StrictModel):
    prompt: str = Field(min_length=1, max_length=8000)


def create_app(db_path=None):
    @asynccontextmanager
    async def lifespan(app):
        store = Store(db_path or os.getenv("MVP_DB_PATH", str(ROOT / "data/assurance.sqlite")))
        app.state.store = store
        app.state.runtime = AssuranceRuntime(store)
        app.state.workflow = asyncio.Lock()
        app.state.sockets = 0
        app.state.live_scanner = None
        app.state.gateway_error = None
        try:
            settings = load_gateway_settings()
        except GatewayFailure as exc:
            settings = None
            app.state.gateway_error = str(exc)
        app.state.campaigns = Campaigns(app.state.runtime, settings, app.state.workflow)
        with store.db:
            store.db.execute(
                "UPDATE documents SET payload=json_set(payload,'$.status','interrupted') "
                "WHERE kind='run' AND json_extract(payload,'$.status')='running'"
            )
        with store.db:
            store.db.execute(
                "UPDATE documents SET payload=json_set(payload,'$.status','partial',"
                "'$.error','Server restarted; completed cases will not be replayed') "
                "WHERE kind='campaign' AND json_extract(payload,'$.status') IN ('running','queued','cancelling')"
            )
        try:
            yield
        finally:
            await app.state.campaigns.shutdown()
            if app.state.live_scanner is not None:
                await app.state.live_scanner.close()
            store.close()

    app = FastAPI(title="Prisma AIRS Behavioral Assurance MVP", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    def origin_allowed(origin, host):
        return origin in {f"http://{host}", f"https://{host}"}

    @app.middleware("http")
    async def local_boundary(request, call_next):
        origin = request.headers.get("origin")
        if origin and not origin_allowed(origin, request.headers.get("host", "")):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 1_000_000:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        owner = request.cookies.get(COOKIE, "")
        fresh = not re.fullmatch(r"[a-f0-9]{64}", owner)
        request.state.owner = secrets.token_hex(32) if fresh else owner
        response = await call_next(request)
        if fresh:
            response.set_cookie(COOKIE, request.state.owner, httponly=True,
                                samesite="strict", max_age=30 * 86400)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Resource not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": redact(str(exc))}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse({"detail": [{"loc": e["loc"], "type": e["type"]}
                                       for e in exc.errors()]}, status_code=422)

    @asynccontextmanager
    async def workflow():
        if app.state.workflow.locked():
            raise HTTPException(409, {
                "code": "WORKFLOW_BUSY",
                "message": "Another workflow is running; retry after it completes",
            })
        async with app.state.workflow:
            yield

    def require_ready(composition):
        if composition["mode"] == "gateway":
            raise HTTPException(409, {
                "code": "GATEWAY_CAMPAIGN_REQUIRED",
                "message": "Use the gateway campaign workflow with approved preflight and budget.",
            })
        if composition["mode"] == "live":
            readiness = live_readiness()
            if not readiness["ready"]:
                raise HTTPException(503, {
                    "code": "LIVE_NOT_CONFIGURED",
                    "message": readiness["message"],
                    "missing": readiness["missing"],
                })

    @asynccontextmanager
    async def scanner_for(composition):
        if composition["mode"] == "offline":
            yield OfflineScanner()
            return
        require_ready(composition)
        # The upstream SDK uses singleton executors. Closing per HTTP request
        # would leave later scanners holding a closed connection pool.
        if app.state.live_scanner is None:
            try:
                app.state.live_scanner = AIRSScanner()
            except ValueError:
                raise HTTPException(503, {
                    "code": "LIVE_CONFIGURATION_ERROR",
                    "message": "Live scanner configuration is invalid; check the AIRS profile and regional endpoint.",
                }) from None
        yield app.state.live_scanner

    def runtime_session(request, session_id):
        current = app.state.store.get("session", request.state.owner, session_id)
        expected = request.headers.get("X-Composition-ID")
        if expected and expected != current["composition_id"]:
            raise HTTPException(409, {
                "code": "SESSION_COMPOSITION_MISMATCH",
                "message": "This session belongs to another composition. Select its composition or start a new session.",
            })
        if current.get("purpose") == "evaluation":
            raise HTTPException(409, {
                "code": "EVALUATION_SESSION",
                "message": "Evaluation sessions are read-only. Start a runtime session for interactive actions.",
            })
        return current

    def snapshot(owner):
        store = app.state.store
        return {
            "compositions": store.list("composition", owner),
            "runs": [{k: v for k, v in r.items() if k != "results"}
                     for r in store.list("run", owner)],
            "policies": store.list("policy", owner),
            "approvals": store.list("approval", owner),
            # Evaluation cases must not evict interactive sessions from the UI.
            "sessions": [
                {**{k: s[k] for k in
                    ("id", "composition_id", "mode", "protected", "calls", "created_at")},
                 "agent_status": s.get("agent_status")}
                for s in store.list("session", owner) if s.get("purpose") != "evaluation"
            ],
            "capabilities": {"live": live_readiness(),
                             "gateway": gateway_readiness(app.state.campaigns.settings)},
            "snapshot_at": time.monotonic(),
        }

    @app.get("/")
    async def dashboard():
        return FileResponse(ROOT / "composition_dashboard.html")

    @app.get("/assets/{name}")
    async def asset(name: str):
        allowed = {"assurance.js": "text/javascript", "assurance.css": "text/css",
                   "campaigns.js": "text/javascript"}
        if name not in allowed:
            raise HTTPException(404)
        return FileResponse(ROOT / "static" / name, media_type=allowed[name])

    @app.get("/health")
    async def health():
        app.state.store.db.execute("SELECT 1")
        readiness = live_readiness()
        return {"status": "healthy", "default_mode": "offline",
                "live_enabled": readiness["enabled"],
                "live_credentials_configured": readiness["credentials_configured"],
                "live_ready": readiness["ready"], "live_missing": readiness["missing"]}

    @app.get("/api/state")
    async def state(request: Request):
        return snapshot(request.state.owner)

    @app.post("/api/compositions")
    async def composition(body: Composition, request: Request):
        async with workflow():
            data, tools = redact(body.model_dump()), TOOLS
            if body.mode in {"live", "gateway"}:
                from src.crm_mcp_client import CRMConnector
                async with CRMConnector() as connector:
                    tools = connector.tools
            data.update(
                id=identifier(), provider="fixture" if body.mode == "offline" else "anthropic",
                skill_hash=digest(data["skill"]), tool_schema_hash=digest(tools),
                connector_version=digest((ROOT / "src/sandbox_crm.py").read_text()),
            )
            if body.mode == "gateway":
                settings = app.state.campaigns.settings
                if settings is None:
                    raise HTTPException(503, "Configure GATEWAY_ASSURANCE_CONFIG before registering a gateway composition")
                data.update(provider="gateway", model=settings.routes[settings.target_route].model,
                            gateway_fingerprint=gateway_identity(settings))
            data["hash"] = digest({k: v for k, v in data.items() if k != "id"})
            return app.state.store.put("composition", request.state.owner, data)

    @app.post("/api/evaluations")
    async def evaluate(body: EvaluationInput, request: Request):
        owner = request.state.owner
        comp = app.state.store.get("composition", owner, body.composition_id)
        async with workflow(), scanner_for(comp) as scanner:
            agent = None
            if comp["mode"] == "live":
                from src.assurance_agent import LiveAgent
                agent = LiveAgent(app.state.runtime, scanner)
            return await Evaluator(app.state.runtime).run(owner, body, scanner, agent)

    @app.get("/api/runs/{run_id}")
    async def run_detail(run_id: str, request: Request):
        return app.state.store.get("run", request.state.owner, run_id)

    @app.get("/api/runs/{run_id}/export")
    async def export(run_id: str, request: Request):
        run = app.state.store.get("run", request.state.owner, run_id)
        policies = [p for p in app.state.store.list("policy", request.state.owner)
                    if p["source_run"] == run_id]
        return JSONResponse(
            redact({"run": run, "policies": policies, "exported_at": time.time()}),
            headers={"Content-Disposition": f'attachment; filename="assurance-{run_id}.json"'},
        )

    @app.post("/api/runs/{run_id}/policies")
    async def suggest(run_id: str, request: Request):
        async with workflow():
            return app.state.runtime.generate_policies(request.state.owner, run_id)

    @app.post("/api/policies/{policy_id}/activate")
    async def activate(policy_id: str, request: Request):
        async with workflow():
            return await app.state.runtime.activate(request.state.owner, policy_id)

    @app.post("/api/sessions")
    async def session(body: RuntimeInput, request: Request):
        async with workflow():
            comp = app.state.store.get("composition", request.state.owner, body.composition_id)
            require_ready(comp)
            created = app.state.runtime.create_session(
                request.state.owner, body.composition_id, body.protected
            )
            return {k: v for k, v in created.items() if k != "state"}

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str, request: Request):
        current = app.state.store.get("session", request.state.owner, session_id)
        return {k: v for k, v in current.items() if k not in {"messages", "state", "pending_outputs"}}

    @app.post("/api/sessions/{session_id}/calls")
    async def tool_call(session_id: str, body: Action, request: Request):
        owner = request.state.owner
        current = runtime_session(request, session_id)
        comp = app.state.store.get("composition", owner, current["composition_id"])
        async with workflow(), scanner_for(comp) as scanner:
            if comp["mode"] == "live":
                from src.crm_mcp_client import CRMConnector
                async with CRMConnector() as connector:
                    return await app.state.runtime.call(owner, session_id, body, scanner, connector)
            return await app.state.runtime.call(owner, session_id, body, scanner)

    @app.post("/api/sessions/{session_id}/agent")
    async def agent_task(session_id: str, body: PromptInput, request: Request):
        owner = request.state.owner
        current = runtime_session(request, session_id)
        comp = app.state.store.get("composition", owner, current["composition_id"])
        if comp["mode"] != "live":
            raise HTTPException(409, {
                "code": "AGENT_MODE_MISMATCH",
                "message": "Offline fixtures do not generate model responses. Select a configured live composition.",
            })
        if current.get("messages") or current.get("agent_status"):
            raise HTTPException(409, {
                "code": "AGENT_SESSION_USED",
                "message": "This agent session already has a task. Resolve pending approvals or start a new session.",
            })
        from src.assurance_agent import LiveAgent
        async with workflow(), scanner_for(comp) as scanner:
            try:
                await LiveAgent(app.state.runtime, scanner).run(owner, session_id, body.prompt)
            except Exception as exc:  # noqa: BLE001 -- sanitize provider errors at API boundary
                current = app.state.store.get("session", owner, session_id)
                current["agent_status"] = "error"
                app.state.store.put("session", owner, current)
                raise HTTPException(502, f"Live task failed ({type(exc).__name__}); inspect readiness") from None
        return await session_detail(session_id, request)

    @app.post("/api/approvals/{approval_id}")
    async def approval(approval_id: str, body: ApprovalInput, request: Request):
        owner = request.state.owner
        pending = app.state.store.get("approval", owner, approval_id)
        comp = app.state.store.get("composition", owner, pending["composition_id"])
        async with workflow(), scanner_for(comp) as scanner:
            if comp["mode"] == "live":
                from src.assurance_agent import LiveAgent
                from src.crm_mcp_client import CRMConnector
                async with CRMConnector() as connector:
                    receipt = await app.state.runtime.approve(
                        owner, approval_id, body.approve, scanner, connector
                    )
                current = app.state.store.get("session", owner, pending["session_id"])
                if current.get("waiting_calls"):
                    try:
                        await LiveAgent(app.state.runtime, scanner).run(owner, current["id"])
                    except Exception as exc:  # noqa: BLE001 -- execution receipt must survive resume errors
                        receipt["resume_error"] = type(exc).__name__
                return receipt
            return await app.state.runtime.approve(owner, approval_id, body.approve, scanner)

    @app.websocket("/ws")
    async def events(websocket: WebSocket):
        owner = websocket.cookies.get(COOKIE, "")
        if not re.fullmatch(r"[a-f0-9]{64}", owner) or not origin_allowed(
            websocket.headers.get("origin", ""), websocket.headers.get("host", "")
        ) or app.state.sockets >= 10:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        app.state.sockets += 1
        try:
            while True:
                await websocket.send_json({"type": "state", "data": snapshot(owner)})
                await asyncio.sleep(1)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass
        finally:
            app.state.sockets -= 1

    install_campaign_routes(app)
    return app
