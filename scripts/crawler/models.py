"""Typed models shared by the recursive catalog crawler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CrawlPolicy:
    """Hard limits that keep a crawl finite and polite."""

    max_depth: int = 5
    request_budget: int = 2_000
    max_tasks: int = 20_000
    max_attempts: int = 3
    timeout: float = 25.0
    lease_seconds: int = 300
    max_document_bytes: int = 2_000_000
    max_vrm_json_bytes: int = 4_000_000
    max_links_per_document: int = 500
    max_redirects: int = 5
    mutable_ttl_seconds: int = 86_400
    negative_ttl_seconds: int = 3_600

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "request_budget": self.request_budget,
            "max_tasks": self.max_tasks,
            "max_attempts": self.max_attempts,
            "timeout": self.timeout,
            "lease_seconds": self.lease_seconds,
            "max_document_bytes": self.max_document_bytes,
            "max_vrm_json_bytes": self.max_vrm_json_bytes,
            "max_links_per_document": self.max_links_per_document,
            "max_redirects": self.max_redirects,
            "mutable_ttl_seconds": self.mutable_ttl_seconds,
            "negative_ttl_seconds": self.negative_ttl_seconds,
        }


@dataclass(frozen=True)
class Binding:
    collection_id: str = ""
    avatar_id: str = ""
    seed_source: str = ""


@dataclass(frozen=True)
class Task:
    id: int
    run_id: int
    kind: str
    canonical_key: str
    payload: dict[str, Any]
    depth: int
    priority: int
    state: str
    attempts: int


@dataclass(frozen=True)
class DiscoveredLink:
    kind: str
    url: str
    path: str
    relation: str
    reason: str
    confidence: float


@dataclass(frozen=True)
class FetchResult:
    canonical_url: str
    final_url: str
    status: str
    http_status: int | None
    content_type: str
    body: bytes
    etag: str = ""
    last_modified: str = ""
    network_requests: int = 0
    from_cache: bool = False


@dataclass(frozen=True)
class VrmValidation:
    canonical_url: str
    transport_url: str
    valid: bool
    status: str
    vrm_spec: str | None
    raw_meta: dict[str, Any] | None
    total_length: int | None
    content_sha256: str = ""
    network_requests: int = 0
    error: str = ""


class CrawlError(RuntimeError):
    """Base error carrying retry and request-accounting semantics."""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        request_count: int = 0,
        retry_after: float | None = None,
        error_class: str = "error",
    ) -> None:
        super().__init__(message)
        self.request_count = request_count
        self.retry_after = retry_after
        self.error_class = error_class


class RetryableCrawlError(CrawlError):
    retryable = True


class PermanentCrawlError(CrawlError):
    retryable = False


@dataclass
class RunSummary:
    run_id: int
    status: str
    requests_used: int
    task_counts: dict[str, int] = field(default_factory=dict)
    observations: int = 0
    materialized_collections: int = 0
