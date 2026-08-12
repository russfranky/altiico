#!/usr/bin/env python3
"""Persist 3dvault's curated avatar graph and match it to known catalog identity."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_REPORT = BASE / "data" / "3dvault_discovery.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_leads (
  lead_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  kind TEXT NOT NULL,
  label TEXT,
  url TEXT,
  image_url TEXT,
  collection_id TEXT,
  identity_state TEXT NOT NULL,
  observed_at TEXT,
  model_signals INTEGER DEFAULT 0,
  contract_signals INTEGER DEFAULT 0,
  opensea_signals INTEGER DEFAULT 0,
  details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_discovery_leads_source ON discovery_leads(source);
CREATE INDEX IF NOT EXISTS idx_discovery_leads_collection ON discovery_leads(collection_id);
"""


def norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def opensea_slugs(urls: list[str]) -> set[str]:
    out = set()
    for url in urls:
        m = re.search(r"opensea\.io/collection/([^/?#]+)", url, re.I)
        if m:
            out.add(m.group(1).lower())
    return out


def match_collection(conn: sqlite3.Connection, lead: dict) -> tuple[str | None, str]:
    page = lead.get("linkedPage") or {}
    contracts = [str(c).lower() for c in page.get("contracts") or []]
    for contract in contracts:
        row = conn.execute("SELECT collection_id FROM contracts WHERE lower(address)=? LIMIT 1", (contract,)).fetchone()
        if row:
            return row[0], "contract"
    for slug in opensea_slugs(page.get("openseaUrls") or []):
        row = conn.execute("SELECT id FROM collections WHERE lower(opensea_slug)=? LIMIT 1", (slug,)).fetchone()
        if row:
            return row[0], "opensea_slug"
    label = norm(lead.get("label"))
    if label:
        for cid, name in conn.execute("SELECT id,name FROM collections"):
            if norm(name) == label:
                return cid, "name_exact_normalized"
    host = urlparse(lead.get("url") or "").netloc.lower().removeprefix("www.")
    if host:
        rows = conn.execute("SELECT id,project_url FROM collections WHERE project_url IS NOT NULL AND project_url<>''").fetchall()
        for cid, project in rows:
            if urlparse(project or "").netloc.lower().removeprefix("www.") == host:
                return cid, "project_host"
    return None, "unresolved"


def upsert_evidence(conn: sqlite3.Connection, collection_id: str, report: dict, lead: dict) -> None:
    # promotion-loop creates this table; create it here too so standalone sync is safe.
    conn.execute("""CREATE TABLE IF NOT EXISTS discovery_evidence (
      collection_id TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT, status TEXT,
      corroborated INTEGER DEFAULT 0, conflicts INTEGER DEFAULT 0, tokens_sampled INTEGER DEFAULT 0,
      uris_observed INTEGER DEFAULT 0, model_signals INTEGER DEFAULT 0, errors INTEGER DEFAULT 0,
      details_json TEXT, PRIMARY KEY(collection_id,source))""")
    page = lead.get("linkedPage") or {}
    models = len(page.get("modelUrls") or [])
    conn.execute("""INSERT INTO discovery_evidence
      (collection_id,source,observed_at,status,corroborated,conflicts,tokens_sampled,uris_observed,model_signals,errors,details_json)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(collection_id,source) DO UPDATE SET
        observed_at=excluded.observed_at,status=excluded.status,corroborated=excluded.corroborated,
        model_signals=excluded.model_signals,errors=excluded.errors,details_json=excluded.details_json""",
      (collection_id,"3dvault",report.get("generatedAt"),"curated_partner",1,0,0,0,models,1 if page.get("error") else 0,
       json.dumps({"leadId":lead.get("leadId"),"label":lead.get("label"),"url":lead.get("url"),"imageUrl":lead.get("imageUrl"),"identityRole":"curated relationship lead"},separators=(",",":"))))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    conn = sqlite3.connect(args.db)
    conn.executescript(SCHEMA)
    matched = 0
    unresolved = 0
    for lead in report.get("avatarCollections") or []:
        cid, method = match_collection(conn, lead)
        page = lead.get("linkedPage") or {}
        state = f"matched:{method}" if cid else "unresolved"
        if cid:
            matched += 1
            upsert_evidence(conn, cid, report, lead)
        else:
            unresolved += 1
        conn.execute("""INSERT INTO discovery_leads
          (lead_id,source,kind,label,url,image_url,collection_id,identity_state,observed_at,model_signals,contract_signals,opensea_signals,details_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(lead_id) DO UPDATE SET
            label=excluded.label,url=excluded.url,image_url=excluded.image_url,collection_id=excluded.collection_id,
            identity_state=excluded.identity_state,observed_at=excluded.observed_at,model_signals=excluded.model_signals,
            contract_signals=excluded.contract_signals,opensea_signals=excluded.opensea_signals,details_json=excluded.details_json""",
          (lead.get("leadId"),"3dvault",lead.get("kind") or "avatar_collection",lead.get("label"),lead.get("url"),lead.get("imageUrl"),cid,state,
           report.get("generatedAt"),len(page.get("modelUrls") or []),len(page.get("contracts") or []),len(page.get("openseaUrls") or []),json.dumps(lead,separators=(",",":"))))
    # Store metaverse relationships too; they are useful recursive targets but not collection matches.
    for lead in report.get("metaversePlatforms") or []:
        conn.execute("""INSERT INTO discovery_leads
          (lead_id,source,kind,label,url,image_url,collection_id,identity_state,observed_at,model_signals,contract_signals,opensea_signals,details_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(lead_id) DO UPDATE SET label=excluded.label,url=excluded.url,image_url=excluded.image_url,observed_at=excluded.observed_at,details_json=excluded.details_json""",
          (lead.get("leadId"),"3dvault","metaverse_platform",lead.get("label"),lead.get("url"),lead.get("imageUrl"),None,"relationship_only",report.get("generatedAt"),0,0,0,json.dumps(lead,separators=(",",":"))))
    conn.commit()
    summary = {
        "source": "3dvault",
        "avatarLeads": len(report.get("avatarCollections") or []),
        "matchedCollections": matched,
        "unresolvedAvatarLeads": unresolved,
        "metaverseRelationships": len(report.get("metaversePlatforms") or []),
        "storedLeads": conn.execute("SELECT COUNT(*) FROM discovery_leads WHERE source='3dvault'").fetchone()[0],
    }
    conn.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
