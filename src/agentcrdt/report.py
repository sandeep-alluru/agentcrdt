"""Rich terminal, JSON, and Markdown formatters for agentcrdt."""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentcrdt.fact import ContradictionEvent, WorldFact

_console = Console()


def _truncate(text: str, max_len: int = 72) -> str:
    """Truncate *text* to *max_len* characters, appending an ellipsis if needed."""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def print_state(facts: list[WorldFact], console: Console | None = None) -> None:
    """Render world facts as a Rich table to *console*.

    Args:
        facts:   List of :class:`~agentcrdt.fact.WorldFact` objects to display.
        console: Optional Rich console; defaults to the module-level singleton.
    """
    con = console or _console
    if not facts:
        con.print("[dim]No world facts stored.[/dim]")
        return
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("ID", width=18)
    table.add_column("Domain", width=12)
    table.add_column("Entity", width=16)
    table.add_column("Attribute", width=16)
    table.add_column("Value", no_wrap=False, min_width=20)
    table.add_column("v", width=4)
    for f in facts:
        table.add_row(f.id, f.domain, f.entity, f.attribute, str(f.value), str(f.version))
    con.print(table)


def print_events(events: list[ContradictionEvent], console: Console | None = None) -> None:
    """Render contradiction events as a Rich table to *console*.

    Args:
        events:  List of :class:`~agentcrdt.fact.ContradictionEvent` objects.
        console: Optional Rich console; defaults to the module-level singleton.
    """
    con = console or _console
    if not events:
        con.print("[green]No contradiction events.[/green]")
        return
    con.print(
        Panel(
            f"[bold red]{len(events)} CONTRADICTION(S)[/bold red]",
            expand=False,
            border_style="red",
        )
    )
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("ID", width=18)
    table.add_column("Rule", width=30)
    table.add_column("Agent A", width=12)
    table.add_column("Agent B", width=12)
    for e in events:
        table.add_row(e.id, e.rule, e.agent_a, e.agent_b)
    con.print(table)


def to_json(
    facts: list[WorldFact], events: list[ContradictionEvent] | None = None
) -> str:
    """Serialise facts (and optionally events) to a JSON string.

    Args:
        facts:  List of world facts to include.
        events: Optional list of contradiction events to include.

    Returns:
        Indented JSON string.
    """
    data: dict[str, Any] = {
        "facts": [f.to_dict() for f in facts],
    }
    if events is not None:
        data["events"] = [e.to_dict() for e in events]
    return json.dumps(data, indent=2)


def to_markdown(
    facts: list[WorldFact], events: list[ContradictionEvent] | None = None
) -> str:
    """Format facts (and optionally events) as a Markdown report.

    Args:
        facts:  List of world facts.
        events: Optional list of contradiction events.

    Returns:
        A Markdown string with header sections and pipe tables.
    """
    lines = ["## agentcrdt world state", ""]
    if facts:
        lines += [
            "| Domain | Entity | Attribute | Value | v |",
            "|--------|--------|-----------|-------|---|",
        ]
        for f in facts:
            lines.append(
                f"| {f.domain} | {f.entity} | {f.attribute} | {f.value} | {f.version} |"
            )
    else:
        lines.append("*No world facts.*")
    if events:
        lines += ["", "## Contradictions", ""]
        lines += [
            "| Rule | Agent A | Agent B |",
            "|------|---------|---------|",
        ]
        for e in events:
            lines.append(f"| {e.rule} | {e.agent_a} | {e.agent_b} |")
    return "\n".join(lines)
