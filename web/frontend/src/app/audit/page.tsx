"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type AuditItem = {
  timestamp: string;
  user: string;
  action: string;
};

export default function AuditPage() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [action, setAction] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ items: AuditItem[] }>(
        "/api/intelligence/audit?limit=200"
      );
      setItems(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit trail");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addNote = async () => {
    if (!action.trim()) return;
    try {
      await apiFetch("/api/intelligence/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action.trim() }),
      });
      setAction("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to write audit entry");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Case Audit Trail</h2>
        <p className="mt-1 text-sm text-slate-400">
          Immutable-style activity log for investigator actions (queries, STR generation, notes) for courtroom admissibility.
        </p>
      </div>

      <div className="flex flex-col gap-2 md:flex-row">
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="Add investigator note / action..."
          className="w-full rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
        />
        <button
          onClick={() => void addNote()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
        >
          Log action
        </button>
      </div>

      {error ? <div className="text-red-300">{error}</div> : null}

      <div className="space-y-2">
        {items.map((item, idx) => (
          <div
            key={`${item.timestamp}-${idx}`}
            className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
              <span>{item.timestamp}</span>
              <span className="text-cyan-300">{item.user}</span>
            </div>
            <div className="mt-1 text-sm text-slate-200">{item.action}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
