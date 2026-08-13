"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import DetailPanel from "@/components/DetailPanel";

type CaseDetail = {
  case: Record<string, unknown> & {
    case_id: string;
    title?: string;
    status?: string;
    stats?: Record<string, number>;
  };
  seed_entities: Array<{
    entity_id: string;
    entity_name?: string;
    phones?: string[];
  }>;
  recent_audit: Array<{ timestamp: string; user: string; action: string }>;
};

export default function CaseDetailPage() {
  const params = useParams<{ case_id: string }>();
  const caseId = params?.case_id;
  const router = useRouter();
  const [data, setData] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    apiFetch<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load case")
      );
  }, [caseId]);

  const openWorkspace = async () => {
    if (!caseId) return;
    await apiFetch(`/api/cases/${encodeURIComponent(caseId)}/open`, {
      method: "POST",
    });
    router.push("/");
  };

  if (error) return <div className="text-red-300">{error}</div>;
  if (!data) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-slate-400">
        Loading case...
      </div>
    );
  }

  const c = data.case;
  const stats = c.stats || {};

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-cyan-400">
            Case dossier
          </div>
          <h2 className="mt-1 text-2xl font-bold text-white">{c.case_id}</h2>
          <p className="mt-1 text-sm text-slate-400">{String(c.title || "")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => void openWorkspace()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
          >
            Open as active workspace
          </button>
          <Link
            href="/cases"
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white"
          >
            ← All cases
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {[
          ["Seeds", stats.seed_count],
          ["Entities", stats.entity_count],
          ["Transactions", stats.transaction_count],
          ["CDR", stats.cdr_count],
          ["IPDR", stats.ipdr_count],
          ["Audit", stats.audit_entries],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4"
          >
            <div className="text-xs text-slate-400">{label}</div>
            <div className="mt-2 text-xl font-bold text-white">
              {Number(value || 0).toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      <DetailPanel
        title="Case identity"
        fields={[
          { label: "Case ID", value: c.case_id },
          { label: "FIR number", value: c.fir_number },
          { label: "Status", value: c.status },
          { label: "Unit", value: c.unit },
          { label: "Lead investigator", value: c.lead_investigator },
          { label: "Police station", value: c.police_station },
          { label: "Created", value: c.created_at },
          { label: "Updated", value: c.updated_at },
          { label: "Last opened", value: c.last_opened_at },
          { label: "Notes", value: c.notes },
        ]}
      />

      <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
        <h3 className="text-sm font-semibold text-cyan-300">Linked seed suspects</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {data.seed_entities.length ? (
            data.seed_entities.map((s) => (
              <Link
                key={s.entity_id}
                href={`/entities/${encodeURIComponent(s.entity_id)}`}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 hover:bg-indigo-500/20"
              >
                {s.entity_name || s.entity_id}
              </Link>
            ))
          ) : (
            <div className="text-sm text-slate-500">
              No seed entities linked yet. Open Command Center after assigning seeds.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
        <h3 className="text-sm font-semibold text-cyan-300">Recent case audit</h3>
        <div className="mt-3 space-y-2">
          {data.recent_audit.map((a, idx) => (
            <div
              key={`${a.timestamp}-${idx}`}
              className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs"
            >
              <div className="text-slate-500">
                {a.timestamp} · {a.user}
              </div>
              <div className="mt-1 text-slate-200">{a.action}</div>
            </div>
          ))}
          {!data.recent_audit.length ? (
            <div className="text-sm text-slate-500">No audit entries for this case yet.</div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
