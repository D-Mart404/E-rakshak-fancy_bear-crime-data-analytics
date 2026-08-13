"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CommandJump from "./CommandJump";
import { useUiStore } from "@/store/useUiStore";

export default function TopBar() {
  const active = useUiStore((s) => s.activeCase);
  const caseLoaded = useUiStore((s) => s.caseLoaded);
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const [jumpOpen, setJumpOpen] = useState(false);

  useEffect(() => {
    const open = () => setJumpOpen(true);
    document.addEventListener("erakshak:open-jump", open);
    return () => document.removeEventListener("erakshak:open-jump", open);
  }, []);

  return (
    <>
      <header className="flex h-14 items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-3 md:px-4">
        <div className="flex min-w-0 items-center gap-2">
          {!sidebarOpen ? (
            <button
              type="button"
              onClick={toggleSidebar}
              className="rounded-md bg-[var(--surface-2)] px-2 py-1 text-[11px] font-semibold text-[var(--text)]"
            >
              Menu
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setJumpOpen(true)}
            className="hidden min-w-[220px] items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-left text-xs text-[var(--muted)] hover:border-[var(--accent)] sm:flex"
          >
            <span>Search or jump to…</span>
            <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px]">
              Ctrl K
            </kbd>
          </button>
          <div className="min-w-0 sm:hidden">
            <div className="truncate text-sm font-semibold text-[var(--text)]">
              {caseLoaded && active ? active.case_id : "E-Rakshak"}
            </div>
          </div>
          <div className="hidden min-w-0 md:block">
            {caseLoaded ? (
              active ? (
                <div className="truncate text-xs text-[var(--muted)]">
                  Working in{" "}
                  <Link
                    href={`/cases/${encodeURIComponent(active.case_id)}`}
                    className="font-semibold text-[var(--accent)] hover:underline"
                  >
                    {active.case_id}
                  </Link>
                  {active.title ? ` — ${active.title}` : ""}
                </div>
              ) : (
                <Link href="/cases" className="text-xs text-[var(--accent)]">
                  Choose a case to start
                </Link>
              )
            ) : (
              <div className="text-xs text-[var(--muted)]">Loading…</div>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setJumpOpen(true)}
            className="rounded-md bg-[var(--surface-2)] px-2 py-1.5 text-[11px] font-semibold text-[var(--text)] sm:hidden"
          >
            Jump
          </button>
          <Link
            href="/documents"
            className="rounded-md bg-[var(--ok)] px-3 py-1.5 text-[11px] font-semibold text-white"
          >
            + Document
          </Link>
        </div>
      </header>
      <CommandJump open={jumpOpen} onClose={() => setJumpOpen(false)} />
    </>
  );
}
