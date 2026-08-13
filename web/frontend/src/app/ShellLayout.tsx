"use client";

import { useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import WorkspaceTabs from "@/components/WorkspaceTabs";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useUiStore } from "@/store/useUiStore";

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const hydrateSidebar = useUiStore((s) => s.hydrateSidebar);
  const refreshActiveCase = useUiStore((s) => s.refreshActiveCase);

  useEffect(() => {
    hydrateSidebar();
    void refreshActiveCase();
  }, [hydrateSidebar, refreshActiveCase]);

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)] text-[var(--text)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar />
        <WorkspaceTabs />
        <Breadcrumbs />
        <main className="flex-1 overflow-y-auto px-4 pb-8 pt-2 md:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
