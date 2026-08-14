#!/usr/bin/env python3
"""Audit the catalog against the full collection research contract.

This is intentionally stricter than Hubzz ingress readiness. A collection only
passes when every required research dimension is resolved:

- banner and collection logo
- short description
- Discord and X account (or an evidenced explicit absence state)
- launch date
- VRM storage type
- complete VRM inventory / access path
- IP-rights information
- file-access ownership requirement
- project lifecycle status (active, dormant, sunset, etc.)

The script derives what it can from vrm_index.db and accepts manually researched
overrides from data/catalog_research.json. Missing/unknown values never silently
pass. Explicit negative states such as ``not_available`` or ``sunset`` require
evidence in the override file.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_OUTPUT = ROOT / "data" / "catalog_completeness_report.json"

SCHEMA = "vrm-catalog-completeness-v1"
REQUIRED_FIELDS = (
    "banner",
    "short_description",
    "discord",
    "x",
    "logo",
    "launch_date",
    "storage",
    "vrm_inventory",
    "ip_rights",
    "file_access",
    "project_status",
)
EXPLICIT_RESOLUTION_STATES = {
    "not_available",
    "not_applicable",
    "unrecoverable",
    "sunset",
    "holder_gated",
}
PROJECT_STATUSES = {"active", "dormant", "sunset"}
ACCESS_MODES = {"public", "holder_gated", "account_gated", "unavailable"}
KNOWN_STORAGE = {"ipfs", "arweave", "https", "onchain", "mixed", "holder_platform"}
URL_TEMPLATE_RE = re.compile(r"\{(?:token_id|id|token)\}|%d", re.I)
UNRESOLVED_TEMPLATE_RE = re.compile(r"\{[^}]+\}|%[a-z]", re.I)


def _has(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _evidence(override: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(override, dict):
        return []
    raw = override.get("evidence")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and any(_has(v) for v in item.values())]


def _override_ok(override: dict[str, Any] | None) -> bool:
    if not isinstance(override, dict):
        return False
    state = _lower(override.get("state"))
    return bool(state in EXPLICIT_RESOLUTION_STATES and _evidence(override))


def _field(
    *,
    ok: bool,
    value: Any = None,
    state: str = "present",
    source: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    detail: Any = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": bool(ok), "state": state}
    if value is not None:
        out["value"] = value
    if source:
        out["source"] = source
    if evidence:
        out["evidence"] = evidence
    if detail is not None:
        out["detail"] = detail
    return out


def _resolved_or_missing(
    value: Any,
    source: str,
    override: dict[str, Any] | None,
    *,
    validator=None,
) -> dict[str, Any]:
    if _has(value) and (validator is None or validator(value)):
        return _field(ok=True, value=value, source=source)
    if _override_ok(override):
        return _field(
            ok=True,
            value=override.get("value"),
            state=_lower(override.get("state")),
            source="catalog_research",
            evidence=_evidence(override),
            detail=override.get("note"),
        )
    return _field(ok=False, state="missing")


def short_description(value: Any, max_chars: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    text = re.sub(r"^[#>*\-\s]+", "", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars + 1]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary >= max_chars // 2:
        return cut[: boundary + 1].strip()
    boundary = cut.rfind(" ")
    if boundary < max_chars // 2:
        boundary = max_chars
    return cut[:boundary].rstrip(" ,;:-") + "…"


def x_url(username: Any) -> str:
    raw = str(username or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"https://x.com/{raw.lstrip('@')}"


def concrete_or_template_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw or any(ch.isspace() for ch in raw):
        return False
    if raw.startswith("ipfs://") or raw.startswith("ar://"):
        return bool(raw.split("://", 1)[1])
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def storage_for_urls(urls: list[str]) -> list[str]:
    providers: set[str] = set()
    for raw in urls:
        url = raw.strip().lower()
        if not url:
            continue
        if url.startswith("ipfs://") or "/ipfs/" in url:
            providers.add("ipfs")
        elif url.startswith("ar://") or "arweave.net/" in url:
            providers.add("arweave")
        elif url.startswith("data:") or url.startswith("ethereum:"):
            providers.add("onchain")
        elif url.startswith("http://") or url.startswith("https://"):
            providers.add("https")
    return sorted(providers)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def load_research(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "vrm-catalog-research-v1", "collections": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    collections = data.get("collections")
    if not isinstance(collections, dict):
        raise ValueError(f"{path}: collections must be an object")
    return data


def load_avatar_facts(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, "avatars"):
        return {}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(avatars)")}
    public_expr = "is_public" if "is_public" in cols else "NULL"
    rows = conn.execute(
        f"""
        SELECT collection_id,
               COUNT(*) AS total,
               SUM(CASE WHEN TRIM(COALESCE(model_file_url,''))<>'' THEN 1 ELSE 0 END) AS with_url,
               SUM(CASE WHEN {public_expr}=1 THEN 1 ELSE 0 END) AS public_rows,
               SUM(CASE WHEN {public_expr}=0 THEN 1 ELSE 0 END) AS nonpublic_rows
        FROM avatars
        GROUP BY collection_id
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = str(row[0])
        urls = [
            r[0]
            for r in conn.execute(
                """
                SELECT DISTINCT model_file_url
                FROM avatars
                WHERE collection_id=? AND TRIM(COALESCE(model_file_url,''))<>''
                ORDER BY model_file_url
                """,
                (cid,),
            ).fetchall()
        ]
        out[cid] = {
            "rows": int(row[1] or 0),
            "with_url": int(row[2] or 0),
            "public_rows": int(row[3] or 0),
            "nonpublic_rows": int(row[4] or 0),
            "urls": urls,
        }
    return out


def load_license_facts(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, "license_dimensions"):
        return {}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(license_dimensions)")}
    wanted = [
        "collection_id",
        "color",
        "confidence",
        "use_scope",
        "commercial_scope",
        "credit",
        "redistribute_original",
        "modify",
        "redistribute_modified",
        "reason_codes",
    ]
    present = [c for c in wanted if c in cols]
    if "collection_id" not in present:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute(f"SELECT {','.join(present)} FROM license_dimensions"):
        item = dict(zip(present, row))
        out[str(item["collection_id"])] = item
    return out


def _expected_count(row: dict[str, Any]) -> int | None:
    for key in ("avatar_count", "total_supply", "max_supply"):
        value = row.get(key)
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def _inventory_field(
    row: dict[str, Any],
    avatar: dict[str, Any],
    override: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    urls: list[str] = list(avatar.get("urls") or [])
    for key in ("vrm_url_https", "vrm_url_pattern"):
        raw = str(row.get(key) or "").strip()
        if raw and concrete_or_template_url(raw) and raw not in urls:
            urls.append(raw)

    expected = _expected_count(row)
    avatar_rows = int(avatar.get("rows") or 0)
    with_url = int(avatar.get("with_url") or 0)
    coverage = "unknown"
    if expected and avatar_rows == expected and with_url == avatar_rows and avatar_rows > 0:
        coverage = "complete"
    elif avatar_rows > 0 and with_url == avatar_rows and expected is None:
        coverage = "catalog_rows_complete"
    elif urls:
        coverage = "partial"

    if isinstance(override, dict):
        override_urls = override.get("urls")
        if isinstance(override_urls, list):
            for url in override_urls:
                if _has(url) and str(url) not in urls:
                    urls.append(str(url))
        override_coverage = _lower(override.get("coverage"))
        if override_coverage in {"complete", "catalog_rows_complete", "holder_gated", "unrecoverable"}:
            coverage = override_coverage
        if _override_ok(override) and coverage in {"holder_gated", "unrecoverable"}:
            return (
                _field(
                    ok=True,
                    state=_lower(override.get("state")),
                    source="catalog_research",
                    evidence=_evidence(override),
                    detail={
                        "coverage": coverage,
                        "known_urls": len(urls),
                        "expected": expected,
                        "access_url": override.get("access_url"),
                    },
                ),
                urls,
            )

    ok = coverage in {"complete", "catalog_rows_complete"}
    return (
        _field(
            ok=ok,
            state="present" if ok else coverage,
            value={"known_urls": len(urls), "expected": expected, "coverage": coverage},
            source="avatars+collection",
            detail={"avatar_rows": avatar_rows, "avatar_rows_with_url": with_url},
        ),
        urls,
    )


def _storage_field(
    urls: list[str], override: dict[str, Any] | None
) -> dict[str, Any]:
    providers = storage_for_urls(urls)
    if providers:
        value: str | list[str] = providers[0] if len(providers) == 1 else providers
        return _field(ok=True, value=value, source="vrm_urls")
    if isinstance(override, dict):
        value = _lower(override.get("value"))
        if value in KNOWN_STORAGE and _evidence(override):
            return _field(
                ok=True,
                value=value,
                state=_lower(override.get("state")) or "present",
                source="catalog_research",
                evidence=_evidence(override),
            )
        if _override_ok(override):
            return _field(
                ok=True,
                value=override.get("value"),
                state=_lower(override.get("state")),
                source="catalog_research",
                evidence=_evidence(override),
            )
    return _field(ok=False, state="unknown")


def _ip_rights_field(
    row: dict[str, Any],
    license_fact: dict[str, Any],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_license = str(row.get("vrm_license") or "").strip()
    lic_cat = _lower(row.get("license_category"))
    allowed_user = _lower(row.get("allowed_user"))
    redistribution = _lower(row.get("redistribution"))
    dim_color = _lower(license_fact.get("color"))
    confidence = _lower(license_fact.get("confidence"))

    known_raw = bool(
        raw_license
        and "unknown" not in raw_license.lower()
        and lic_cat not in {"", "unknown"}
        and allowed_user not in {"", "unknown"}
        and redistribution not in {"", "unknown"}
    )
    known_dims = bool(
        dim_color not in {"", "gray", "unknown"}
        and confidence not in {"", "unknown"}
        and any(
            _has(license_fact.get(key))
            for key in (
                "use_scope",
                "commercial_scope",
                "redistribute_original",
                "modify",
                "redistribute_modified",
            )
        )
    )
    if known_raw or known_dims:
        return _field(
            ok=True,
            value={
                "license": raw_license or None,
                "category": lic_cat or None,
                "allowed_user": allowed_user or None,
                "redistribution": redistribution or None,
                "dimensions": license_fact or None,
            },
            source="license_dimensions" if known_dims else "collections",
        )
    if _override_ok(override):
        return _field(
            ok=True,
            value=override.get("value"),
            state=_lower(override.get("state")),
            source="catalog_research",
            evidence=_evidence(override),
            detail=override.get("note"),
        )
    return _field(ok=False, state="unknown")


def _file_access_field(
    row: dict[str, Any],
    avatar: dict[str, Any],
    inventory: dict[str, Any],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    # Access is intentionally NOT inferred from license terms.
    if isinstance(override, dict):
        mode = _lower(override.get("mode") or override.get("value"))
        if mode in ACCESS_MODES and _evidence(override):
            return _field(
                ok=True,
                value=mode,
                state=_lower(override.get("state")) or "present",
                source="catalog_research",
                evidence=_evidence(override),
                detail={"access_url": override.get("access_url"), "note": override.get("note")},
            )
        if _override_ok(override):
            return _field(
                ok=True,
                value=override.get("value"),
                state=_lower(override.get("state")),
                source="catalog_research",
                evidence=_evidence(override),
            )

    # Strong public evidence: every catalog avatar row is explicitly public and
    # the inventory coverage is complete for those rows.
    avatar_rows = int(avatar.get("rows") or 0)
    public_rows = int(avatar.get("public_rows") or 0)
    inv_value = inventory.get("value") if isinstance(inventory, dict) else {}
    coverage = inv_value.get("coverage") if isinstance(inv_value, dict) else None
    if avatar_rows > 0 and public_rows == avatar_rows and coverage in {"complete", "catalog_rows_complete"}:
        return _field(ok=True, value="public", source="avatars.is_public")

    # A successful public network validation is useful evidence only for a
    # single/shared asset, not enough to declare a per-token collection public.
    expected = _expected_count(row)
    if (
        row.get("vrm_check_status") == "ok_vrm"
        and expected == 1
        and concrete_or_template_url(row.get("vrm_check_url") or row.get("vrm_url_https"))
    ):
        return _field(ok=True, value="public", source="vrm_reachability")
    return _field(ok=False, state="unknown")


def _project_status_field(override: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(override, dict):
        return _field(ok=False, state="unknown")
    value = _lower(override.get("value") or override.get("state"))
    if value in PROJECT_STATUSES and _evidence(override):
        return _field(
            ok=True,
            value=value,
            state=value,
            source="catalog_research",
            evidence=_evidence(override),
            detail=override.get("note"),
        )
    return _field(ok=False, state="unknown")


def evaluate_collection(
    row: dict[str, Any],
    avatar: dict[str, Any] | None = None,
    license_fact: dict[str, Any] | None = None,
    research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    avatar = avatar or {}
    license_fact = license_fact or {}
    research = research or {}

    fields: dict[str, dict[str, Any]] = {}
    fields["banner"] = _resolved_or_missing(
        row.get("banner_image_url"), "collections.banner_image_url", research.get("banner")
    )
    derived_short = research.get("short_description", {}).get("value") if isinstance(research.get("short_description"), dict) else None
    if not _has(derived_short):
        derived_short = short_description(row.get("curated_description") or row.get("description"))
    fields["short_description"] = _resolved_or_missing(
        derived_short, "derived:description", research.get("short_description"),
        validator=lambda v: len(str(v).strip()) >= 20,
    )
    fields["discord"] = _resolved_or_missing(
        row.get("discord_url"), "collections.discord_url", research.get("discord")
    )
    fields["x"] = _resolved_or_missing(
        x_url(row.get("twitter_username")), "collections.twitter_username", research.get("x")
    )
    fields["logo"] = _resolved_or_missing(
        row.get("image_url") or row.get("sample_nft_image"),
        "collections.image_url|sample_nft_image",
        research.get("logo"),
    )
    fields["launch_date"] = _resolved_or_missing(
        row.get("release_date"), "collections.release_date", research.get("launch_date")
    )

    inventory, urls = _inventory_field(row, avatar, research.get("vrm_inventory"))
    fields["vrm_inventory"] = inventory
    fields["storage"] = _storage_field(urls, research.get("storage"))
    fields["ip_rights"] = _ip_rights_field(row, license_fact, research.get("ip_rights"))
    fields["file_access"] = _file_access_field(
        row, avatar, inventory, research.get("file_access")
    )
    fields["project_status"] = _project_status_field(research.get("project_status"))

    missing = [name for name in REQUIRED_FIELDS if not fields[name]["ok"]]
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "tier": row.get("tier"),
        "complete": not missing,
        "missing": missing,
        "fields": fields,
    }


def run(
    db_path: Path,
    research_path: Path,
    output_path: Path | None = None,
    tiers: set[str] | None = None,
) -> dict[str, Any]:
    research = load_research(research_path)
    overrides = research.get("collections") or {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        avatar_facts = load_avatar_facts(conn)
        license_facts = load_license_facts(conn)
        rows = [dict(row) for row in conn.execute("SELECT * FROM collections ORDER BY name")]
    finally:
        conn.close()

    if tiers:
        rows = [row for row in rows if _lower(row.get("tier")).upper() in tiers]

    results = [
        evaluate_collection(
            row,
            avatar_facts.get(str(row.get("id"))) or {},
            license_facts.get(str(row.get("id"))) or {},
            overrides.get(str(row.get("id"))) or {},
        )
        for row in rows
    ]

    missing_counts = {
        field: sum(1 for item in results if field in item["missing"])
        for field in REQUIRED_FIELDS
    }
    complete = sum(1 for item in results if item["complete"])
    payload = {
        "schema": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "Every required collection research dimension must be concrete or explicitly "
            "resolved with evidence; IP rights and file-access gating are independent."
        ),
        "summary": {
            "collections": len(results),
            "complete": complete,
            "incomplete": len(results) - complete,
            "missingByField": missing_counts,
        },
        "collections": results,
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--tiers", default="A,B,C")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    tiers = {part.strip().upper() for part in args.tiers.split(",") if part.strip()}
    payload = run(args.db, args.research, args.output, tiers)
    print(json.dumps(payload["summary"], indent=2))
    if args.strict and payload["summary"]["incomplete"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
