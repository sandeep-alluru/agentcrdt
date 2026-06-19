"""4 AI agents co-simulate an MMO raid boss fight using agentcrdt.

Story: A raid boss fight in an online RPG. Four agents — Tank, Healer, DPS,
Rogue — each independently update the shared world state. Their writes are
merged with LWW CRDT semantics. A semantic rule fires when the boss's HP
reaches zero but its status is still "alive", resolving the contradiction
automatically to "dead" and unlocking the loot chest.

Run from repo root:
    python examples/collaborative_game_agents.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore


def ts(offset: float = 0.0) -> float:
    """Return a stable base timestamp + offset (avoids wall-clock dependency)."""
    return 1_700_000_000.0 + offset


def print_separator(char: str = "-", width: int = 70) -> None:
    print(char * width)


def print_world_state(store: WorldStore, title: str = "World State") -> None:
    print(f"\n{title}")
    print_separator()
    facts = store.list_facts()
    if not facts:
        print("  (empty)")
    for f in facts:
        print(f"  {f.domain:12} | {f.entity:12} | {f.attribute:12} = {f.value!r:<16}"
              f"  (agent={f.agent_id}, v={f.version})")
    print()


def main() -> None:
    print(f"\n{'=' * 70}")
    print("  RAID SIMULATION — agentcrdt Collaborative Agent Demo")
    print("  Dungeon: Lair of the Eternal Void  |  Boss: Malachar the Undying")
    print(f"{'=' * 70}\n")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── Step 1: Set up initial world state (game engine) ─────────────────
        print("Step 1: Game engine initializes world state.")
        engine_db = str(base / "engine.db")
        with WorldStore(engine_db) as engine_store:
            initial_facts = [
                WorldFact(domain="combat",     entity="boss",     attribute="health",
                          value=10000, version=1, agent_id="game-engine", timestamp=ts(0)),
                WorldFact(domain="combat",     entity="boss",     attribute="status",
                          value="alive", version=1, agent_id="game-engine", timestamp=ts(0)),
                WorldFact(domain="combat",     entity="player-001", attribute="health",
                          value=4500, version=1, agent_id="game-engine", timestamp=ts(0)),
                WorldFact(domain="combat",     entity="player-002", attribute="health",
                          value=5000, version=1, agent_id="game-engine", timestamp=ts(0)),
                WorldFact(domain="inventory",  entity="loot-chest-01", attribute="status",
                          value="locked", version=1, agent_id="game-engine", timestamp=ts(0)),
            ]
            for f in initial_facts:
                engine_store.set_fact(f)
            print(f"  Initialized {len(initial_facts)} world facts.")

        # ── Step 2: Each agent writes to its own local store ──────────────────
        print("\nStep 2: Agents act independently during the fight.\n")

        # Agent-Tank: absorbs damage, hits boss for 1500 HP
        tank_db = str(base / "tank.db")
        print("  Agent-Tank: attacks boss (-1500 HP), records shield activation.")
        with WorldStore(tank_db) as tank_store:
            # First copy engine state into tank's local view
            with WorldStore(engine_db) as eng:
                for f in eng.list_facts():
                    tank_store.set_fact(f)
            # Tank hits boss: 10000 - 1500 = 8500
            tank_store.set_fact(WorldFact(
                domain="combat", entity="boss", attribute="health",
                value=8500, version=2, agent_id="agent-tank", timestamp=ts(1.0),
            ))
            # Tank absorbs a hit (player-001 takes 800 damage)
            tank_store.set_fact(WorldFact(
                domain="combat", entity="player-001", attribute="health",
                value=3700, version=2, agent_id="agent-tank", timestamp=ts(1.1),
            ))

        # Agent-Healer: heals player-002 for 300 HP
        healer_db = str(base / "healer.db")
        print("  Agent-Healer: heals player-002 (+300 HP).")
        with WorldStore(healer_db) as healer_store:
            with WorldStore(engine_db) as eng:
                for f in eng.list_facts():
                    healer_store.set_fact(f)
            healer_store.set_fact(WorldFact(
                domain="combat", entity="player-002", attribute="health",
                value=5300, version=2, agent_id="agent-healer", timestamp=ts(1.5),
            ))

        # Agent-DPS: has stale read (thinks boss has 10000 HP), hits for 3000
        # but writes at later timestamp — its version will win LWW for boss health
        dps_db = str(base / "dps.db")
        print("  Agent-DPS: hits boss (-3000 HP from stale 10000 view → writes 7000, later ts).")
        with WorldStore(dps_db) as dps_store:
            with WorldStore(engine_db) as eng:
                for f in eng.list_facts():
                    dps_store.set_fact(f)
            # DPS had a stale read of 10000, so: 10000 - 3000 = 7000
            # But this is at version=2 with a higher timestamp than tank
            dps_store.set_fact(WorldFact(
                domain="combat", entity="boss", attribute="health",
                value=7000, version=2, agent_id="agent-dps", timestamp=ts(2.0),
            ))

        # Agent-Rogue: same version as DPS but even higher timestamp, hits for 2500 more
        rogue_db = str(base / "rogue.db")
        print("  Agent-Rogue: hits boss (-2500 HP, simultaneous with DPS → latest ts wins).")
        with WorldStore(rogue_db) as rogue_store:
            with WorldStore(engine_db) as eng:
                for f in eng.list_facts():
                    rogue_store.set_fact(f)
            # Rogue applies damage from DPS's state: 7000 - 2500 = 4500
            rogue_store.set_fact(WorldFact(
                domain="combat", entity="boss", attribute="health",
                value=4500, version=2, agent_id="agent-rogue", timestamp=ts(2.3),
            ))
            # Rogue also delivers final strike bringing boss to 0
            rogue_store.set_fact(WorldFact(
                domain="combat", entity="boss", attribute="health",
                value=0, version=3, agent_id="agent-rogue", timestamp=ts(3.0),
            ))

        # ── Step 3: Define semantic rules ────────────────────────────────────
        print("\nStep 3: Loading semantic rules.")
        alive_dead_rule = SemanticRule(
            name="boss-zero-hp-must-be-dead",
            trigger_domain="combat",
            trigger_attribute="health",
            trigger_value=0,
            implies_domain="combat",
            implies_entity_same=True,
            implies_attribute="status",
            implies_value="dead",
        )
        engine_rule = RuleEngine(rules=[alive_dead_rule])
        merger = WorldMerger(rule_engine=engine_rule)
        print("  Rule: boss.health=0 → boss.status must be 'dead'")

        # ── Step 4: Merge all agent stores sequentially ───────────────────────
        print("\nStep 4: Merging all agent world views (LWW CRDT).")
        master_db = str(base / "master.db")

        # Start master from engine state
        with WorldStore(engine_db) as eng, WorldStore(master_db) as master:
            r0 = merger.merge(master, eng)
            print(f"  + engine state:   merged {r0.merged_count} facts")

        with WorldStore(master_db) as master, WorldStore(tank_db) as remote:
            r1 = merger.merge(master, remote)
            print(f"  + agent-tank:     merged {r1.merged_count} facts")

        with WorldStore(master_db) as master, WorldStore(healer_db) as remote:
            r2 = merger.merge(master, remote)
            print(f"  + agent-healer:   merged {r2.merged_count} facts")

        with WorldStore(master_db) as master, WorldStore(dps_db) as remote:
            r3 = merger.merge(master, remote)
            print(f"  + agent-dps:      merged {r3.merged_count} facts")

        with WorldStore(master_db) as master, WorldStore(rogue_db) as remote:
            r4 = merger.merge(master, remote)
            print(f"  + agent-rogue:    merged {r4.merged_count} facts, "
                  f"conflicts detected: {len(r4.conflicts)}")

        # ── Step 5: Auto-resolve contradiction (set boss.status = dead) ──────
        print("\nStep 5: Auto-resolving contradiction (alive/dead).")
        with WorldStore(master_db) as master:
            events = master.list_events()
            alive_dead_conflict = next(
                (e for e in events if "zero-hp" in e.rule or "dead" in e.rule), None
            )
            if alive_dead_conflict or r4.conflicts:
                print(f"  Contradiction detected! Rule: boss-zero-hp-must-be-dead")
                print(f"  Auto-resolving: boss.status → 'dead'")
                master.set_fact(WorldFact(
                    domain="combat", entity="boss", attribute="status",
                    value="dead", version=10, agent_id="rule-engine", timestamp=ts(4.0),
                ))
                # Unlock loot chest
                print(f"  Loot trigger: chest unlocked as boss death consequence.")
                master.set_fact(WorldFact(
                    domain="inventory", entity="loot-chest-01", attribute="status",
                    value="unlocked", version=2, agent_id="rule-engine", timestamp=ts(4.1),
                ))

        # ── Final world state ─────────────────────────────────────────────────
        with WorldStore(master_db) as master:
            print_world_state(master, "FINAL MERGED WORLD STATE")

        # ── Summary ───────────────────────────────────────────────────────────
        print_separator("=")
        with WorldStore(master_db) as master:
            boss_hp   = next((f.value for f in master.list_facts()
                              if f.entity == "boss" and f.attribute == "health"), "?")
            boss_st   = next((f.value for f in master.list_facts()
                              if f.entity == "boss" and f.attribute == "status"), "?")
            chest_st  = next((f.value for f in master.list_facts()
                              if f.entity == "loot-chest-01"), "?")
            n_conflicts = len(master.list_events())

        print(f"\n  RAID COMPLETE:")
        print(f"    Boss HP:        10000 → {boss_hp}")
        print(f"    Boss Status:    alive → {boss_st}")
        print(f"    Contradictions: {n_conflicts} resolved (alive/dead)")
        chest_icon = "UNLOCKED" if chest_st == "unlocked" else "LOCKED"
        print(f"    Loot Chest:     {chest_icon}")
        print()
        print_separator("=")
        print()


if __name__ == "__main__":
    main()
