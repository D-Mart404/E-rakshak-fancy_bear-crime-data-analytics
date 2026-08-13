"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import { apiFetch } from "@/lib/api";

type EntityReport = {
  status: string;
  entity: {
    entity_id: string;
    entity_name?: string;
    phones?: string[];
    accounts?: Array<{ account_id?: string; account_number?: string; bank_name?: string }>;
  };
  analytics: {
    transactions: {
      total_transactions: number;
      by_direction: Array<{ _id: string; count: number; totalAmount: number }>;
      top_counterparties: Array<{
        _id: string;
        count: number;
        totalAmount: number;
      }>;
    };
    telecom: {
      by_event_type: Array<{
        _id: string;
        count: number;
        cdrDurationTotalSec: number;
        ipdrDataVolumeTotal: number;
      }>;
      cdr_total_duration_sec: number;
      ipdr_total_data_volume: number;
    };
  };
};

export default function InvestigationEntityPage() {
  const router = useRouter();
  const params = useParams<{ entity_id: string }>();
  const entityId = params?.entity_id;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<EntityReport | null>(null);

  useEffect(() => {
    if (!entityId) return;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<EntityReport>(
          `/api/investigation/entity/${encodeURIComponent(entityId)}`
        );
        setReport(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        setReport(null);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [entityId]);

  const primaryAccountId = report?.entity?.accounts?.[0]?.account_id;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-200">
            Deep investigation report
          </div>
          <div className="mt-1 text-2xl font-bold text-white">
            {report?.entity?.entity_name ?? entityId}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            ID: {entityId}
            {report?.entity?.phones?.length
              ? ` · Phones: ${report.entity.phones.join(", ")}`
              : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Link
            href={`/entities/${encodeURIComponent(String(entityId))}`}
            className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15"
          >
            Full profile
          </Link>
          <button
            onClick={() =>
              router.push(
                `/investigation/${encodeURIComponent(entityId)}/graph`
              )
            }
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Network graph
          </button>
          {primaryAccountId ? (
            <Link
              href={`/transactions?account_id=${encodeURIComponent(primaryAccountId)}`}
              className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
            >
              All transactions
            </Link>
          ) : null}
          <button
            onClick={() => router.push("/")}
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            Dashboard
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-6">
          Loading report...
        </div>
      ) : null}

      {error ? <div className="text-red-300">{error}</div> : null}

      {report ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
              <div className="text-xs text-slate-400">Total transactions</div>
              <div className="mt-2 text-2xl font-bold text-white">
                {report.analytics.transactions.total_transactions.toLocaleString()}
              </div>
            </div>
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
              <div className="text-xs text-slate-400">Call time (CDR)</div>
              <div className="mt-2 text-2xl font-bold text-white">
                {report.analytics.telecom.cdr_total_duration_sec.toLocaleString()} sec
              </div>
            </div>
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
              <div className="text-xs text-slate-400">Data volume (IPDR)</div>
              <div className="mt-2 text-2xl font-bold text-white">
                {report.analytics.telecom.ipdr_total_data_volume.toLocaleString()}
              </div>
            </div>
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
              <div className="text-xs text-slate-400">Bank accounts</div>
              <div className="mt-2 text-lg font-bold text-white">
                {report.entity.accounts?.length ?? 0}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5 lg:col-span-1">
              <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Money in vs out
              </div>
              <div className="mt-3 space-y-2">
                {report.analytics.transactions.by_direction.length ? (
                  report.analytics.transactions.by_direction.map((d) => (
                    <div key={d._id} className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">
                        {d._id === "CR" ? "Credits (received)" : d._id === "DR" ? "Debits (sent)" : d._id}
                      </span>
                      <span className="text-sm font-semibold text-white">
                        {d.count} · ₹{Math.round(d.totalAmount).toLocaleString()}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-slate-500">No transactions found.</div>
                )}
              </div>
            </section>

            <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5 lg:col-span-1">
              <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Calls & internet usage
              </div>
              <div className="mt-3 space-y-2">
                {report.analytics.telecom.by_event_type.length ? (
                  report.analytics.telecom.by_event_type.map((x) => (
                    <div key={x._id} className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">{x._id}</span>
                      <span className="text-sm font-semibold text-white">
                        {x.count.toLocaleString()} events
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-slate-500">No telecom events for linked phones.</div>
                )}
              </div>
            </section>

            <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5 lg:col-span-1">
              <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Linked bank accounts
              </div>
              <div className="mt-3 space-y-2">
                {(report.entity.accounts ?? []).map((acc) => (
                  <Link
                    key={acc.account_id}
                    href={`/transactions?account_id=${encodeURIComponent(String(acc.account_id ?? ""))}`}
                    className="block rounded-lg border border-white/10 bg-white/5 p-3 hover:bg-indigo-500/10"
                  >
                    <div className="text-sm font-semibold text-white">
                      {acc.bank_name ?? "Bank"}
                    </div>
                    <div className="text-xs text-slate-400">
                      {acc.account_number ?? acc.account_id}
                    </div>
                    <div className="mt-1 text-[11px] text-indigo-300">
                      View all transactions →
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          </div>

          <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
            <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Top counterparties (who they paid or received from most)
            </div>
            <div className="mt-3">
              <PaginatedDataTable
                loading={false}
                page={1}
                totalPages={1}
                total={report.analytics.transactions.top_counterparties.length}
                onPageChange={() => {}}
                columns={[
                  { key: "_id", label: "Counterparty" },
                  { key: "count", label: "Transactions" },
                  { key: "totalAmount", label: "Total ₹" },
                ]}
                rows={report.analytics.transactions.top_counterparties.map((c) => ({
                  ...c,
                  totalAmount: Math.round(c.totalAmount).toLocaleString(),
                }))}
                emptyMessage="No counterparties found."
              />
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
