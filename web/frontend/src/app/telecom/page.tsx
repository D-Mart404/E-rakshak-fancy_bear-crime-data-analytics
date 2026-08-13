"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import PageHeader from "@/components/PageHeader";
import { apiFetch } from "@/lib/api";
import {
  DirectionBadge,
  EventTypeBadge,
  formatAmount,
  isSuspiciousTelecom,
} from "@/lib/evidenceFormat";

type ListResponse = {
  items: Array<Record<string, unknown>>;
  pagination: { page: number; pages: number; total: number };
  sort?: string;
};

const POLL_MS = 20_000;

function TelecomPageContent() {
  const searchParams = useSearchParams();
  const initialType = searchParams.get("event_type") ?? "";
  const initialQ = searchParams.get("q") ?? "";

  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [q, setQ] = useState(initialQ);
  const [searchInput, setSearchInput] = useState(initialQ);
  const [eventType, setEventType] = useState(initialType);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState("");

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (q.trim()) params.set("q", q.trim());
      if (eventType) params.set("event_type", eventType);
      try {
        const json = await apiFetch<ListResponse>(`/api/telecom?${params}`);
        setData(json);
        setUpdatedAt(new Date().toLocaleTimeString());
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        if (!silent) setData(null);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [page, q, eventType, limit]
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => void load(true), POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Evidence table · phones"
        title="Phone calls (CDR) & internet (IPDR)"
        description="CDR and IPDR, newest first."
        dataType={
          eventType === "IPDR"
            ? "IPDR"
            : eventType === "CDR"
              ? "CDR"
              : "CDR + IPDR"
        }
        dataHint={
          updatedAt
            ? `Live · last refresh ${updatedAt}`
            : "Sorted by time descending"
        }
      />

      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search phone, B-party, IP, event ID..."
          className="w-full rounded-lg border border-slate-700/60 bg-slate-950/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400 md:flex-1"
        />
        <select
          value={eventType}
          onChange={(e) => {
            setPage(1);
            setEventType(e.target.value);
          }}
          className="rounded-lg border border-slate-700/60 bg-slate-950/30 px-3 py-2 text-sm text-white"
        >
          <option value="">All types</option>
          <option value="CDR">CDR only</option>
          <option value="IPDR">IPDR only</option>
        </select>
        <button
          onClick={() => {
            setPage(1);
            setQ(searchInput);
          }}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
        >
          Search
        </button>
        <button
          onClick={() => void load()}
          className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white"
        >
          Refresh now
        </button>
      </div>

      {error ? <div className="text-red-300">{error}</div> : null}

      <PaginatedDataTable
        loading={loading}
        page={data?.pagination.page ?? page}
        totalPages={data?.pagination.pages ?? 1}
        total={data?.pagination.total ?? 0}
        onPageChange={setPage}
        pageSize={limit}
        onPageSizeChange={(size) => {
          setPage(1);
          setLimit(size);
        }}
        rowClassName={(row) =>
          isSuspiciousTelecom(row)
            ? "bg-amber-500/10 ring-1 ring-inset ring-amber-500/30"
            : undefined
        }
        columns={[
          { key: "timestamp", label: "Time" },
          {
            key: "event_type",
            label: "Type",
            render: (v) => EventTypeBadge(v),
          },
          { key: "msisdn", label: "Phone (A)" },
          {
            key: "b_party",
            label: "B-Party / IP",
            render: (v, row) =>
              String(row.event_type) === "IPDR"
                ? String(row.ip_address ?? v ?? "")
                : String(v ?? ""),
          },
          {
            key: "call_type",
            label: "Dir",
            render: (v) => DirectionBadge(v),
          },
          { key: "duration_sec", label: "Duration" },
        ]}
        rows={data?.items ?? []}
        rowHref={(row) =>
          row.event_id
            ? `/telecom/${encodeURIComponent(String(row.event_id))}`
            : null
        }
      />
    </div>
  );
}

export default function TelecomPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-center text-slate-400">
          Loading telecom...
        </div>
      }
    >
      <TelecomPageContent />
    </Suspense>
  );
}
