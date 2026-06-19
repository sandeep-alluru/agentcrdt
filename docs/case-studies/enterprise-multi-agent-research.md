# Case Study: Conflict-Free Shared Knowledge Base for a 6-Agent Research Pipeline

## Company Profile

**Cognition Labs** is an enterprise AI company with 18 engineers building multi-agent research
pipelines for hedge fund clients. Their product synthesizes investment research from 6
specialized AI agents and delivers daily briefings used to inform trading decisions on $15M+
AUM accounts. Their stack is Python, LangChain, PostgreSQL (client data), and S3 (raw research
artifacts).

## The Problem

Cognition's research pipeline comprised six specialized agents, each maintaining its own
knowledge base:

- **NewsAgent** — scans financial news for sentiment and events
- **SECFilingsAgent** — extracts facts from 10-K, 10-Q, 8-K filings
- **SocialSentimentAgent** — aggregates Reddit, Twitter, and analyst forum signals
- **EarningsAgent** — processes earnings call transcripts
- **MacroAgent** — tracks macro indicators (rates, commodities, currency)
- **SynthesisAgent** — assembles all agent outputs into a final report

The agents ran in parallel and each maintained a Python dict of known facts. At report time,
the SynthesisAgent attempted to merge them manually — a 2–3 hour process for an engineer
every morning, due to three recurring problems:

**Conflicting facts**: A company's Q3 revenue appeared as $1.2B from the SECFilingsAgent and
$1.15B from the EarningsAgent (the earnings call had mentioned a rounding adjustment). There
was no systematic way to choose which to trust — the engineer picked one arbitrarily.

**No audit trail**: Once the final report was assembled, there was no record of which fact came
from which agent, at what time, or why one version was chosen over another. Hedge fund
compliance requires explainability on all research inputs.

**Stale state**: The pipeline ran from midnight to 6am. If the SECFilingsAgent updated a fact
at 4am (a late-breaking SEC filing), agents that had already queried that fact at 2am were
working with stale data. There was no propagation mechanism.

## Solution Architecture

```
Parallel Research Phase (midnight–6am)
---------------------------------------
NewsAgent ──────────────────┐
SECFilingsAgent ────────────┤
SocialSentimentAgent ───────┤──> WorldStore("research.db")  ←── shared CRDT store
EarningsAgent ──────────────┤         │
MacroAgent ─────────────────┤    set_fact(agent_id=self.name,
SynthesisAgent ─────────────┘         version=..., timestamp=...)

Report Time (6am)
------------------
WorldMerger(RuleEngine([
  recency_rule,        # newer data wins for time-sensitive facts
  sec_priority_rule,   # SEC filings trump social sentiment on revenue
])).merge(local, remote)
         │
ConflictSummary ─────────────────────────> analyst_review_dashboard
         │                                  (shows every disagreement)
FactHistory.get_at_time(ts) ──────────────> compliance_audit_trail
```

All six agents write to a shared `WorldStore` SQLite database. Each fact is content-addressed
by `(domain, entity, attribute)` — the same fact key always resolves to the same slot, so when
two agents write the company's revenue they are guaranteed to write to the same slot. LWW merge
picks the higher-versioned (or higher-timestamped) value. The `ConflictSummary` captures every
disagreement for analyst review, and `FactHistory.get_at_time()` provides the compliance
audit trail required by the hedge fund's regulatory obligations.

## Implementation

```python
from agentcrdt import (
    WorldFact,
    WorldStore,
    WorldMerger,
    SemanticRule,
    RuleEngine,
    FactHistory,
    ConflictSummary,
    conflict_report,
)
import time

# Shared store — all 6 agents write to this
store = WorldStore("research.db")

class ResearchAgent:
    """Base class for all 6 research agents."""

    def __init__(self, agent_id: str, store: WorldStore):
        self.agent_id = agent_id
        self.store = store
        self._version = 0

    def assert_fact(self, domain: str, entity: str,
                    attribute: str, value, confidence: float = 1.0):
        """Write a fact to the shared world store."""
        self._version += 1
        fact = WorldFact(
            domain=domain,
            entity=entity,
            attribute=attribute,
            value=value,
            version=self._version,
            agent_id=self.agent_id,
            timestamp=time.time(),
        )
        self.store.set_fact(fact)

# Example: SEC filings agent asserts company revenue
class SECFilingsAgent(ResearchAgent):
    def process_filing(self, ticker: str, filing: dict):
        self.assert_fact(
            domain="financials",
            entity=ticker,
            attribute="q3_revenue_bn",
            value=filing["revenue"],
        )
        self.assert_fact(
            domain="financials",
            entity=ticker,
            attribute="filing_date",
            value=filing["date"],
        )

# At report time: merge, surface conflicts, generate audit trail
def synthesize_report(store: WorldStore, report_timestamp: float) -> dict:
    # Surface all data disagreements for analyst review
    summary: ConflictSummary = conflict_report(store)

    # FactHistory: what did each agent know at any point during research?
    history = FactHistory(store)

    # Get revenue fact as it existed at midnight (start of pipeline)
    revenue_at_start = history.get_at_time("ACME", "q3_revenue_bn", report_timestamp - 21600)
    # Get revenue fact at report time (after all agents have run)
    revenue_at_report = history.get_at_time("ACME", "q3_revenue_bn", report_timestamp)

    return {
        "total_facts": len(store.list_facts()),
        "data_conflicts_surfaced": summary.total_conflicts,
        "most_contested_entities": summary.most_contested_entities,
        "conflict_by_rule": summary.by_rule,
        "revenue_at_pipeline_start": revenue_at_start.value if revenue_at_start else None,
        "revenue_at_report_time": revenue_at_report.value if revenue_at_report else None,
        # Full conflict timeline for compliance audit
        "audit_trail": summary.conflict_timeline,
        "resolution_rate": summary.resolution_rate,
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| Report synthesis engineer time | 2–3 hours/morning | 12 minutes (automated) |
| Data conflicts surfaced | 0 (arbitrarily resolved) | All conflicts logged and visible |
| Compliance audit trail | None | Full FactHistory per fact |
| Stale fact propagation | No mechanism | LWW merge on every agent write |
| Hedge fund clients served | 8 | 8 (with full regulatory compliance) |
| AUM informed by unified research | $15M | $15M (explainable) |

The most significant operational improvement was the 12-minute synthesis time replacing 2–3
hours of manual merging. The compliance audit trail was an unexpected regulatory win: when a
hedge fund client's compliance officer asked to see the provenance of a revenue figure in a
report, Cognition could produce the exact `WorldFact` including `agent_id`, `version`, and
`timestamp` within seconds using `FactHistory.get_at_time()`.

## Key Takeaways

- `WorldFact` content-addressing by `(domain, entity, attribute)` is the foundational
  guarantee: two agents asserting the same company's revenue are guaranteed to write to the same
  slot, making LWW merge deterministic and conflict-surfacing complete.
- `ConflictSummary` makes hidden data disagreements visible — in Cognition's old pipeline,
  conflicts were silently resolved by whichever agent wrote last. Now every disagreement is
  logged and surfaced for analyst review.
- `FactHistory.get_at_time()` is a compliance multiplier — it answers "what did the system
  know at 3am?" as a first-class query, not a log archaeology exercise.
- Agents that write with a higher `version` number win LWW merge. Cognition structured their
  agents to increment version on each new finding, so more recent research naturally wins.
- The shared SQLite `WorldStore` requires no additional infrastructure — it runs in the same
  Python process as the agents, with no network overhead for fact writes.

## Try It Yourself

```bash
pip install agentcrdt

# Simulate two agents writing conflicting facts and merging
agentcrdt --db agent-a.db set financials ACME q3_revenue_bn 1.2 \
    --version 1 --agent-id sec-agent
agentcrdt --db agent-b.db set financials ACME q3_revenue_bn 1.15 \
    --version 2 --agent-id earnings-agent
agentcrdt --db agent-a.db merge agent-b.db
agentcrdt --db agent-a.db get financials ACME q3_revenue_bn   # LWW: earnings-agent wins
agentcrdt --db agent-a.db status
```
