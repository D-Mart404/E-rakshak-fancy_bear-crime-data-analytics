"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import PaginatedDataTable from "@/components/PaginatedDataTable";

type IpdrSummary = {
  stats: { total: number; with_phone: number };
  top_ips: Array<{ ip: string; count: number; phones: string[] }>;
  top_phones: Array<{
    msisdn: string;
    sessions: number;
    data_volume_up: number;
    data_volume_down: number;
  }>;
  recent: Array<Record<string, unknown>>;
};

export default function IpdrPage() {
  const [data, setData] = useState<IpdrSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<IpdrSummary>("/api/intelligence/ipdr/summary")
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load IPDR")
      );
  }, []);

  if (error) return <div className="text-red-300">{error}</div>;
  if (!data) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-slate-400">
        Loading IPDR intelligence...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">IPDR Internet Sessions</h2>
          <p className="mt-1 text-sm text-slate-400">
            Internet Protocol Detail Records — IP address, cell tower, upload/download volume linked to case phones.
          </p>
        </div>
        <Link
          href="/telecom?event_type=IPDR"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
        >
          Browse all IPDR rows
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Total IPDR sessions</div>
          <div className="mt-2 text-2xl font-bold text-white">{data.stats.total}</div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">With phone number</div>
          <div className="mt-2 text-2xl font-bold text-white">{data.stats.with_phone}</div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Distinct IPs</div>
          <div className="mt-2 text-2xl font-bold text-white">{data.top_ips.length}</div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4">
          <div className="text-xs text-slate-400">Active phones</div>
          <div className="mt-2 text-2xl font-bold text-white">{data.top_phones.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
          <h3 className="text-sm font-semibold text-cyan-300">Top IP addresses</h3>
          <div className="mt-3 space-y-2">
            {data.top_ips.map((row) => (
              <div
                key={row.ip}
                className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs"
              >
                <div className="font-semibold text-white break-all">{row.ip}</div>
                <div className="mt-1 text-slate-400">
                  {row.count} sessions · phones: {row.phones.slice(0, 3).join(", ") || "—"}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
          <h3 className="text-sm font-semibold text-cyan-300">Phones with most IPDR activity</h3>
          <div className="mt-3 space-y-2">
            {data.top_phones.map((row) => (
              <div
                key={row.msisdn}
                className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs"
              >
                <div className="font-semibold text-white">{row.msisdn}</div>
                <div className="mt-1 text-slate-400">
                  {row.sessions} sessions · ↑{Math.round(row.data_volume_up || 0).toLocaleString()}{" "}
                  ↓{Math.round(row.data_volume_down || 0).toLocaleString()}
                </div>
                <Link
                  href={`/telecom?q=${encodeURIComponent(row.msisdn)}`}
                  className="mt-1 inline-block text-indigo-300"
                >
                  View sessions →
                </Link>
              </div>
            ))}
            {!data.top_phones.length ? (
              <div className="text-sm text-amber-200">
                Many IPDR rows had empty MSISDN in the source CSV. Reload data after phone normalization,
                or browse all IPDR rows by IP address.
              </div>
            ) : null}
          </div>
        </section>
      </div>

      <section>
        <h3 className="mb-3 text-lg font-bold text-white">Recent IPDR records</h3>
        <PaginatedDataTable
          loading={false}
          page={1}
          totalPages={1}
          total={data.recent.length}
          onPageChange={() => {}}
          columns={[
            { key: "timestamp", label: "Start" },
            { key: "msisdn", label: "Phone" },
            { key: "ip_address", label: "IP Address" },
            { key: "cell_id", label: "Cell ID" },
            { key: "duration_sec", label: "Duration" },
            { key: "data_volume_down", label: "Download" },
          ]}
          rows={data.recent}
          rowHref={(row) =>
            row.event_id
              ? `/telecom/${encodeURIComponent(String(row.event_id))}`
              : null
          }
        />
      </section>
    </div>
  );
}
