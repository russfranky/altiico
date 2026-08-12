import argparse
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from scripts.validate_documented_metadata import run

ROOT = Path(__file__).resolve().parent.parent


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        args = argparse.Namespace(
            registry=ROOT / "data" / "awesome_3d_avatar_collections.md",
            db=ROOT / "data" / "vrm_index.db",
            staging=ROOT / "static" / "data" / "hubzz-prealpha-staging.json",
            output=Path("/tmp/documented_metadata_validation.json"),
            max_targets=12,
            timeout=12.0,
            max_attempts=1,
            max_vrm_bytes=64 * 1024 * 1024,
        )
        try:
            payload = run(args)
            body = json.dumps(
                {
                    "ok": True,
                    "summary": payload.get("summary"),
                    "validatedHits": payload.get("validatedHits"),
                    "results": payload.get("results"),
                },
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
