"""MMO Territory Control — Multi-Library Integration Demo

Demonstrates agentcrdt + normsync + worldoracle + rulegraph working together
as the "game brain" for Thornvale Keep, an MMO siege scenario with 4 competing
AI faction agents.

Scenario flow
─────────────
Step 1  [rulegraph]    Game Master loads siege law:
                        "Attackers need 3:1 ratio to breach walls" and
                        "No siege during truce" as RuleNodes with a
                        supersedes edge. RuleArbiter answers a rules query.

Step 2  [normsync]     A WorldNorm prohibits attacking in the truce_zone.
                        Faction B defies the ceasefire — NormMonitor fires a
                        violation and the action is blocked.

Step 3  [agentcrdt]    Factions A, B, C, D each write their own belief about
                        who controls the throne room into separate WorldStores.
                        WorldMerger folds all four into a single canonical store
                        using LWW semantics. A SemanticRule then catches
                        Faction C's bogus claim that the dead king is still
                        active, emitting a ContradictionEvent.

Step 4  [worldoracle]  Two NPC guards carry conflicting intel: Guard-1 heard
                        the king is alive; Guard-2 personally witnessed his
                        death. ContradictionDetector surfaces the conflict.
                        BeliefRepairer proposes the authoritative fix using
                        the prefer_newer / prefer_observation strategy.

Run:
    pip install agentcrdt normsync worldoracle rulegraph
    python 03_multi_agent_game_brain.py
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

# ── agentcrdt ────────────────────────────────────────────────────────────────
from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore

# ── normsync ─────────────────────────────────────────────────────────────────
from normsync.monitor import NormMonitor
from normsync.norm import AgentAction, WorldNorm

# ── worldoracle ──────────────────────────────────────────────────────────────
from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    WorldPredicate,
)

# ── rulegraph ─────────────────────────────────────────────────────────────────
from rulegraph.rule import RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _sub(label: str) -> None:
    print(f"\n  -- {label}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — rulegraph: The Game Master loads and arbitrates siege law
# ─────────────────────────────────────────────────────────────────────────────

def step1_rulegraph(tmp: str) -> None:
    _header("STEP 1 — rulegraph: Game Master loads Thornvale Keep siege rules")

    graph = RuleGraph()

    # The baseline siege mechanic
    breach_rule = RuleNode(
        rule_id="siege.breach_ratio",
        text=(
            "An attacking force must achieve a 3:1 numerical ratio over defenders "
            "before a successful wall breach can be declared. Any assault with fewer "
            "than three attackers per defender is automatically repelled."
        ),
        node_type="mechanic",
        tags=["siege", "breach", "ratio", "attack"],
        source="Thornvale Keep Rulebook v2",
        confidence=1.0,
    )

    # The truce override — it supersedes the breach rule during a ceasefire
    truce_rule = RuleNode(
        rule_id="siege.no_siege_truce",
        text=(
            "No siege actions — including wall assaults, battering-ram deployments, "
            "or catapult fire — may be initiated while an active truce is in force "
            "between any two factions. Violations forfeit captured territory."
        ),
        node_type="mechanic",
        tags=["siege", "truce", "ceasefire", "prohibit", "attack"],
        source="Thornvale Keep Rulebook v2",
        confidence=1.0,
    )

    # A narrative flavour note about Thornvale's history
    lore_rule = RuleNode(
        rule_id="lore.thornvale_history",
        text=(
            "Thornvale Keep has changed hands fourteen times in recorded history. "
            "The throne room is considered the symbolic seat of power; formal "
            "control requires planting the faction banner before the Iron Throne."
        ),
        node_type="narrative",
        tags=["lore", "thornvale", "throne", "control"],
        source="Thornvale Keep Lore Compendium",
        confidence=0.9,
    )

    graph.add_node(breach_rule)
    graph.add_node(truce_rule)
    graph.add_node(lore_rule)

    # Truce supersedes the breach mechanic (during a truce, ratio is irrelevant)
    graph.add_edge(RuleEdge(
        source_id="siege.no_siege_truce",
        target_id="siege.breach_ratio",
        relation="supersedes",
        condition="while active truce is in force",
        confidence=1.0,
    ))

    print(f"  Graph loaded: {graph.node_count()} rules, {graph.edge_count()} edge(s)")

    # Persist to a temp DB and reload (round-trip verification)
    store_path = Path(tmp) / "rulegraph.db"
    rule_store = RuleStore(store_path)
    for node in graph.nodes():
        rule_store.save_node(node)
    for edge in graph.get_edges():
        rule_store.save_edge(edge)
    loaded_graph = rule_store.load_graph()
    print(f"  Persisted and reloaded: {loaded_graph.node_count()} rules confirmed")

    # Arbitrate a rules question
    arbiter = RuleArbiter(loaded_graph)

    _sub("Query: 'Can attackers breach during a siege if they outnumber defenders?'")
    result = arbiter.query("Can attackers breach during a siege if they outnumber defenders?")
    rule_store.save_result(result)
    print(f"    Tier:       {result.tier}")
    print(f"    Confidence: {result.confidence:.2f}")
    print(f"    Provenance: {result.provenance}")
    if result.contradictions:
        print(f"    Contradictions detected: {result.contradictions}")
        print("    => The truce rule supersedes the ratio mechanic — siege is illegal!")
    print(f"    Answer snippet: {result.answer.splitlines()[0]}")

    _sub("Why this matters")
    print(
        "    rulegraph lets the game engine answer rules questions with full\n"
        "    provenance and automatically surfaces when one rule overrides another.\n"
        "    The Game Master no longer needs to hand-code every interaction."
    )

    rule_store.close()


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — normsync: Faction B ignores the truce ceasefire
# ─────────────────────────────────────────────────────────────────────────────

def step2_normsync() -> None:
    _header("STEP 2 — normsync: Faction B attempts to attack inside the truce_zone")

    # The Game Master has declared a ceasefire — this norm is now active
    truce_norm = WorldNorm(
        name="no-attack-in-truce-zone",
        description="No faction may perform attack actions in the designated truce zone.",
        condition="truce_zone",
        prohibited="attack",
        scope="thornvale_keep",
        active=True,
        priority=10,
    )

    monitor = NormMonitor(norms=[truce_norm])
    print(f"  Active norms: {len(monitor.active_norms())}")
    print(f"  Norm '{truce_norm.name}' is live (id={truce_norm.id})")

    # Faction A respects the ceasefire — a scout action is fine
    _sub("Faction A: scouting inside truce_zone (should pass)")
    scout_action = AgentAction(
        agent_id="faction-A",
        action="scout",
        location="truce_zone",
        target="eastern_wall",
        faction="Iron_Wolves",
        timestamp=time.time(),
    )
    violations = monitor.check(scout_action)
    if violations:
        print(f"    BLOCKED — {violations[0].description}")
    else:
        print("    ALLOWED — scout action does not violate the ceasefire norm")

    # Faction B defies the truce and attacks
    _sub("Faction B: attacking inside truce_zone (should be BLOCKED)")
    attack_action = AgentAction(
        agent_id="faction-B",
        action="attack",
        location="truce_zone",
        target="northern_gate",
        faction="Shadow_Keep",
        timestamp=time.time(),
    )
    violations = monitor.check(attack_action)
    if violations:
        v = violations[0]
        print(f"    BLOCKED  — norm '{v.norm_name}' triggered")
        print(f"    Violation: {v.description}")
        print(f"    Severity:  {v.severity}")
    else:
        print("    ERROR — attack was not blocked (unexpected)")

    _sub("Why this matters")
    print(
        "    normsync acts as a real-time constraint layer: faction AI can\n"
        "    attempt any action they like, but NormMonitor intercepts illegal\n"
        "    moves before they reach the world state engine."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — agentcrdt: Four factions race to claim the throne room
# ─────────────────────────────────────────────────────────────────────────────

def step3_agentcrdt(tmp: str) -> None:
    _header(
        "STEP 3 — agentcrdt: Four factions simultaneously update throne room control"
    )

    # Each faction writes to their own isolated store (simulating separate agents)
    db_paths = {
        "faction-A": Path(tmp) / "faction_a.db",
        "faction-B": Path(tmp) / "faction_b.db",
        "faction-C": Path(tmp) / "faction_c.db",
        "faction-D": Path(tmp) / "faction_d.db",
    }

    # Timestamps spread 1 second apart so LWW has a clear winner
    base_ts = time.time()

    faction_claims = [
        # (agent_id, owner_value, version, timestamp_offset, king_active_value)
        ("faction-A", "Iron_Wolves",  1, 0.0,  None),   # claims throne, no king belief
        ("faction-B", "Shadow_Keep",  1, 1.0,  None),   # claims throne, no king belief
        # Faction C has the latest timestamp (wins LWW on "owner") BUT also incorrectly
        # asserts the dead king is still active=True — SemanticRule will catch this
        ("faction-C", "Ember_Court",  1, 2.0,  True),
        ("faction-D", "Ember_Court",  1, 1.5,  None),   # second-latest; same owner as C
    ]

    _sub("Each faction writing their local belief store")
    for agent_id, owner, ver, ts_offset, king_active in faction_claims:
        with WorldStore(db_paths[agent_id]) as store:
            # Throne room ownership claim
            store.set_fact(WorldFact(
                domain="control",
                entity="throne_room",
                attribute="owner",
                value=owner,
                version=ver,
                agent_id=agent_id,
                timestamp=base_ts + ts_offset,
            ))
            # King-is-alive status (written by all factions)
            store.set_fact(WorldFact(
                domain="life",
                entity="king",
                attribute="alive",
                value=False,          # every faction knows the king is dead
                version=2,
                agent_id=agent_id,
                timestamp=base_ts + ts_offset,
            ))
            # Faction C also (incorrectly) claims the king is active
            if king_active is not None:
                store.set_fact(WorldFact(
                    domain="session",
                    entity="king",
                    attribute="active",
                    value=king_active,    # True — contradicts the dead-king fact
                    version=1,
                    agent_id=agent_id,
                    timestamp=base_ts + ts_offset,
                ))
        print(f"    {agent_id}: throne_room.owner={owner!r}  (ts+{ts_offset:.1f}s)")

    # Semantic rule: if king is dead (life.king.alive=False) then
    # session.king.active must be False
    dead_king_rule = SemanticRule(
        name="dead-king-cannot-be-active",
        trigger_domain="life",
        trigger_attribute="alive",
        trigger_value=False,
        implies_domain="session",
        implies_entity_same=True,
        implies_attribute="active",
        implies_value=False,
    )
    engine = RuleEngine(rules=[dead_king_rule])
    merger = WorldMerger(rule_engine=engine)

    # Canonical store starts empty; we merge all four faction stores into it
    canonical_db = Path(tmp) / "canonical.db"

    _sub("Merging all four faction stores into the canonical world store (LWW)")
    with WorldStore(canonical_db) as canonical:
        for agent_id, db_path in db_paths.items():
            with WorldStore(db_path) as remote:
                result = merger.merge(canonical, remote)
            print(
                f"    Merged {agent_id}: "
                f"{result.merged_count} fact(s), "
                f"{len(result.conflicts)} conflict(s)"
            )

    # Inspect the result
    _sub("Canonical world state after LWW merge")
    with WorldStore(canonical_db) as store:
        all_facts = store.list_facts()
        all_events = store.list_events()

    owner_fact = next(
        (f for f in all_facts
         if f.domain == "control" and f.entity == "throne_room" and f.attribute == "owner"),
        None,
    )
    if owner_fact:
        print(f"    throne_room.owner = {owner_fact.value!r}  (agent={owner_fact.agent_id})")
        print("    => LWW picked the faction with the highest timestamp (faction-C)")

    king_alive = next(
        (f for f in all_facts if f.domain == "life" and f.attribute == "alive"), None
    )
    if king_alive:
        print(f"    king.alive        = {king_alive.value!r}")

    _sub("Contradiction events from SemanticRule check")
    if all_events:
        for evt in all_events:
            print(f"    Rule fired: '{evt.rule}'")
            print(f"    Agents involved: {evt.agent_a} vs {evt.agent_b}")
            print(
                "    => faction-C claimed session.king.active=True while king.alive=False "
                "— the game engine flags this as a contradiction to be resolved."
            )
    else:
        print("    No contradiction events (unexpected — check SemanticRule config)")

    _sub("Why this matters")
    print(
        "    agentcrdt lets every faction agent write independently with no\n"
        "    coordination. LWW automatically resolves concurrent ownership claims.\n"
        "    SemanticRules catch logical inconsistencies that LWW alone cannot see."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — worldoracle: Two NPC guards have contradictory beliefs about the king
# ─────────────────────────────────────────────────────────────────────────────

def step4_worldoracle() -> None:
    _header(
        "STEP 4 — worldoracle: NPC guards hold contradictory beliefs about the king"
    )

    # Guard-1: was told by the court herald (a quest-giver NPC) that the king lives
    guard1_state = BeliefState(npc_id="guard-1")
    guard1_state.add(WorldPredicate(
        subject="king",
        attribute="alive",
        value=True,
        source="quest-giver",       # second-hand information
        confidence=0.65,
        timestamp=1000.0,           # older intel
    ))
    # Guard-1 also believes the throne room is occupied
    guard1_state.add(WorldPredicate(
        subject="throne_room",
        attribute="occupied",
        value=True,
        source="observation",
        confidence=0.9,
        timestamp=1200.0,
    ))

    # Guard-2: personally witnessed the king's assassination
    guard2_state = BeliefState(npc_id="guard-2")
    guard2_state.add(WorldPredicate(
        subject="king",
        attribute="alive",
        value=False,
        source="observation",       # direct first-hand observation
        confidence=1.0,
        timestamp=1500.0,           # newer — guard saw it happen
    ))
    guard2_state.add(WorldPredicate(
        subject="throne_room",
        attribute="occupied",
        value=True,
        source="observation",
        confidence=0.95,
        timestamp=1200.0,
    ))

    print(f"  guard-1 beliefs: {len(guard1_state.predicates)} predicate(s)")
    for p in guard1_state.predicates:
        print(f"    {p.subject}.{p.attribute} = {p.value!r}  "
              f"(source={p.source}, confidence={p.confidence})")

    print(f"\n  guard-2 beliefs: {len(guard2_state.predicates)} predicate(s)")
    for p in guard2_state.predicates:
        print(f"    {p.subject}.{p.attribute} = {p.value!r}  "
              f"(source={p.source}, confidence={p.confidence})")

    # Build a merged belief state so ContradictionDetector sees both guards' views
    # (same as if we were asking: "what does the game world collectively believe?")
    _sub("Merging guard beliefs into a shared world-view for contradiction detection")
    merged_state = BeliefState(npc_id="world-view")
    for pred in guard1_state.predicates + guard2_state.predicates:
        merged_state.add(pred)

    print(f"  Combined predicates: {len(merged_state.predicates)}")

    _sub("ContradictionDetector scanning merged world-view")
    detector = ContradictionDetector()
    contradictions = detector.detect(merged_state)
    print(f"  Contradictions found: {len(contradictions)}")

    repairer = BeliefRepairer()
    repairs = []

    for pred_a, pred_b in contradictions:
        print(
            f"\n  CONFLICT: {pred_a.subject}.{pred_a.attribute}\n"
            f"    Belief A — value={pred_a.value!r}  source={pred_a.source!r}  "
            f"confidence={pred_a.confidence}  ts={pred_a.timestamp}\n"
            f"    Belief B — value={pred_b.value!r}  source={pred_b.source!r}  "
            f"confidence={pred_b.confidence}  ts={pred_b.timestamp}"
        )

        frame = repairer.repair(pred_a, pred_b)
        repairs.append(frame)

        print(f"\n  REPAIR PROPOSAL:")
        print(f"    Strategy:       {frame.strategy}")
        print(f"    Resolved value: {frame.resolved_value!r}")
        print(f"    Reason:         {frame.reason}")
        print(
            "    => The game engine should update guard-1's belief to king.alive=False "
            "to bring the world into a consistent state."
        )

    if not contradictions:
        print("  No contradictions detected (unexpected — check predicate setup)")

    _sub("Why this matters")
    print(
        "    worldoracle gives every NPC an independent, self-consistent belief\n"
        "    state. ContradictionDetector surfaces conflicts when guards share intel,\n"
        "    and BeliefRepairer proposes which version to trust — so NPCs always\n"
        "    act on the best available information, not stale hearsay."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "#" * 70)
    print("#  MMO Game Brain — Thornvale Keep Siege Integration Demo")
    print("#  Libraries: agentcrdt | normsync | worldoracle | rulegraph")
    print("#" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        step1_rulegraph(tmp)
        step2_normsync()
        step3_agentcrdt(tmp)
        step4_worldoracle()

    _header("SUMMARY")
    print(
        "  rulegraph  — Game Master queried siege law; truce supersedes breach ratio\n"
        "  normsync   — Faction B's attack in truce_zone was intercepted and blocked\n"
        "  agentcrdt  — 4 concurrent ownership claims merged via LWW; semantic rule\n"
        "               caught faction-C's invalid 'dead king is active' assertion\n"
        "  worldoracle— Guards' contradictory king-alive beliefs detected and a\n"
        "               repair frame proposed (prefer_newer / prefer_observation)\n"
        "\n"
        "  Together these four libraries form a coherent game-world brain:\n"
        "  rules arbitration -> norm enforcement -> distributed belief sync\n"
        "  -> NPC epistemic consistency.  Each component is independently useful;\n"
        "  combined they eliminate the three biggest sources of MMO agent bugs:\n"
        "  illegal actions, stale beliefs, and undetected logical contradictions.\n"
    )


if __name__ == "__main__":
    main()
