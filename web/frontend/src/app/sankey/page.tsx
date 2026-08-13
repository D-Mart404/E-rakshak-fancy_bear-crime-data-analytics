"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type Flow = { source: string; target: string; amount: number; count: number };

export default function SankeyPage() {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ flows: Flow[] }>("/api/intelligence/sankey?limit=40")
      .then((d) => setFlows(d.flows))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load money flow")
      );
  }, []);

  const maxAmount = Math.max(...flows.map((f) => f.amount), 1);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Money Flow & Pass-Through</h2>
        <p className="mt-1 text-sm text-slate-400">
          Highest-volume account → counterparty movements across the case (Sankey-style list).
        </p>
      </div>

      {error ? <div className="text-red-300">{error}</div> : null}

      <div className="space-y-2">
        {flows.map((f, idx) => (
          <div
            key={`${f.source}-${f.target}-${idx}`}
            className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div className="text-slate-200">
                <Link
                  href={`/transactions?account_id=${encodeURIComponent(f.source)}`}
                  className="font-semibold text-white hover:text-indigo-300 hover:underline"
                >
                  {f.source}
                </Link>
                <span className="mx-2 text-slate-500">→</span>
                <Link
                  href={`/entities?q=${encodeURIComponent(f.target)}`}
                  className="font-semibold text-white hover:text-indigo-300 hover:underline"
                >
                  {f.target}
                </Link>
              </div>
              <Link
                href={`/transactions?account_id=${encodeURIComponent(f.source)}`}
                className="text-cyan-300 font-bold hover:underline"
              >
                ₹ {Math.round(f.amount).toLocaleString()}
                <span className="ml-2 text-[11px] font-normal text-slate-500">
                  {f.count} txns
                </span>
              </Link>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded bg-slate-950/60">
              <div
                className="h-full rounded bg-gradient-to-r from-cyan-500 to-indigo-500"
                style={{ width: `${Math.max(4, (f.amount / maxAmount) * 100)}%` }}
              />
            </div>
          </div>
        ))}
        {!flows.length && !error ? (
          <div className="text-sm text-slate-500">Loading money flows...</div>
        ) : null}
      </div>
    </div>
  );
}
