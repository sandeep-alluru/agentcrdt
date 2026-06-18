# agentcrdt — Session Anchor

**Research spec:** `../tech-research/14-Gaming/semantic-causal-crdt-for-agent-mutable-world-state/README.md`  
**One-liner:** CRDT where concurrent agent-world conflicts become observable events, not silent overwrites  
**Phase:** backlog  
**Stack:** Python, automerge-py (or py-crdt), NetworkX  

## Key decisions
<!-- fill in as decisions are made during build sessions -->

## Next step
Read the research spec, then design the semantic domain lattice and causal entailment DAG schema.

## MVP definition
- `pip install agentcrdt` works
- CRDT over semantic domain lattice (not just a standard LWW or OR-Set)
- Causal entailment DAG tracking logical dependencies between facts
- Conflict resolution emits observable world events (not silent merges)
- API: `agentcrdt.merge(a, b)`, `agentcrdt.observe_conflicts()`, `agentcrdt.subscribe(callback)`
- Demo: two concurrent agents write contradictory world facts → conflict surfaces as an event
- README with distributed systems context and example
