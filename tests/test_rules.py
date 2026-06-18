"""Tests for SemanticRule and RuleEngine."""
from __future__ import annotations

from agentcrdt.fact import WorldFact
from agentcrdt.rules import RuleEngine, SemanticRule


def _make_fact(
    domain: str, entity: str, attribute: str, value: object, agent_id: str = ""
) -> WorldFact:
    return WorldFact(
        domain=domain, entity=entity, attribute=attribute, value=value, agent_id=agent_id
    )


class TestSemanticRule:
    """Tests for SemanticRule dataclass."""

    def test_fields_stored(self) -> None:
        """All constructor fields must be accessible."""
        rule = SemanticRule(
            name="test-rule",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="alliance",
            implies_entity_same=True,
            implies_attribute="valid",
            implies_value=False,
        )
        assert rule.name == "test-rule"
        assert rule.trigger_domain == "life"
        assert rule.trigger_attribute == "alive"
        assert rule.trigger_value is False
        assert rule.implies_domain == "alliance"
        assert rule.implies_entity_same is True
        assert rule.implies_attribute == "valid"
        assert rule.implies_value is False

    def test_default_implies_entity_same(self) -> None:
        """implies_entity_same should default to True."""
        rule = SemanticRule(
            name="r",
            trigger_domain="a",
            trigger_attribute="x",
            trigger_value=True,
            implies_domain="b",
        )
        assert rule.implies_entity_same is True

    def test_default_implies_value(self) -> None:
        """implies_value should default to None."""
        rule = SemanticRule(
            name="r",
            trigger_domain="a",
            trigger_attribute="x",
            trigger_value=True,
            implies_domain="b",
        )
        assert rule.implies_value is None


class TestRuleEngine:
    """Tests for RuleEngine contradiction detection."""

    def test_empty_rule_engine_returns_no_events(self) -> None:
        """No rules means no contradictions."""
        engine = RuleEngine(rules=[])
        king_alive = _make_fact("life", "king", "alive", True)
        facts = {king_alive.id: king_alive}
        assert engine.check(facts) == []

    def test_consistent_facts_no_contradiction(self) -> None:
        """No contradiction when the implied fact matches the rule."""
        rule = SemanticRule(
            name="dead-king-voids-treaty",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="health",
            implies_value=0,
        )
        king_dead = _make_fact("life", "king", "alive", False)
        king_health_zero = _make_fact("life", "king", "health", 0)
        facts = {king_dead.id: king_dead, king_health_zero.id: king_health_zero}
        engine = RuleEngine(rules=[rule])
        events = engine.check(facts)
        assert events == []

    def test_detects_contradiction_same_entity(self) -> None:
        """A contradiction is detected when the same-entity implied fact has wrong value."""
        rule = SemanticRule(
            name="dead-king-should-have-zero-health",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="health",
            implies_value=0,
        )
        king_dead = _make_fact("life", "king", "alive", False, agent_id="agent-1")
        # agent-2 says health is 100 — contradiction!
        king_health_wrong = _make_fact("life", "king", "health", 100, agent_id="agent-2")
        facts = {king_dead.id: king_dead, king_health_wrong.id: king_health_wrong}
        engine = RuleEngine(rules=[rule])
        events = engine.check(facts)
        assert len(events) == 1
        assert events[0].rule == "dead-king-should-have-zero-health"
        assert king_dead.id in events[0].facts_involved
        assert king_health_wrong.id in events[0].facts_involved

    def test_no_contradiction_when_implied_fact_missing(self) -> None:
        """If the implied fact doesn't exist, no contradiction is fired."""
        rule = SemanticRule(
            name="dead-king-voids-treaty",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="health",
            implies_value=0,
        )
        king_dead = _make_fact("life", "king", "alive", False)
        facts = {king_dead.id: king_dead}  # no health fact
        engine = RuleEngine(rules=[rule])
        assert engine.check(facts) == []

    def test_multiple_rules_multiple_violations(self) -> None:
        """Multiple rules can fire simultaneously."""
        rule1 = SemanticRule(
            name="rule-1",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="health",
            implies_value=0,
        )
        rule2 = SemanticRule(
            name="rule-2",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="status",
            implies_value="deceased",
        )
        king_dead = _make_fact("life", "king", "alive", False, agent_id="agent-1")
        king_health = _make_fact("life", "king", "health", 100, agent_id="agent-2")
        king_status = _make_fact("life", "king", "status", "active", agent_id="agent-3")
        facts = {
            king_dead.id: king_dead,
            king_health.id: king_health,
            king_status.id: king_status,
        }
        engine = RuleEngine(rules=[rule1, rule2])
        events = engine.check(facts)
        assert len(events) == 2
        rule_names = {e.rule for e in events}
        assert rule_names == {"rule-1", "rule-2"}

    def test_no_violation_when_trigger_value_not_matched(self) -> None:
        """Rule does not fire when trigger_value does not match the fact value."""
        rule = SemanticRule(
            name="dead-king",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="life",
            implies_entity_same=True,
            implies_attribute="health",
            implies_value=0,
        )
        king_alive = _make_fact("life", "king", "alive", True)  # alive=True, rule won't trigger
        king_health = _make_fact("life", "king", "health", 100)
        facts = {king_alive.id: king_alive, king_health.id: king_health}
        engine = RuleEngine(rules=[rule])
        assert engine.check(facts) == []

    def test_implies_entity_same_false_skips(self) -> None:
        """implies_entity_same=False prevents entity-based implied key lookup."""
        rule = SemanticRule(
            name="cross-entity-rule",
            trigger_domain="life",
            trigger_attribute="alive",
            trigger_value=False,
            implies_domain="alliance",
            implies_entity_same=False,  # can't look up cross-entity without more info
            implies_attribute="valid",
            implies_value=False,
        )
        king_dead = _make_fact("life", "king", "alive", False)
        treaty_valid = _make_fact("alliance", "treaty-1", "valid", True)
        facts = {king_dead.id: king_dead, treaty_valid.id: treaty_valid}
        engine = RuleEngine(rules=[rule])
        # With implies_entity_same=False, entity is None so no lookup is done
        events = engine.check(facts)
        assert events == []
