"use client";

import { memo } from "react";

type DetailField = {
  label: string;
  value: unknown;
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function DetailPanel({
  title,
  subtitle,
  fields,
  actions,
}: {
  title: string;
  subtitle?: string;
  fields: DetailField[];
  actions?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-white">{title}</h3>
          {subtitle ? (
            <p className="mt-1 text-xs text-slate-400">{subtitle}</p>
          ) : null}
        </div>
        {actions}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
        {fields.map((field) => (
          <div
            key={field.label}
            className="rounded-lg border border-white/10 bg-white/5 p-3"
          >
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              {field.label}
            </div>
            <div className="mt-1 text-sm font-medium text-slate-100 break-words">
              {formatValue(field.value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default memo(DetailPanel);
