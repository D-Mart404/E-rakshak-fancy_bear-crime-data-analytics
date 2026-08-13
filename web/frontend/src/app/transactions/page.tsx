"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import PageHeader from "@/components/PageHeader";
import { apiFetch } from "@/lib/api";
import {
  DirectionBadge,
  formatAmount,
  isSuspiciousTransaction,
} from "@/lib/evidenceFormat";

type ListResponse = {
  items: Array<Record<string, unknown>>;
  pagination: {
    page: number;
    pages: number;
    total: number;
  };
  sort?: string;
};

const POLL_MS = 20_000;

function TransactionsPageContent() {
  const searchParams = useSearchParams();
  const accountFilter = searchParams.get("account_id") ?? "";

  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [q, setQ] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<string>("");

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (q.trim()) params.set("q", q.trim());
      if (accountFilter) params.set("account_id", accountFilter);
      try {
        const json = await apiFetch<ListResponse>(`/api/transactions?${params}`);
        setData(json);
        setUpdatedAt(new Date().toLocaleTimeString());
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        if (!silent) setData(null);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [page, q, accountFilter, limit]
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void load(true);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Evidence table · money"
        title="Bank transactions"
        description="Bank movements, newest first."
        dataType="Bank transactions"
        dataHint={
          accountFilter
            ? `Filtered to account ${accountFilter}`
            : updatedAt
              ? `Live · last refresh ${updatedAt}`
              : "Sorted by date descending"
        }
      />

      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search transaction ID, account, counterparty, narration..."
          className="w-full rounded-lg border border-slate-700/60 bg-slate-950/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400 md:flex-1"
        />
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
          isSuspiciousTransaction(row)
            ? "bg-amber-500/10 ring-1 ring-inset ring-amber-500/30"
            : undefined
        }
        columns={[
          { key: "transaction_date", label: "Date" },
          { key: "transaction_id", label: "Transaction ID" },
          { key: "account_id", label: "Account" },
          {
            key: "direction",
            label: "Dir",
            render: (v) => DirectionBadge(v),
          },
          {
            key: "amount",
            label: "Amount (₹)",
            render: (v) => formatAmount(v),
          },
          { key: "counterparty_name", label: "Counterparty / Narration" },
          { key: "mode", label: "Mode" },
        ]}
        rows={data?.items ?? []}
        rowHref={(row) =>
          row.transaction_id
            ? `/transactions/${encodeURIComponent(String(row.transaction_id))}`
            : null
        }
      />
    </div>
  );
}

export default function TransactionsPage() {
  return (
    <Suspense
      fallback={<div className="p-6 text-sm text-slate-400">Loading transactions…</div>}
    >
      <TransactionsPageContent />
    </Suspense>
  );
}
