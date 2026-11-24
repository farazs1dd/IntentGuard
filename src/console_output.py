# src/console_output.py
"""
Console output formatting for IntentGuard.

Provides color-coded, formatted output for monitoring sessions.
"""
from typing import Dict, Any
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from src.deviation_detector import DeviationAnalysis

console = Console()


class ConsoleFormatter:
    """Formats IntentGuard output for terminal display."""

    def format_header(self, session_id: str, contract_id: str, goal: str) -> None:
        """
        Print monitoring session header.

        Args:
            session_id: Session being monitored
            contract_id: Intent contract ID
            goal: Contract goal description
        """
        header_text = Text()
        header_text.append("IntentGuard Monitoring\n", style="bold cyan")
        header_text.append(f"Session: {session_id}\n", style="white")
        header_text.append(f"Contract: {contract_id}\n", style="white")
        header_text.append(f"Goal: {goal}\n", style="white")
        header_text.append("Polling every 10s...\n", style="dim")

        console.print(Panel(header_text, border_style="cyan"))

    def format_tool_call(self, tool_call: Dict[str, Any], analysis: DeviationAnalysis) -> None:
        """
        Print formatted tool call with deviation analysis.

        Args:
            tool_call: Tool call dict with name, params, timestamp
            analysis: Deviation analysis result
        """
        # Convert timestamp (float) to formatted string
        ts = tool_call.get('timestamp', 0)
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ''
        tool_name = tool_call.get('name', 'unknown')
        params = tool_call.get('params', {})

        # Format parameters concisely
        param_str = ', '.join([f"{k}={v}" for k, v in params.items()])

        if analysis.severity == 'LOW' and analysis.overall_score == 0:
            # Expected behavior
            line = Text()
            line.append(f"[{timestamp}] ", style="dim")
            line.append("✓ ", style="green bold")
            line.append(f"{tool_name}({param_str})", style="green")
            line.append(" - EXPECTED\n", style="green")
            line.append(f"           Deviation: {analysis.overall_score}/100 ({analysis.severity})",
                       style="dim")
            console.print(line)
        else:
            # Deviation detected
            line = Text()
            line.append(f"[{timestamp}] ", style="dim")
            line.append("✗ ", style="red bold")
            line.append(f"{tool_name}({param_str})", style="red")
            line.append(" - DEVIATION DETECTED\n", style="red bold")

            # Show reasons
            for reason in analysis.reasons:
                line.append(f"           {reason}\n", style="yellow")

            # Show deviation score
            severity_color = "red" if analysis.severity == "HIGH" else "yellow"
            line.append(f"           Deviation: {analysis.overall_score}/100 ({analysis.severity})",
                       style=severity_color)

            console.print(line)
            console.print()  # Extra newline for readability

    def format_polling_message(self) -> None:
        """Print polling indicator."""
        console.print("[dim]Polling AI Gateway...[/dim]")

    def format_session_complete(self, report_path: str) -> None:
        """
        Print session completion message.

        Args:
            report_path: Path to generated report
        """
        console.print()
        console.print("[bold green]Session complete.[/bold green]")
        console.print(f"[cyan]Report saved: {report_path}[/cyan]")
