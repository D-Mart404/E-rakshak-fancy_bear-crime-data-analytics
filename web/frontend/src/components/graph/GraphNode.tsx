"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

type GraphNodeData = {
  label: string;
  nodeType: string;
  riskScore: number;
  metadata?: Record<string, unknown>;
};

function riskColor(score: number) {
  if (score >= 75) return "border-red-400/60 bg-red-500/15";
  if (score >= 50) return "border-amber-400/60 bg-amber-500/15";
  if (score >= 25) return "border-yellow-400/50 bg-yellow-500/10";
  return "border-slate-500/40 bg-slate-800/60";
}

function GraphNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as GraphNodeData;
  const typeLabel = nodeData.nodeType?.replace(/_/g, " ") ?? "node";

  return (
    <div
      className={`min-w-[170px] rounded-xl border px-3 py-2 shadow-lg transition-shadow ${
        riskColor(nodeData.riskScore)
      } ${selected ? "ring-2 ring-indigo-400" : ""}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-400" />
      <div className="text-[10px] uppercase tracking-wider text-slate-400">
        {typeLabel}
      </div>
      <div className="mt-1 text-sm font-semibold text-white truncate max-w-[160px]">
        {nodeData.label}
      </div>
      <div className="mt-1 text-xs text-slate-300">
        Risk: <span className="font-semibold">{nodeData.riskScore}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-slate-400" />
    </div>
  );
}

export default memo(GraphNodeComponent);
