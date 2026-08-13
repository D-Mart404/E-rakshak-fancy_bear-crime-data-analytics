"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type Finding = {
  finding_id: string;
  title: string;
  severity: string;
  confidence_score: number;
  pattern_type?: string;
  summary: string;
  entities_involved: string[];
  total_amount_involved: number;
  recommended_action?: string;
};

type Correlation = {
  correlation_id: string;
  call_event: { event_id?: string; a_party: string; b_party: string; timestamp: string };
  ipdr_event: { event_id?: string; ip_address: string; matched?: boolean };
  financial_transfer: { transaction_id?: string; account_id?: string; amount: number };
  time_delta_human: string;
  correlation_score: number;
  explanation: string;
};

function sev(s: string) {
  if (s === "CRITICAL") return { border: "border-red-500/40 border-l-red-500", title: "text-red-400", badge: "bg-red-500/20 text-red-300" };
  if (s === "HIGH") return { border: "border-amber-500/30 border-l-amber-400", title: "text-amber-400", badge: "bg-amber-500/20 text-amber-200" };
  return { border: "border-white/10 border-l-slate-400", title: "text-slate-200", badge: "bg-slate-500/20 text-slate-300" };
}

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [correlations, setCorrelations] = useState<Correlation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<{ findings: Finding[] }>("/api/intelligence/findings"),
      apiFetch<{ correlations: Correlation[] }>("/api/intelligence/correlations?limit=30"),
    ])
      .then(([f, c]) => {
        setFindings(f.findings || []);
        setCorrelations(c.correlations || []);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Findings & Correlations</h2>
          <p className="mt-1 text-sm text-slate-400">
            Pattern detections with confidence scores. Open links for proof.
          </p>
        </div>
        <span className="rounded-full bg-red-500/20 px-3 py-1 text-[11px] font-semibold text-red-200">
          {findings.length} findings
        </span>
      </div>

      {loading ? <div className="text-sm text-slate-500">Scanning…</div> : null}
      {error ? <div className="text-sm text-red-300">{error}</div> : null}

      <section className="space-y-3">
        {findings.map((f) => {
          const s = sev(f.severity);
          return (
            <div key={f.finding_id} className={`rounded-lg border border-l-4 bg-white/[0.02] p-4 ${s.border}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <Link
                    href={
                      f.entities_involved?.[0]
                        ? `/entities/${encodeURIComponent(f.entities_involved[0])}`
                        : "/leaderboard"
                    }
                    className={`text-sm font-semibold hover:underline ${s.title}`}
                  >
                    {f.title}
                  </Link>
                  {f.pattern_type ? (
                    <div className="mt-1 text-[11px] uppercase tracking-wider text-slate-500">{f.pattern_type}</div>
                  ) : null}
                </div>
                <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${s.badge}`}>
                  {f.confidence_score}% Confidence
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-400">{f.summary}</p>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                <span className="flex flex-wrap gap-2">
                  {(f.entities_involved || []).slice(0, 3).map((e) => (
                    <Link key={e} href={`/entities/${encodeURIComponent(e)}`} className="text-indigo-300 hover:underline">
                      {e}
                    </Link>
                  ))}
                </span>
                <strong className="text-cyan-300">
                  ₹ {Math.round(f.total_amount_involved || 0).toLocaleString()}
                </strong>
              </div>
              {f.recommended_action ? (
                <div className="mt-2 rounded bg-white/5 px-3 py-2 text-[11px] text-slate-300">
                  Next: {f.recommended_action}
                </div>
              ) : null}
            </div>
          );
        })}
      </section>

      <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
        <div className="mb-3 flex justify-between text-sm">
          <h3 className="font-semibold text-cyan-300">Call → IP → Transfer (±10 min)</h3>
          <span className="text-[11px] text-slate-400">{correlations.length} matches</span>
        </div>
        <div className="max-h-[520px] space-y-3 overflow-y-auto">
          {correlations.map((c) => (
            <div key={c.correlation_id} className="rounded-lg border border-cyan-500/30 bg-slate-950/40 p-3 text-[11px]">
              <div className="flex justify-between">
                <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-cyan-300">Δ {c.time_delta_human}</span>
                <span className="font-semibold text-cyan-200">Score {Math.round(c.correlation_score)}/100</span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <div>
                  <div className="text-slate-500">Call</div>
                  <Link
                    href={
                      c.call_event.event_id
                        ? `/telecom/${encodeURIComponent(c.call_event.event_id)}`
                        : `/telecom?q=${encodeURIComponent(c.call_event.a_party || "")}`
                    }
                    className="block font-semibold text-white hover:text-indigo-300 hover:underline"
                  >
                    {c.call_event.a_party} → {c.call_event.b_party}
                  </Link>
                </div>
                <div>
                  <div className="text-slate-500">IPDR</div>
                  <Link
                    href={
                      c.ipdr_event.event_id
                        ? `/telecom/${encodeURIComponent(c.ipdr_event.event_id)}`
                        : `/telecom?event_type=IPDR`
                    }
                    className="block font-semibold text-white hover:text-indigo-300 hover:underline"
                  >
                    {c.ipdr_event.ip_address || "IPDR"}
                  </Link>
                </div>
                <div>
                  <div className="text-slate-500">Transfer</div>
                  <Link
                    href={
                      c.financial_transfer.transaction_id
                        ? `/transactions/${encodeURIComponent(String(c.financial_transfer.transaction_id))}`
                        : c.financial_transfer.account_id
                          ? `/transactions?account_id=${encodeURIComponent(c.financial_transfer.account_id)}`
                          : "/transactions"
                    }
                    className="block font-semibold text-emerald-300 hover:underline"
                  >
                    ₹ {Math.round(c.financial_transfer.amount || 0).toLocaleString()}
                  </Link>
                </div>
              </div>
              <p className="mt-2 text-slate-400">{c.explanation}</p>
            </div>
          ))}
          {!correlations.length && !loading ? (
            <div className="text-sm text-slate-500">No temporal coincidences yet.</div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
