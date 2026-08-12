const PAGE_URL = "https://www.lucii.io";
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

function extractInterestingLinks(html) {
  const matches = [...html.matchAll(/(?:href|src)=["']([^"']+)["']/gi)].map((match) => match[1]);
  return [...new Set(matches)].filter((value) => /vrm|meepl|avatar|model|download|asset/i.test(value)).slice(0, 100);
}

export async function GET() {
  const startedAt = Date.now();
  try {
    const response = await fetch(PAGE_URL, {
      headers: {
        accept: "text/html,*/*",
        "user-agent": "vrm-catalog/1.0",
      },
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    const html = await response.text();
    return jsonResponse({
      ok: response.ok,
      elapsedMs: Date.now() - startedAt,
      httpStatus: response.status,
      finalUrl: response.url,
      pageBytes: html.length,
      containsMeeple: /meepl/i.test(html),
      containsVrm: /vrm/i.test(html),
      links: extractInterestingLinks(html),
    }, response.ok ? 200 : 502);
  } catch (error) {
    return jsonResponse({
      ok: false,
      elapsedMs: Date.now() - startedAt,
      error: `${error?.name || "Error"}: ${error?.message || error}`,
    });
  }
}
