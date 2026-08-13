"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import GraphNode from "./GraphNode";
import NodeDetailPanel from "./NodeDetailPanel";
import { layoutGraph } from "@/lib/graphLayout";
import { apiFetch } from "@/lib/api";
import { formatAmount } from "@/lib/evidenceFormat";

const nodeTypes = { graphNode: GraphNode };

type GraphResponse = {
  status: string;
  entity_id: string;
  summary: {
    node_count: number;
    edge_count: number;
    transaction_count: number;
    counterparty_count: number;
    call_target_count: number;
  };
  nodes: Node[];
  edges: Edge[];
};

type HighlightRow = {
  id: string;
  label: string;
  kind: string;
  metric: string;
  detail: string;
  risk: number;
  href: string;
};

function buildHighlights(nodes: Node[]): HighlightRow[] {
  const rows: HighlightRow[] = [];
  for (const n of nodes) {
    const d = n.data as {
      label?: string;
      nodeType?: string;
      riskScore?: number;
      metadata?: Record<string, unknown>;
    };
    const meta = d.metadata ?? {};
    const type = d.nodeType ?? "";
    const risk = Number(d.riskScore ?? 0);

    if (type === "counterparty_account") {
      const amt = Number(meta.total_amount ?? 0);
      const txs = Number(meta.transaction_count ?? 0);
      const acct = String(meta.account_id ?? meta.counterparty_account ?? "");
      rows.push({
        id: n.id,
        label: String(d.label ?? meta.counterparty_name ?? "Counterparty"),
        kind: "Money",
        metric: `₹${formatAmount(amt)}`,
        detail: `${txs} transaction(s)`,
        risk: risk + Math.min(40, amt / 50000),
        href: acct
          ? `/transactions?account_id=${encodeURIComponent(acct)}`
          : `/entities?q=${encodeURIComponent(String(d.label ?? ""))}`,
      });
    } else if (type === "phone" && meta.call_count) {
      const calls = Number(meta.call_count ?? 0);
      const dur = Number(meta.total_duration_sec ?? 0);
      const msisdn = String(d.label ?? meta.msisdn ?? "");
      rows.push({
        id: n.id,
        label: msisdn || "Phone",
        kind: "Calls",
        metric: `${calls} calls`,
        detail: dur ? `${Math.round(dur / 60)} min total` : "CDR link",
        risk: risk + Math.min(30, calls * 2),
        href: `/telecom?q=${encodeURIComponent(msisdn)}`,
      });
    } else if (type === "ip") {
      const sessions = Number(meta.session_count ?? 0);
      const ip = String(d.label ?? meta.ip_address ?? "");
      rows.push({
        id: n.id,
        label: ip || "IP",
        kind: "Internet",
        metric: `${sessions} sessions`,
        detail: "IPDR activity",
        risk: risk + Math.min(20, sessions),
        href: `/telecom?event_type=IPDR&q=${encodeURIComponent(ip)}`,
      });
    }
  }
  return rows.sort((a, b) => b.risk - a.risk).slice(0, 12);
}

function InvestigationGraph({ entityId }: { entityId: string }) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [summary, setSummary] = useState<GraphResponse["summary"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [showGraph, setShowGraph] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<GraphResponse>(
          `/api/investigation/graph/${encodeURIComponent(entityId)}`
        );

        const normalizedNodes: Node[] = data.nodes.map((n) => ({
          ...n,
          type: "graphNode",
        }));
        const layouted = layoutGraph(normalizedNodes, data.edges);

        setNodes(layouted.nodes);
        setEdges(layouted.edges);
        setSummary(data.summary);
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : "Unknown error";
        setError(message);
        setNodes([]);
        setEdges([]);
        setSummary(null);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [entityId]);

  const highlights = useMemo(() => buildHighlights(nodes), [nodes]);

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  const onClosePanel = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const miniMapNodeColor = useCallback((n: Node) => {
    const score = (n.data as { riskScore?: number }).riskScore ?? 0;
    if (score >= 75) return "#f87171";
    if (score >= 50) return "#fbbf24";
    return "#64748b";
  }, []);

  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center rounded-xl border border-slate-700/50 bg-slate-800/40">
        Loading investigation links...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
        {error}
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-center">
        <div className="text-sm font-semibold text-amber-100">
          No links found for this entity yet
        </div>
        <div className="max-w-md text-xs text-amber-100/80">
          Upload bank statements and CDR files, or pick another seed from the list.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {summary ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {[
            { label: "Transactions", value: summary.transaction_count },
            { label: "Counterparties", value: summary.counterparty_count },
            { label: "Call targets", value: summary.call_target_count },
            { label: "Graph nodes", value: summary.node_count },
            { label: "Links", value: summary.edge_count },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-lg border border-white/10 bg-slate-900/60 px-3 py-2"
            >
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                {s.label}
              </div>
              <div className="text-lg font-bold text-white">
                {s.value.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <section className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-amber-200">Priority links</h3>
          </div>
          <button
            type="button"
            onClick={() => setShowGraph((v) => !v)}
            className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-semibold text-white"
          >
            {showGraph ? "Hide network map" : "Show network map"}
          </button>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3 py-2">Kind</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Signal</th>
                <th className="px-3 py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {highlights.map((row) => (
                <tr key={row.id} className="border-t border-white/5 hover:bg-white/5">
                  <td className="px-3 py-2">
                    <Link
                      href={row.href}
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold hover:underline ${
                        row.kind === "Money"
                          ? "bg-emerald-500/20 text-emerald-200"
                          : row.kind === "Calls"
                            ? "bg-cyan-500/20 text-cyan-200"
                            : "bg-violet-500/20 text-violet-200"
                      }`}
                    >
                      {row.kind}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-medium text-white max-w-[200px] truncate">
                    <Link href={row.href} className="hover:text-indigo-300 hover:underline">
                      {row.label}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-semibold text-amber-100">
                    <Link href={row.href} className="hover:underline">
                      {row.metric}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-400">
                    <Link href={row.href} className="hover:text-indigo-300 hover:underline">
                      {row.detail}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!highlights.length ? (
            <div className="py-4 text-center text-xs text-slate-500">
              No counterparty or call links yet — check Bank money and Phone calls tabs.
            </div>
          ) : null}
        </div>
      </section>

      {showGraph ? (
        <div className="relative h-[55vh] min-h-[400px] w-full rounded-xl border border-slate-700/50 bg-slate-950/40">
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              fitView
              minZoom={0.12}
              maxZoom={1.6}
              proOptions={{ hideAttribution: true }}
              className="h-full w-full"
            >
              <Background color="#334155" gap={20} />
              <Controls />
            </ReactFlow>
          </ReactFlowProvider>
          <NodeDetailPanel node={selectedNode} onClose={onClosePanel} />
        </div>
      ) : null}
    </div>
  );
}

export default memo(InvestigationGraph);
