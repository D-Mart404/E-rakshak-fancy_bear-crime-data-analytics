"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { apiFetch } from "@/lib/api";

type CommandCenter = {
  case: { case_id: string; unit: string };
  stats: {
    fir_seed_suspects: number;
    resolved_entities: number;
    money_traced_display: string;
    total_events: number;
    transactions: number;
    cdr_events: number;
    ipdr_events: number;
    priority_leads: number;
  };
  top_case_findings: Array<{
    finding_id: string;
    title: string;
    severity: string;
    confidence_score: number;
    summary: string;
    entities_involved: string[];
    total_amount_involved: number;
  }>;
  discovered_networks: Array<{
    network_id: string;
    title: string;
    total_nodes: number;
    total_seed_links: number;
    high_risk_count: number;
    primary_motif: string;
    total_traced_volume: number;
    seed_entity_id?: string;
  }>;
  seed_entities: Array<{ entity_id: string; entity_name?: string }>;
};

export default function DashboardPage() {
  const [data, setData] = useState<CommandCenter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<CommandCenter>("/api/intelligence/command-center")
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load command center")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 text-[var(--muted)]">
        Loading overview…
      </div>
    );
  }

  if (error || !data) {
    return <div className="text-red-300">{error ?? "No data"}</div>;
  }

  const s = data.stats;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Overview"
        title="Case at a glance"
        description="Case summary and live counts."
        dataType="Case summary"
        dataHint={`Active case ${data.case.case_id}`}
        actions={
          <>
            <Link
              href="/cases"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--text)]"
            >
              Switch case
            </Link>
            <Link
              href="/documents"
              className="rounded-lg bg-[var(--ok)] px-3 py-2 text-xs font-semibold text-white"
            >
              Add document
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {[
          {
            href: "/entities",
            title: "Evidence",
            body: "Raw records: people, bank money, phone calls, internet sessions, uploaded files.",
            badge: "Tables",
          },
          {
            href: "/findings",
            title: "Insights",
            body: "Analysis: call→money links, network map, timeline, money flow, priority list.",
            badge: "Tools",
          },
          {
            href: "/str",
            title: "Reports",
            body: "Outputs for file: STR / case report and investigator activity log.",
            badge: "Output",
          },
        ].map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 hover:border-[var(--accent)]"
          >
            <div className="flex items-center justify-between">
              <div className="text-base font-bold text-[var(--text)]">{card.title}</div>
              <span className="rounded bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
                {card.badge}
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">{card.body}</p>
            <div className="mt-3 text-[11px] font-semibold text-[var(--accent)]">
              Open →
            </div>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          { label: "FIR seed suspects", value: s.fir_seed_suspects },
          { label: "Resolved entities", value: s.resolved_entities },
          { label: "Money traced", value: s.money_traced_display },
          {
            label: "Total events",
            value: s.total_events.toLocaleString(),
            hint: `${s.transactions.toLocaleString()} bank · ${s.cdr_events.toLocaleString()} CDR · ${s.ipdr_events} IPDR`,
          },
          { label: "Priority leads", value: s.priority_leads },
        ].map((box) => (
          <div
            key={box.label}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <div className="text-xs uppercase tracking-wider text-[var(--muted)]">
              {box.label}
            </div>
            <div className="mt-2 text-2xl font-bold text-[var(--text)]">{box.value}</div>
            {"hint" in box && box.hint ? (
              <div className="mt-1 text-[11px] text-[var(--muted)]">{box.hint}</div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--accent)]">
              Top case findings
            </h3>
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[11px] text-red-200">
              {data.top_case_findings.length} findings
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {data.top_case_findings.length ? (
              data.top_case_findings.map((f) => {
                const isCrit = f.severity === "CRITICAL";
                const isHigh = f.severity === "HIGH";
                return (
                  <div
                    key={f.finding_id}
                    className={`rounded-lg border bg-white/[0.02] p-3 border-l-4 ${
                      isCrit
                        ? "border-red-500/40 border-l-red-500"
                        : isHigh
                          ? "border-amber-500/30 border-l-amber-400"
                          : "border-white/10 border-l-slate-400"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div
                        className={`text-sm font-semibold ${
                          isCrit
                            ? "text-red-400"
                            : isHigh
                              ? "text-amber-400"
                              : "text-white"
                        }`}
                      >
                        {f.title}
                      </div>
                      <span
                        className={`shrink-0 rounded px-2 py-0.5 text-[11px] font-semibold ${
                          isCrit
                            ? "bg-red-500/20 text-red-300"
                            : isHigh
                              ? "bg-amber-500/20 text-amber-200"
                              : "bg-slate-500/20 text-slate-300"
                        }`}
                      >
                        {f.confidence_score}% Confidence
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-slate-400">
                      {f.summary}
                    </p>
                    <div className="mt-2 flex justify-between text-[11px] text-slate-500">
                      <span>
                        {(f.entities_involved || []).slice(0, 2).join(", ") || "—"}
                      </span>
                      <span className="font-semibold text-cyan-300">
                        ₹ {Math.round(f.total_amount_involved || 0).toLocaleString()}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-slate-500">
                No automated findings yet. Open Findings to run correlations.
              </div>
            )}
          </div>
          <Link
            href="/findings"
            className="mt-4 inline-block text-xs font-semibold text-indigo-300"
          >
            Open findings & correlations →
          </Link>
        </section>

        <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
          <h3 className="text-sm font-semibold text-cyan-300">
            Discovered network rings
          </h3>
          <div className="mt-4 space-y-3">
            {data.discovered_networks.map((n) => (
              <div
                key={n.network_id}
                className="rounded-lg border border-white/10 bg-white/5 p-3"
              >
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-white">{n.title}</div>
                  <span className="text-[11px] text-violet-300">
                    {n.total_nodes} nodes
                  </span>
                </div>
                <div className="mt-2 flex justify-between text-[11px] text-slate-400">
                  <span>Seeds linked: {n.total_seed_links}</span>
                  <span>High-risk: {n.high_risk_count}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">{n.primary_motif}</span>
                  <span className="font-semibold text-emerald-300">
                    ₹ {Math.round(n.total_traced_volume).toLocaleString()}
                  </span>
                </div>
                {n.seed_entity_id ? (
                  <Link
                    href={`/investigation/${encodeURIComponent(n.seed_entity_id)}/graph`}
                    className="mt-2 inline-block text-[11px] font-semibold text-indigo-300"
                  >
                    Open network graph →
                  </Link>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      </div>

      {data.seed_entities.length ? (
        <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
          <h3 className="text-sm font-semibold text-cyan-300">FIR seed suspects</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.seed_entities.map((s) => (
              <Link
                key={s.entity_id}
                href={`/entities/${encodeURIComponent(s.entity_id)}`}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 hover:bg-indigo-500/20"
              >
                {s.entity_name || s.entity_id}
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
