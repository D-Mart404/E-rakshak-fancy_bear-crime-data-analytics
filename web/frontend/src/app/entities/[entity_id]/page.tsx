"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import DetailPanel from "@/components/DetailPanel";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import RiskDecompositionPanel, {
  type RiskProfile,
} from "@/components/RiskDecompositionPanel";
import { apiFetch } from "@/lib/api";

type EntityDetail = {
  entity: Record<string, unknown>;
  related: {
    transaction_count: number;
    telecom_count: number;
    recent_transactions: Array<Record<string, unknown>>;
    recent_telecom: Array<Record<string, unknown>>;
  };
};

export default function EntityDetailPage() {
  const params = useParams<{ entity_id: string }>();
  const entityId = params?.entity_id;
  const [data, setData] = useState<EntityDetail | null>(null);
  const [risk, setRisk] = useState<RiskProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entityId) return;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [json, riskJson] = await Promise.all([
          apiFetch<{
            entity: Record<string, unknown>;
            related: EntityDetail["related"];
          }>(`/api/entities/${encodeURIComponent(entityId)}`),
          apiFetch<{ risk_profile: RiskProfile }>(
            `/api/intelligence/risk/${encodeURIComponent(entityId)}`
          ).catch(() => null),
        ]);
        setData({ entity: json.entity, related: json.related });
        setRisk(riskJson?.risk_profile ?? null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [entityId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-center text-slate-400">
        Loading entity profile...
      </div>
    );
  }

  if (error || !data) {
    return <div className="text-red-300">{error ?? "Entity not found"}</div>;
  }

  const entity = data.entity;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-slate-400">Person / business profile</div>
          <h2 className="mt-1 text-2xl font-bold text-white">
            {String(entity.entity_name ?? entityId)}
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {data.related.transaction_count.toLocaleString()} transactions ·{" "}
            {data.related.telecom_count.toLocaleString()} telecom events
            {risk
              ? ` · Risk ${risk.risk_score}/100 (${risk.risk_category})`
              : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/investigation/${encodeURIComponent(String(entityId))}`}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
          >
            Investigation report
          </Link>
          <Link
            href={`/investigation/${encodeURIComponent(String(entityId))}/graph`}
            className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15"
          >
            Network graph
          </Link>
          <Link
            href="/entities"
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            ← All entities
          </Link>
        </div>
      </div>

      {risk ? <RiskDecompositionPanel profile={risk} /> : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Transactions</div>
          <div className="mt-2 text-2xl font-bold text-white">
            {data.related.transaction_count.toLocaleString()}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Telecom events</div>
          <div className="mt-2 text-2xl font-bold text-white">
            {data.related.telecom_count.toLocaleString()}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Seed suspect?</div>
          <div className="mt-2 text-2xl font-bold text-white">
            {entity.is_seed ? "Yes" : "No"}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Role</div>
          <div className="mt-2 text-lg font-bold text-white">
            {String(risk?.account_role ?? entity.account_role ?? "—")}
          </div>
        </div>
      </div>

      <DetailPanel
        title="Identity & accounts"
        subtitle="From FIR and bank ingestion"
        fields={[
          { label: "Entity ID", value: entity.entity_id },
          { label: "Full name", value: entity.entity_name },
          { label: "PAN", value: entity.pan },
          { label: "Phone numbers", value: entity.phones },
          { label: "Bank accounts", value: entity.accounts },
          { label: "Address", value: entity.address },
          { label: "FIR reference", value: entity.fir_id },
          { label: "Risk flags", value: entity.risk_flags },
        ]}
      />

      <div>
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-bold text-white">Recent bank transactions</h3>
          {Array.isArray(entity.accounts) && entity.accounts.length > 0 ? (
            <Link
              href={`/transactions?account_id=${encodeURIComponent(
                String(
                  (entity.accounts as Array<{ account_id?: string }>)[0]
                    ?.account_id ?? ""
                )
              )}`}
              className="text-xs font-semibold text-indigo-300"
            >
              View all for first account →
            </Link>
          ) : null}
        </div>
        <div className="mt-3">
          <PaginatedDataTable
            loading={false}
            page={1}
            totalPages={1}
            total={data.related.recent_transactions.length}
            onPageChange={() => {}}
            columns={[
              { key: "transaction_date", label: "Date" },
              { key: "transaction_id", label: "ID" },
              { key: "direction", label: "Dir" },
              { key: "amount", label: "Amount" },
              { key: "counterparty_name", label: "Counterparty" },
            ]}
            rows={data.related.recent_transactions}
            rowHref={(row) =>
              row.transaction_id
                ? `/transactions/${encodeURIComponent(String(row.transaction_id))}`
                : null
            }
          />
        </div>
      </div>

      <div>
        <h3 className="text-lg font-bold text-white">Recent calls & data sessions</h3>
        <div className="mt-3">
          <PaginatedDataTable
            loading={false}
            page={1}
            totalPages={1}
            total={data.related.recent_telecom.length}
            onPageChange={() => {}}
            columns={[
              { key: "timestamp", label: "Time" },
              { key: "event_type", label: "Type" },
              { key: "msisdn", label: "Phone" },
              { key: "b_party", label: "B-Party" },
              { key: "duration_sec", label: "Duration" },
            ]}
            rows={data.related.recent_telecom}
            rowHref={(row) =>
              row.event_id
                ? `/telecom/${encodeURIComponent(String(row.event_id))}`
                : null
            }
          />
        </div>
      </div>
    </div>
  );
}
