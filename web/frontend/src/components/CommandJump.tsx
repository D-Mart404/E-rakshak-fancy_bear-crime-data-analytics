"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { JUMP_TARGETS } from "@/lib/nav";

export default function CommandJump({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) onClose();
        else document.dispatchEvent(new CustomEvent("erakshak:open-jump"));
      }
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return JUMP_TARGETS;
    return JUMP_TARGETS.filter(
      (t) =>
        t.label.toLowerCase().includes(needle) ||
        t.keywords.includes(needle) ||
        t.href.includes(needle)
    );
  }, [q]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 p-4 pt-[12vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Jump to… people, money, calls, network, reports"
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 text-sm text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
          onKeyDown={(e) => {
            if (e.key === "Enter" && results[0]) {
              router.push(results[0].href);
              onClose();
            }
          }}
        />
        <div className="max-h-72 overflow-y-auto p-2">
          {results.map((r) => (
            <button
              key={r.href}
              type="button"
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-[var(--text)] hover:bg-[var(--surface-2)]"
              onClick={() => {
                router.push(r.href);
                onClose();
              }}
            >
              <span>{r.label}</span>
              <span className="text-[11px] text-[var(--muted)]">{r.href}</span>
            </button>
          ))}
          {!results.length ? (
            <div className="px-3 py-4 text-sm text-[var(--muted)]">No matches</div>
          ) : null}
        </div>
        <div className="border-t border-[var(--border)] px-3 py-2 text-[10px] text-[var(--muted)]">
          Tip: press Ctrl+K anytime to jump
        </div>
      </div>
    </div>
  );
}
