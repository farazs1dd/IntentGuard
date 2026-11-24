"""
Activity Timeline Logger for IntentGuard

Production-grade logging with timeline view, structured events, and audit trail.
Inspired by security scanning tools with step-by-step execution tracking.
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ActivityStatus(Enum):
    """Activity execution status."""
    STARTED = "STARTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    ALLOWED = "ALLOWED"
    FAILED = "FAILED"


class ActivityType(Enum):
    """Type of activity being logged."""
    SESSION_INIT = "SESSION_INIT"
    USER_REQUEST = "USER_REQUEST"
    INTENT_ANALYSIS = "INTENT_ANALYSIS"
    TOOL_DISCOVERY = "TOOL_DISCOVERY"
    TOOL_CALL = "TOOL_CALL"
    INTERCEPTION = "INTERCEPTION"
    DEVIATION_ANALYSIS = "DEVIATION_ANALYSIS"
    VERDICT = "VERDICT"
    EXECUTION = "EXECUTION"
    RESPONSE = "RESPONSE"


@dataclass
class ActivityEvent:
    """Structured activity event with full context."""
    timestamp: str
    elapsed_ms: float
    event_id: str
    event_type: ActivityType
    status: ActivityStatus
    method: Optional[str]  # HTTP method or action type (POST, GET, CALL, etc.)
    endpoint: Optional[str]  # Tool name or API endpoint
    message: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "elapsed_ms": self.elapsed_ms,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "status": self.status.value,
            "method": self.method,
            "endpoint": self.endpoint,
            "message": self.message,
            "metadata": self.metadata
        }


class ActivityLogger:
    """
    Production-grade activity logger with timeline tracking.

    Features:
    - Timeline-based event tracking
    - Structured JSON logging
    - Audit trail persistence
    - Real-time streaming
    - Compliance-ready output
    """

    def __init__(self, session_id: str, output_dir: str = "logs"):
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.start_time = time.time()
        self.events: List[ActivityEvent] = []
        self.event_counter = 0

        # Create session log file
        self.log_file = self.output_dir / f"session_{session_id}.jsonl"

    def _elapsed_ms(self) -> float:
        """Calculate elapsed time in milliseconds."""
        return (time.time() - self.start_time) * 1000

    def _elapsed_str(self) -> str:
        """Format elapsed time as string (e.g., '1.2s', '345ms')."""
        ms = self._elapsed_ms()
        if ms >= 1000:
            return f"{ms/1000:.1f}s"
        else:
            return f"{int(ms)}ms"

    def _next_event_id(self) -> str:
        """Generate sequential event ID."""
        self.event_counter += 1
        return f"evt_{self.session_id[:8]}_{self.event_counter:04d}"

    def log_event(
        self,
        event_type: ActivityType,
        status: ActivityStatus,
        message: str,
        method: Optional[str] = None,
        endpoint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ActivityEvent:
        """
        Log a structured activity event.

        Args:
            event_type: Type of activity
            status: Execution status
            message: Human-readable message
            method: HTTP method or action type (POST, CALL, etc.)
            endpoint: Tool name or API endpoint
            metadata: Additional context

        Returns:
            ActivityEvent object
        """
        event = ActivityEvent(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            elapsed_ms=self._elapsed_ms(),
            event_id=self._next_event_id(),
            event_type=event_type,
            status=status,
            method=method,
            endpoint=endpoint,
            message=message,
            metadata=metadata or {}
        )

        self.events.append(event)

        # Write to JSONL file for persistence
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')

        return event

    def log_session_init(self, contract_path: str, user_request: str):
        """Log session initialization."""
        self.log_event(
            ActivityType.SESSION_INIT,
            ActivityStatus.STARTED,
            f"Session initialized with contract: {Path(contract_path).name}",
            method="INIT",
            endpoint="session",
            metadata={
                "session_id": self.session_id,
                "contract_path": contract_path,
                "user_request": user_request
            }
        )

    def log_user_request(self, request: str, request_id: str):
        """Log incoming user request."""
        self.log_event(
            ActivityType.USER_REQUEST,
            ActivityStatus.PROCESSING,
            f"User request received: {request[:100]}",
            method="REQUEST",
            endpoint="user_input",
            metadata={
                "request_id": request_id,
                "request": request
            }
        )

    def log_intent_analysis(self, detected_intent: str, authorized_tools: List[str]):
        """Log intent analysis results."""
        self.log_event(
            ActivityType.INTENT_ANALYSIS,
            ActivityStatus.COMPLETED,
            f"Intent analyzed - {len(authorized_tools)} tools authorized",
            method="ANALYZE",
            endpoint="intent",
            metadata={
                "detected_intent": detected_intent,
                "authorized_tools": authorized_tools
            }
        )

    def log_tool_discovery(self, available_tools: List[str], total_count: int):
        """Log tool discovery phase."""
        self.log_event(
            ActivityType.TOOL_DISCOVERY,
            ActivityStatus.COMPLETED,
            f"Discovered {total_count} available tools/skills",
            method="SCAN",
            endpoint="tools",
            metadata={
                "available_tools": available_tools,
                "total_count": total_count
            }
        )

    def log_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        call_id: str
    ):
        """Log tool call initiation."""
        self.log_event(
            ActivityType.TOOL_CALL,
            ActivityStatus.STARTED,
            f"Tool call: {tool_name}({', '.join(f'{k}={v}' for k, v in params.items())})",
            method="CALL",
            endpoint=tool_name,
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "params": params
            }
        )

    def log_interception(
        self,
        tool_name: str,
        verdict: str,
        deviation_score: float,
        reasons: List[str]
    ):
        """Log interception decision."""
        status = ActivityStatus.BLOCKED if verdict == "BLOCK" else \
                 ActivityStatus.ALLOWED if verdict == "ALLOW" else \
                 ActivityStatus.PROCESSING

        self.log_event(
            ActivityType.INTERCEPTION,
            status,
            f"Interception verdict: {verdict} (score: {deviation_score:.1f})",
            method="INTERCEPT",
            endpoint=tool_name,
            metadata={
                "verdict": verdict,
                "deviation_score": deviation_score,
                "reasons": reasons
            }
        )

    def log_deviation_analysis(
        self,
        tool_name: str,
        scores: Dict[str, float],
        overall_score: float
    ):
        """Log deviation analysis breakdown."""
        self.log_event(
            ActivityType.DEVIATION_ANALYSIS,
            ActivityStatus.COMPLETED,
            f"Deviation analysis: {overall_score:.1f} overall",
            method="ANALYZE",
            endpoint=tool_name,
            metadata={
                "overall_score": overall_score,
                "operation_score": scores.get("operation", 0),
                "scope_score": scores.get("scope", 0),
                "side_effects_score": scores.get("side_effects", 0),
                "sequence_score": scores.get("sequence", 0)
            }
        )

    def log_execution(
        self,
        tool_name: str,
        executed: bool,
        result: Optional[Dict[str, Any]] = None
    ):
        """Log tool execution result."""
        status = ActivityStatus.COMPLETED if executed else ActivityStatus.BLOCKED

        self.log_event(
            ActivityType.EXECUTION,
            status,
            f"Tool {'executed' if executed else 'blocked'}: {tool_name}",
            method="EXEC" if executed else "BLOCK",
            endpoint=tool_name,
            metadata={
                "executed": executed,
                "result": result
            }
        )

    def get_timeline(self) -> List[Dict[str, Any]]:
        """
        Get timeline view of all events.

        Returns:
            List of events formatted for timeline display
        """
        timeline = []
        for event in self.events:
            timeline.append({
                "elapsed": self._format_elapsed(event.elapsed_ms),
                "status": event.status.value,
                "method": event.method or "",
                "endpoint": event.endpoint or "",
                "message": event.message,
                "metadata": event.metadata
            })
        return timeline

    def _format_elapsed(self, ms: float) -> str:
        """Format elapsed time for display."""
        if ms >= 1000:
            return f"{ms/1000:.1f}s"
        else:
            return f"{int(ms)}ms"

    def get_audit_trail(self) -> Dict[str, Any]:
        """
        Generate compliance audit trail.

        Returns:
            Audit trail with session summary and all events
        """
        blocked_count = sum(1 for e in self.events if e.status == ActivityStatus.BLOCKED)
        allowed_count = sum(1 for e in self.events if e.status == ActivityStatus.ALLOWED)

        return {
            "session_id": self.session_id,
            "start_time": self.events[0].timestamp if self.events else None,
            "duration_ms": self._elapsed_ms(),
            "total_events": len(self.events),
            "blocked_actions": blocked_count,
            "allowed_actions": allowed_count,
            "events": [e.to_dict() for e in self.events]
        }

    def save_audit_trail(self, output_file: Optional[str] = None):
        """Save audit trail to JSON file."""
        if output_file is None:
            output_file = self.output_dir / f"audit_{self.session_id}.json"

        with open(output_file, 'w') as f:
            json.dump(self.get_audit_trail(), f, indent=2)

        return output_file
