import type { ReactNode } from "react";

export function DirectionBadge(value: unknown): ReactNode {
  const dir = String(value ?? "").toUpperCase();
  if (dir === "CR" || dir.includes("CREDIT") || dir.includes("INCOMING")) {
    return (
      <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-200">
        {dir === "CR" ? "CR" : dir.slice(0, 8)}
      </span>
    );
  }
  if (dir === "DR" || dir.includes("DEBIT") || dir.includes("OUTGOING")) {
    return (
      <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[11px] font-semibold text-rose-200">
        {dir === "DR" ? "DR" : dir.slice(0, 8)}
      </span>
    );
  }
  if (!dir) return <span className="text-slate-500">—</span>;
  return (
    <span className="rounded-full bg-slate-500/20 px-2 py-0.5 text-[11px] text-slate-300">
      {dir}
    </span>
  );
}

export function EventTypeBadge(value: unknown): ReactNode {
  const t = String(value ?? "").toUpperCase();
  if (t === "CDR") {
    return (
      <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-[11px] font-semibold text-cyan-200">
        CDR
      </span>
    );
  }
  if (t === "IPDR") {
    return (
      <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[11px] font-semibold text-violet-200">
        IPDR
      </span>
    );
  }
  return <span className="text-slate-400">{t || "—"}</span>;
}

export function formatAmount(value: unknown): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "");
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function isSuspiciousTransaction(row: Record<string, unknown>): boolean {
  const amount = Number(row.amount ?? 0);
  const dir = String(row.direction ?? "").toUpperCase();
  return amount >= 100000 || (dir === "DR" && amount >= 50000);
}

export function isSuspiciousTelecom(row: Record<string, unknown>): boolean {
  const type = String(row.call_type ?? "").toUpperCase();
  let dur = Number(row.duration_sec ?? 0);
  if (!dur && row.duration_sec != null) {
    const m = String(row.duration_sec).match(/(\d+)/);
    dur = m ? Number(m[1]) : 0;
  }
  const b = String(row.b_party ?? "");
  if (type.includes("OUT") && dur >= 300) return true;
  if (dur >= 1800) return true;
  if (b && b.length <= 4 && type.includes("OUT")) return true;
  return false;
}
