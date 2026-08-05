"""Closed-loop gates for agentcrdt (CONST-AS-STATE / Non-Ornament).

Who reads the output?
  Multi-agent merger consumers, CI, eagle-eyes — anything that must refuse
  caching *code constants* (recipes, fixed configs) as CRDT world state.

What outcome changes?
  Constant-only domains are rejected at write and at gate time (FAIL / FAIL_LOUD).
  Empty stores FAIL_LOUD. Mutable world facts can merge and PASS.

Farm case CONST-AS-STATE:
  POLYMATTER_RECIPE (and similar) was treated as multi-writer world state and
  LWW-merged across agents — constants are not agent-mutable reality. The CRDT
  must refuse constant-only domains so conflicts surface as policy errors, not
  silent last-write-wins of recipes.

Public map (Track B): multi-agent coordination failures (FedCritic, History
Matters, multi-agent planning) — shared state must be *world* state, not code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from agentcrdt.fact import WorldFact
from agentcrdt.store import WorldStore

# Domains that are code/config constants — never CRDT world state.
DEFAULT_CONSTANT_DOMAINS: frozenset[str] = frozenset(
    {
        "constant",
        "constants",
        "recipe",
        "recipes",
        "polymatter_recipe",
        "polymatter",
        "code",
        "config",
        "configuration",
        "static",
        "immutable",
        "template",
        "hardcoded",
        "literal",
    }
)

# Domains expected for mutable multi-agent world state (documentation / hints).
DEFAULT_MUTABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "life",
        "alliance",
        "possession",
        "knowledge",
        "location",
        "status",
        "inventory",
        "world",
        "belief",
        "claim",
    }
)


class ClosedLoopError(ValueError):
    """Raised when the gate refuses empty, constant-only, or unusable state."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of a closed-loop read of an agentcrdt world store.

    Attributes:
        ok: True only when the pipeline may continue (PASS).
        verdict: ``PASS``, ``FAIL``, or ``FAIL_LOUD``.
        reason: Always non-empty explanation.
        exit_code: 0 PASS, 1 FAIL (policy), 2 FAIL_LOUD (empty/unusable).
        fact_count: Facts examined.
        mutable_count: Facts in non-constant domains.
        constant_count: Facts in constant-only domains.
        constant_domains: Distinct constant domains seen.
        refused_writes: Count of writes refused (when gating a write batch).
    """

    ok: bool
    verdict: str
    reason: str
    exit_code: int
    fact_count: int = 0
    mutable_count: int = 0
    constant_count: int = 0
    constant_domains: tuple[str, ...] = ()
    refused_writes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "fact_count": self.fact_count,
            "mutable_count": self.mutable_count,
            "constant_count": self.constant_count,
            "constant_domains": list(self.constant_domains),
            "refused_writes": self.refused_writes,
        }


def _canonical_domain(domain: str) -> str:
    return (domain or "").strip().lower().replace("-", "_").replace(" ", "_")


def is_constant_domain(
    domain: str,
    *,
    extra: Iterable[str] | None = None,
) -> bool:
    """True if *domain* is a constant/recipe/code domain (CONST-AS-STATE)."""
    d = _canonical_domain(domain)
    if not d:
        return True  # empty domain is never valid mutable world state
    banned = set(DEFAULT_CONSTANT_DOMAINS)
    if extra:
        banned |= {_canonical_domain(x) for x in extra}
    if d in banned:
        return True
    # Prefix match: recipe_v2, constant_xyz, polymatter_*
    for b in banned:
        if d.startswith(b + "_") or d.endswith("_" + b):
            return True
    return False


def is_mutable_fact(
    fact: WorldFact,
    *,
    extra_constant_domains: Iterable[str] | None = None,
) -> bool:
    """True when the fact is allowed as multi-writer world state."""
    return not is_constant_domain(fact.domain, extra=extra_constant_domains)


def _fail_loud(reason: str, **kwargs: Any) -> GateOutcome:
    return GateOutcome(
        ok=False,
        verdict="FAIL_LOUD",
        reason=reason,
        exit_code=2,
        **kwargs,
    )


def _fail(reason: str, **kwargs: Any) -> GateOutcome:
    return GateOutcome(
        ok=False,
        verdict="FAIL",
        reason=reason,
        exit_code=1,
        **kwargs,
    )


def classify_facts(
    facts: Iterable[WorldFact],
    *,
    extra_constant_domains: Iterable[str] | None = None,
) -> tuple[list[WorldFact], list[WorldFact]]:
    """Split facts into (mutable, constant)."""
    mutable: list[WorldFact] = []
    constant: list[WorldFact] = []
    for f in facts:
        if is_mutable_fact(f, extra_constant_domains=extra_constant_domains):
            mutable.append(f)
        else:
            constant.append(f)
    return mutable, constant


def gate_world_state(
    store: WorldStore | list[WorldFact],
    *,
    extra_constant_domains: Iterable[str] | None = None,
    allow_mixed: bool = False,
    require_mutable: bool = True,
) -> GateOutcome:
    """Gate a world store / fact list for CONST-AS-STATE discipline.

    * Empty → ``FAIL_LOUD`` (exit 2).
    * Only constant domains → ``FAIL`` (exit 1) — refuse constant-only CRDT.
    * Constants mixed with mutable → ``FAIL`` unless ``allow_mixed=True``.
    * Mutable present (and no banned constants if not allow_mixed) → ``PASS``.

    Args:
        store: :class:`WorldStore` or list of :class:`WorldFact`.
        extra_constant_domains: Additional domain names to treat as constants.
        allow_mixed: If True, constant facts are counted but do not fail when
            mutable facts also exist (still refuse constant-only).
        require_mutable: If True, at least one mutable fact is required.
    """
    if isinstance(store, WorldStore):
        facts = store.list_facts()
    else:
        facts = list(store)

    if len(facts) == 0:
        return _fail_loud(
            "empty world store — no load-bearing mutable state "
            "(CONST-AS-STATE: constant-only or empty is ornament)"
        )

    mutable, constant = classify_facts(facts, extra_constant_domains=extra_constant_domains)
    const_domains = tuple(sorted({_canonical_domain(f.domain) for f in constant}))

    if require_mutable and len(mutable) == 0:
        return _fail(
            f"CONST-AS-STATE: constant-only domains {list(const_domains)} — "
            f"refuse CRDT world state for recipes/code constants "
            f"(POLYMATTER_RECIPE class)",
            fact_count=len(facts),
            mutable_count=0,
            constant_count=len(constant),
            constant_domains=const_domains,
        )

    if constant and not allow_mixed:
        return _fail(
            f"CONST-AS-STATE: store mixes constant domains {list(const_domains)} "
            f"with mutable state — strip constants before merge",
            fact_count=len(facts),
            mutable_count=len(mutable),
            constant_count=len(constant),
            constant_domains=const_domains,
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"world state ok: mutable={len(mutable)} constant={len(constant)} "
            f"allow_mixed={allow_mixed}"
        ),
        exit_code=0,
        fact_count=len(facts),
        mutable_count=len(mutable),
        constant_count=len(constant),
        constant_domains=const_domains,
    )


def refuse_constant_write(
    fact: WorldFact,
    *,
    extra_constant_domains: Iterable[str] | None = None,
) -> GateOutcome:
    """Gate a single write: constant domains FAIL (do not set_fact).

    Returns PASS only for mutable-domain facts.
    """
    if not fact.domain or not str(fact.domain).strip():
        return _fail_loud(
            "empty domain — refuse write",
            fact_count=1,
            constant_count=1,
        )
    if is_constant_domain(fact.domain, extra=extra_constant_domains):
        d = _canonical_domain(fact.domain)
        return _fail(
            f"CONST-AS-STATE: refuse write to constant domain {d!r} "
            f"(entity={fact.entity!r} attr={fact.attribute!r}) — "
            f"not multi-writer world state",
            fact_count=1,
            mutable_count=0,
            constant_count=1,
            constant_domains=(d,),
            refused_writes=1,
        )
    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"mutable domain {fact.domain!r} allowed",
        exit_code=0,
        fact_count=1,
        mutable_count=1,
        constant_count=0,
    )


def set_fact_if_mutable(
    store: WorldStore,
    fact: WorldFact,
    *,
    extra_constant_domains: Iterable[str] | None = None,
) -> GateOutcome:
    """Write *fact* only if domain is mutable; otherwise refuse (CONST-AS-STATE)."""
    outcome = refuse_constant_write(fact, extra_constant_domains=extra_constant_domains)
    if not outcome.ok:
        return outcome
    store.set_fact(fact)
    return outcome


def assert_world_state_ok(
    store: WorldStore | list[WorldFact],
    **kwargs: Any,
) -> GateOutcome:
    """Gate and raise :class:`ClosedLoopError` unless outcome is ok."""
    outcome = gate_world_state(store, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def assert_mutable_write(
    fact: WorldFact,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` if *fact* is a constant-domain write."""
    outcome = refuse_constant_write(fact, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
