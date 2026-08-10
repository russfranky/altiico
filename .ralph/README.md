# VRM mapping loop (.ralph)

Ongoing, L1 report-only strategy to map existing VRMs and surface hubzz-ready
sets. See STATE.md for intent + criteria, items.json for the backlog.

## Run one iteration (deterministic map refresh — no LLM, safe)
    ./scripts/loop_iterate.sh

## Agent iteration (judgment items: new sources, re-hosting, rulings)
Feed prompt.md to an agent (ralph runner). It picks one item, does it,
verifies, logs, commits. Human-gated on new collections + hubzz ingress.

## Files
- STATE.md          intent, criteria, current state, strategy
- prompt.md         the per-iteration instruction
- items.json        backlog (todo/blocked/done + depends_on)
- loop.md           iteration counter / last_promise
- loop-budget.md    token caps
- loop-run-log.md   evidence trail (appended each run)
