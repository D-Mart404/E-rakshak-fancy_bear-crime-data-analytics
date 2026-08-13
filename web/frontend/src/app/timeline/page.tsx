"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

type Entity = { entity_id: string; entity_name?: string };
type Ev = {
  source: string;
  timestamp?: string;
  time_precision?: string;
  ref?: string;
  title: string;
  detail: string;
  href?: string;
};
type Evidence = { id: string; type?: string; href?: string | null };
type Episode = {
  episode_id: string;
  title: string;
  severity: string;
  episode_score: number;
  time_window_str: string;
  duration_human?: string;
  calls_count: number;
  ip_sessions_count: number;
  transactions_count: number;
  total_money_moved_inr: number;
  entities_involved?: string[];
  plain_narrative?: string;
  detected_typologies: string[];
  raw_evidence?: Evidence[];
  raw_evidence_ids?: Array<string | undefined>;
};
type HeatRow = {
  entity_id: string;
  entity_name?: string;
  hours: Array<{ hour: number; val: number; count: number; status: string }>;
};

function sev(s: string) {
  if (s === "CRITICAL") return { t: "text-red-400", b: "border-l-red-500", g: "bg-red-500/20 text-red-300" };
  if (s === "HIGH") return { t: "text-amber-400", b: "border-l-amber-400", g: "bg-amber-500/20 text-amber-200" };
  return { t: "text-slate-200", b: "border-l-slate-400", g: "bg-slate-500/20 text-slate-300" };
}

function hrefOf(id: string, type?: string) {
  return type === "BANK" || id.includes("TX")
    ? `/transactions/${encodeURIComponent(id)}`
    : `/telecom/${encodeURIComponent(id)}`;
}

function Inner() {
  const sp = useSearchParams();
  const entityQ = sp.get("entity") || "";
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selected, setSelected] = useState(entityQ);
  const [source, setSource] = useState("");
  const [events, setEvents] = useState<Ev[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [heatmap, setHeatmap] = useState<HeatRow[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [tab, setTab] = useState<"episodes" | "heatmap" | "stream">(entityQ ? "stream" : "episodes");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (entityQ) {
      setSelected(entityQ);
      setTab("stream");
    }
  }, [entityQ]);

  useEffect(() => {
    apiFetch<{ items: Entity[] }>("/api/entities?limit=100&seed_only=true")
      .then((d) => (d.items?.length ? d : apiFetch<{ items: Entity[] }>("/api/entities?limit=50")))
      .then((d) => {
        setEntities(d.items);
        setSelected((p) => p || d.items[0]?.entity_id || "");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed"));

    apiFetch<{ episodes: Episode[] }>("/api/intelligence/episodes?limit=20")
      .then((d) => setEpisodes(d.episodes || []))
      .catch(() => setEpisodes([]));
    apiFetch<{ heatmap_matrix: HeatRow[] }>("/api/intelligence/heatmap?limit_entities=10")
      .then((d) => setHeatmap(d.heatmap_matrix || []))
      .catch(() => setHeatmap([]));
  }, []);

  useEffect(() => {
    if (!selected) return;
    const q = new URLSearchParams({ limit: "200" });
    if (source) q.set("source", source);
    apiFetch<{ events: Ev[] }>(`/api/intelligence/timeline/${encodeURIComponent(selected)}?${q}`)
      .then((d) => setEvents(d.events))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Timeline failed"));
  }, [selected, source]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Timeline</h2>
        <p className="mt-1 text-sm text-slate-400">
          Cross-source activity ordered by time.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {(["episodes", "heatmap", "stream"] as const).map((id) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === id ? "bg-indigo-600 text-white" : "bg-white/10 text-slate-300"
            }`}
          >
            {id === "episodes" ? "Episodes" : id === "heatmap" ? "Heatmap" : "Raw stream"}
          </button>
        ))}
      </div>
      {error ? <div className="text-red-300">{error}</div> : null}

      {tab === "episodes" && (
        <div className="space-y-3">
          {episodes.map((ep) => {
            const s = sev(ep.severity);
            const evidence =
              ep.raw_evidence?.length
                ? ep.raw_evidence
                : (ep.raw_evidence_ids || []).filter(Boolean).map((id) => ({
                    id: String(id),
                    href: hrefOf(String(id)),
                  }));
            const ent = (ep.entities_involved || [])[0];
            const open = openId === ep.episode_id;
            return (
              <div key={ep.episode_id} className={`rounded-xl border border-white/10 bg-white/[0.02] p-4 border-l-[5px] ${s.b}`}>
                <div className="flex flex-wrap justify-between gap-2">
                  <div>
                    <div className={`text-sm font-bold ${s.t}`}>{ep.title}</div>
                    <div className="text-[11px] text-slate-400">
                      {ep.time_window_str} · {ep.duration_human}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-extrabold ${s.t}`}>{ep.episode_score}/100</div>
                    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${s.g}`}>{ep.severity}</span>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                  <span>{ep.calls_count} calls</span>
                  <span>{ep.ip_sessions_count} IPDR</span>
                  <span>{ep.transactions_count} txns</span>
                  <span className="text-emerald-300">
                    ₹ {Math.round(ep.total_money_moved_inr).toLocaleString()}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-400">{ep.plain_narrative}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setOpenId(open ? null : ep.episode_id)}
                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-[11px] font-semibold text-white"
                  >
                    {open ? "Hide" : "Open"} {evidence.length} proof
                  </button>
                  {ent ? (
                    <>
                      <Link href={`/entities/${encodeURIComponent(ent)}`} className="rounded-md bg-white/10 px-3 py-1.5 text-[11px] font-semibold text-white">
                        Entity
                      </Link>
                      <Link href={`/network?seed=${encodeURIComponent(ent)}`} className="rounded-md bg-violet-600/80 px-3 py-1.5 text-[11px] font-semibold text-white">
                        Network
                      </Link>
                    </>
                  ) : null}
                </div>
                {open ? (
                  <ul className="mt-3 space-y-1 rounded-lg bg-black/30 p-3 text-[11px]">
                    {evidence.map((e) => (
                      <li key={e.id}>
                        <Link href={e.href || hrefOf(e.id, e.type)} className="font-semibold text-indigo-300 hover:underline">
                          [{e.type || "REC"}] {e.id} →
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
          {!episodes.length ? <div className="text-sm text-slate-500">No episodes yet.</div> : null}
        </div>
      )}

      {tab === "heatmap" && (
        <div className="overflow-x-auto rounded-xl border border-slate-700/50 p-4">
          <table className="min-w-full border-collapse text-center text-[11px]">
            <thead>
              <tr className="text-slate-500">
                <th className="px-2 py-1 text-left">Entity</th>
                {Array.from({ length: 24 }, (_, i) => (
                  <th key={i}>{String(i).padStart(2, "0")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmap.map((row) => (
                <tr key={row.entity_id} className="border-t border-white/5">
                  <td className="truncate px-2 py-1 text-left text-cyan-300">
                    <button
                      type="button"
                      className="hover:underline"
                      onClick={() => {
                        setSelected(row.entity_id);
                        setTab("stream");
                      }}
                    >
                      {(row.entity_name || row.entity_id || "").slice(0, 22)}
                    </button>
                  </td>
                  {row.hours.map((h) => (
                    <td
                      key={h.hour}
                      className={`px-1 py-1 font-bold ${
                        h.status === "CRITICAL"
                          ? "bg-red-500/70"
                          : h.status === "HIGH"
                            ? "bg-amber-500/50"
                            : "bg-white/5 text-slate-600"
                      }`}
                    >
                      {h.val > 60 ? "●" : "·"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "stream" && (
        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          <aside className="max-h-[600px] space-y-1 overflow-y-auto rounded-xl border border-slate-700/50 p-3">
            {entities.map((e) => (
              <button
                key={e.entity_id}
                onClick={() => setSelected(e.entity_id)}
                className={`block w-full rounded-lg px-2 py-2 text-left text-xs ${
                  selected === e.entity_id ? "bg-indigo-600/30 text-indigo-200" : "text-slate-300 hover:bg-white/5"
                }`}
              >
                {e.entity_name || e.entity_id}
              </button>
            ))}
          </aside>
          <section className="rounded-xl border border-slate-700/50 p-4">
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="mb-3 rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white"
            >
              <option value="">All</option>
              <option value="BANK">Bank</option>
              <option value="CDR">CDR</option>
              <option value="IPDR">IPDR</option>
            </select>
            <div className="max-h-[640px] space-y-2 overflow-y-auto">
              {events.map((ev, i) => (
                <div key={`${ev.ref}-${i}`} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs">
                  <div className="flex justify-between gap-2">
                    <span className="rounded bg-white/10 px-2 py-0.5 text-[10px]">{ev.source}</span>
                    <span className="text-slate-200">{ev.timestamp || "—"}</span>
                  </div>
                  <div className="mt-1 font-semibold text-white">{ev.title}</div>
                  <div className="text-slate-400">{ev.detail}</div>
                  {ev.href ? (
                    <Link href={ev.href} className="mt-1 inline-block text-indigo-300">
                      Open →
                    </Link>
                  ) : null}
                </div>
              ))}
              {!events.length ? <div className="text-sm text-slate-500">No events.</div> : null}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default function TimelinePage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400">Loading…</div>}>
      <Inner />
    </Suspense>
  );
}
