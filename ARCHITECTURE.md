# agentcrdt Architecture

This document is the authoritative developer reference for agentcrdt's internals.

---

## Data Flow

```
┌─────────────┐     WorldFact(domain,entity,attr,value)      ┌──────────────┐
│    Agent    │ ──────────────────────────────────────────► │  WorldStore  │
│  (or CLI)   │                                              │  (SQLite)    │
└─────────────┘                                              └──────┬───────┘
                                                                    │
                         WorldMerger.merge(local, remote)           │
                 ◄──────────────────────────────────────────────────┘
                         LWW: higher version wins, then timestamp
                                                                    │
                                              RuleEngine.check(facts)
                                                                    │
                                                                    ▼
                                                          ┌──────────────────┐
                                                          │ ContradictionEvent│
                                                          │ (saved to store) │
                                                          └──────────────────┘
```

## Module Map

| File | Responsibility |
|------|---------------|
| `fact.py` | `WorldFact` and `ContradictionEvent`. Content-addressed via `_sha16()`. |
| `rules.py` | `SemanticRule` and `RuleEngine`. Cross-domain implication checking. |
| `store.py` | SQLite persistence. `WorldStore` owns the DB connection. LWW semantics in `set_fact`. |
| `merger.py` | `WorldMerger`. Merges two stores using LWW CRDT, then runs rule engine. |
| `report.py` | Output formatters: `print_state()` (Rich), `print_events()`, `to_json()`, `to_markdown()`. |
| `cli.py` | Click CLI. Subcommands: `set`, `get`, `merge`, `events`, `status`. |
| `api.py` | FastAPI REST server. Endpoints: `/fact`, `/facts`, `/merge`, `/events`, `/health`. |
| `mcp_server.py` | Model Context Protocol server. Exposes `set_world_fact`, `get_world_facts`, `merge_world_state`. |

---

## Key Invariants

### 1. WorldFact.id is deterministic

```
WorldFact.id = SHA-256[:16]("{domain}|{entity}|{attribute}")
```

The same `(domain, entity, attribute)` triple always produces the same 16-char hex ID.
The `value`, `version`, `agent_id`, and `timestamp` are *not* included in the hash —
they are mutable metadata. LWW merge determines which version of `value` wins.

### 2. Last-Write-Wins (LWW) CRDT Semantics

`WorldStore.set_fact()` applies the following policy:
- If `fact.version > existing.version` → update wins
- If `fact.version == existing.version` and `fact.timestamp > existing.timestamp` → update wins
- Otherwise → existing value is kept

This makes the store eventually consistent under concurrent writes from multiple agents.

### 3. SemanticRule contradiction detection

The `RuleEngine` checks all trigger-matching facts and their implied counterparts.
Contradiction detection is O(n_rules × n_facts). Rules with `implies_entity_same=False`
require cross-entity lookup which is skipped (entity cannot be inferred automatically).

### 4. WorldStore is thread-unsafe

A single `sqlite3.Connection` is held per `WorldStore` instance. Do not share across threads.

---

## SQLite Schema

```sql
CREATE TABLE facts (
    id        TEXT PRIMARY KEY,
    domain    TEXT NOT NULL,
    entity    TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value     TEXT NOT NULL,   -- JSON-serialised
    version   INTEGER NOT NULL DEFAULT 0,
    agent_id  TEXT NOT NULL DEFAULT '',
    timestamp REAL NOT NULL
);

CREATE TABLE events (
    id             TEXT PRIMARY KEY,
    rule           TEXT NOT NULL,
    facts_involved TEXT NOT NULL,   -- JSON array of fact IDs
    agent_a        TEXT NOT NULL,
    agent_b        TEXT NOT NULL,
    timestamp      REAL NOT NULL
);
```
