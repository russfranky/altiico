import { createHash } from "node:crypto";

const VRM_URL = "https://m.cyberbrokers.com/eth/mech/419/files/mech_768.vrm";
const MAX_BYTES = 64 * 1024 * 1024;
const FETCH_TIMEOUT_MS = 90_000;

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

export async function GET() {
  const startedAt = Date.now();
  try {
    const response = await fetch(VRM_URL, {
      headers: {
        accept: "model/gltf-binary, application/octet-stream, */*",
        "user-agent": "vrm-catalog/1.0",
      },
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) {
      return jsonResponse({ ok: false, stage: "http", httpStatus: response.status, elapsedMs: Date.now() - startedAt }, 502);
    }

    const advertisedLength = Number(response.headers.get("content-length") || "0");
    if (advertisedLength && advertisedLength > MAX_BYTES) {
      return jsonResponse({ ok: false, stage: "size", advertisedLength, elapsedMs: Date.now() - startedAt }, 413);
    }

    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length > MAX_BYTES) {
      return jsonResponse({ ok: false, stage: "size", byteLength: buffer.length, elapsedMs: Date.now() - startedAt }, 413);
    }

    const validation = validateGlb(buffer);
    return jsonResponse({
      ok: validation.validGlb && Boolean(validation.vrmSpec),
      stage: "complete",
      vrmUrl: VRM_URL,
      elapsedMs: Date.now() - startedAt,
      byteLength: buffer.length,
      sha256: createHash("sha256").update(buffer).digest("hex"),
      contentType: response.headers.get("content-type"),
      ...validation,
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
