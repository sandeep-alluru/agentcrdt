"""Tests for WorldFact and ContradictionEvent primitives."""
from __future__ import annotations

import time

from agentcrdt.fact import ContradictionEvent, WorldFact, _sha16


class TestWorldFact:
    """Tests for WorldFact content-addressing and serialisation."""

    def test_same_key_produces_same_id(self) -> None:
        """Two facts with the same domain|entity|attribute must have the same id."""
        f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False)
        assert f1.id == f2.id

    def test_different_attribute_produces_different_id(self) -> None:
        """Different attributes must produce different ids."""
        f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        f2 = WorldFact(domain="life", entity="king", attribute="health", value=100)
        assert f1.id != f2.id

    def test_different_entity_produces_different_id(self) -> None:
        """Different entities must produce different ids."""
        f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        f2 = WorldFact(domain="life", entity="queen", attribute="alive", value=True)
        assert f1.id != f2.id

    def test_different_domain_produces_different_id(self) -> None:
        """Different domains must produce different ids."""
        f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        f2 = WorldFact(domain="alliance", entity="king", attribute="alive", value=True)
        assert f1.id != f2.id

    def test_id_is_sha16_of_key(self) -> None:
        """The id must equal _sha16 of 'domain|entity|attribute'."""
        f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        expected = _sha16("life|king|alive")
        assert f.id == expected

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() followed by from_dict() must reproduce the same object."""
        f = WorldFact(
            domain="possession",
            entity="sword",
            attribute="owner",
            value="knight",
            version=3,
            agent_id="agent-007",
        )
        d = f.to_dict()
        assert d["id"] == f.id
        assert d["domain"] == "possession"
        assert d["entity"] == "sword"
        assert d["attribute"] == "owner"
        assert d["value"] == "knight"
        assert d["version"] == 3
        assert d["agent_id"] == "agent-007"
        f2 = WorldFact.from_dict(d)
        assert f2.id == f.id
        assert f2.value == f.value
        assert f2.version == f.version
        assert f2.agent_id == f.agent_id

    def test_from_dict_default_fields(self) -> None:
        """from_dict() must use sensible defaults for optional fields."""
        d = {
            "domain": "life",
            "entity": "king",
            "attribute": "alive",
            "value": True,
        }
        f = WorldFact.from_dict(d)
        assert f.version == 0
        assert f.agent_id == ""
        assert f.timestamp == 0.0

    def test_repr(self) -> None:
        """__repr__ must include the id and key."""
        f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        r = repr(f)
        assert f.id in r
        assert "life.king.alive" in r

    def test_timestamp_defaults_to_now(self) -> None:
        """timestamp must default to a recent unix timestamp."""
        before = time.time()
        f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
        after = time.time()
        assert before <= f.timestamp <= after

    def test_value_none(self) -> None:
        """WorldFact.value may be None."""
        f = WorldFact(domain="knowledge", entity="agent-1", attribute="goal", value=None)
        d = f.to_dict()
        assert d["value"] is None
        f2 = WorldFact.from_dict(d)
        assert f2.value is None

    def test_value_float(self) -> None:
        """WorldFact.value may be a float."""
        f = WorldFact(domain="possession", entity="gold", attribute="amount", value=42.5)
        d = f.to_dict()
        assert d["value"] == 42.5


class TestContradictionEvent:
    """Tests for ContradictionEvent content-addressing and serialisation."""

    def test_content_addressed_id(self) -> None:
        """Same rule + facts + agents must produce same id."""
        e1 = ContradictionEvent(
            rule="rule-a",
            facts_involved=["fact1", "fact2"],
            agent_a="agent-1",
            agent_b="agent-2",
        )
        e2 = ContradictionEvent(
            rule="rule-a",
            facts_involved=["fact2", "fact1"],  # different order — should still match
            agent_a="agent-1",
            agent_b="agent-2",
        )
        assert e1.id == e2.id

    def test_different_rule_produces_different_id(self) -> None:
        """Different rule names must produce different ids."""
        e1 = ContradictionEvent(
            rule="rule-a",
            facts_involved=["fact1"],
            agent_a="a",
            agent_b="b",
        )
        e2 = ContradictionEvent(
            rule="rule-b",
            facts_involved=["fact1"],
            agent_a="a",
            agent_b="b",
        )
        assert e1.id != e2.id

    def test_to_dict_fields(self) -> None:
        """to_dict() must include all expected keys."""
        e = ContradictionEvent(
            rule="dead-king-voids-treaty",
            facts_involved=["abc123", "def456"],
            agent_a="agent-1",
            agent_b="agent-2",
        )
        d = e.to_dict()
        assert d["id"] == e.id
        assert d["rule"] == "dead-king-voids-treaty"
        assert set(d["facts_involved"]) == {"abc123", "def456"}
        assert d["agent_a"] == "agent-1"
        assert d["agent_b"] == "agent-2"
        assert "timestamp" in d

    def test_timestamp_defaults_to_now(self) -> None:
        """timestamp must default to a recent unix timestamp."""
        before = time.time()
        e = ContradictionEvent(rule="r", facts_involved=[], agent_a="a", agent_b="b")
        after = time.time()
        assert before <= e.timestamp <= after
