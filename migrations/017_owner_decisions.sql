-- 017_owner_decisions.sql
--
-- Persist the owner's call on a collection so a declined set never resurfaces
-- as an onboarding candidate on the next loop iteration.
--
--   owner_decision         exclude | include | defer | NULL (undecided)
--   owner_decision_reason  why, for the audit trail
--
-- Source of truth is data/owner_decisions.yaml (reviewable, git-tracked);
-- scripts/apply_owner_decisions.py writes it here.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/017_owner_decisions.sql

ALTER TABLE collections ADD COLUMN owner_decision        TEXT;
ALTER TABLE collections ADD COLUMN owner_decision_reason TEXT;
