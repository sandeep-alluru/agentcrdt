# Closed loop — `agentcrdt`

**Status:** reader wired (eagle-eyes / 2026-08-05) — **CONST-AS-STATE**  
**Owner loop:** Multi-agent only

## Load-bearing job

Semantic-causal CRDT merge for multi-writer agent state

## Who reads the output?

- Library: `gate_world_state` / `refuse_constant_write` / `set_fact_if_mutable`
- Merger consumers still read ContradictionEvents for *mutable* conflicts

## What outcome changes?

Conflict becomes observable event, not silent LWW of constants.
**CONST-AS-STATE:** writes to `recipe` / `polymatter_recipe` / `config` / … → FAIL;
constant-only store → FAIL; empty → FAIL_LOUD.

## When NOT to use (anti-ornament)

Do not cache code constants as world state (Foundry POLYMATTER_RECIPE class)

## Non-Ornament checklist

- [x] Reader implemented in library (`closed_loop.gate_world_state`)
- [x] Empty/wrong output fails loudly (exit 2 / 1)
- [x] Not exposed as free MCP that auto-accepts constant domains
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

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2
