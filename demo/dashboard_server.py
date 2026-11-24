"""
IntentGuard Security Benchmark Dashboard Server

Live dashboard for demonstrating security test execution.
WebSocket-based real-time updates.
"""
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from test_runner import TestRunner
from test_schema import TestCase, TestResult, Domain, AttackPattern


app = FastAPI(title="IntentGuard Security Benchmark")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting: {e}")


manager = ConnectionManager()


# API Models
class RunRequest(BaseModel):
    domain: Optional[str] = None  # Run specific domain or all
    verbose: bool = True


class TestStatus(BaseModel):
    test_id: str
    status: str  # "pending", "running", "completed"
    result: Optional[Dict[str, Any]] = None


# Test runner instance
runner = TestRunner()


@app.get("/")
async def get_dashboard():
    """Serve the split-screen dashboard HTML."""
    html_path = Path(__file__).parent / "ui" / "dashboard_split.html"
    with open(html_path, 'r') as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/demo")
async def get_demo_player():
    """Serve the interactive demo player."""
    html_path = Path(__file__).parent / "ui" / "demo_player.html"
    with open(html_path, 'r') as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/dashboard_unified.js")
async def get_dashboard_js():
    """Serve the dashboard JavaScript."""
    js_path = Path(__file__).parent / "ui" / "dashboard_unified.js"
    with open(js_path, 'r') as f:
        js_content = f.read()
    from fastapi.responses import Response
    return Response(content=js_content, media_type="application/javascript")


@app.get("/api/tests")
async def list_tests() -> Dict[str, Any]:
    """List all available test cases."""
    test_cases = runner.load_all_tests()

    # Group by domain
    by_domain = {}
    for test in test_cases:
        domain = test.domain.value
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append({
            "test_id": test.test_id,
            "attack_pattern": test.attack_pattern.value,
            "severity": test.severity.value,
            "user_intent": test.user_intent,
            "attack_description": test.ground_truth.attack_description,
            "business_impact": test.ground_truth.business_impact
        })

    return {
        "total": len(test_cases),
        "by_domain": by_domain,
        "domains": [d.value for d in Domain]
    }


@app.post("/api/run")
async def run_tests(request: RunRequest) -> Dict[str, Any]:
    """Trigger test execution (returns immediately, results via WebSocket)."""
    # Load test cases
    all_tests = runner.load_all_tests()

    # Filter by domain if specified
    if request.domain:
        test_cases = [t for t in all_tests if t.domain.value == request.domain]
    else:
        test_cases = all_tests

    # Send first test's contract info immediately for left panel
    if test_cases:
        first_test = test_cases[0]
        await manager.broadcast({
            "type": "contract_info",
            "data": {
                "user_intent": first_test.user_intent,
                "contract": {
                    "authorized_tools": first_test.intent_contract.authorized_tools,
                    "resource_scope": {
                        "transaction_ids": first_test.intent_contract.resource_scope.transaction_ids,
                        "account_ids": first_test.intent_contract.resource_scope.account_ids,
                    },
                    "constraints": first_test.intent_contract.constraints.model_dump()
                }
            }
        })

    # Run tests in background
    asyncio.create_task(
        run_tests_background(test_cases, request.verbose)
    )

    return {
        "status": "started",
        "test_count": len(test_cases),
        "domain": request.domain or "all"
    }


async def run_test_with_streaming(test_case: TestCase, verbose: bool) -> TestResult:
    """Run a single test and stream step execution via WebSocket."""
    from src.deviation_detector import DeviationDetector

    detector = DeviationDetector(test_case.intent_contract)

    for step_idx, step in enumerate(test_case.attack_sequence, start=1):
        # Send step execution start
        await manager.broadcast({
            "type": "step_executing",
            "data": {
                "test_id": test_case.test_id,
                "step": step_idx,
                "tool": step.tool,
                "params": step.params
            }
        })

        await asyncio.sleep(0.4)  # Visual delay

        # Analyze this step
        try:
            # Create tool_call dict in the format DeviationDetector expects
            tool_call = {
                'name': step.tool,
                'params': step.params,
                'timestamp': None
            }
            analysis = detector.analyze_tool_call(tool_call)

            # Map DeviationAnalysis to expected format
            class AnalysisResult:
                def __init__(self, da):
                    self.score = da.overall_score
                    self.reason = '; '.join(da.reasons) if da.reasons else "No violations"

            analysis = AnalysisResult(analysis)

        except Exception as e:
            print(f"Error analyzing step {step_idx}: {e}")
            import traceback
            traceback.print_exc()
            # Continue with score 0 if analysis fails
            class FallbackAnalysis:
                score = 0
                reason = f"Analysis error: {str(e)}"
            analysis = FallbackAnalysis()

        # Determine violation type
        violation_type = None
        violated_contract_part = None

        if analysis.score >= 70:
            # Parse the reason to determine what was violated
            reason = analysis.reason.lower()
            if 'unauthorized tool' in reason:
                violation_type = 'unauthorized_tool'
                violated_contract_part = step.tool
            elif 'not in authorized scope' in reason or 'resource' in reason:
                violation_type = 'scope_violation'
                # Extract resource ID from params
                for param_name in ['tx_id', 'order_id', 'booking_id', 'account_id', 'loan_id']:
                    if param_name in step.params:
                        violated_contract_part = step.params[param_name]
                        break
            elif 'constraint' in reason or 'violates' in reason:
                violation_type = 'constraint_violation'
                violated_contract_part = analysis.reason.split('constraint:')[-1].strip() if 'constraint:' in analysis.reason else 'unknown'
            elif 'timing violation' in reason or 'prerequisite' in reason:
                violation_type = 'timing_violation'
                violated_contract_part = step.tool
            elif 'duplicate' in reason:
                violation_type = 'business_logic'
                violated_contract_part = step.tool

        # Send step execution result
        await manager.broadcast({
            "type": "step_executed",
            "data": {
                "test_id": test_case.test_id,
                "step": step_idx,
                "tool": step.tool,
                "params": step.params,
                "deviation_score": analysis.score,
                "blocked": analysis.score >= 70,
                "reason": analysis.reason if analysis.score >= 70 else None,
                "violation_type": violation_type,
                "violated_contract_part": violated_contract_part
            }
        })

        # If blocked, stop execution
        if analysis.score >= 70:
            result = TestResult(
                test_id=test_case.test_id,
                detected=True,
                blocked_at_stage=step_idx,
                deviation_score=analysis.score,
                block_reason=analysis.reason,
                execution_time_ms=0.0,
                false_positive=False
            )
            return result

        await asyncio.sleep(0.3)  # Delay between steps

    # All steps passed - test failed to detect
    result = TestResult(
        test_id=test_case.test_id,
        detected=False,
        blocked_at_stage=None,
        deviation_score=None,
        block_reason=None,
        execution_time_ms=0.0,
        false_positive=False
    )
    return result


async def run_tests_background(test_cases: List[TestCase], verbose: bool):
    """Run tests in background and stream results via WebSocket."""
    # Send start event
    await manager.broadcast({
        "type": "test_suite_started",
        "data": {
            "total_tests": len(test_cases),
            "timestamp": datetime.utcnow().isoformat()
        }
    })

    results = []

    for idx, test_case in enumerate(test_cases, start=1):
        # Send test start event
        await manager.broadcast({
            "type": "test_started",
            "data": {
                "test_id": test_case.test_id,
                "domain": test_case.domain.value,
                "attack_pattern": test_case.attack_pattern.value,
                "user_intent": test_case.user_intent,
                "progress": idx,
                "total": len(test_cases),
                "intent_contract": {
                    "authorized_tools": test_case.intent_contract.authorized_tools,
                    "resource_scope": {
                        "transaction_ids": test_case.intent_contract.resource_scope.transaction_ids,
                        "account_ids": test_case.intent_contract.resource_scope.account_ids,
                        "allowed_scope_expansion": test_case.intent_contract.resource_scope.allowed_scope_expansion
                    },
                    "constraints": test_case.intent_contract.constraints.model_dump()
                },
                "attack_sequence": [
                    {
                        "step": i + 1,
                        "tool": tc.tool,
                        "params": tc.params,
                        "should_allow": tc.should_allow,
                        "note": tc.note
                    }
                    for i, tc in enumerate(test_case.attack_sequence)
                ]
            }
        })

        # Execute steps one by one with streaming
        try:
            result = await run_test_with_streaming(test_case, verbose)
            results.append(result)
            print(f"✓ Completed test {test_case.test_id}: {'DETECTED' if result.detected else 'MISSED'}")
        except Exception as e:
            print(f"✗ Error running test {test_case.test_id}: {e}")
            import traceback
            traceback.print_exc()
            # Create a failed result
            result = TestResult(
                test_id=test_case.test_id,
                detected=False,
                blocked_at_stage=None,
                deviation_score=None,
                block_reason=f"Test execution error: {str(e)}",
                execution_time_ms=0.0,
                false_positive=False
            )
            results.append(result)

        # Send test complete event with detailed results
        await manager.broadcast({
            "type": "test_completed",
            "data": {
                "test_id": test_case.test_id,
                "domain": test_case.domain.value,
                "attack_pattern": test_case.attack_pattern.value,
                "severity": test_case.severity.value,
                "user_intent": test_case.user_intent,
                "attack_description": test_case.ground_truth.attack_description,
                "business_impact": test_case.ground_truth.business_impact,
                "intent_contract": {
                    "authorized_tools": test_case.intent_contract.authorized_tools,
                    "resource_scope": {
                        "transaction_ids": test_case.intent_contract.resource_scope.transaction_ids,
                        "account_ids": test_case.intent_contract.resource_scope.account_ids,
                        "allowed_scope_expansion": test_case.intent_contract.resource_scope.allowed_scope_expansion
                    },
                    "constraints": test_case.intent_contract.constraints.model_dump()
                },
                "result": {
                    "detected": result.detected,
                    "blocked_at_stage": result.blocked_at_stage,
                    "expected_block_stage": test_case.ground_truth.block_stage,
                    "deviation_score": result.deviation_score,
                    "block_reason": result.block_reason,
                    "execution_time_ms": result.execution_time_ms,
                    "false_positive": result.false_positive
                },
                "attack_sequence": [
                    {
                        "step": i + 1,
                        "tool": tc.tool,
                        "params": tc.params,
                        "should_allow": tc.should_allow,
                        "note": tc.note
                    }
                    for i, tc in enumerate(test_case.attack_sequence)
                ],
                "progress": idx,
                "total": len(test_cases)
            }
        })

        # Delay between tests so user can see each one
        await asyncio.sleep(1.0)

    # Calculate final metrics
    total = len(results)
    detected = sum(1 for r in results if r.detected)
    missed = total - detected
    detection_rate = (detected / total * 100) if total > 0 else 0

    detected_scores = [r.deviation_score for r in results if r.deviation_score is not None]
    avg_deviation = sum(detected_scores) / len(detected_scores) if detected_scores else 0

    # Send suite complete event
    await manager.broadcast({
        "type": "test_suite_completed",
        "data": {
            "total_tests": total,
            "detected": detected,
            "missed": missed,
            "detection_rate": detection_rate,
            "average_deviation_score": avg_deviation,
            "timestamp": datetime.utcnow().isoformat()
        }
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "intentguard-benchmark",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("IntentGuard Security Benchmark Dashboard")
    print("="*60)
    print("Starting server at http://localhost:8002")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
