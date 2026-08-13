"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

type CaseStats = {
  seed_count: number;
  entity_count: number;
  transaction_count: number;
  cdr_count: number;
  ipdr_count: number;
  audit_entries: number;
  total_events: number;
};

type CaseRow = {
  case_id: string;
  title: string;
  unit?: string;
  lead_investigator?: string;
  fir_number?: string;
  police_station?: string;
  status: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  last_opened_at?: string | null;
  stats?: CaseStats;
};

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    case_id: "",
    title: "",
    fir_number: "",
    police_station: "",
    lead_investigator: "Inspector V. Sharma",
    unit: "Special Financial Cybercrime Unit",
    notes: "",
    status: "open",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<{
        cases: CaseRow[];
        active_case_id: string | null;
      }>("/api/cases");
      setCases(data.cases);
      setActiveCaseId(data.active_case_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openCase = async (caseId: string) => {
    try {
      await apiFetch(`/api/cases/${encodeURIComponent(caseId)}/open`, {
        method: "POST",
      });
      setActiveCaseId(caseId);
      await load();
      router.push("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to open case");
    }
  };

  const createCase = async () => {
    if (!form.case_id.trim() || !form.title.trim()) {
      setError("Case ID and title are required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/api/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          case_id: form.case_id.trim().toUpperCase(),
          fir_number: form.fir_number.trim() || form.case_id.trim().toUpperCase(),
        }),
      });
      setShowForm(false);
      setForm({
        case_id: "",
        title: "",
        fir_number: "",
        police_station: "",
        lead_investigator: "Inspector V. Sharma",
        unit: "Special Financial Cybercrime Unit",
        notes: "",
        status: "open",
      });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create case");
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (caseId: string, status: string) => {
    try {
      await apiFetch(`/api/cases/${encodeURIComponent(caseId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">All Cases</h2>
          <p className="mt-1 text-sm text-slate-400">
            Track every FIR / investigation workspace. Open a case to make it the active command-center case.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
        >
          {showForm ? "Cancel" : "Register new case"}
        </button>
      </div>

      {error ? <div className="text-red-300">{error}</div> : null}

      {showForm ? (
        <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
          <h3 className="text-sm font-semibold text-cyan-300">New case registration</h3>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            {[
              ["case_id", "Case / FIR ID", "FIR-2026-0418"],
              ["title", "Case title", "Online fraud mule network"],
              ["fir_number", "FIR number", "FIR-2026-0418"],
              ["police_station", "Police station", "Cyber Crime PS"],
              ["lead_investigator", "Lead investigator", "Inspector V. Sharma"],
              ["unit", "Unit", "Special Financial Cybercrime Unit"],
            ].map(([key, label, placeholder]) => (
              <label key={key} className="text-xs text-slate-400">
                {label}
                <input
                  value={(form as Record<string, string>)[key]}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  placeholder={placeholder}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                />
              </label>
            ))}
          </div>
          <label className="mt-3 block text-xs text-slate-400">
            Notes
            <textarea
              value={form.notes}
              onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
              rows={3}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
            />
          </label>
          <button
            onClick={() => void createCase()}
            disabled={saving}
            className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save case"}
          </button>
        </section>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-slate-400">
          Loading case registry...
        </div>
      ) : (
        <div className="space-y-3">
          {cases.map((c) => {
            const isActive = c.case_id === activeCaseId || c.status === "active";
            return (
              <div
                key={c.case_id}
                className={`rounded-xl border p-5 ${
                  isActive
                    ? "border-cyan-500/40 bg-cyan-500/10"
                    : "border-slate-700/50 bg-slate-800/40"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-bold text-white">{c.case_id}</h3>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          c.status === "active"
                            ? "bg-cyan-500/20 text-cyan-200"
                            : c.status === "closed"
                              ? "bg-slate-500/20 text-slate-300"
                              : c.status === "archived"
                                ? "bg-violet-500/20 text-violet-200"
                                : "bg-amber-500/20 text-amber-200"
                        }`}
                      >
                        {c.status.toUpperCase()}
                      </span>
                      {isActive ? (
                        <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] text-emerald-200">
                          ACTIVE WORKSPACE
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1 text-sm text-slate-200">{c.title}</div>
                    <div className="mt-1 text-xs text-slate-400">
                      {c.unit || "—"} · Lead: {c.lead_investigator || "—"}
                      {c.police_station ? ` · ${c.police_station}` : ""}
                    </div>
                    {c.notes ? (
                      <div className="mt-2 text-xs text-slate-500">{c.notes}</div>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => void openCase(c.case_id)}
                      className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white"
                    >
                      Open workspace
                    </button>
                    <Link
                      href={`/cases/${encodeURIComponent(c.case_id)}`}
                      className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-semibold text-white"
                    >
                      View details
                    </Link>
                    {c.status !== "closed" ? (
                      <button
                        onClick={() => void setStatus(c.case_id, "closed")}
                        className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-300"
                      >
                        Close
                      </button>
                    ) : (
                      <button
                        onClick={() => void setStatus(c.case_id, "open")}
                        className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-300"
                      >
                        Reopen
                      </button>
                    )}
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-6">
                  {[
                    ["Seeds", c.stats?.seed_count],
                    ["Entities", c.stats?.entity_count],
                    ["Transactions", c.stats?.transaction_count],
                    ["CDR", c.stats?.cdr_count],
                    ["IPDR", c.stats?.ipdr_count],
                    ["Audit logs", c.stats?.audit_entries],
                  ].map(([label, value]) => (
                    <div
                      key={String(label)}
                      className="rounded-lg border border-white/10 bg-white/5 p-2"
                    >
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">
                        {label}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-white">
                        {Number(value || 0).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-3 text-[11px] text-slate-500">
                  Updated {c.updated_at || "—"}
                  {c.last_opened_at ? ` · Last opened ${c.last_opened_at}` : ""}
                </div>
              </div>
            );
          })}
          {!cases.length ? (
            <div className="text-sm text-slate-500">No cases registered yet.</div>
          ) : null}
        </div>
      )}
    </div>
  );
}
