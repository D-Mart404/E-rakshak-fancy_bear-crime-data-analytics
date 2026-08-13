"use client";

import { memo, useMemo } from "react";

type DataTableProps = {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  emptyMessage?: string;
};

function DataTable({
  columns,
  rows,
  emptyMessage = "No records found.",
}: DataTableProps) {
  const visibleColumns = useMemo(() => columns.slice(0, 8), [columns]);

  if (!rows.length) {
    return <div className="text-sm text-slate-500">{emptyMessage}</div>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-700/50">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-900/80 text-xs uppercase tracking-wider text-slate-400">
          <tr>
            {visibleColumns.map((col) => (
              <th key={col} className="px-4 py-3 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={idx}
              className="border-t border-slate-700/40 bg-slate-800/30 hover:bg-slate-800/60"
            >
              {visibleColumns.map((col) => (
                <td key={col} className="px-4 py-3 text-slate-200">
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default memo(DataTable);
