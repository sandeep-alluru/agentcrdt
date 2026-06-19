# Quick Start

This guide walks you through the core agentcrdt workflow: creating world facts,
storing them, merging two agents' world views, and detecting semantic contradictions.

## Install

```bash
pip install agentcrdt
```

Optional extras:

```bash
pip install 'agentcrdt[api]'   # FastAPI REST server
pip install 'agentcrdt[mcp]'   # MCP server for Claude Desktop
```

---

## Step 1 — Create WorldFacts

A `WorldFact` is the fundamental unit. It is content-addressed by
`(domain, entity, attribute)`, so two agents recording the same fact key
always produce the same `id`.

```python
from agentcrdt import WorldFact

# Agent A asserts: the king is dead
fact_a = WorldFact(
    domain="life",
    entity="king",
    attribute="alive",
    value=False,
    version=1,
    agent_id="agent-A",
)

# Agent B asserts: the king's treaty is still valid (will contradict!)
fact_b = WorldFact(
    domain="alliance",
    entity="king",
    attribute="valid",
    value=True,
    version=1,
    agent_id="agent-B",
)

print(fact_a)
# WorldFact('a1b2c3d4e5f6a7b8': life.king.alive=False)
```

Key points:
- `domain` groups facts logically (e.g. `"life"`, `"alliance"`, `"possession"`).
- `entity` names the subject (e.g. `"king"`, `"treaty-1"`).
- `attribute` names the property (e.g. `"alive"`, `"valid"`, `"owner"`).
- `version` is your CRDT clock — higher version wins during merge.

---

## Step 2 — Store Facts in a WorldStore

`WorldStore` is a SQLite-backed store. You can use it as a context manager
so the connection is closed automatically.

```python
from agentcrdt import WorldStore

with WorldStore("local.db") as local_store:
    local_store.set_fact(fact_a)
    retrieved = local_store.get_fact_by_key("life", "king", "alive")
    print(retrieved.value)  # False

with WorldStore("remote.db") as remote_store:
    remote_store.set_fact(fact_b)
```

> **Note:** This creates `local.db` and `remote.db` in the current working
> directory. Delete them when you are done experimenting.

---

## Step 3 — Define Semantic Rules

`SemanticRule` expresses a logical implication: "if X then Y must hold".
The `RuleEngine` evaluates all rules after every merge.

```python
from agentcrdt import SemanticRule, RuleEngine

rule = SemanticRule(
    name="dead-king-voids-treaty",
    trigger_domain="life",
    trigger_attribute="alive",
    trigger_value=False,          # when king.alive == False …
    implies_domain="alliance",
    implies_entity_same=True,     # … the same entity's …
    implies_attribute="valid",
    implies_value=False,          # … alliance.valid must be False
)

engine = RuleEngine([rule])
```

---

## Step 4 — Merge Two World Views

`WorldMerger` merges a remote store into a local one using LWW CRDT semantics,
then optionally runs the rule engine to detect contradictions.

```python
from agentcrdt import WorldMerger

with WorldStore("local.db") as local, WorldStore("remote.db") as remote:
    result = WorldMerger(rule_engine=engine).merge(local, remote)

print(f"Merged {result.merged_count} facts")
print(f"Contradictions: {len(result.conflicts)}")
for event in result.conflicts:
    print(f"  [{event.rule}] agent_a={event.agent_a} agent_b={event.agent_b}")
```

Expected output:

```
Merged 1 facts
Contradictions: 1
  [dead-king-voids-treaty] agent_a=agent-A agent_b=agent-B
```

---

## Full Example

```python
import tempfile, os
from agentcrdt import WorldFact, WorldStore, WorldMerger, SemanticRule, RuleEngine

with tempfile.TemporaryDirectory() as tmp:
    local_path  = os.path.join(tmp, "local.db")
    remote_path = os.path.join(tmp, "remote.db")

    fact_a = WorldFact(domain="life",     entity="king", attribute="alive",
                       value=False, version=1, agent_id="agent-A")
    fact_b = WorldFact(domain="alliance", entity="king", attribute="valid",
                       value=True,  version=1, agent_id="agent-B")

    rule = SemanticRule(
        name="dead-king-voids-treaty",
        trigger_domain="life", trigger_attribute="alive", trigger_value=False,
        implies_domain="alliance", implies_entity_same=True,
        implies_attribute="valid", implies_value=False,
    )

    with WorldStore(local_path) as local, WorldStore(remote_path) as remote:
        local.set_fact(fact_a)
        remote.set_fact(fact_b)
        result = WorldMerger(rule_engine=RuleEngine([rule])).merge(local, remote)

    print(result.conflicts)
    # [ContradictionEvent(rule='dead-king-voids-treaty', ...)]
```

---

## Next Steps

- **CLI**: `agentcrdt --help` — set, get, merge, and inspect facts from the shell.
- **REST API**: see [REST Server](../README.md#rest-server) for FastAPI endpoints.
- **MCP / Claude Desktop**: see [MCP Integration](../README.md#mcp--claude-desktop-integration).
- **Python API reference**: `pydoc agentcrdt` or the inline docstrings in `src/agentcrdt/`.
