import { createHash } from "node:crypto";

const METADATA_URL = "https://m.cyberbrokers.com/mainnet/mech/419";
const MAX_BYTES = 64 * 1024 * 1024;

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
  if (buffer.length < 20) {
    return { validGlb: false, reason: "header_too_short" };
  }
  if (buffer.toString("ascii", 0, 4) !== "glTF") {
    return { validGlb: false, reason: "invalid_glb_magic" };
  }

  const version = buffer.readUInt32LE(4);
  const declaredLength = buffer.readUInt32LE(8);
  const jsonChunkLength = buffer.readUInt32LE(12);
  const jsonChunkType = buffer.readUInt32LE(16);
  const jsonEnd = 20 + jsonChunkLength;

  if (version !== 2) {
    return { validGlb: false, reason: "unsupported_glb_version", version };
  }
  if (jsonChunkType !== 0x4e4f534a || jsonEnd > buffer.length) {
    return { validGlb: false, reason: "invalid_json_chunk", version, declaredLength };
  }

  let document;
  try {
    const jsonText = buffer
      .subarray(20, jsonEnd)
      .toString("utf8")
      .replace(/[\u0000\u0020]+$/g, "");
    document = JSON.parse(jsonText);
  } catch (error) {
    return {
      validGlb: false,
      reason: "json_parse_error",
      version,
      declaredLength,
      error: String(error),
    };
  }

  const extensions = document?.extensions || {};
  const vrmSpec = extensions.VRMC_vrm ? "1.0" : extensions.VRM ? "0.x" : null;
  return {
    validGlb: true,
    version,
    declaredLength,
    jsonChunkLength,
    vrmSpec,
  };
}

export async function GET() {
  try {
    const metadataResponse = await fetch(METADATA_URL, {
      headers: { accept: "application/json", "user-agent": "vrm-catalog/1.0" },
      redirect: "follow",
    });
    if (!metadataResponse.ok) {
      return jsonResponse(
        { stage: "metadata", ok: false, httpStatus: metadataResponse.status },
        502,
      );
    }

    const metadata = await metadataResponse.json();
    const vrmUrl = typeof metadata?.vrm_url === "string" ? metadata.vrm_url.trim() : "";
    if (!vrmUrl || !/^https?:\/\//i.test(vrmUrl)) {
      return jsonResponse(
        {
          stage: "metadata",
          ok: false,
          reason: "documented_vrm_url_missing_or_not_http",
          metadataKeys: Object.keys(metadata || {}).sort(),
        },
        422,
      );
    }

    const vrmResponse = await fetch(vrmUrl, {
      headers: { accept: "model/gltf-binary, application/octet-stream, */*" },
      redirect: "follow",
    });
    if (!vrmResponse.ok) {
      return jsonResponse(
        { stage: "binary", ok: false, httpStatus: vrmResponse.status, vrmUrl },
        502,
      );
    }

    const contentLength = Number(vrmResponse.headers.get("content-length") || "0");
    if (contentLength && contentLength > MAX_BYTES) {
      return jsonResponse(
        { stage: "binary", ok: false, reason: "binary_too_large", contentLength, vrmUrl },
        413,
      );
    }

    const buffer = Buffer.from(await vrmResponse.arrayBuffer());
    if (buffer.length > MAX_BYTES) {
      return jsonResponse(
        { stage: "binary", ok: false, reason: "binary_too_large", byteLength: buffer.length, vrmUrl },
        413,
      );
    }

    const validation = validateGlb(buffer);
    const sha256 = createHash("sha256").update(buffer).digest("hex");
    return jsonResponse({
      stage: "complete",
      ok: validation.validGlb && Boolean(validation.vrmSpec),
      metadataUrl: METADATA_URL,
      vrmUrl,
      byteLength: buffer.length,
      sha256,
      contentType: vrmResponse.headers.get("content-type"),
      ...validation,
    });
  } catch (error) {
    return jsonResponse(
      { stage: "exception", ok: false, error: `${error?.name || "Error"}: ${error?.message || error}` },
      500,
    );
  }
}
