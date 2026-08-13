"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

type OverviewStats = {
  entities_total: number;
  seed_entities: number;
  transactions_total: number;
  telecom_events_total: number;
  cdr_events: number;
  ipdr_events: number;
  credit_total_amount: number;
  debit_total_amount: number;
};

export default function OverviewStatsBanner() {
  const [stats, setStats] = useState<OverviewStats | null>(null);

  useEffect(() => {
    apiFetch<{ stats: OverviewStats }>("/api/overview")
      .then((d) => setStats(d.stats))
      .catch(() => setStats(null));
  }, []);

  if (!stats) return null;

  const boxes = [
    { label: "Entities", value: stats.entities_total, hint: `${stats.seed_entities} seeds` },
    { label: "Transactions", value: stats.transactions_total, hint: "All bank movements" },
    { label: "Telecom Events", value: stats.telecom_events_total, hint: `${stats.cdr_events} CDR / ${stats.ipdr_events} IPDR` },
    { label: "Credits (₹)", value: Math.round(stats.credit_total_amount).toLocaleString(), hint: "Total incoming" },
    { label: "Debits (₹)", value: Math.round(stats.debit_total_amount).toLocaleString(), hint: "Total outgoing" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      {boxes.map((b) => (
        <div
          key={b.label}
          className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4"
        >
          <div className="text-xs uppercase tracking-wider text-slate-400">{b.label}</div>
          <div className="mt-2 text-2xl font-bold text-white">{b.value}</div>
          <div className="mt-1 text-[11px] text-slate-500">{b.hint}</div>
        </div>
      ))}
    </div>
  );
}
