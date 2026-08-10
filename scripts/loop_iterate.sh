#!/usr/bin/env bash
# One iteration of the VRM-mapping loop.
# L1 report-only: it MAPS (reachability, discovery), SCORES readiness, and
# commits the refreshed map. It NEVER onboards a set into hubzz — ingress stays
# a human gate. Safe to schedule.
set -uo pipefail
cd /Users/russ/src/local/superyeti || exit 1
PY=./venv/bin/python
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG=.ralph/loop-run-log.md
echo "== VRM-map iterate $TS =="
$PY scripts/check_vrm_reachable.py --tier A,B --now "$TS"        2>&1 | tail -2
$PY scripts/discover_vrm_urls.py   --tiers A,B,C --now "$TS"     2>&1 | tail -3
$PY scripts/sync_hubzz_status.py                                      2>&1 | tail -2
$PY scripts/apply_owner_decisions.py                                  2>&1 | tail -1
$PY scripts/score_readiness.py     --tiers A,B,C --now "$TS"     2>&1 | tail -4
$PY scripts/build_catalog.py                                    2>&1 | tail -1
READY=$(sqlite3 data/vrm_index.db "SELECT COUNT(*) FROM collections WHERE ready=1;")
OKVRM=$(sqlite3 data/vrm_index.db "SELECT COUNT(*) FROM collections WHERE vrm_check_status='ok_vrm';")
NOURL=$(sqlite3 data/vrm_index.db "SELECT COUNT(*) FROM collections WHERE vrm_check_status='no_url';")
echo "| $TS | $READY | $OKVRM | $NOURL |" >> "$LOG"
git add data/vrm_index.db static/ .ralph/loop-run-log.md 2>/dev/null
git commit -q -m "chore(loop): VRM map refresh — ready=$READY ok_vrm=$OKVRM no_url=$NOURL ($TS)" 2>/dev/null \
  && echo "committed map refresh" || echo "no changes this iteration"
echo "== done: ready=$READY  ok_vrm=$OKVRM  no_url=$NOURL =="
