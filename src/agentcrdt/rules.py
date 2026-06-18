"""SemanticRule and RuleEngine for cross-domain implication checking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentcrdt.fact import ContradictionEvent, WorldFact


@dataclass
class SemanticRule:
    """A first-order semantic implication rule between two world facts.

    When a fact matching ``trigger_domain / trigger_attribute / trigger_value``
    exists, the rule asserts that a related fact in ``implies_domain`` must have
    ``implies_value``.  If the implied fact disagrees, a ``ContradictionEvent``
    is emitted.
    """

    name: str
    trigger_domain: str
    trigger_attribute: str
    trigger_value: Any
    implies_domain: str
    implies_entity_same: bool = True
    implies_attribute: str = ""
    implies_value: Any = None


class RuleEngine:
    """Evaluates a set of ``SemanticRule`` objects against a snapshot of world facts."""

    def __init__(self, rules: list[SemanticRule]) -> None:
        """Initialise with a list of semantic rules to enforce."""
        self.rules = rules

    def check(self, facts: dict[str, WorldFact]) -> list[ContradictionEvent]:
        """Check all semantic rules and return ContradictionEvents for violations.

        Args:
            facts: Mapping of ``fact_id -> WorldFact`` representing the current
                world state.

        Returns:
            A list of :class:`ContradictionEvent` objects, one per violated rule.
        """
        events: list[ContradictionEvent] = []
        # Group facts by (domain, entity, attribute) for fast lookup
        by_key: dict[tuple[str, str, str], WorldFact] = {}
        for f in facts.values():
            by_key[(f.domain, f.entity, f.attribute)] = f

        for rule in self.rules:
            # Find all facts that trigger this rule
            for f in facts.values():
                if f.domain != rule.trigger_domain or f.attribute != rule.trigger_attribute:
                    continue
                if f.value != rule.trigger_value:
                    continue
                # This fact triggers the rule
                entity = f.entity if rule.implies_entity_same else None
                if entity is None:
                    continue
                implied_key = (rule.implies_domain, entity, rule.implies_attribute)
                implied = by_key.get(implied_key)
                if implied is None:
                    continue
                # Check if the implied fact contradicts the rule
                if implied.value != rule.implies_value:
                    evt = ContradictionEvent(
                        rule=rule.name,
                        facts_involved=[f.id, implied.id],
                        agent_a=f.agent_id,
                        agent_b=implied.agent_id,
                    )
                    events.append(evt)
        return events
