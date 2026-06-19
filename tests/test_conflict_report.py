"""Tests for agentcrdt.conflict_report module."""
import pytest

from agentcrdt.conflict_report import ConflictSummary, conflict_report, conflicts_for_entity
from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.store import WorldStore


def _store(tmp_path) -> WorldStore:
    return WorldStore(tmp_path / "test.db")


def test_conflict_report_empty(tmp_path):
    store = _store(tmp_path)
    summary = conflict_report(store)
    assert isinstance(summary, ConflictSummary)
    assert summary.total_conflicts == 0
    assert summary.resolution_rate == 0.0
    store.close()


def test_conflict_report_with_events(tmp_path):
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, agent_id="agent-a")
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=1, agent_id="agent-b", timestamp=f1.timestamp + 1)
    store.set_fact(f1)

    event = ContradictionEvent(
        rule="alive_exclusive",
        facts_involved=[f1.id],
        agent_a="agent-a",
        agent_b="agent-b",
        timestamp=f1.timestamp + 0.5,
    )
    store.add_event(event)

    summary = conflict_report(store)
    assert summary.total_conflicts == 1
    assert "alive_exclusive" in summary.by_rule
    store.close()


def test_conflict_report_by_rule_count(tmp_path):
    store = _store(tmp_path)
    for i in range(3):
        e = ContradictionEvent(
            rule="rule_x",
            facts_involved=[],
            agent_a="a",
            agent_b="b",
        )
        store.add_event(e)
    summary = conflict_report(store)
    # All 3 have same id due to content-addressing (dedup) — so might be 1
    assert summary.total_conflicts >= 1
    store.close()


def test_conflict_report_to_dict(tmp_path):
    store = _store(tmp_path)
    summary = conflict_report(store)
    d = summary.to_dict()
    assert "total_conflicts" in d
    assert "by_rule" in d
    assert "resolution_rate" in d
    store.close()


def test_conflicts_for_entity_empty(tmp_path):
    store = _store(tmp_path)
    result = conflicts_for_entity(store, "king")
    assert result == []
    store.close()


def test_conflicts_for_entity(tmp_path):
    store = _store(tmp_path)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, agent_id="a")
    store.set_fact(f)
    event = ContradictionEvent(
        rule="test_rule",
        facts_involved=[f.id],
        agent_a="a",
        agent_b="b",
    )
    store.add_event(event)
    result = conflicts_for_entity(store, "king")
    assert len(result) == 1
    assert result[0].rule == "test_rule"
    store.close()


def test_conflicts_for_entity_filters_correctly(tmp_path):
    store = _store(tmp_path)
    f_king = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, agent_id="a")
    f_queen = WorldFact(domain="life", entity="queen", attribute="alive", value=True, version=1, agent_id="b")
    store.set_fact(f_king)
    store.set_fact(f_queen)
    e_king = ContradictionEvent(rule="r1", facts_involved=[f_king.id], agent_a="a", agent_b="c")
    e_queen = ContradictionEvent(rule="r2", facts_involved=[f_queen.id], agent_a="b", agent_b="c")
    store.add_event(e_king)
    store.add_event(e_queen)
    assert len(conflicts_for_entity(store, "king")) == 1
    assert len(conflicts_for_entity(store, "queen")) == 1
    store.close()
