#!/usr/bin/env python3
"""Roll discovery evidence into collection columns consumed by build_catalog.py."""
import argparse
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent.parent
DB = BASE / "data" / "vrm_index.db"

COLUMNS = {
    "evidence_sources": "INTEGER DEFAULT 0",
    "evidence_last_seen": "TEXT",
    "evidence_corroborated": "INTEGER DEFAULT 0",
    "evidence_conflicts": "INTEGER DEFAULT 0",
    "evidence_tokens_sampled": "INTEGER DEFAULT 0",
    "evidence_uris_observed": "INTEGER DEFAULT 0",
    "evidence_model_signals": "INTEGER DEFAULT 0",
    "promotion_candidate_count": "INTEGER DEFAULT 0",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    existing = {r[1] for r in conn.execute("PRAGMA table_info(collections)")}
    for name, spec in COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {name} {spec}")

    conn.execute("""
      UPDATE collections SET
        evidence_sources = COALESCE((SELECT COUNT(*) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        evidence_last_seen = (SELECT MAX(observed_at) FROM discovery_evidence d WHERE d.collection_id=collections.id),
        evidence_corroborated = COALESCE((SELECT SUM(corroborated) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        evidence_conflicts = COALESCE((SELECT SUM(conflicts) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        evidence_tokens_sampled = COALESCE((SELECT SUM(tokens_sampled) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        evidence_uris_observed = COALESCE((SELECT SUM(uris_observed) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        evidence_model_signals = COALESCE((SELECT SUM(model_signals) FROM discovery_evidence d WHERE d.collection_id=collections.id),0),
        promotion_candidate_count = COALESCE((SELECT COUNT(*) FROM promotion_candidates p WHERE p.collection_id=collections.id AND p.promotion_state='ready_for_reconciliation'),0)
    """)
    conn.commit()
    summary = conn.execute("""
      SELECT COUNT(*) collections,
             SUM(CASE WHEN evidence_sources>0 THEN 1 ELSE 0 END) with_evidence,
             SUM(evidence_sources) sources,
             SUM(evidence_corroborated) corroborations,
             SUM(evidence_conflicts) conflicts,
             SUM(evidence_tokens_sampled) tokens,
             SUM(evidence_uris_observed) uris,
             SUM(evidence_model_signals) model_signals,
             SUM(promotion_candidate_count) candidates
      FROM collections
    """).fetchone()
    print(dict(zip(["collections","withEvidence","sources","corroborations","conflicts","tokensSampled","urisObserved","modelSignals","promotionCandidates"], summary)))
    conn.close()

if __name__ == "__main__":
    main()
