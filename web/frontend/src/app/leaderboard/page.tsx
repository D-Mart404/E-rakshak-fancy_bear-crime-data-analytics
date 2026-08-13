"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import RiskDecompositionPanel, { type RiskProfile } from "@/components/RiskDecompositionPanel";

export default function LeaderboardPage() {
  const [rows, setRows] = useState<RiskProfile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<RiskProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ leaderboard: RiskProfile[] }>("/api/intelligence/leaderboard?limit=60")
      .then((d) => {
        setRows(d.leaderboard);
        if (d.leaderboard[0]?.entity_id) setSelectedId(d.leaderboard[0].entity_id);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    apiFetch<{ risk_profile: RiskProfile }>(
      `/api/intelligence/risk/${encodeURIComponent(selectedId)}`
    )
      .then((d) => setDetail(d.risk_profile))
      .catch(() => setDetail(rows.find((r) => r.entity_id === selectedId) || null));
  }, [selectedId, rows]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Priority suspects</h2>
      </div>
      {error ? <div className="text-red-300">{error}</div> : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1fr]">
        <div className="overflow-x-auto rounded-xl border border-slate-700/50">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900/80 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Pass%</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={r.entity_id}
                  onClick={() => setSelectedId(r.entity_id)}
                  className={`cursor-pointer border-t border-slate-700/40 ${
                    selectedId === r.entity_id ? "bg-indigo-500/15" : "hover:bg-indigo-500/10"
                  }`}
                >
                  <td className="px-4 py-3 text-slate-400">{i + 1}</td>
                  <td className="px-4 py-3 text-white">
                    <Link
                      href={`/entities/${encodeURIComponent(r.entity_id)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-medium hover:text-indigo-300 hover:underline"
                    >
                      {r.entity_name || r.entity_id}
                    </Link>
                    {r.is_seed ? (
                      <Link
                        href={`/entities/${encodeURIComponent(r.entity_id)}`}
                        onClick={(e) => e.stopPropagation()}
                        className="ml-2 rounded bg-red-500/20 px-1.5 text-[10px] text-red-200 hover:bg-red-500/30"
                      >
                        SEED
                      </Link>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-[10px] text-violet-200">
                    <Link
                      href={`/entities/${encodeURIComponent(r.entity_id)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="hover:underline"
                    >
                      {r.account_role || "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-semibold text-red-200">
                    <Link
                      href={`/network?seed=${encodeURIComponent(r.entity_id)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="hover:underline"
                    >
                      {r.risk_score}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[11px] text-amber-200">
                    <Link
                      href={`/timeline?entity=${encodeURIComponent(r.entity_id)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="hover:underline"
                    >
                      {r.risk_category}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-amber-200">
                    <Link
                      href={
                        r.primary_account_id
                          ? `/transactions?account_id=${encodeURIComponent(r.primary_account_id)}`
                          : `/transactions`
                      }
                      onClick={(e) => e.stopPropagation()}
                      className="hover:underline"
                    >
                      {Math.round((r.pass_through_ratio || 0) * 100)}%
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="xl:sticky xl:top-4 xl:self-start">
          {detail ? (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-slate-400">
                <span>Proof panel</span>
                <Link href={`/entities/${encodeURIComponent(detail.entity_id)}`} className="text-indigo-300">
                  Full profile →
                </Link>
              </div>
              <RiskDecompositionPanel profile={detail} />
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-white/10 p-6 text-sm text-slate-500">
              Select a lead…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
