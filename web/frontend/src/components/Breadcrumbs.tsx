"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { resolvePrimary, resolveTab } from "@/lib/nav";
import { useUiStore } from "@/store/useUiStore";

export default function Breadcrumbs() {
  const pathname = usePathname();
  const primary = resolvePrimary(pathname);
  const tab = resolveTab(pathname);
  const activeCase = useUiStore((s) => s.activeCase);

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex flex-wrap items-center gap-1.5 px-4 py-2 text-[11px] text-[var(--muted)] md:px-6"
    >
      {activeCase ? (
        <>
          <Link
            href={`/cases/${encodeURIComponent(activeCase.case_id)}`}
            className="font-semibold text-[var(--accent)] hover:underline"
          >
            {activeCase.case_id}
          </Link>
          <span>/</span>
        </>
      ) : (
        <>
          <Link href="/cases" className="hover:text-[var(--text)]">
            No case
          </Link>
          <span>/</span>
        </>
      )}
      <Link href={primary.href} className="hover:text-[var(--text)]">
        {primary.label}
      </Link>
      {tab && primary.tabs ? (
        <>
          <span>/</span>
          <span className="text-[var(--text)]">{tab.label}</span>
        </>
      ) : null}
    </nav>
  );
}
