"use client";

import { memo } from "react";
import Link from "next/link";

type FlaggedRecordsTableProps = {
  records: Array<Record<string, unknown>>;
  presetKey: string;
};

function summarizeRecord(record: Record<string, unknown>, presetKey: string) {
  if (presetKey === "rapid_layering_mules") {
    return {
      id: String(record.transaction_id ?? ""),
      title: `Transaction ${record.transaction_id ?? "—"}`,
      detail: `Outgoing/Ingoing ratio: ${Number(record.outgoing_to_incoming_ratio ?? 0).toFixed(2)} | Credit ₹${record.rolling_credit} | Debit ₹${record.rolling_debit}`,
      href: record.transaction_id
        ? `/transactions/${encodeURIComponent(String(record.transaction_id))}`
        : null,
    };
  }
  if (presetKey === "multi_seed_convergence") {
    const dest = record.destination_key ?? record.destination_account ?? "—";
    return {
      id: String(dest),
      title: `Hub: ${dest}`,
      detail: `${record.distinct_source_count} sources | ${record.transaction_count} tx | ₹${record.total_amount}`,
      href: null,
    };
  }
  if (presetKey === "call_transfer_coincidences") {
    return {
      id: String(record.transaction_id ?? ""),
      title: `Call → Transfer: ${record.transaction_id ?? "—"}`,
      detail: `${record.matching_call_count ?? 0} matching calls | Amount ₹${record.amount}`,
      href: record.transaction_id
        ? `/transactions/${encodeURIComponent(String(record.transaction_id))}`
        : null,
    };
  }
  return {
    id: "record",
    title: "Flagged record",
    detail: JSON.stringify(record),
    href: null,
  };
}

function FlaggedRecordsTable({ records, presetKey }: FlaggedRecordsTableProps) {
  if (!records.length) {
    return (
      <div className="text-sm text-slate-500">
        No records matched current thresholds for this seed.
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      {records.slice(0, 10).map((record, idx) => {
        const row = summarizeRecord(record, presetKey);
        return (
          <div
            key={`${row.id}-${idx}`}
            className="rounded-lg border border-white/10 bg-white/5 p-3"
          >
            <div className="text-sm font-semibold text-white">{row.title}</div>
            <div className="mt-1 text-xs text-slate-400">{row.detail}</div>
            {row.href ? (
              <Link
                href={row.href}
                className="mt-2 inline-block text-xs font-semibold text-indigo-300 hover:text-indigo-200"
              >
                Open full transaction details →
              </Link>
            ) : null}
          </div>
        );
      })}
      {records.length > 10 ? (
        <div className="text-xs text-slate-500">
          + {records.length - 10} more flagged records (refine seed or export via API)
        </div>
      ) : null}
    </div>
  );
}

export default memo(FlaggedRecordsTable);
