"""Tests for report formatters (Rich, JSON, Markdown)."""
from __future__ import annotations

import io
import json

from rich.console import Console

from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.report import print_events, print_state, to_json, to_markdown


def _make_fact(
    domain: str = "life",
    entity: str = "king",
    attribute: str = "alive",
    value: object = True,
    version: int = 0,
) -> WorldFact:
    return WorldFact(
        domain=domain, entity=entity, attribute=attribute, value=value, version=version
    )


def _make_event(rule: str = "dead-king-voids-treaty") -> ContradictionEvent:
    return ContradictionEvent(
        rule=rule,
        facts_involved=["fact1", "fact2"],
        agent_a="agent-a",
        agent_b="agent-b",
    )


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=False, width=200)
    return con, buf


class TestPrintState:
    """Tests for print_state Rich output."""

    def test_empty_facts_prints_message(self) -> None:
        """print_state with empty list must print 'No world facts stored.'."""
        con, buf = _console()
        print_state([], console=con)
        assert "No world facts" in buf.getvalue()

    def test_facts_table_contains_domain(self) -> None:
        """print_state must include the domain name in output."""
        con, buf = _console()
        fact = _make_fact(domain="possession", entity="sword", attribute="owner", value="knight")
        print_state([fact], console=con)
        output = buf.getvalue()
        assert "possession" in output

    def test_facts_table_contains_entity(self) -> None:
        """print_state must include the entity name."""
        con, buf = _console()
        fact = _make_fact()
        print_state([fact], console=con)
        assert "king" in buf.getvalue()

    def test_facts_table_contains_value(self) -> None:
        """print_state must include the value."""
        con, buf = _console()
        fact = _make_fact(value="active")
        print_state([fact], console=con)
        assert "active" in buf.getvalue()

    def test_multiple_facts_all_shown(self) -> None:
        """All facts must appear in the table."""
        con, buf = _console()
        facts = [
            _make_fact(domain="life", entity="king", attribute="alive", value=True),
            _make_fact(domain="possession", entity="sword", attribute="owner", value="knight"),
        ]
        print_state(facts, console=con)
        output = buf.getvalue()
        assert "life" in output
        assert "possession" in output


class TestPrintEvents:
    """Tests for print_events Rich output."""

    def test_empty_events_prints_no_contradiction(self) -> None:
        """print_events with empty list must print 'No contradiction events.'."""
        con, buf = _console()
        print_events([], console=con)
        assert "No contradiction" in buf.getvalue()

    def test_events_table_contains_rule(self) -> None:
        """print_events must include the rule name."""
        con, buf = _console()
        evt = _make_event(rule="my-test-rule")
        print_events([evt], console=con)
        assert "my-test-rule" in buf.getvalue()

    def test_events_table_contains_agents(self) -> None:
        """print_events must include agent IDs."""
        con, buf = _console()
        evt = _make_event()
        print_events([evt], console=con)
        output = buf.getvalue()
        assert "agent-a" in output
        assert "agent-b" in output


class TestToJson:
    """Tests for to_json serialisation."""

    def test_facts_only(self) -> None:
        """to_json must include a 'facts' key when events is not passed."""
        fact = _make_fact()
        result = json.loads(to_json([fact]))
        assert "facts" in result
        assert len(result["facts"]) == 1
        assert "events" not in result

    def test_facts_and_events(self) -> None:
        """to_json must include both 'facts' and 'events' when events is provided."""
        fact = _make_fact()
        evt = _make_event()
        result = json.loads(to_json([fact], [evt]))
        assert "facts" in result
        assert "events" in result
        assert len(result["facts"]) == 1
        assert len(result["events"]) == 1

    def test_empty_lists(self) -> None:
        """to_json with empty lists must return valid JSON with empty arrays."""
        result = json.loads(to_json([], []))
        assert result["facts"] == []
        assert result["events"] == []

    def test_fact_fields_in_json(self) -> None:
        """Each fact dict in the JSON must contain the expected keys."""
        fact = _make_fact(domain="alliance", entity="treaty-1", attribute="valid", value=True)
        result = json.loads(to_json([fact]))
        fact_dict = result["facts"][0]
        assert fact_dict["domain"] == "alliance"
        assert fact_dict["entity"] == "treaty-1"
        assert fact_dict["attribute"] == "valid"
        assert fact_dict["value"] is True


class TestToMarkdown:
    """Tests for to_markdown output."""

    def test_heading_present(self) -> None:
        """Output must contain the main heading."""
        md = to_markdown([])
        assert "agentcrdt world state" in md

    def test_empty_facts_shows_placeholder(self) -> None:
        """No facts means the 'No world facts' placeholder must appear."""
        md = to_markdown([])
        assert "No world facts" in md

    def test_fact_row_in_table(self) -> None:
        """A stored fact must appear as a Markdown table row."""
        fact = _make_fact(domain="life", entity="king", attribute="alive", value=True)
        md = to_markdown([fact])
        assert "life" in md
        assert "king" in md
        assert "alive" in md
        assert "True" in md
        assert "|" in md

    def test_events_section_present(self) -> None:
        """When events are provided, a Contradictions section must appear."""
        evt = _make_event(rule="dead-king-voids-treaty")
        md = to_markdown([], [evt])
        assert "Contradictions" in md
        assert "dead-king-voids-treaty" in md

    def test_no_events_section_when_none(self) -> None:
        """No Contradictions section when events parameter is None."""
        md = to_markdown([_make_fact()])
        assert "Contradictions" not in md
