import { createHash } from "node:crypto";

const METADATA_URL = "https://m.cyberbrokers.com/mainnet/mech/419";
const DIRECT_VRM_URL = "https://m.cyberbrokers.com/eth/mech/419/files/mech_1k.0.vrm";
const MAX_BYTES = 64 * 1024 * 1024;
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

function validateGlb(buffer) {
  if (buffer.length < 20) return { validGlb: false, reason: "header_too_short" };
  if (buffer.toString("ascii", 0, 4) !== "glTF") return { validGlb: false, reason: "invalid_glb_magic" };

  const version = buffer.readUInt32LE(4);
  const declaredLength = buffer.readUInt32LE(8);
  const jsonChunkLength = buffer.readUInt32LE(12);
  const jsonChunkType = buffer.readUInt32LE(16);
  const jsonEnd = 20 + jsonChunkLength;
  if (version !== 2) return { validGlb: false, reason: "unsupported_glb_version", version };
  if (jsonChunkType !== 0x4e4f534a || jsonEnd > buffer.length) {
    return { validGlb: false, reason: "invalid_json_chunk", version, declaredLength };
  }

  try {
    const jsonText = buffer.subarray(20, jsonEnd).toString("utf8").replace(/[\u0000\u0020]+$/g, "");
    const document = JSON.parse(jsonText);
    const extensions = document?.extensions || {};
    const vrmSpec = extensions.VRMC_vrm ? "1.0" : extensions.VRM ? "0.x" : null;
    return { validGlb: true, version, declaredLength, jsonChunkLength, vrmSpec };
  } catch (error) {
    return { validGlb: false, reason: "json_parse_error", version, declaredLength, error: String(error) };
  }
}

async function boundedFetch(url, headers) {
  const startedAt = Date.now();
  try {
    const response = await fetch(url, {
      headers,
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    return { response, elapsedMs: Date.now() - startedAt };
  } catch (error) {
    return {
      response: null,
      elapsedMs: Date.now() - startedAt,
      error: `${error?.name || "Error"}: ${error?.message || error}`,
    };
  }
}

async function probeMetadata() {
  const attempt = await boundedFetch(METADATA_URL, {
    accept: "application/json",
    "user-agent": "vrm-catalog/1.0",
  });
  if (!attempt.response) return { ok: false, elapsedMs: attempt.elapsedMs, error: attempt.error };
  const result = { ok: attempt.response.ok, elapsedMs: attempt.elapsedMs, httpStatus: attempt.response.status };
  if (!attempt.response.ok) return result;
  try {
    const metadata = await attempt.response.json();
    return {
      ...result,
      metadataKeys: Object.keys(metadata || {}).sort(),
      vrmUrl: typeof metadata?.vrm_url === "string" ? metadata.vrm_url.trim() : null,
    };
  } catch (error) {
    return { ...result, ok: false, error: `json: ${error?.message || error}` };
  }
}

async function probeBinary() {
  const attempt = await boundedFetch(DIRECT_VRM_URL, {
    accept: "model/gltf-binary, application/octet-stream, */*",
    range: "bytes=0-65535",
    "user-agent": "vrm-catalog/1.0",
  });
  if (!attempt.response) return { ok: false, elapsedMs: attempt.elapsedMs, error: attempt.error };

  const contentLength = Number(attempt.response.headers.get("content-length") || "0");
  const base = {
    ok: attempt.response.ok,
    elapsedMs: attempt.elapsedMs,
    httpStatus: attempt.response.status,
    contentType: attempt.response.headers.get("content-type"),
    contentLength: contentLength || null,
    contentRange: attempt.response.headers.get("content-range"),
  };
  if (!attempt.response.ok) return base;
  if (contentLength > MAX_BYTES) return { ...base, ok: false, reason: "binary_too_large" };

  const buffer = Buffer.from(await attempt.response.arrayBuffer());
  const validation = validateGlb(buffer);
  return {
    ...base,
    receivedBytes: buffer.length,
    prefixSha256: createHash("sha256").update(buffer).digest("hex"),
    ...validation,
    ok: validation.validGlb && Boolean(validation.vrmSpec),
  };
}

export async function GET() {
  const [metadata, binary] = await Promise.all([probeMetadata(), probeBinary()]);
  return jsonResponse({
    target: "CyberBrokers Genesis Mech #419",
    metadataUrl: METADATA_URL,
    directVrmUrl: DIRECT_VRM_URL,
    timeoutMs: FETCH_TIMEOUT_MS,
    metadata,
    binary,
  });
}
