"use client";

import { memo, useMemo, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export type DataColumn = {
  key: string;
  label: string;
  render?: (value: unknown, row: Record<string, unknown>) => ReactNode;
};

type PaginatedDataTableProps = {
  columns: DataColumn[];
  rows: Array<Record<string, unknown>>;
  emptyMessage?: string;
  rowHref?: (row: Record<string, unknown>) => string | null;
  rowClassName?: (row: Record<string, unknown>) => string | undefined;
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
  loading?: boolean;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
};

function PaginatedDataTable({
  columns,
  rows,
  emptyMessage = "No records found.",
  rowHref,
  rowClassName,
  page,
  totalPages,
  total,
  onPageChange,
  loading = false,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100, 250],
}: PaginatedDataTableProps) {
  const router = useRouter();
  const visibleColumns = useMemo(() => columns, [columns]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>
          Showing page <span className="text-white font-semibold">{page}</span> of{" "}
          <span className="text-white font-semibold">{totalPages}</span> —{" "}
          <span className="text-white font-semibold">{total.toLocaleString()}</span> total records
        </span>
        <div className="flex items-center gap-3">
          {onPageSizeChange && pageSize ? (
            <label className="flex items-center gap-2 text-[11px] text-slate-400">
              Rows
              <select
                value={pageSize}
                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-white"
              >
                {pageSizeOptions.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="flex gap-2">
            <button
              disabled={page <= 1 || loading}
              onClick={() => onPageChange(page - 1)}
              className="rounded-lg bg-white/10 px-3 py-1 text-white disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages || loading}
              onClick={() => onPageChange(page + 1)}
              className="rounded-lg bg-white/10 px-3 py-1 text-white disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-center text-slate-400">
          Loading records...
        </div>
      ) : !rows.length ? (
        <div className="text-sm text-slate-500">{emptyMessage}</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700/50">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900/80 text-xs uppercase tracking-wider text-slate-400">
              <tr>
                {visibleColumns.map((col) => (
                  <th key={col.key} className="px-4 py-3 font-medium">
                    {col.label}
                  </th>
                ))}
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const href = rowHref?.(row);
                const extra = rowClassName?.(row) ?? "";
                return (
                  <tr
                    key={String(
                      row.transaction_id ?? row.event_id ?? row.entity_id ?? idx
                    )}
                    className={`border-t border-slate-700/40 bg-slate-800/30 hover:bg-indigo-500/10 ${extra} ${
                      href ? "cursor-pointer" : ""
                    }`}
                    onMouseEnter={() => {
                      if (href) router.prefetch(href);
                    }}
                    onClick={() => {
                      if (href) router.push(href);
                    }}
                  >
                    {visibleColumns.map((col) => (
                      <td
                        key={col.key}
                        className="px-4 py-3 text-slate-200 max-w-[280px] truncate"
                      >
                        {col.render
                          ? col.render(row[col.key], row)
                          : String(row[col.key] ?? "")}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      {href ? (
                        <Link
                          href={href}
                          prefetch
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs font-semibold text-indigo-300 hover:text-indigo-200"
                        >
                          View details →
                        </Link>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default memo(PaginatedDataTable);
