"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { resolvePrimary, resolveTab } from "@/lib/nav";

export default function WorkspaceTabs() {
  const pathname = usePathname();
  const primary = resolvePrimary(pathname);
  const tabs = primary.tabs;
  if (!tabs?.length) return null;

  const activeTab = resolveTab(pathname);

  return (
    <div className="border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-end gap-1 overflow-x-auto px-4 pt-2 md:px-6">
        {tabs.map((tab) => {
          const active =
            activeTab?.href === tab.href ||
            pathname === tab.href ||
            pathname.startsWith(`${tab.href}/`);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              prefetch
              className={`relative shrink-0 rounded-t-md px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-[var(--surface-2)] font-semibold text-[var(--text)]"
                  : "text-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              <span className="sm:hidden">{tab.short}</span>
              <span className="hidden sm:inline">{tab.label}</span>
              {active ? (
                <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-[var(--accent)]" />
              ) : null}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
