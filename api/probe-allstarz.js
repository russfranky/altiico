const METADATA_URL = "https://ipfs.io/ipfs/bafybeib6ii2hpiknnyyinrbywmulnjnznwxpwsubigneip54tzdus66xpi/117";
const FETCH_TIMEOUT_MS = 15_000;

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function collectCandidateStrings(value, path = "$", out = []) {
  if (typeof value === "string") {
    const text = value.trim();
    if (/vrm|\.glb(?:$|[?#])|\.vrm(?:$|[?#])|model|avatar|asset/i.test(path + " " + text)) {
      out.push({ path, value: text });
    }
    return out;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectCandidateStrings(item, `${path}[${index}]`, out));
    return out;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, item]) => collectCandidateStrings(item, `${path}.${key}`, out));
  }
  return out;
}

export async function GET() {
  const startedAt = Date.now();
  try {
    const response = await fetch(METADATA_URL, {
      headers: {
        accept: "application/json",
        "user-agent": "vrm-catalog/1.0",
      },
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) {
      return jsonResponse({ ok: false, elapsedMs: Date.now() - startedAt, httpStatus: response.status }, 502);
    }
    const metadata = await response.json();
    return jsonResponse({
      ok: true,
      elapsedMs: Date.now() - startedAt,
      metadataUrl: METADATA_URL,
      name: metadata?.name ?? null,
      keys: Object.keys(metadata || {}).sort(),
      candidates: collectCandidateStrings(metadata),
    });
  } catch (error) {
    return jsonResponse({
      ok: false,
      elapsedMs: Date.now() - startedAt,
      error: `${error?.name || "Error"}: ${error?.message || error}`,
    });
  }
}
