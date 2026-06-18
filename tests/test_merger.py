"""Tests for WorldMerger CRDT merge semantics."""
from __future__ import annotations

from pathlib import Path

import pytest

from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore


def _make_fact(
    domain: str = "life",
    entity: str = "king",
    attribute: str = "alive",
    value: object = True,
    version: int = 0,
    agent_id: str = "",
    timestamp: float | None = None,
) -> WorldFact:
    f = WorldFact(domain=domain, entity=entity, attribute=attribute, value=value,
                  version=version, agent_id=agent_id)
    if timestamp is not None:
        f.timestamp = timestamp
    return f


@pytest.fixture
def local_store(tmp_path: Path) -> WorldStore:
    """Fresh local WorldStore."""
    s = WorldStore(tmp_path / "local.db")
    yield s
    s.close()


@pytest.fixture
def remote_store(tmp_path: Path) -> WorldStore:
    """Fresh remote WorldStore."""
    s = WorldStore(tmp_path / "remote.db")
    yield s
    s.close()


class TestBasicMerge:
    """Tests for basic merge behaviour."""

    def test_empty_remote_merges_zero_facts(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """Merging an empty remote must return merged_count=0."""
        result = WorldMerger().merge(local_store, remote_store)
        assert result.merged_count == 0
        assert result.conflicts == []

    def test_basic_merge_copies_facts(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """Facts in the remote store must appear in local after merge."""
        fact = _make_fact()
        remote_store.set_fact(fact)
        result = WorldMerger().merge(local_store, remote_store)
        assert result.merged_count == 1
        assert local_store.get_fact(fact.id) is not None

    def test_merge_count_matches_remote_facts(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """merged_count must equal the number of facts in the remote store."""
        for i in range(5):
            remote_store.set_fact(_make_fact(entity=f"entity-{i}", attribute=f"attr-{i}"))
        result = WorldMerger().merge(local_store, remote_store)
        assert result.merged_count == 5

    def test_merge_result_to_dict(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """MergeResult.to_dict must include merged_count and conflicts."""
        fact = _make_fact()
        remote_store.set_fact(fact)
        result = WorldMerger().merge(local_store, remote_store)
        d = result.to_dict()
        assert d["merged_count"] == 1
        assert d["conflicts"] == []


class TestIdempotentMerge:
    """Tests for idempotency under repeated merges."""

    def test_idempotent_merge(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """Merging the same remote twice must not duplicate facts in local."""
        fact = _make_fact()
        remote_store.set_fact(fact)
        WorldMerger().merge(local_store, remote_store)
        WorldMerger().merge(local_store, remote_store)  # second merge
        assert len(local_store.list_facts()) == 1


class TestContradictionDetection:
    """Tests for contradiction detection via RuleEngine integration."""

    def test_no_rule_engine_no_conflicts(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """Without a rule engine, no contradiction events should be generated."""
        king_dead = _make_fact(value=False)
        remote_store.set_fact(king_dead)
        result = WorldMerger().merge(local_store, remote_store)
        assert result.conflicts == []

    def test_contradiction_detected_after_merge(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """If king dies (agent-A) and treaty is still valid (agent-B), contradiction fires."""
        # agent-A sets king.alive=False
        king_dead = _make_fact(
            domain="life", entity="king", attribute="alive", value=False,
            version=1, agent_id="agent-A",
        )
        local_store.set_fact(king_dead)

        # agent-B sets treaty.valid=True (inconsistent with dead king)
        treaty_valid = _make_fact(
            domain="alliance", entity="king", attribute="valid", value=True,
            version=1, agent_id="agent-B",
        )
        remote_store.set_fact(treaty_valid)

        # Rule: if life.king.alive=False then alliance.king.valid must be False
        rule = SemanticRule(
            name="dead-king-voids-treaty",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="alliance",
            implies_entity_same=True,
            implies_attribute="valid",
            implies_value=False,
        )
        engine = RuleEngine(rules=[rule])
        result = WorldMerger(rule_engine=engine).merge(local_store, remote_store)

        assert len(result.conflicts) == 1
        assert result.conflicts[0].rule == "dead-king-voids-treaty"

    def test_contradiction_saved_to_store(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """Contradiction events must be persisted in the local store."""
        king_dead = _make_fact(
            domain="life", entity="king", attribute="alive", value=False,
            version=1, agent_id="agent-A",
        )
        local_store.set_fact(king_dead)
        treaty_valid = _make_fact(
            domain="alliance", entity="king", attribute="valid", value=True,
            version=1, agent_id="agent-B",
        )
        remote_store.set_fact(treaty_valid)

        rule = SemanticRule(
            name="dead-king-voids-treaty",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="alliance",
            implies_entity_same=True,
            implies_attribute="valid",
            implies_value=False,
        )
        engine = RuleEngine(rules=[rule])
        WorldMerger(rule_engine=engine).merge(local_store, remote_store)

        events = local_store.list_events()
        assert len(events) == 1
        assert events[0].rule == "dead-king-voids-treaty"

    def test_no_contradiction_when_consistent(
        self, local_store: WorldStore, remote_store: WorldStore
    ) -> None:
        """No contradiction when both king is dead and treaty is voided."""
        king_dead = _make_fact(
            domain="life", entity="king", attribute="alive", value=False,
            version=1, agent_id="agent-A",
        )
        local_store.set_fact(king_dead)
        treaty_void = _make_fact(
            domain="alliance", entity="king", attribute="valid", value=False,
            version=1, agent_id="agent-B",
        )
        remote_store.set_fact(treaty_void)

        rule = SemanticRule(
            name="dead-king-voids-treaty",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="alliance",
            implies_entity_same=True,
            implies_attribute="valid",
            implies_value=False,
        )
        engine = RuleEngine(rules=[rule])
        result = WorldMerger(rule_engine=engine).merge(local_store, remote_store)
        assert result.conflicts == []
