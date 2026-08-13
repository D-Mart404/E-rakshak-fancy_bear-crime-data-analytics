"use client";

import { memo } from "react";
import Link from "next/link";
import type { Node } from "@xyflow/react";

type GraphNodeData = {
  label: string;
  nodeType: string;
  riskScore: number;
  metadata?: Record<string, unknown>;
};

function hrefForNode(data: GraphNodeData): string {
  const meta = data.metadata ?? {};
  const type = data.nodeType;
  if (type === "entity" || type === "person") {
    const eid = String(meta.entity_id ?? "");
    return eid ? `/entities/${encodeURIComponent(eid)}` : "/entities";
  }
  if (type === "account" || type === "counterparty_account") {
    const acct = String(meta.account_id ?? meta.counterparty_account ?? data.label ?? "");
    return acct ? `/transactions?account_id=${encodeURIComponent(acct)}` : "/transactions";
  }
  if (type === "phone") {
    return `/telecom?q=${encodeURIComponent(String(meta.msisdn ?? data.label ?? ""))}`;
  }
  if (type === "ip") {
    return `/telecom?event_type=IPDR&q=${encodeURIComponent(String(meta.ip_address ?? data.label ?? ""))}`;
  }
  return `/entities?q=${encodeURIComponent(data.label)}`;
}

function NodeDetailPanel({
  node,
  onClose,
}: {
  node: Node | null;
  onClose: () => void;
}) {
  if (!node) return null;

  const data = node.data as GraphNodeData;
  const metadata = data.metadata ?? {};
  const href = hrefForNode(data);

  return (
    <aside className="absolute right-0 top-0 z-20 h-full w-full max-w-md border-l border-slate-700/60 bg-slate-900/95 p-5 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">{data.nodeType}</div>
          <Link
            href={href}
            className="mt-1 block text-lg font-bold text-white hover:text-indigo-300 hover:underline"
          >
            {data.label}
          </Link>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg bg-white/10 px-3 py-1 text-xs font-semibold text-white hover:bg-white/20"
        >
          Close
        </button>
      </div>

      <Link
        href={href}
        className="mt-4 block rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4 hover:bg-indigo-500/20"
      >
        <div className="text-xs text-slate-300">Risk score</div>
        <div className="mt-1 text-3xl font-bold text-white">{data.riskScore}</div>
      </Link>

      <div className="mt-4">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Metadata</div>
        <div className="mt-2 space-y-2">
          {Object.entries(metadata).map(([key, value]) => {
            const text = typeof value === "object" ? JSON.stringify(value) : String(value);
            const looksId =
              /account|entity|msisdn|phone|ip|transaction/i.test(key) && text && text !== "null";
            return (
              <div
                key={key}
                className="flex items-start justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-2"
              >
                <span className="text-xs text-slate-400">{key}</span>
                {looksId ? (
                  <Link href={href} className="text-right text-xs font-medium text-indigo-300 hover:underline">
                    {text}
                  </Link>
                ) : (
                  <span className="text-right text-xs font-medium text-slate-100">{text}</span>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <Link
        href={href}
        className="mt-4 inline-block rounded-md bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
      >
        Open records
      </Link>
    </aside>
  );
}

export default memo(NodeDetailPanel);
