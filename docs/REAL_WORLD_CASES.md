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

---

## Case COVERT-COLLUSION — population steganalysis (arXiv 2608.02698)

**Source:** Track B research (`20260809T121239Z`) —
[Steganalysis of Adaptive Covert Collusion in Tool-Using Agent Populations](https://arxiv.org/abs/2608.02698).

**What fails:**

1. Multiple agents quietly coordinate while each trace looks well-behaved.
2. Single-agent safeguards miss **shared rare payloads**, **synchronized
   tool timing**, and **side-channel codes**.
3. MAST-MULTI only sees value divergence — not black-box behavioural collusion.

**Product in this repo:**

| Control | API |
|---------|-----|
| Event type | `AgentTraceEvent` |
| Detector | `detect_covert_collusion` → `CollusionReport` |
| Gate | `gate_covert_collusion(...)` |
| Raise form | `assert_no_covert_collusion` |

**Rules (load-bearing):**

- Empty / single-agent inventory → **FAIL_LOUD**
- Shared rare payload / sync timing / side-channel across agents → **FAIL**
- Independent diverse traces → **PASS**

**Tests:** `tests/test_covert_collusion.py`

**Non-Ornament:** Call `gate_covert_collusion` on multi-agent tool traces before
treating agents as independent. Pair with `gate_multi_agent` for CRDT values.

---

## Case COMM-ATTACK — multi-robot communication attacks (arXiv 2608.06830)

**Source:** Track B research (`20260810T081229Z`) —
[When Coordination Becomes a Threat: Communication Attacks in LLM-Controlled
Multi-Robot Systems](https://arxiv.org/abs/2608.06830v1).

**What fails:**

1. LLM planners coordinate multi-robot / multi-agent systems over message
   channels (DMAS, HMAS-1, HMAS-2).
2. **External Entry Point Attack** — untrusted external senders inject into the mesh.
3. **Privileged In-System Attack** — peers spoof planner/control plane messages.
4. Content-level reassignment ("ignore previous plan", "reassign target") slips
   past value-divergence and tool-collusion detectors.

**Product in this repo:**

| Control | API |
|---------|-----|
| Message type | `AgentMessage` |
| Detector | `analyze_comm_attacks` → `CommAttackReport` |
| Gate | `gate_comm_integrity(...)` |
| Raise form | `assert_comm_integrity` |
| Helpers | `detect_comm_injection_phrases`, role/channel classifiers |

**Rules (load-bearing):**

- claim coordinated + empty messages → **FAIL_LOUD**
- untrusted external entry → **FAIL**
- privileged channel/role without grant → **FAIL**
- coordination injection phrases → **FAIL**
- clean internal mesh → **PASS**

**Tests:** `tests/test_comm_attack.py`

**Non-Ornament:** Call `gate_comm_integrity` **before** executing multi-agent
coordination plans. Pair with `gate_multi_agent` (values) and
`gate_covert_collusion` (tool behaviour).

## Related queue IDs

- **CONST-AS-STATE** — constant domains (P2)
- **MAST-MULTI** — silent multi-agent divergence
- **COVERT-COLLUSION** — behavioural collusion
- **COMM-ATTACK** — message-layer integrity (this section)
- **NORM-ENFORCE** (normsync) — unattended action without norm
- **POLICY-ARBITRATION** (rulegraph) — COI / endorse rules
