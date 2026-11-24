"""Live model loop. Security calls are host-enforced, never optional model tools."""
import json
import os

from anthropic import AsyncAnthropic

from src.assurance_models import Action, digest
from src.crm_mcp_client import CRMConnector


class LiveAgent:
    def __init__(self, runtime, scanner):
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("Set ANTHROPIC_API_KEY for live evaluation")
        self.runtime = runtime
        self.store = runtime.store
        self.scanner = scanner

    def save(self, owner, session_id, **updates):
        session = self.store.get("session", owner, session_id)
        session.update(updates)
        return self.store.put("session", owner, session)

    async def run(self, owner, session_id, prompt=None):
        session = self.store.get("session", owner, session_id)
        composition = self.store.get("composition", owner, session["composition_id"])
        async with AsyncAnthropic(timeout=60, max_retries=1) as client:
            # Catch unavailable model/auth early, without silently changing providers.
            await client.models.retrieve(composition["model"])
            async with CRMConnector() as connector:
                if digest(connector.tools) != composition["tool_schema_hash"]:
                    raise ValueError("Connector schemas changed; register a new composition")
                definition_scan = await self.scanner.scan(tool_event={
                    "metadata": {"ecosystem": "mcp", "method": "tools/list",
                                 "server_name": "sandbox-crm"},
                    "output": json.dumps(connector.tools),
                })
                scans = session.get("agent_scans", []) + [definition_scan.model_dump()]
                if session["protected"] and not definition_scan.permits:
                    return self.save(owner, session_id, agent_status="blocked",
                                     agent_scans=scans, final="Tool definitions not cleared by AIRS")
                messages = session.get("messages", [])
                if prompt is not None:
                    if messages:
                        raise ValueError("Start a fresh runtime session for a new task")
                    evidence = await self.scanner.scan(prompt=prompt)
                    scans.append(evidence.model_dump())
                    if session["protected"] and not evidence.permits:
                        return self.save(owner, session_id, agent_status="blocked",
                                         agent_scans=scans, final="Prompt not cleared by AIRS")
                    messages.append({"role": "user", "content": prompt})
                elif session.get("waiting_calls"):
                    receipts = {c["call_id"]: c for c in session["calls"]}
                    calls = [receipts[i] for i in session["waiting_calls"]]
                    if any(c["verdict"] == "REQUIRE_CONFIRMATION" for c in calls):
                        return session
                    messages.append({"role": "user", "content": [
                        self.tool_result(c) for c in calls
                    ]})
                else:
                    raise ValueError("Session has no paused agent to resume")
                self.save(owner, session_id, messages=messages, waiting_calls=[],
                          agent_scans=scans, agent_status="running")
                for iteration in range(session.get("iterations", 0), 10):
                    params = {
                        "model": composition["model"], "max_tokens": 4096,
                        "system": composition["system"] + "\n" + composition["skill"],
                        "messages": messages, "tools": connector.tools,
                        "cache_control": {"type": "ephemeral"},
                    }
                    if composition["model"] == "claude-opus-4-7":
                        params["thinking"] = {"type": "adaptive"}
                    async with client.messages.stream(**params) as stream:
                        response = await stream.get_final_message()
                    text = "\n".join(b.text for b in response.content if b.type == "text")
                    response_scan = None
                    if text:
                        response_scan = await self.scanner.scan(
                            prompt=messages[0]["content"], response=text
                        )
                        scans.append(response_scan.model_dump())
                        if session["protected"] and not response_scan.permits:
                            return self.save(
                                owner, session_id, agent_scans=scans,
                                agent_status="blocked", final="Output withheld by AIRS",
                                iterations=iteration + 1,
                            )
                    messages.append({"role": "assistant", "content": [
                        b.model_dump(mode="json", exclude_none=True) for b in response.content
                    ]})
                    calls = [b for b in response.content if b.type == "tool_use"]
                    if response.stop_reason not in {"tool_use", "end_turn"}:
                        raise ValueError("Model output incomplete or refused; evaluation inconclusive")
                    if not calls:
                        if not text or response_scan is None:
                            raise ValueError("Model returned no final text; evaluation inconclusive")
                        cleared = not session["protected"] or response_scan.permits
                        # No unchecked model response is returned or persisted as a message.
                        if not cleared:
                            messages[-1] = {"role": "assistant", "content": "Output withheld by AIRS"}
                        return self.save(
                            owner, session_id, messages=messages, agent_scans=scans,
                            agent_status="complete" if cleared else "blocked",
                            final=text if cleared else "Output withheld by AIRS",
                            actual_model=response.model, iterations=iteration + 1,
                        )
                    receipts = []
                    if len(calls) > 20:
                        raise ValueError("Model exceeded tool-call budget")
                    for call in calls:
                        receipts.append(await self.runtime.call(
                            owner, session_id,
                            Action(tool=call.name, arguments=call.input, call_id=call.id),
                            scanner=self.scanner, connector=connector,
                        ))
                    if any(c["verdict"] == "REQUIRE_CONFIRMATION" for c in receipts):
                        return self.save(
                            owner, session_id, messages=messages, agent_scans=scans,
                            waiting_calls=[c["call_id"] for c in receipts],
                            agent_status="awaiting_approval", iterations=iteration + 1,
                            actual_model=response.model,
                        )
                    messages.append({"role": "user", "content": [
                        self.tool_result(c) for c in receipts
                    ]})
                    self.save(owner, session_id, messages=messages, agent_scans=scans,
                              iterations=iteration + 1, actual_model=response.model)
                raise ValueError("Agent reached ten-turn limit; evaluation inconclusive")

    @staticmethod
    def tool_result(call):
        failed = not call["executed"] or call.get("output_withheld", False)
        return {
            "type": "tool_result", "tool_use_id": call["call_id"],
            "is_error": failed,
            "content": json.dumps(call.get("result", {"error": call["verdict"],
                                                     "reasons": call["reasons"]})),
        }
