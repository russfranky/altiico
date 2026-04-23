/**
 * Debug panel that renders the `window.__hubzzObs__` ring buffer when the
 * URL contains `?obs=1`. Companion to src/lib/obs.ts — gives altiico the
 * same "CLI parity" signal that `hubzz obs tail` provides for the server.
 *
 * Not gated on environment so it works identically in dev and production
 * (the `?obs=1` query param is the gate). No sensitive data is written
 * to the ring — only kind/msg/tags/ctx that the app intentionally emits.
 */

import { useEffect, useState } from "react";
import { obs, type ObsEvent } from "@/lib/obs";

function levelColor(lvl: ObsEvent["lvl"]): string {
    switch (lvl) {
        case "fatal":   return "text-red-400";
        case "error":   return "text-red-300";
        case "warning": return "text-yellow-300";
        case "info":    return "text-sky-300";
        case "debug":   return "text-slate-400";
        default:        return "text-slate-300";
    }
}

export default function ObsOverlay() {
    const [events, setEvents] = useState<ObsEvent[]>([]);
    const [open, setOpen] = useState(true);

    useEffect(() => {
        const isEnabled = new URLSearchParams(window.location.search).get("obs") === "1";
        if (!isEnabled) return;

        const tick = () => setEvents(obs.snapshot());
        tick();
        const id = window.setInterval(tick, 1000);
        return () => window.clearInterval(id);
    }, []);

    const enabled = new URLSearchParams(window.location.search).get("obs") === "1";
    if (!enabled) return null;

    const recent = events.slice(-50).reverse();

    return (
        <div
            style={{ position: "fixed", right: 12, bottom: 12, zIndex: 2147483647 }}
            className="w-[480px] max-w-[92vw] rounded-md border border-slate-700 bg-slate-950/95 text-xs text-slate-200 shadow-2xl backdrop-blur"
        >
            <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
                <div className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                    obs · {events.length} event{events.length === 1 ? "" : "s"}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => { obs.clear(); setEvents([]); }}
                        className="rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-slate-800"
                    >
                        clear
                    </button>
                    <button
                        type="button"
                        onClick={() => setOpen((v) => !v)}
                        className="rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-slate-800"
                    >
                        {open ? "hide" : "show"}
                    </button>
                </div>
            </div>
            {open && (
                <div className="max-h-[40vh] overflow-auto px-3 py-2 font-mono">
                    {recent.length === 0 ? (
                        <div className="py-4 text-center text-slate-500">no events yet</div>
                    ) : (
                        recent.map((e, i) => (
                            <div key={i} className="border-b border-slate-900 py-1 last:border-0">
                                <div className="flex items-baseline gap-2">
                                    <span className="text-slate-500">{e.t?.slice(11, 19) ?? "?"}</span>
                                    <span className={`font-semibold ${levelColor(e.lvl)}`}>{e.lvl}</span>
                                    <span className="text-slate-300">{e.kind}</span>
                                </div>
                                <div className="ml-[72px] text-slate-400">{e.msg}</div>
                                {e.tags && Object.keys(e.tags).length > 0 && (
                                    <div className="ml-[72px] text-[10px] text-slate-500">
                                        {Object.entries(e.tags).map(([k, v]) => `${k}=${v}`).join(" · ")}
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
