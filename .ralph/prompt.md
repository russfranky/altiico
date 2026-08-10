# LOOP — VRM mapping (ralph iteration prompt)

You continue an autonomous strategy to map existing VRMs and drive collections
toward hubzz-ingress readiness. Read STATE.md first. Level = L1 report-only.

Each iteration:
1. Read STATE.md and items.json. Pick the highest-value `todo` item whose
   `depends_on` are all `done` and that is not `blocked`.
2. Do exactly that one item. Prefer the existing scripts:
   - scripts/loop_iterate.sh        (deterministic map refresh: reachability + discovery + readiness + build)
   - scripts/check_vrm_reachable.py (re-validate VRM URLs)
   - scripts/discover_vrm_urls.py   (on-chain tokenURI -> metadata -> VRM pointer -> validate)
   - scripts/score_readiness.py     (recompute hubzz readiness)
   - scripts/build_catalog.py       (regenerate static/data for the UI)
3. Verify with evidence (query the DB / run the script). Never claim done without it.
4. Update the item status (done | blocked | todo) and append one line to
   loop-run-log.md. Update STATE.md "Current state" if the numbers changed.
5. Commit the refreshed map. Do NOT deploy or onboard — those are human gates.

Rules (L1):
- NEVER onboard a set into hubzz. NEVER add a brand-new collection without a
  ruling — propose it as a `blocked` item with reason and stop.
- Respect the token cap in loop-budget.md. If near the cap, stop and report.
- If an item needs a human decision, set it `blocked` with a clear `reason` and
  move on — do not guess.
- One item per iteration. Small, verifiable steps.
