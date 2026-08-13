"use client";

import Link from "next/link";

type BreakdownRow = {
  evidence: string;
  finding: string;
  points: number;
  href?: string;
  href_label?: string;
};

export type RiskProfile = {
  entity_id: string;
  entity_name?: string;
  is_seed: boolean;
  account_role?: string;
  risk_score: number;
  risk_category: string;
  transaction_count: number;
  inflow: number;
  outflow: number;
  pass_through_ratio: number;
  cdr_count: number;
  ipdr_count: number;
  primary_account_id?: string;
  flow_stats?: { pass_through_ratio: number; retained_amount: number; total_inflow: number; total_outflow: number };
  risk_decomposition?: {
    case_link?: number;
    network: number;
    transactions: number;
    behavior: number;
    communication: number;
    identifiers: number;
    breakdown_table: BreakdownRow[];
  };
  plain_language_narrative?: string;
  proof?: {
    deep_links?: Array<{ label: string; href: string }>;
    sample_transactions?: Array<{
      transaction_id?: string;
      amount?: number;
      direction?: string;
      transaction_date?: string;
      counterparty_name?: string;
      href?: string | null;
    }>;
    sample_telecom?: Array<{
      event_id?: string;
      event_type?: string;
      msisdn?: string;
      timestamp?: string;
      ip_address?: string;
      href?: string | null;
    }>;
  };
};

function badge(cat: string, seed: boolean) {
  if (seed || cat === "CRITICAL") return "bg-red-500/20 text-red-300";
  if (cat === "HIGH") return "bg-amber-500/20 text-amber-200";
  return "bg-cyan-500/15 text-cyan-300";
}

export default function RiskDecompositionPanel({ profile }: { profile: RiskProfile }) {
  const d = profile.risk_decomposition || {
    case_link: 0,
    network: 0,
    transactions: 0,
    behavior: 0,
    communication: 0,
    identifiers: 0,
    breakdown_table: [],
  };
  const caseLink = d.case_link ?? d.network;
  const passPct =
    profile.flow_stats?.pass_through_ratio ??
    Math.round((profile.pass_through_ratio || 0) * 100);
  const links = profile.proof?.deep_links || [];
  const txs = profile.proof?.sample_transactions || [];
  const tels = profile.proof?.sample_telecom || [];

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/entities/${encodeURIComponent(profile.entity_id)}`}
          className={`rounded px-2 py-0.5 text-[11px] font-semibold hover:underline ${badge(profile.risk_category, profile.is_seed)}`}
        >
          {profile.is_seed ? "FIR SEED" : profile.risk_category}
        </Link>
        <Link
          href={`/network?seed=${encodeURIComponent(profile.entity_id)}`}
          className="text-sm font-bold text-cyan-300 hover:underline"
        >
          {profile.risk_score}/100
        </Link>
      </div>
      <div className="mt-2 text-xs text-slate-400">
        Role:{" "}
        <Link
          href={`/entities/${encodeURIComponent(profile.entity_id)}`}
          className="font-semibold text-cyan-300 hover:underline"
        >
          {profile.account_role || "—"}
        </Link>
        {passPct ? (
          <Link
            href={
              profile.primary_account_id
                ? `/transactions?account_id=${encodeURIComponent(profile.primary_account_id)}`
                : "/transactions"
            }
            className="hover:underline"
          >
            {" "}
            · {passPct}%
          </Link>
        ) : null}
      </div>

      <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.02] p-3">
        <div className="mb-2 flex h-2.5 overflow-hidden rounded bg-white/5">
          <div className="bg-red-500" style={{ width: `${caseLink}%` }} />
          <div className="bg-orange-500" style={{ width: `${d.transactions}%` }} />
          <div className="bg-amber-500" style={{ width: `${d.behavior}%` }} />
          <div className="bg-blue-500" style={{ width: `${d.communication}%` }} />
          <div className="bg-emerald-500" style={{ width: `${d.identifiers}%` }} />
        </div>
        <div className="flex flex-wrap gap-x-3 text-[10px] text-slate-400">
          <span>Case {caseLink}</span>
          <span>Tx {d.transactions}</span>
          <span>Beh {d.behavior}</span>
          <span>Comm {d.communication}</span>
          <span>ID {d.identifiers}</span>
        </div>
      </div>

      {profile.plain_language_narrative ? (
        <p className="mt-3 rounded-lg border-l-4 border-cyan-400 bg-cyan-500/10 p-3 text-xs text-slate-300">
          <Link
            href={`/entities/${encodeURIComponent(profile.entity_id)}`}
            className="font-semibold text-white hover:underline"
          >
            {profile.entity_name || profile.entity_id}
          </Link>
          <span className="mt-1 block">{profile.plain_language_narrative}</span>
        </p>
      ) : null}

      <table className="mt-3 w-full text-left text-[11px]">
        <thead>
          <tr className="border-b border-white/10 text-slate-500">
            <th className="py-1 pr-2">Evidence</th>
            <th className="py-1 pr-2">Finding</th>
            <th className="py-1 pr-2 text-right">Pts</th>
            <th className="py-1 text-right">Proof</th>
          </tr>
        </thead>
        <tbody>
          {(d.breakdown_table || []).map((r, i) => {
            const inner = (
              <>
                <td className="py-1.5 pr-2 font-semibold text-white">{r.evidence}</td>
                <td className="py-1.5 pr-2 text-slate-400">{r.finding}</td>
                <td className="py-1.5 pr-2 text-right font-bold text-cyan-300">+{r.points}</td>
                <td className="py-1.5 text-right text-indigo-300">
                  {r.href ? r.href_label || "Open" : "—"}
                </td>
              </>
            );
            return r.href ? (
              <tr key={`${r.evidence}-${i}`} className="border-b border-white/[0.04]">
                <td colSpan={4} className="p-0">
                  <Link
                    href={r.href}
                    className="grid grid-cols-[1.2fr_1.4fr_48px_72px] items-center px-0 py-1.5 hover:bg-indigo-500/10"
                  >
                    <span className="pr-2 font-semibold text-white">{r.evidence}</span>
                    <span className="pr-2 text-slate-400">{r.finding}</span>
                    <span className="pr-2 text-right font-bold text-cyan-300">+{r.points}</span>
                    <span className="text-right text-indigo-300">{r.href_label || "Open"}</span>
                  </Link>
                </td>
              </tr>
            ) : (
              <tr key={`${r.evidence}-${i}`} className="border-b border-white/[0.04]">
                {inner}
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-3 flex flex-wrap gap-2">
        {(links.length
          ? links
          : [{ label: "Profile", href: `/entities/${profile.entity_id}` }]
        ).map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="rounded-md bg-indigo-600/90 px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-500"
          >
            {l.label} →
          </Link>
        ))}
      </div>

      {(txs.length > 0 || tels.length > 0) && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="max-h-44 space-y-1 overflow-y-auto">
            <div className="mb-1 text-[10px] uppercase text-slate-500">Proof transfers</div>
            {txs.map((t) => (
              <Link
                key={String(t.transaction_id)}
                href={t.href || "#"}
                className="block rounded border border-white/5 bg-white/[0.03] px-2 py-1.5 text-[11px] hover:bg-indigo-500/10"
              >
                <div className="flex justify-between gap-2">
                  <span className="text-slate-300">{t.direction} · {t.counterparty_name || "—"}</span>
                  <span className="text-emerald-300">₹ {Math.round(t.amount || 0).toLocaleString()}</span>
                </div>
              </Link>
            ))}
          </div>
          <div className="max-h-44 space-y-1 overflow-y-auto">
            <div className="mb-1 text-[10px] uppercase text-slate-500">Proof telecom</div>
            {tels.length ? (
              tels.map((e) => (
                <Link
                  key={String(e.event_id)}
                  href={e.href || "#"}
                  className="block rounded border border-white/5 bg-white/[0.03] px-2 py-1.5 text-[11px] hover:bg-indigo-500/10"
                >
                  <span className="text-violet-200">{e.event_type}</span>{" "}
                  <span className="text-slate-400">{e.msisdn}</span>
                </Link>
              ))
            ) : (
              <Link href="/telecom?event_type=IPDR" className="text-[11px] text-indigo-300 hover:underline">
                IPDR
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
