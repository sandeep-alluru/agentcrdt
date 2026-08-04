# Closed loop — `agentcrdt`

**Status:** stub (eagle-eyes Phase 0 / 2026-08-04)  
**Owner loop:** Multi-agent only

## Load-bearing job

Semantic-causal CRDT merge for multi-writer agent state

## Who reads the output?

Merger consumers read ContradictionEvents

## What outcome changes?

Conflict becomes observable event, not silent LWW of constants

## When NOT to use (anti-ornament)

Do not cache code constants as world state (Foundry POLYMATTER_RECIPE class)

## Non-Ornament checklist

- [ ] Reader implemented in CI, gate, or eagle-eyes script
- [ ] Empty/wrong output fails loudly
- [ ] Not exposed as free MCP in product agents
- [ ] Linked gap IDs in mem0 when improving

## Related failures (farm memory)

- 2026-07-22 MCP buffet trim: write-only tools removed from Foundry framework
- D-FOGHORN: misuse of append-only fact log as current state
- Dual-path mem0: never rely on MCP-only for critical memory

## Daily rotation note

This file exists so pillar **C (closed loop)** can rise with real wiring over time. Prefer small daily commits that move a checkbox toward done.

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2
