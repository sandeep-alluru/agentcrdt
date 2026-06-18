"""agentcrdt end-to-end demo.

Demonstrates:
- WorldFact content-addressing
- WorldStore LWW merge semantics
- SemanticRule contradiction detection via WorldMerger
- Report formatters (JSON and Markdown)

Run from repo root:
    python examples/demo.py
"""
from __future__ import annotations

import json
import tempfile

from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.report import print_events, print_state, to_json, to_markdown
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore


def main() -> None:
    """Run the agentcrdt demo."""
    print("\n=== agentcrdt demo ===\n")

    with tempfile.TemporaryDirectory() as tmp:
        local_db = f"{tmp}/local.db"
        remote_db = f"{tmp}/remote.db"

        # ── Step 1: agent-A records that the king has died ────────────────────
        print("Step 1: Agent A records that the king died.")
        king_dead = WorldFact(
            domain="life", entity="king", attribute="alive",
            value=False, version=1, agent_id="agent-A",
        )
        with WorldStore(local_db) as store:
            store.set_fact(king_dead)
            facts = store.list_facts()
            print(f"  local store: {len(facts)} fact(s)")

        # ── Step 2: agent-B (independently) keeps the treaty valid ───────────
        print("\nStep 2: Agent B keeps the treaty valid (inconsistent!).")
        treaty_valid = WorldFact(
            domain="alliance", entity="king", attribute="valid",
            value=True, version=1, agent_id="agent-B",
        )
        with WorldStore(remote_db) as store:
            store.set_fact(treaty_valid)

        # ── Step 3: define a semantic rule ───────────────────────────────────
        print("\nStep 3: Define rule — dead king must void the treaty.")
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

        # ── Step 4: merge and detect contradiction ───────────────────────────
        print("\nStep 4: Merge agent-B store into local (with semantic checking).")
        with WorldStore(local_db) as local, WorldStore(remote_db) as remote:
            result = WorldMerger(rule_engine=engine).merge(local, remote)

        print(f"  merged_count: {result.merged_count}")
        print(f"  conflicts:    {len(result.conflicts)}")
        if result.conflicts:
            print(f"  rule fired:   {result.conflicts[0].rule}")

        # ── Step 5: show state ────────────────────────────────────────────────
        print("\nStep 5: World state after merge.")
        with WorldStore(local_db) as store:
            facts = store.list_facts()
            events = store.list_events()
        print_state(facts)
        print_events(events)

        # ── Step 6: formatters ────────────────────────────────────────────────
        print("\nStep 6: JSON and Markdown output.")
        j = json.loads(to_json(facts, events))
        assert "facts" in j and "events" in j
        md = to_markdown(facts, events)
        assert "agentcrdt world state" in md
        print("  JSON:     OK")
        print("  Markdown: OK")

    print("\n=== demo complete ===\n")


if __name__ == "__main__":
    main()
