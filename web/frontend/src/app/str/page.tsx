"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

type Entity = { entity_id: string; entity_name?: string };
type StrReport = {
  report_type: string;
  generated_at: string;
  narrative: string;
  entity: Record<string, unknown>;
  risk_profile: Record<string, unknown> | null;
  highlight_transactions: Array<Record<string, unknown>>;
  recent_multimodal_events: Array<Record<string, unknown>>;
};

function Inner() {
  const entityQ = useSearchParams().get("entity") || "";
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selected, setSelected] = useState(entityQ);
  const [report, setReport] = useState<StrReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (entityQ) setSelected(entityQ);
  }, [entityQ]);

  useEffect(() => {
    apiFetch<{ items: Entity[] }>("/api/entities?limit=100")
      .then((d) => {
        setEntities(d.items);
        setSelected((p) => p || d.items[0]?.entity_id || "");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  const generate = async (id?: string) => {
    const eid = id || selected;
    if (!eid) return;
    setSelected(eid);
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<StrReport>(`/api/intelligence/str/${encodeURIComponent(eid)}`);
      setReport(data);
      await apiFetch("/api/intelligence/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: `Generated STR report for ${eid}` }),
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "STR failed");
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (entityQ) void generate(entityQ);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityQ]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold text-white">STR / Case Report</h2>
        <p className="mt-1 text-sm text-slate-400">
          Deep-link with /str?entity=ID from any proof panel.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="min-w-[280px] rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white"
        >
          {entities.map((e) => (
            <option key={e.entity_id} value={e.entity_id}>
              {e.entity_name || e.entity_id}
            </option>
          ))}
        </select>
        <button
          onClick={() => void generate()}
          disabled={loading || !selected}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Generating…" : "Generate STR"}
        </button>
      </div>
      {error ? <div className="text-red-300">{error}</div> : null}

      {report ? (
        <article className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-6">
          <div className="text-xs uppercase text-cyan-400">{report.report_type}</div>
          <h3 className="mt-2 text-xl font-bold text-white">
            {String(report.entity.entity_name || report.entity.entity_id)}
          </h3>
          <div className="mt-1 text-xs text-slate-500">Generated {report.generated_at}</div>
          <p className="mt-4 text-sm text-slate-300">{report.narrative}</p>

          {report.risk_profile ? (
            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {(["risk_category", "risk_score", "cdr_count", "ipdr_count"] as const).map((k) => (
                <div key={k} className="rounded-lg bg-white/5 p-3">
                  <div className="text-[11px] text-slate-400">{k}</div>
                  <div className="text-lg font-bold text-white">{String(report.risk_profile?.[k])}</div>
                </div>
              ))}
            </div>
          ) : null}

          <h4 className="mt-6 text-sm font-semibold text-cyan-300">Highlight transfers</h4>
          <div className="mt-2 space-y-2">
            {report.highlight_transactions.map((t, i) => {
              const tid = t.transaction_id ? String(t.transaction_id) : "";
              const body = `${t.transaction_date || ""} · ${t.direction} ₹${t.amount} · ${t.counterparty_name || ""}`;
              return tid ? (
                <Link key={tid} href={`/transactions/${encodeURIComponent(tid)}`} className="block rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-slate-300 hover:bg-indigo-500/10">
                  {body}
                </Link>
              ) : (
                <div key={i} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                  {body}
                </div>
              );
            })}
          </div>

          <h4 className="mt-6 text-sm font-semibold text-cyan-300">Recent multimodal events</h4>
          <div className="mt-2 space-y-2">
            {report.recent_multimodal_events.map((e, i) => {
              const href = e.href ? String(e.href) : "";
              const body = (
                <>
                  <span className="mr-2 text-cyan-300">{String(e.source)}</span>
                  {String(e.title)} — {String(e.detail)}
                </>
              );
              return href ? (
                <Link key={String(e.ref || i)} href={href} className="block rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-slate-300 hover:bg-indigo-500/10">
                  {body}
                </Link>
              ) : (
                <div key={String(e.ref || i)} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                  {body}
                </div>
              );
            })}
          </div>
        </article>
      ) : null}
    </div>
  );
}

export default function StrPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400">Loading…</div>}>
      <Inner />
    </Suspense>
  );
}
