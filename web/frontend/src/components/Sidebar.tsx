"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { PRIMARY_NAV } from "@/lib/nav";
import { useUiStore } from "@/store/useUiStore";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const activeCase = useUiStore((s) => s.activeCase);

  useEffect(() => {
    for (const item of PRIMARY_NAV) router.prefetch(item.href);
  }, [router]);

  if (!sidebarOpen) {
    return (
      <aside className="flex h-screen w-14 flex-col items-center gap-2 border-r border-[var(--border)] bg-[var(--rail)] py-3">
        <button
          type="button"
          onClick={toggleSidebar}
          title="Expand sidebar"
          className="rounded-md bg-[var(--surface-2)] px-2 py-2 text-xs text-[var(--text)] hover:bg-[var(--accent-soft)]"
        >
          ›
        </button>
        {PRIMARY_NAV.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.id}
              href={item.href}
              title={item.label}
              className={`flex h-9 w-9 items-center justify-center rounded-md text-sm ${
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
              }`}
            >
              {item.icon}
            </Link>
          );
        })}
      </aside>
    );
  }

  return (
    <aside className="flex h-screen w-[220px] flex-col border-r border-[var(--border)] bg-[var(--rail)]">
      <div className="flex h-14 items-center justify-between px-3">
        <Link href="/" className="text-base font-bold tracking-tight text-[var(--text)]">
          E-Rakshak
        </Link>
        <button
          type="button"
          onClick={toggleSidebar}
          className="rounded-md px-2 py-1 text-[11px] text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
        >
          Hide
        </button>
      </div>

      {activeCase ? (
        <Link
          href={`/cases/${encodeURIComponent(activeCase.case_id)}`}
          className="mx-2 mb-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 hover:border-[var(--accent)]"
        >
          <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
            Active case
          </div>
          <div className="truncate text-sm font-semibold text-[var(--accent)]">
            {activeCase.case_id}
          </div>
        </Link>
      ) : (
        <Link
          href="/cases"
          className="mx-2 mb-3 rounded-lg border border-dashed border-[var(--border)] px-3 py-2 text-xs text-[var(--muted)] hover:text-[var(--text)]"
        >
          Open a case to begin →
        </Link>
      )}

      <nav className="flex flex-1 flex-col gap-1 px-2">
        <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
          Main
        </div>
        {PRIMARY_NAV.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.id}
              href={item.href}
              prefetch
              className={`rounded-lg px-3 py-2.5 transition-colors ${
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-semibold">
                <span className="opacity-80">{item.icon}</span>
                {item.label}
              </div>
              <div
                className={`mt-0.5 text-[10px] ${
                  active ? "text-[var(--accent)]/80" : "text-[var(--muted)]"
                }`}
              >
                {item.hint}
                {item.tabs ? ` · ${item.tabs.length} tabs` : ""}
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[var(--border)] px-3 py-3 text-[10px] text-[var(--muted)]">
        Left = main areas only.
        <br />
        Top tabs = details inside each area.
      </div>
    </aside>
  );
}
