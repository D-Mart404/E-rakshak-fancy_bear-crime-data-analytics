"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import PageHeader from "@/components/PageHeader";
import { apiFetch } from "@/lib/api";

type ListResponse = {
  items: Array<Record<string, unknown>>;
  pagination: { page: number; pages: number; total: number };
};

function EntitiesInner() {
  const initialQ = useSearchParams().get("q") ?? "";
  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [q, setQ] = useState(initialQ);
  const [searchInput, setSearchInput] = useState(initialQ);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (q.trim()) params.set("q", q.trim());
    try {
      setData(await apiFetch<ListResponse>(`/api/entities?${params}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [page, q, limit]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Evidence table · people"
        title="People & bank accounts"
        description="Account holders linked to this case."
        dataType="Entities (people / firms)"
        dataHint=""
      />

      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search entity name, ID, phone, PAN..."
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
        columns={[
          { key: "entity_id", label: "Entity ID" },
          { key: "entity_name", label: "Name" },
          { key: "is_seed", label: "Seed?" },
          { key: "account_role", label: "Role" },
        ]}
        rows={
          (data?.items ?? []).map((item) => ({
            ...item,
            is_seed: item.is_seed ? "Yes" : "No",
            phones: Array.isArray(item.phones) ? item.phones.join(", ") : "",
          }))
        }
        rowHref={(row) =>
          row.entity_id
            ? `/entities/${encodeURIComponent(String(row.entity_id))}`
            : null
        }
      />
    </div>
  );
}

export default function EntitiesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400">Loading…</div>}>
      <EntitiesInner />
    </Suspense>
  );
}
