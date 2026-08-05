# Real-world cases driving agentcrdt

Mined from farm lessons (Foundry / eagle-eyes queue) and public multi-agent
research (Track B).

## Case CONST-AS-STATE (farm) — CRITICAL

**Source:** eagle-eyes `REAL_WORK_QUEUE` P2; CLOSED_LOOP anti-ornament note:
*Do not cache code constants as world state (Foundry POLYMATTER_RECIPE class)*.

**What failed:**

Agents and pipelines stored **immutable recipe / config / code constants**
(e.g. `POLYMATTER_RECIPE`) in a multi-writer CRDT:

1. Multiple writers “merged” the same constant with LWW semantics.
2. Conflicts looked like world-state races instead of **policy errors**.
3. Downstream consumers treated the latest LWW constant as “current world”
   truth — wrong class of data for CRDT world state.

**Public twins:**

| Case | Mapping |
|------|---------|
| FedCritic-MIMO (arXiv 2608.03852) | Shared multi-agent state must be real coordination state |
| History Matters meta-policy (arXiv 2608.03833) | Heterogeneous agents + policy, not static recipe LWW |
| Multi-agent planning diagnosis (arXiv 2608.03735) | Shared plan state ≠ hardcoded templates |

**Product fix in this repo:**

| Control | API |
|---------|-----|
| Domain classifier | `is_constant_domain(domain)` |
| Default bans | `recipe`, `polymatter_recipe`, `config`, `constant`, `code`, … |
| Single write gate | `refuse_constant_write(fact)` / `set_fact_if_mutable(store, fact)` |
| Store gate | `gate_world_state(store)` — empty FAIL_LOUD; constant-only FAIL |
| Raise forms | `assert_world_state_ok`, `assert_mutable_write` |

**Tests:** `tests/test_const_as_state.py`

**Non-Ornament:** Call `set_fact_if_mutable` (or `refuse_constant_write` before
`set_fact`) and `gate_world_state` before merge/consume. Recipes belong in
versioned config files, not CRDT world stores.

---

## Related queue IDs

- **CONST-AS-STATE** — this case (P2)
- **NORM-ENFORCE** (normsync) — unattended action without norm
- **POLICY-ARBITRATION** (rulegraph) — COI / endorse rules
