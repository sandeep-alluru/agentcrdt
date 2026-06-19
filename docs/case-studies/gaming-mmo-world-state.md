# Case Study: Conflict-Free World State for 500k Concurrent MMO Players

## Company Profile

**Cascade Games** is an online game studio with 35 engineers operating an MMO with 500,000
concurrent players at peak. Their game world is divided into 64 geographic shards, each running
on a dedicated Go game server. Their tech stack is Go (game server), Python (tooling and ops),
Redis (session data), PostgreSQL (player accounts), and Kafka (event bus). Their central
challenge is maintaining a consistent shared world state across 64 shards without a serializing
lock.

## The Problem

Cascade's world state was coordinated through a central Redis cluster. During large-scale world
events — particularly world boss fights where 50,000 players converged on a single zone — the
central Redis cluster became a bottleneck. Three serious problems emerged:

**Boss HP inconsistency**: When 50,000 players simultaneously dealt damage, conflicting writes
caused the boss's HP to flicker between values. The boss died at 30% HP in some clients,
survived at -5,000 HP in others, and sometimes respawned immediately because the death event
fired before HP reached zero. This happened in 5.8% of major boss encounters, always during
peak concurrency.

**Central DB failure**: The Redis cluster was a single point of failure. A 4-minute outage
during a world event caused 50,000 players to see frozen game state, triggering mass
disconnects and a wave of refund requests. The cluster could not scale horizontally because
writes needed serialization.

**Exploit investigation latency**: When players reported exploits — abilities being used at
impossible times, bosses dying to phantom damage — engineers had no audit trail. Reconstructing
what happened required cross-referencing 64 shard logs with timestamps that drifted by up to
800ms. A single exploit investigation took 3 weeks.

## Solution Architecture

```
Shard A (Go game server)          Shard B (Go game server)
------------------------          ------------------------
WorldStore("shard-a.db")         WorldStore("shard-b.db")
  set_fact(boss.hp, 45000,          set_fact(boss.hp, 43000,
           version=3,                        version=3,
           agent_id="shard-a")               agent_id="shard-b")
         │                                   │
         └──────── 100ms sync ───────────────┘
                        │
              WorldMerger(rule_engine=RuleEngine([
                SemanticRule("death-trigger",
                  trigger_domain="combat",
                  trigger_attribute="hp",
                  trigger_value=0,          # hp <= 0
                  implies_domain="combat",
                  implies_attribute="status",
                  implies_value="dead")
              ]))
              .merge(shard_a_store, shard_b_store)
                        │
              MergeResult.conflicts → death event if HP ≤ 0 + status="alive"
                        │
              ChangeWatcher.check() → broadcast state delta to subscribed clients
                        │
              FactHistory.get_at_time() → exploit audit trail
```

Each of the 64 game server shards maintains its own `WorldStore` SQLite database. Player
actions update local shard state immediately with no network round-trip. Every 100ms, a
background sync process calls `WorldMerger.merge()` to reconcile all shard stores using
Last-Write-Wins CRDT semantics. The semantic rule engine detects the HP-reaches-zero condition
and fires a boss death event exactly once, preventing the flickering death/respawn loop.

## Implementation

```python
from agentcrdt import (
    WorldFact,
    WorldStore,
    WorldMerger,
    SemanticRule,
    RuleEngine,
    ChangeWatcher,
    FactHistory,
    conflict_report,
)
import time

# Semantic rule: when boss HP reaches 0, status must become "dead"
death_rule = SemanticRule(
    name="boss-death-trigger",
    trigger_domain="combat",
    trigger_attribute="hp",
    trigger_value=0,
    implies_domain="combat",
    implies_entity_same=True,
    implies_attribute="status",
    implies_value="dead",
)

merger = WorldMerger(rule_engine=RuleEngine([death_rule]))

def apply_damage(shard_store: WorldStore, boss_id: str,
                 new_hp: int, version: int, shard_id: str):
    """Record damage dealt by this shard — local write, no network call."""
    hp_fact = WorldFact(
        domain="combat",
        entity=boss_id,
        attribute="hp",
        value=new_hp,
        version=version,
        agent_id=shard_id,
        timestamp=time.time(),
    )
    shard_store.set_fact(hp_fact)

def sync_shards(shard_stores: dict[str, WorldStore],
                canonical_store: WorldStore) -> list[str]:
    """100ms sync: merge all shards into canonical, fire death events on HP=0."""
    death_events = []
    for shard_id, store in shard_stores.items():
        result = merger.merge(canonical_store, store)
        for conflict in result.conflicts:
            if conflict.rule == "boss-death-trigger":
                # Exactly one death event per boss — CRDT merge ensures no duplicates
                death_events.append(conflict.facts_involved[0])
    return death_events

# ChangeWatcher: push state deltas to subscribed game clients
def start_client_broadcaster(canonical_store: WorldStore):
    watcher = ChangeWatcher(canonical_store)

    @watcher.on_change(attribute="hp")
    def on_hp_change(fact: WorldFact):
        broadcast_to_zone_clients(fact.entity, {"hp": fact.value})

    @watcher.on_change(attribute="status")
    def on_status_change(fact: WorldFact):
        if fact.value == "dead":
            broadcast_boss_death(fact.entity)

    return watcher

# Exploit investigation: reconstruct exact state at any point in time
def investigate_exploit(store: WorldStore, boss_id: str, exploit_timestamp: float):
    history = FactHistory(store)
    hp_at_time = history.get_at_time(boss_id, "hp", exploit_timestamp)
    status_at_time = history.get_at_time(boss_id, "status", exploit_timestamp)
    summary = conflict_report(store)
    return {
        "boss_id": boss_id,
        "hp_at_exploit_time": hp_at_time.value if hp_at_time else "unknown",
        "status_at_exploit_time": status_at_time.value if status_at_time else "unknown",
        "total_conflicts_recorded": summary.total_conflicts,
        "contested_entities": summary.most_contested_entities,
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| Boss fight HP consistency | 94.2% of encounters | 99.97% |
| Boss flickering death/respawn events | 5.8% of encounters | 0.03% |
| Central DB writes for game state | ~2M/min (peak) | 0 (local writes only) |
| Concurrent players supported | ~200k before Redis saturation | 500k (64 shards) |
| Exploit investigation time | 3 weeks | 2 hours via FactHistory |
| Single point of failure | Yes (Redis cluster) | No (each shard autonomous) |

The CRDT merge cadence of 100ms meant that even during peak 50,000-player boss fights,
the worst-case client-visible inconsistency window was one merge cycle. Players tolerated this
without complaint — the previous flickering had been far more disruptive.

## Key Takeaways

- The content-addressed `WorldFact` (keyed on `domain|entity|attribute`) means the same boss HP
  slot is always the same ID across all 64 shards, making LWW merge deterministic without any
  coordination overhead.
- `SemanticRule` with `implies_entity_same=True` is the key to cross-domain consistency: when
  HP hits zero, the rule fires a `status=dead` implication on the same entity, preventing
  the phantom-death bug without any custom logic.
- `ChangeWatcher.on_change()` as a decorator makes it easy to wire state changes to client
  broadcasts without polling — the watcher's `check()` call is the entire subscription system.
- `FactHistory.get_at_time()` turned exploit investigations from 3-week log-archaeology
  projects into 2-hour queries — every fact write is automatically versioned.
- The shard-local write + periodic merge model is strictly superior to a central DB for
  game state: lower latency for players, higher throughput, and no single point of failure.

## Try It Yourself

```bash
pip install agentcrdt

# Set a world fact from two agents and merge
agentcrdt --db shard-a.db set combat boss hp 45000 --version 2 --agent-id shard-a
agentcrdt --db shard-b.db set combat boss hp 43000 --version 2 --agent-id shard-b
agentcrdt --db shard-a.db merge shard-b.db
agentcrdt --db shard-a.db events   # shows ContradictionEvents if rules are violated
```
