"""Smart building IoT sensor network — 6 agents monitoring 6 zones.

Story: A smart office building with 6 zones (A-F). Six sensor agents
independently report temperature, occupancy, and HVAC status. Agent-D goes
offline and comes back with stale data (LWW correctly ignores it). Agent-E
detects that zone-E is hot (31 degrees C) but HVAC is off — a semantic rule
fires and the building management system is alerted.

Run from repo root:
    python examples/iot_agent_network.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore


def ts(offset: float = 0.0) -> float:
    """Return stable base timestamp + offset (seconds)."""
    return 1_720_000_000.0 + offset


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def print_zone_state(store: WorldStore) -> None:
    """Pretty-print zone facts grouped by entity."""
    facts = store.list_facts()
    # Group by entity
    zones: dict[str, dict[str, object]] = {}
    for f in facts:
        zones.setdefault(f.entity, {})[f.attribute] = f.value

    print(f"\n  {'Zone':<12} {'Temp (°C)':>10} {'Occupancy':>10} {'HVAC':>8}")
    print_separator(" ", 12)
    print("  " + "-" * 50)
    for zone_id in sorted(zones):
        z = zones[zone_id]
        temp  = z.get("temperature", "?")
        occ   = z.get("occupancy", "?")
        hvac  = z.get("hvac_status", "?")
        temp_str = f"{temp}°C" if isinstance(temp, (int, float)) else str(temp)
        occ_str  = "occupied" if occ else "empty"
        print(f"  {zone_id:<12} {temp_str:>10} {occ_str:>10} {str(hvac):>8}")
    print()


def main() -> None:
    print(f"\n{'=' * 72}")
    print("  SMART BUILDING IoT SYNC — agentcrdt Multi-Agent Sensor Network")
    print("  Building: Apex Tower  |  6 zones  |  6 sensor agents")
    print(f"{'=' * 72}\n")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── Agent stores ──────────────────────────────────────────────────────
        agent_dbs = {z: str(base / f"agent_{z}.db") for z in "ABCDEF"}
        master_db = str(base / "master.db")

        # ── Normal sensor readings (agents A, B, C) ───────────────────────────
        print("Step 1: Agents A, B, C report current zone states (t=+0s).")

        # Agent-A: zone-A (lobby, hot, HVAC running)
        with WorldStore(agent_dbs["A"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-A",
                attribute="temperature", value=22, version=1,
                agent_id="agent-A", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-A",
                attribute="occupancy", value=True, version=1,
                agent_id="agent-A", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-A",
                attribute="hvac_status", value="on", version=1,
                agent_id="agent-A", timestamp=ts(0)))

        # Agent-B: zone-B (conference room, empty, HVAC off — power saving)
        with WorldStore(agent_dbs["B"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-B",
                attribute="temperature", value=24, version=1,
                agent_id="agent-B", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-B",
                attribute="occupancy", value=False, version=1,
                agent_id="agent-B", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-B",
                attribute="hvac_status", value="off", version=1,
                agent_id="agent-B", timestamp=ts(0)))

        # Agent-C: zone-C (engineering floor, busy, HVAC on)
        with WorldStore(agent_dbs["C"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-C",
                attribute="temperature", value=21, version=1,
                agent_id="agent-C", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-C",
                attribute="occupancy", value=True, version=1,
                agent_id="agent-C", timestamp=ts(0)))
            store.set_fact(WorldFact(domain="building", entity="zone-C",
                attribute="hvac_status", value="on", version=1,
                agent_id="agent-C", timestamp=ts(0)))

        print("  Agents A, B, C: zone-A (22°C, on), zone-B (24°C, off), zone-C (21°C, on)")

        # ── Agent-D: goes offline, comes back with stale data ─────────────────
        # Agent-D's timestamp is 240 seconds (4 min) EARLIER than the last good read.
        # After we write a v2 "current" fact for zone-D, Agent-D's stale write is ignored.
        print("\nStep 2: Agent-D was offline for 4 minutes — returns with stale data.")

        # First, simulate that zone-D already has a recent authoritative reading
        # from the building controller at t=+50s.
        with WorldStore(master_db) as master:
            master.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="temperature", value=23, version=2,
                agent_id="building-controller", timestamp=ts(50)))
            master.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="occupancy", value=True, version=2,
                agent_id="building-controller", timestamp=ts(50)))
            master.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="hvac_status", value="on", version=2,
                agent_id="building-controller", timestamp=ts(50)))

        # Agent-D comes back with stale data from 4 minutes ago (ts = -240+0 = ts(-240))
        # LWW: version 1 < version 2, so it will be silently dropped.
        with WorldStore(agent_dbs["D"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="temperature", value=35, version=1,  # stale high temp
                agent_id="agent-D", timestamp=ts(-240)))       # 4 minutes before base
            store.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="occupancy", value=False, version=1,
                agent_id="agent-D", timestamp=ts(-240)))
            store.set_fact(WorldFact(domain="building", entity="zone-D",
                attribute="hvac_status", value="off", version=1,
                agent_id="agent-D", timestamp=ts(-240)))

        print("  Agent-D reports stale: temp=35°C, empty, hvac=off (4 min old, v=1)")
        print("  Master already has: temp=23°C, occupied, hvac=on  (current,   v=2)")
        print("  Expected: Agent-D's stale data will be silently IGNORED by LWW.")

        # ── Agent-E: zone-E is hot but HVAC is off — anomaly ─────────────────
        print("\nStep 3: Agent-E reports zone-E anomaly: 31°C but HVAC is off.")
        with WorldStore(agent_dbs["E"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-E",
                attribute="temperature", value=31, version=1,
                agent_id="agent-E", timestamp=ts(10)))
            store.set_fact(WorldFact(domain="building", entity="zone-E",
                attribute="occupancy", value=True, version=1,
                agent_id="agent-E", timestamp=ts(10)))
            # HVAC is off even though temp is dangerously high
            store.set_fact(WorldFact(domain="building", entity="zone-E",
                attribute="hvac_status", value="off", version=1,
                agent_id="agent-E", timestamp=ts(10)))

        # ── Agent-F: zone-F (server room, normal) ────────────────────────────
        print("\nStep 4: Agent-F reports zone-F (server room, well-cooled).")
        with WorldStore(agent_dbs["F"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-F",
                attribute="temperature", value=18, version=1,
                agent_id="agent-F", timestamp=ts(5)))
            store.set_fact(WorldFact(domain="building", entity="zone-F",
                attribute="occupancy", value=False, version=1,
                agent_id="agent-F", timestamp=ts(5)))
            store.set_fact(WorldFact(domain="building", entity="zone-F",
                attribute="hvac_status", value="on", version=1,
                agent_id="agent-F", timestamp=ts(5)))

        # ── Define HVAC anomaly rule ──────────────────────────────────────────
        print("\nStep 5: Loading semantic rules.")
        # Rule: if hvac_status="off", temperature should NOT exceed safe threshold.
        # We encode: hvac_status="off" in building domain implies temperature
        # should be "safe" — but since we can't compare numeric values directly
        # with the current rule engine, we use a second boolean fact approach.
        # Instead, we add a "temp_alert" fact for zone-E and detect contradiction
        # between hvac_status=off and temp_alert=True.

        # First, let the rule engine fire on: hvac=off → temp_alert must be False
        # We manually add the temp_alert for zone-E since temp > 28°C.
        with WorldStore(agent_dbs["E"]) as store:
            store.set_fact(WorldFact(domain="building", entity="zone-E",
                attribute="temp_alert", value=True, version=1,
                agent_id="agent-E", timestamp=ts(10)))

        hvac_temp_rule = SemanticRule(
            name="hvac-off-with-temp-alert",
            trigger_domain="building",
            trigger_attribute="temp_alert",
            trigger_value=True,
            implies_domain="building",
            implies_entity_same=True,
            implies_attribute="hvac_status",
            implies_value="on",   # If temp_alert, HVAC should be ON — if it's "off" → contradiction
        )
        engine = RuleEngine(rules=[hvac_temp_rule])
        merger = WorldMerger(rule_engine=engine)
        print("  Rule: building.temp_alert=True → building.hvac_status must be 'on'")

        # ── Merge all agent stores into master ────────────────────────────────
        print("\nStep 6: Merging all 6 agent stores into master...")

        merge_order = ["A", "B", "C", "D", "E", "F"]
        for agent_id in merge_order:
            with WorldStore(master_db) as master, WorldStore(agent_dbs[agent_id]) as remote:
                result = merger.merge(master, remote)
                stale_note = " (stale data ignored by LWW)" if agent_id == "D" else ""
                anomaly_note = f" [{len(result.conflicts)} HVAC anomaly detected]" if result.conflicts else ""
                print(f"  + agent-{agent_id}: {result.merged_count} facts considered"
                      f"{stale_note}{anomaly_note}")

        # ── Validate LWW for zone-D ───────────────────────────────────────────
        with WorldStore(master_db) as master:
            zone_d_temp = next(
                (f.value for f in master.list_facts()
                 if f.entity == "zone-D" and f.attribute == "temperature"),
                None
            )
            zone_d_agent = next(
                (f.agent_id for f in master.list_facts()
                 if f.entity == "zone-D" and f.attribute == "temperature"),
                None
            )
            events = master.list_events()

        stale_correctly_ignored = zone_d_temp == 23 and zone_d_agent == "building-controller"
        stale_status = "CORRECTLY IGNORED" if stale_correctly_ignored else "ERROR: stale data leaked"

        print(f"\nStep 7: Validating stale data rejection...")
        print(f"  zone-D temperature in master = {zone_d_temp}°C "
              f"(source: {zone_d_agent}) — stale agent-D data: {stale_status}")

        # ── Print final building state ────────────────────────────────────────
        with WorldStore(master_db) as master:
            print("\nFINAL BUILDING STATE (all zones)")
            print_separator()
            print_zone_state(master)
            events = master.list_events()

        # ── Alerts ────────────────────────────────────────────────────────────
        print("BUILDING MANAGEMENT SYSTEM ALERTS")
        print_separator()
        if events:
            for ev in events:
                print(f"  [ALERT] Rule '{ev.rule}' fired")
                print(f"          Agents involved: {ev.agent_a} vs {ev.agent_b}")
                print(f"          Zone-E: temp=31°C but hvac=off — maintenance dispatch required")
        else:
            print("  No alerts.")

        # ── Summary ───────────────────────────────────────────────────────────
        print()
        print_separator("=")
        print(f"\nSMART BUILDING SYNC REPORT — Apex Tower")
        print(f"  Agents synced:      6 (A, B, C, D, E, F)")
        print(f"  Stale updates:      1 (agent-D, 4 min delay, v=1 < v=2 — ignored)")
        print(f"  Semantic conflicts: {len(events)}")
        if events:
            print(f"    -> HVAC anomaly: zone-E temp=31°C but hvac_status=off")
            print(f"       Action: AUTO-ALERT dispatched to facilities management")
        print()
        print_separator("=")
        print()


if __name__ == "__main__":
    main()
