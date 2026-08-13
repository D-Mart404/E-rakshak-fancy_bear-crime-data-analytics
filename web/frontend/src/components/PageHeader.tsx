"use client";

import Link from "next/link";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  dataType: string;
  dataHint?: string;
  actions?: React.ReactNode;
};

export default function PageHeader({
  eyebrow,
  title,
  description,
  dataType,
  dataHint,
  actions,
}: PageHeaderProps) {
  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent)]">
            {eyebrow}
          </div>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)]">
            {title}
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">{description}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent)]">
              Data: {dataType}
            </span>
            {dataHint ? (
              <span className="text-[11px] text-[var(--muted)]">{dataHint}</span>
            ) : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}

export function QuickJump({
  items,
}: {
  items: Array<{ href: string; label: string }>;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[11px] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}
