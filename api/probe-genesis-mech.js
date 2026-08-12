const METADATA_URL = "https://m.cyberbrokers.com/mainnet/mech/419";
const FETCH_TIMEOUT_MS = 10_000;

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
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
      return jsonResponse({ ok: false, httpStatus: response.status }, 502);
    }
    const metadata = await response.json();
    return jsonResponse({
      ok: true,
      elapsedMs: Date.now() - startedAt,
      tokenId: metadata?.tokenId ?? null,
      name: metadata?.name ?? null,
      vrm_url: metadata?.vrm_url ?? null,
      glb_url: metadata?.glb_url ?? null,
      files: metadata?.files ?? null,
    });
  } catch (error) {
    return jsonResponse(
      { ok: false, elapsedMs: Date.now() - startedAt, error: `${error?.name || "Error"}: ${error?.message || error}` },
      500,
    );
  }
}
