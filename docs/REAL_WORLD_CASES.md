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

## Case MAST-MULTI — silent multi-agent value divergence (ICLR / AdaMAST)

**Source:** Track B research (`20260807T041224Z`) + matrix gap **MAST multi-agent
failures = no** until this ship:

| Source | Case |
|--------|------|
| HN / Substack | What ICLR 2026 Taught Us About Multi-Agent Failures |
| HN | AdaMAST adaptive failure taxonomies |
| HN | AgentPulse multi-agent failure detection |
| arXiv twins | FedCritic / History Matters (prior CONST-AS-STATE map) |

**What fails:**

1. Two agents write **different values** for the same
   `domain.entity.attribute` key.
2. LWW merge keeps the winner; **no** `ContradictionEvent` is recorded.
3. Downstream agents treat the LWW survivor as uncontested world truth.

**Product in this repo:**

| Control | API |
|---------|-----|
| Detector | `detect_silent_divergences(store)` → `ValueDivergence` list |
| Store gate | `gate_multi_agent(store)` — empty FAIL_LOUD; events/divergences FAIL |
| Merge gate | `gate_merge_result(result)` — conflict budget + empty merge |
| Raise form | `assert_multi_agent_ok(store)` |

**Rules (load-bearing):**

- Unresolved events > budget → **FAIL** (`human_required`)
- Silent multi-agent multi-value history without event → **FAIL**
- Single-agent versioning (same agent, new value) → not a divergence
- Event covering `fact_id` removes it from silent set (still counts as event)

**Tests:** `tests/test_multi_agent_mast.py` including e2e merge-then-gate.

**Non-Ornament:** After every multi-agent merge, call `gate_multi_agent` (and
ideally run a `RuleEngine` so conflicts become events). Silent LWW alone is
not a coordination protocol.

## Related queue IDs

- **CONST-AS-STATE** — this case (P2)
- **MAST-MULTI** — silent multi-agent divergence (this section)
- **NORM-ENFORCE** (normsync) — unattended action without norm
- **POLICY-ARBITRATION** (rulegraph) — COI / endorse rules
