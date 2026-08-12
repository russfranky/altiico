const METADATA_URL = "https://allstarz.world/api/metadata/886.json";
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

function pickFields(metadata) {
  return {
    name: metadata?.name ?? null,
    vrm_url: metadata?.vrm_url ?? null,
    vrm: metadata?.vrm ?? null,
    asset: metadata?.asset ?? null,
    animation_url: metadata?.animation_url ?? null,
    external_url: metadata?.external_url ?? null,
    files: metadata?.files ?? null,
    keys: Object.keys(metadata || {}).sort(),
  };
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
      return jsonResponse({
        ok: false,
        stage: "metadata",
        elapsedMs: Date.now() - startedAt,
        httpStatus: response.status,
      }, 502);
    }
    const metadata = await response.json();
    return jsonResponse({
      ok: true,
      stage: "metadata",
      metadataUrl: METADATA_URL,
      elapsedMs: Date.now() - startedAt,
      ...pickFields(metadata),
    });
  } catch (error) {
    return jsonResponse({
      ok: false,
      stage: "exception",
      elapsedMs: Date.now() - startedAt,
      error: `${error?.name || "Error"}: ${error?.message || error}`,
    });
  }
}
