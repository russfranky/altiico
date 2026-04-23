/**
 * Local observability sink for the browser — the altiico counterpart to
 * hubzz-alpha/packages/server/src/Helpers/Obs.ts. Same interface shape so
 * call sites stay portable and a future @hubzz/avatar-sdk extraction is
 * mechanical.
 *
 * Server-side obs writes structured JSON lines to stdout (picked up by
 * journald / log files and parsed by the `hubzz obs` CLI). Altiico runs
 * in a browser, so the same idea maps to:
 *   - a capped ring buffer at `window.__hubzzObs__` (last 200 events)
 *   - a mirror `console.debug('[obs]', ...)` so DevTools shows events
 *     without a separate tool
 *   - a debug overlay (ObsOverlay.tsx) gated on `?obs=1` that reads the
 *     ring buffer and renders it bottom-right
 *
 * Emitting here does NOT call Sentry — callers are expected to call both
 * (or neither). Keeping the sinks independent means turning Sentry off
 * doesn't kill local signal, and turning the ring buffer off doesn't lose
 * Sentry.
 */

export type ObsLevel = "debug" | "info" | "warning" | "error" | "fatal";

export interface ObsEvent {
    /** ISO8601 timestamp (set automatically). */
    t?: string;
    /** severity */
    lvl: ObsLevel;
    /** dot-namespaced category — e.g. "api.collections", "vrm.load", "webgl.init". Matches the Sentry tag conventions used in hubzz-alpha. */
    kind: string;
    /** human-readable summary (short) */
    msg: string;
    /** key-value tags — identical shape to Sentry tags, used by the debug overlay for filtering */
    tags?: Record<string, string | number | boolean | undefined>;
    /** free-form structured context */
    ctx?: Record<string, unknown>;
}

const RING_SIZE = 200;
const GLOBAL_KEY = "__hubzzObs__";

function getRing(): ObsEvent[] {
    const w = window as unknown as Record<string, unknown>;
    if (!Array.isArray(w[GLOBAL_KEY])) w[GLOBAL_KEY] = [];
    return w[GLOBAL_KEY] as ObsEvent[];
}

/**
 * Emit a structured event. Non-throwing — a JSON.stringify failure (e.g.
 * circular reference in ctx) falls back to a minimal record rather than
 * cascading the failure into the caller.
 */
export function emit(event: ObsEvent): void {
    const payload: ObsEvent = { t: new Date().toISOString(), ...event };
    const ring = getRing();
    ring.push(payload);
    if (ring.length > RING_SIZE) ring.shift();
    try {
        console.debug("[obs]", JSON.stringify(payload));
    } catch {
        console.debug("[obs]", `{"lvl":"${event.lvl}","kind":"${event.kind}","msg":"serialize_failed"}`);
    }
}

/** Convenience helpers mirroring Sentry level methods + hubzz-alpha Obs.ts. */
export const obs = {
    debug:   (kind: string, msg: string, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => emit({ lvl: "debug",   kind, msg, tags, ctx }),
    info:    (kind: string, msg: string, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => emit({ lvl: "info",    kind, msg, tags, ctx }),
    warn:    (kind: string, msg: string, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => emit({ lvl: "warning", kind, msg, tags, ctx }),
    error:   (kind: string, msg: string, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => emit({ lvl: "error",   kind, msg, tags, ctx }),
    fatal:   (kind: string, msg: string, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => emit({ lvl: "fatal",   kind, msg, tags, ctx }),
    /** Capture an Error — extracts message+stack into the ctx.err subobject. */
    exception: (kind: string, err: unknown, tags?: ObsEvent["tags"], ctx?: ObsEvent["ctx"]) => {
        const e = err instanceof Error ? err : new Error(String(err));
        emit({
            lvl: "error",
            kind,
            msg: e.message.slice(0, 200),
            tags,
            ctx: { ...ctx, err: { name: e.name, stack: e.stack?.split("\n").slice(0, 8).join("\n") } },
        });
    },
    /** Read the current ring buffer (consumed by ObsOverlay). */
    snapshot: (): ObsEvent[] => [...getRing()],
    /** Empty the ring buffer — used by the overlay's Clear button. */
    clear: (): void => {
        const w = window as unknown as Record<string, unknown>;
        w[GLOBAL_KEY] = [];
    },
};
