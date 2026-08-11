"""Safe network transport, partial-GLB validation, and EVM tokenURI lookup."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from scripts.chain_registry import EVM_RPCS
from scripts.crawler.models import (
    CrawlPolicy,
    FetchResult,
    PermanentCrawlError,
    RetryableCrawlError,
    VrmValidation,
)
from scripts.crawler.store import CrawlStore
from scripts.crawler.uri import (
    canonicalize_uri,
    decode_data_json,
    transport_candidates,
)


GLB_MAGIC = 0x46546C67
GLB_VERSION_2 = 2
JSON_CHUNK_TYPE = 0x4E4F534A
UA = "vrm-catalog-recursive-crawler/1.0"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_CONTRACT_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

TOKEN_URI_SELECTOR = "0xc87b56dd"  # tokenURI(uint256)
ERC1155_URI_SELECTOR = "0x0e89341c"  # uri(uint256)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class NetworkLoader:
    """Bounded HTTP client that validates every destination and redirect."""

    def __init__(
        self,
        store: CrawlStore,
        policy: CrawlPolicy,
        *,
        resolver: Callable[..., Any] = socket.getaddrinfo,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self.store = store
        self.policy = policy
        self.resolver = resolver
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    # -------------------------------------------------------------- URL safety

    def assert_public_url(self, url: str) -> None:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            raise PermanentCrawlError(
                f"transport scheme is not HTTP(S): {parts.scheme}",
                error_class="unsupported_transport",
            )
        if parts.username or parts.password:
            raise PermanentCrawlError(
                "credential-bearing URLs are blocked", error_class="blocked_destination"
            )
        host = parts.hostname
        if not host:
            raise PermanentCrawlError("URL has no host", error_class="invalid_uri")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            infos = self.resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise RetryableCrawlError(
                f"DNS resolution failed for {host}: {exc}",
                error_class="dns_or_conn",
            ) from exc
        if not infos:
            raise RetryableCrawlError(
                f"DNS returned no addresses for {host}", error_class="dns_or_conn"
            )
        for info in infos:
            address = info[4][0]
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise PermanentCrawlError(
                    f"invalid resolved address for {host}: {address}",
                    error_class="blocked_destination",
                ) from exc
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise PermanentCrawlError(
                    f"blocked non-public destination {host} -> {ip}",
                    error_class="blocked_destination",
                )

    # ------------------------------------------------------------- raw request

    def _request_transport(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        max_bytes: int,
        allow_truncate: bool = False,
    ) -> FetchResult:
        current = url
        requests = 0
        request_headers = {"User-Agent": UA, "Accept-Encoding": "identity"}
        request_headers.update(headers or {})

        for _ in range(self.policy.max_redirects + 1):
            try:
                self.assert_public_url(current)
            except (RetryableCrawlError, PermanentCrawlError) as exc:
                exc.request_count += requests
                raise
            req = urllib.request.Request(
                current,
                data=body,
                headers=request_headers,
                method=method,
            )
            requests += 1
            try:
                with self.opener.open(req, timeout=self.policy.timeout) as response:  # noqa: S310
                    status = getattr(response, "status", None) or response.getcode()
                    if allow_truncate:
                        data = response.read(max_bytes)
                    else:
                        data = response.read(max_bytes + 1)
                        if len(data) > max_bytes:
                            raise PermanentCrawlError(
                                f"response exceeds {max_bytes} byte cap",
                                request_count=requests,
                                error_class="response_too_large",
                            )
                    return FetchResult(
                        canonical_url="",
                        final_url=current,
                        status="ok",
                        http_status=status,
                        content_type=response.headers.get("Content-Type", ""),
                        body=data,
                        etag=response.headers.get("ETag", ""),
                        last_modified=response.headers.get("Last-Modified", ""),
                        network_requests=requests,
                    )
            except urllib.error.HTTPError as exc:
                if exc.code in _REDIRECT_CODES:
                    location = exc.headers.get("Location")
                    if not location:
                        raise PermanentCrawlError(
                            f"redirect {exc.code} without Location",
                            request_count=requests,
                            error_class="invalid_redirect",
                        ) from exc
                    current = urllib.parse.urljoin(current, location)
                    continue
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else None
                    except ValueError:
                        delay = None
                    raise RetryableCrawlError(
                        f"HTTP 429 for {current}",
                        request_count=requests,
                        retry_after=delay,
                        error_class="rate_limited",
                    ) from exc
                if 500 <= exc.code < 600:
                    raise RetryableCrawlError(
                        f"HTTP {exc.code} for {current}",
                        request_count=requests,
                        error_class="server_error",
                    ) from exc
                raise PermanentCrawlError(
                    f"HTTP {exc.code} for {current}",
                    request_count=requests,
                    error_class=f"http_{exc.code}",
                ) from exc
            except (socket.timeout, TimeoutError) as exc:
                raise RetryableCrawlError(
                    f"timeout fetching {current}",
                    request_count=requests,
                    error_class="timeout",
                ) from exc
            except urllib.error.URLError as exc:
                reason = str(getattr(exc, "reason", exc)).lower()
                cls = "timeout" if "timed out" in reason else "dns_or_conn"
                raise RetryableCrawlError(
                    f"network error fetching {current}: {exc}",
                    request_count=requests,
                    error_class=cls,
                ) from exc
        raise PermanentCrawlError(
            f"too many redirects for {url}",
            request_count=requests,
            error_class="too_many_redirects",
        )

    def _try_transports(
        self,
        canonical_url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        max_bytes: int,
        preferred_transport: str | None = None,
        allow_truncate: bool = False,
    ) -> FetchResult:
        candidates = transport_candidates(canonical_url)
        if preferred_transport and preferred_transport in candidates:
            candidates.remove(preferred_transport)
            candidates.insert(0, preferred_transport)
        elif preferred_transport:
            candidates.insert(0, preferred_transport)

        total_requests = 0
        last_error: Exception | None = None
        for candidate in dict.fromkeys(candidates):
            try:
                result = self._request_transport(
                    candidate,
                    method=method,
                    headers=headers,
                    body=body,
                    max_bytes=max_bytes,
                    allow_truncate=allow_truncate,
                )
                return FetchResult(
                    canonical_url=canonical_url,
                    final_url=result.final_url,
                    status=result.status,
                    http_status=result.http_status,
                    content_type=result.content_type,
                    body=result.body,
                    etag=result.etag,
                    last_modified=result.last_modified,
                    network_requests=total_requests + result.network_requests,
                )
            except (RetryableCrawlError, PermanentCrawlError) as exc:
                total_requests += exc.request_count
                last_error = exc
                # Alternate IPFS/IPNS gateways are independent transports. Try
                # each before deciding that the underlying resource failed.
                continue
        if isinstance(last_error, RetryableCrawlError):
            raise RetryableCrawlError(
                str(last_error),
                request_count=total_requests,
                retry_after=last_error.retry_after,
                error_class=last_error.error_class,
            ) from last_error
        if isinstance(last_error, PermanentCrawlError):
            raise PermanentCrawlError(
                str(last_error),
                request_count=total_requests,
                error_class=last_error.error_class,
            ) from last_error
        raise PermanentCrawlError(
            f"no transport candidates for {canonical_url}",
            error_class="unsupported_transport",
        )

    # --------------------------------------------------------------- JSON load

    @staticmethod
    def _is_fresh(expires_at: str) -> bool:
        if expires_at.startswith("9999-"):
            return True
        try:
            parsed = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return False
        return parsed > datetime.now(timezone.utc)

    def load_json(self, value: str) -> tuple[Any, FetchResult, str]:
        canonical = canonicalize_uri(value)
        cached = self.store.get_resource(canonical)
        if (
            cached is not None
            and cached["status"] == "ok"
            and cached["body_text"] is not None
            and self._is_fresh(cached["expires_at"])
        ):
            body = cached["body_text"].encode("utf-8")
            try:
                document = json.loads(cached["body_text"])
            except json.JSONDecodeError:
                # A corrupt cache row should be replaced, not trusted forever.
                document = None
            if document is not None:
                return (
                    document,
                    FetchResult(
                        canonical_url=canonical,
                        final_url=cached["final_url"],
                        status="ok",
                        http_status=cached["http_status"],
                        content_type=cached["content_type"],
                        body=body,
                        etag=cached["etag"],
                        last_modified=cached["last_modified"],
                        network_requests=0,
                        from_cache=True,
                    ),
                    cached["body_sha256"],
                )

        if canonical.lower().startswith("data:"):
            body = decode_data_json(canonical, self.policy.max_document_bytes)
            result = FetchResult(
                canonical_url=canonical,
                final_url=canonical,
                status="ok",
                http_status=None,
                content_type="application/json",
                body=body,
                network_requests=0,
            )
        else:
            result = self._try_transports(
                canonical,
                headers={"Accept": "application/json, application/ld+json;q=0.9, */*;q=0.1"},
                max_bytes=self.policy.max_document_bytes,
            )
            body = result.body

        try:
            text = body.decode("utf-8-sig")
            document = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._cache_error(canonical, result.final_url, result.http_status, "invalid_json", str(exc))
            raise PermanentCrawlError(
                f"invalid JSON at {canonical}: {exc}",
                request_count=result.network_requests,
                error_class="invalid_json",
            ) from exc

        digest = hashlib.sha256(body).hexdigest()
        scheme = urllib.parse.urlsplit(canonical).scheme
        if scheme in {"ipfs", "ar", "data"}:
            expires = "9999-12-31T23:59:59Z"
        else:
            expires = (
                datetime.now(timezone.utc)
                + timedelta(seconds=self.policy.mutable_ttl_seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.store.put_resource(
            canonical,
            final_url=result.final_url,
            status="ok",
            http_status=result.http_status,
            content_type=result.content_type,
            body_sha256=digest,
            body_text=text,
            etag=result.etag,
            last_modified=result.last_modified,
            expires_at=expires,
        )
        return document, result, digest

    def _cache_error(
        self,
        canonical: str,
        final_url: str,
        http_status: int | None,
        error_class: str,
        message: str,
    ) -> None:
        expires = (
            datetime.now(timezone.utc)
            + timedelta(seconds=self.policy.negative_ttl_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.store.put_resource(
            canonical,
            final_url=final_url,
            status="error",
            http_status=http_status,
            content_type="",
            body_sha256="",
            body_text=None,
            expires_at=expires,
            error_class=error_class,
            error_message=message,
        )

    # -------------------------------------------------------------- range load

    def fetch_range(
        self,
        canonical_url: str,
        start: int,
        end: int,
        *,
        preferred_transport: str | None = None,
    ) -> FetchResult:
        if start < 0 or end < start:
            raise ValueError("invalid byte range")
        canonical = canonicalize_uri(canonical_url)
        # A 200 response may contain the entire file despite the Range header.
        # Read only through the requested end byte, then slice locally.
        result = self._try_transports(
            canonical,
            headers={"Range": f"bytes={start}-{end}", "Accept": "*/*"},
            max_bytes=end + 1,
            preferred_transport=preferred_transport,
            allow_truncate=True,
        )
        requested = end - start + 1
        if result.http_status == 200:
            if len(result.body) < end + 1:
                data = result.body[start:]
            else:
                data = result.body[start : end + 1]
        else:
            data = result.body[:requested]
        return FetchResult(
            canonical_url=canonical,
            final_url=result.final_url,
            status=result.status,
            http_status=result.http_status,
            content_type=result.content_type,
            body=data,
            etag=result.etag,
            last_modified=result.last_modified,
            network_requests=result.network_requests,
        )

    # --------------------------------------------------------------- VRM check

    def validate_vrm(self, value: str) -> VrmValidation:
        canonical = canonicalize_uri(value)
        requests = 0
        transport_url = transport_candidates(canonical)[0]

        def outcome(
            *,
            valid: bool,
            status: str,
            vrm_spec: str | None = None,
            raw_meta: dict[str, Any] | None = None,
            total_length: int | None = None,
            content_sha256: str = "",
            json_chunk_sha256: str = "",
            observed_length: int | None = None,
            error: str = "",
        ) -> VrmValidation:
            return VrmValidation(
                canonical_url=canonical,
                transport_url=transport_url,
                valid=valid,
                status=status,
                vrm_spec=vrm_spec,
                raw_meta=raw_meta,
                total_length=total_length,
                content_sha256=content_sha256,
                network_requests=requests,
                error=error,
                observed_length=observed_length,
                json_chunk_sha256=json_chunk_sha256,
                extractor_version="recursive-crawler-2",
            )

        try:
            header_result = self.fetch_range(canonical, 0, 19)
            requests += header_result.network_requests
            transport_url = header_result.final_url
            header = header_result.body
            if len(header) < 20:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    observed_length=len(header),
                    error=f"header too short: {len(header)}",
                )

            magic, version, total_length = struct.unpack("<III", header[:12])
            json_length, chunk_type = struct.unpack("<II", header[12:20])
            if magic != GLB_MAGIC or version != GLB_VERSION_2 or chunk_type != JSON_CHUNK_TYPE:
                return outcome(
                    valid=False,
                    status="not_glb",
                    total_length=total_length,
                    error="asset is not a GLB 2.0 file with a JSON first chunk",
                )
            if total_length < 20 or total_length > self.policy.max_vrm_bytes:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    total_length=total_length,
                    error=(
                        f"GLB declared length {total_length} exceeds "
                        f"{self.policy.max_vrm_bytes} byte policy"
                    ),
                )
            if json_length <= 0 or json_length > self.policy.max_vrm_json_bytes:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    total_length=total_length,
                    error=f"GLB JSON chunk length {json_length} exceeds policy",
                )
            if 20 + json_length > total_length:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    total_length=total_length,
                    error="GLB JSON chunk exceeds declared total length",
                )

            json_result = self.fetch_range(
                canonical,
                20,
                20 + json_length - 1,
                preferred_transport=header_result.final_url,
            )
            requests += json_result.network_requests
            transport_url = json_result.final_url
            json_bytes = json_result.body
            json_digest = hashlib.sha256(json_bytes).hexdigest()
            try:
                gltf = json.loads(json_bytes.decode("utf-8").rstrip("\x00 \t\r\n"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    total_length=total_length,
                    json_chunk_sha256=json_digest,
                    error=f"invalid GLB JSON: {exc}",
                )

            extensions = gltf.get("extensions") if isinstance(gltf, dict) else None
            if not isinstance(extensions, dict):
                return outcome(
                    valid=False,
                    status="valid_glb_not_vrm",
                    total_length=total_length,
                    json_chunk_sha256=json_digest,
                    error="GLB has no extensions object",
                )

            vrm_spec: str | None = None
            raw_meta: dict[str, Any] | None = None
            if isinstance(extensions.get("VRMC_vrm"), dict):
                block = extensions["VRMC_vrm"]
                vrm_spec = "1.0"
                raw_meta = block.get("meta") if isinstance(block.get("meta"), dict) else None
            elif isinstance(extensions.get("VRM"), dict):
                block = extensions["VRM"]
                vrm_spec = "0.x"
                raw_meta = block.get("meta") if isinstance(block.get("meta"), dict) else None
            else:
                return outcome(
                    valid=False,
                    status="valid_glb_not_vrm",
                    total_length=total_length,
                    json_chunk_sha256=json_digest,
                    error="GLB has no VRM or VRMC_vrm extension",
                )

            # A valid extension is only structural proof. Fetch the complete,
            # bounded binary so the catalog can identify exactly what Hubzz
            # later mirrors or optimizes.
            full_result = self.fetch_range(
                canonical,
                0,
                total_length - 1,
                preferred_transport=json_result.final_url,
            )
            requests += full_result.network_requests
            transport_url = full_result.final_url
            full_bytes = full_result.body
            observed_length = len(full_bytes)
            if observed_length != total_length:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    vrm_spec=vrm_spec,
                    raw_meta=raw_meta,
                    total_length=total_length,
                    observed_length=observed_length,
                    json_chunk_sha256=json_digest,
                    error=(
                        f"complete binary length {observed_length} does not match "
                        f"declared GLB length {total_length}"
                    ),
                )
            if full_bytes[:20] != header:
                return outcome(
                    valid=False,
                    status="invalid_glb",
                    vrm_spec=vrm_spec,
                    raw_meta=raw_meta,
                    total_length=total_length,
                    observed_length=observed_length,
                    json_chunk_sha256=json_digest,
                    error="complete binary header changed between range requests",
                )

            return outcome(
                valid=True,
                status="valid_vrm",
                vrm_spec=vrm_spec,
                raw_meta=raw_meta,
                total_length=total_length,
                observed_length=observed_length,
                content_sha256=hashlib.sha256(full_bytes).hexdigest(),
                json_chunk_sha256=json_digest,
            )
        except (RetryableCrawlError, PermanentCrawlError) as exc:
            exc.request_count += requests
            raise

    # --------------------------------------------------------------- JSON-RPC

    def post_json(self, url: str, payload: dict[str, Any]) -> tuple[Any, int]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        result = self._request_transport(
            url,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            body=body,
            max_bytes=self.policy.max_document_bytes,
        )
        try:
            return json.loads(result.body.decode("utf-8")), result.network_requests
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RetryableCrawlError(
                f"invalid JSON-RPC response from {url}",
                request_count=result.network_requests,
                error_class="invalid_rpc_response",
            ) from exc


class EvmTokenResolver:
    """Resolve ERC-721 tokenURI or ERC-1155 uri for an explicit token."""

    def __init__(self, loader: NetworkLoader) -> None:
        self.loader = loader

    @staticmethod
    def decode_abi_string(result_hex: str) -> str | None:
        if not isinstance(result_hex, str) or not result_hex.startswith("0x"):
            return None
        try:
            data = bytes.fromhex(result_hex[2:])
        except ValueError:
            return None
        if len(data) < 32:
            return data.rstrip(b"\x00").decode("utf-8", "replace").strip() or None
        offset = int.from_bytes(data[:32], "big")
        if offset + 32 <= len(data):
            length = int.from_bytes(data[offset : offset + 32], "big")
            start = offset + 32
            end = start + length
            if 0 <= length and end <= len(data):
                return data[start:end].decode("utf-8", "replace").rstrip("\x00").strip() or None
        # Non-standard contracts sometimes return a fixed bytes value.
        return data.rstrip(b"\x00").decode("utf-8", "replace").strip() or None

    @staticmethod
    def expand_erc1155_template(uri: str, token_id: int) -> str:
        replacement = f"{token_id:064x}"
        return re.sub(r"\{id\}", replacement, uri, flags=re.I)

    def resolve(self, chain: str, contract: str, token_id: int) -> tuple[str, int, str]:
        if chain not in EVM_RPCS:
            raise PermanentCrawlError(
                f"unsupported EVM chain: {chain}", error_class="unsupported_chain"
            )
        if not _CONTRACT_RE.fullmatch(contract):
            raise PermanentCrawlError("invalid EVM contract address", error_class="invalid_contract")
        if token_id < 0:
            raise PermanentCrawlError("token id must be non-negative", error_class="invalid_token_id")

        total_requests = 0
        last_retryable: RetryableCrawlError | None = None
        encoded_id = f"{token_id:064x}"
        for rpc in EVM_RPCS[chain]:
            for selector, standard in (
                (TOKEN_URI_SELECTOR, "erc721"),
                (ERC1155_URI_SELECTOR, "erc1155"),
            ):
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_call",
                    "params": [
                        {"to": contract, "data": selector + encoded_id},
                        "latest",
                    ],
                }
                try:
                    response, used = self.loader.post_json(rpc, payload)
                    total_requests += used
                except RetryableCrawlError as exc:
                    total_requests += exc.request_count
                    last_retryable = exc
                    break
                except PermanentCrawlError as exc:
                    total_requests += exc.request_count
                    continue
                if not isinstance(response, dict) or response.get("error"):
                    continue
                uri = self.decode_abi_string(response.get("result"))
                if not uri:
                    continue
                if standard == "erc1155":
                    uri = self.expand_erc1155_template(uri, token_id)
                return canonicalize_uri(uri), total_requests, standard

        if last_retryable is not None:
            raise RetryableCrawlError(
                f"all RPCs failed for {chain}:{contract}/{token_id}",
                request_count=total_requests,
                error_class=last_retryable.error_class,
            ) from last_retryable
        raise PermanentCrawlError(
            f"no token URI for {chain}:{contract}/{token_id}",
            request_count=total_requests,
            error_class="no_token_uri",
        )
