"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { apiFetch, apiUrl } from "@/lib/api";
import { useUiStore } from "@/store/useUiStore";

type DocRow = {
  document_id: string;
  case_id: string;
  original_filename: string;
  doc_type: string;
  note?: string;
  size_bytes: number;
  uploaded_at: string;
  uploaded_by?: string;
  detected_category?: string;
  classify_reason?: string;
  staged_path?: string;
  staging_status?: string;
  ingest_status?: string;
  ingest_message?: string;
  ingest_stats?: {
    entities?: number;
    transactions?: number;
    events?: number;
    kind?: string;
  };
};

const DOC_TYPES = [
  { value: "auto", label: "Auto-detect (recommended)" },
  { value: "bank_statement", label: "Force: Bank statement" },
  { value: "cdr", label: "Force: CDR" },
  { value: "ipdr", label: "Force: IPDR" },
  { value: "fir", label: "Force: FIR / complaint" },
  { value: "evidence", label: "Store only (no classify override)" },
];

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function ingestBadge(status?: string) {
  if (status === "ok" || status === "classified") return "bg-emerald-500/20 text-emerald-200";
  if (status === "failed" || status === "quarantined") return "bg-red-500/20 text-red-200";
  if (status === "skipped") return "bg-slate-500/20 text-slate-300";
  return "bg-white/10 text-slate-300";
}

export default function DocumentsPage() {
  const activeCase = useUiStore((s) => s.activeCase);
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastIngest, setLastIngest] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [docType, setDocType] = useState("auto");
  const [note, setNote] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [stagingHint, setStagingHint] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const q = activeCase?.case_id
        ? `?case_id=${encodeURIComponent(activeCase.case_id)}`
        : "";
      const data = await apiFetch<{ documents: DocRow[]; staging_root?: string }>(
        `/api/documents${q}`
      );
      setDocs(data.documents);
      if (data.staging_root) setStagingHint(data.staging_root);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [activeCase?.case_id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Keep document list in sync after deletes / uploads from other tabs
  useEffect(() => {
    const id = window.setInterval(() => {
      void load(true);
    }, 20_000);
    return () => window.clearInterval(id);
  }, [load]);

  const uploadFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;
    if (!activeCase?.case_id) {
      setError("Open a case first from All Cases, then upload.");
      return;
    }
    setUploading(true);
    setError(null);
    setLastIngest(null);
    const messages: string[] = [];
    try {
      for (const file of list) {
        const body = new FormData();
        body.append("file", file);
        body.append("case_id", activeCase.case_id);
        body.append("doc_type", docType);
        body.append("note", note);
        body.append("auto_ingest", "true");
        const res = await fetch(apiUrl("/api/documents/upload"), {
          method: "POST",
          body,
        });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            payload?.detail || payload?.message || `Upload failed (${res.status})`
          );
        }
        const cls = payload?.classification;
        const ingest = payload?.ingest;
        const cat = cls?.category || payload?.document?.detected_category || "?";
        const folder = cls?.processed_path
          ? `processed/${cat}/`
          : cls?.status === "quarantined"
            ? "quarantine/"
            : "raw/";
        let line = `${file.name} → ${folder} (${cls?.reason || "classified"})`;
        if (ingest?.status === "ok") line += `\n  loaded: ${ingest.message}`;
        else if (ingest?.status === "failed") line += `\n  ingest FAILED: ${ingest.message}`;
        messages.push(line);
      }
      setNote("");
      setLastIngest(messages.join("\n\n"));
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const reingest = async (id: string) => {
    setBusyId(id);
    setError(null);
    try {
      const data = await apiFetch<{ ingest: { status: string; message: string } }>(
        `/api/documents/${encodeURIComponent(id)}/ingest`,
        { method: "POST" }
      );
      setLastIngest(data.ingest?.message || "Re-ingest finished");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setBusyId(null);
    }
  };

  const removeDoc = async (id: string) => {
    const row = docs.find((d) => d.document_id === id);
    const label = row?.original_filename || id;
    if (
      !window.confirm(
        `Remove "${label}" and purge its linked bank data from MongoDB?\n\nTransactions / accounts loaded from this file will disappear from Bank money.`
      )
    ) {
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      const res = await apiFetch<{
        status: string;
        purged?: { transactions?: number; entities?: number };
      }>(`/api/documents/${encodeURIComponent(id)}?purge_data=true`, {
        method: "DELETE",
      });
      const purgedTx = res.purged?.transactions ?? 0;
      const purgedEnt = res.purged?.entities ?? 0;
      setLastIngest(
        `Removed ${label}. Purged ${purgedTx} transaction(s) and ${purgedEnt} account entit(ies). Bank money will refresh shortly.`
      );
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Generalized evidence inbox"
        title="Upload any file — auto-route"
        description="Upload bank, CDR, IPDR, or FIR. Files are classified and loaded into the case."
        dataType="Classified staging + case data"
        dataHint={
          activeCase
            ? `Case ${activeCase.case_id}`
            : "No active case — open one first"
        }
        actions={
          <Link
            href="/cases"
            className="rounded-lg bg-white/10 px-3 py-2 text-xs font-semibold text-white"
          >
            Switch case
          </Link>
        }
      />

      {!activeCase ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          No active case. Go to{" "}
          <Link href="/cases" className="font-semibold underline">
            All Cases
          </Link>{" "}
          and click <strong>Open workspace</strong> first.
        </div>
      ) : null}

      <section className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-5">
        <div className="mb-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2 text-xs text-cyan-100/90">
          Flow: <strong>raw/</strong> → auto-classify →{" "}
          <strong>processed/bank|cdr|ipdr|fir|…</strong> → MongoDB load.
          {stagingHint ? (
            <>
              {" "}
              Staging root: <code className="text-cyan-200">{stagingHint}</code>
            </>
          ) : null}
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="text-xs text-slate-400">
            Type (optional)
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white"
            >
              {DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Short note (optional)
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. batch from Surat PS"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
            />
          </label>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (e.dataTransfer.files?.length) void uploadFiles(e.dataTransfer.files);
          }}
          className={`mt-4 rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            dragOver
              ? "border-cyan-400 bg-cyan-500/10"
              : "border-slate-600 bg-slate-950/30"
          }`}
        >
          <div className="text-3xl">📂</div>
          <div className="mt-2 text-sm font-semibold text-white">
            Drop any investigation file here
          </div>
          <div className="mt-1 text-xs text-slate-400">
            PDF / CSV / Excel / JSON / Word / images — content decides the folder
          </div>
          <label className="mt-4 inline-block cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">
            {uploading ? "Classifying & loading…" : "Browse files"}
            <input
              type="file"
              multiple
              className="hidden"
              disabled={uploading || !activeCase}
              onChange={(e) => {
                if (e.target.files?.length) void uploadFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </section>

      {error ? <div className="text-sm text-red-300 whitespace-pre-wrap">{error}</div> : null}
      {lastIngest ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100 whitespace-pre-wrap">
          {lastIngest}
        </div>
      ) : null}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-cyan-300">
          Documents in this case ({docs.length})
        </h3>
        {loading ? (
          <div className="text-sm text-slate-500">Loading…</div>
        ) : !docs.length ? (
          <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6 text-sm text-slate-500">
            No documents yet. Upload the first file above.
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map((d) => (
              <div
                key={d.document_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700/50 bg-slate-800/40 p-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-white">
                    {d.original_filename}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-400">
                    <span className={`rounded px-1.5 py-0.5 ${ingestBadge(d.staging_status)}`}>
                      {d.detected_category || d.doc_type}
                    </span>{" "}
                    <span className={`rounded px-1.5 py-0.5 ${ingestBadge(d.ingest_status)}`}>
                      {d.ingest_status || "stored"}
                    </span>{" "}
                    · {formatBytes(d.size_bytes)} · {d.uploaded_at}
                    {d.note ? ` · ${d.note}` : ""}
                  </div>
                  {d.classify_reason ? (
                    <div className="mt-1 text-[11px] text-slate-500">{d.classify_reason}</div>
                  ) : null}
                  {d.staged_path ? (
                    <div className="mt-0.5 truncate text-[10px] text-slate-600" title={d.staged_path}>
                      {d.staged_path}
                    </div>
                  ) : null}
                  {d.ingest_message ? (
                    <div className="mt-1 text-[11px] text-slate-400">{d.ingest_message}</div>
                  ) : null}
                </div>
                <div className="flex gap-2">
                  {["bank_statement", "cdr", "ipdr"].includes(d.doc_type) ||
                  ["bank", "cdr", "ipdr", "accounts", "transactions"].includes(
                    d.detected_category || ""
                  ) ||
                  /\.(xlsx|xls|xlsm|csv|pdf)$/i.test(d.original_filename) ? (
                    <button
                      onClick={() => void reingest(d.document_id)}
                      disabled={busyId === d.document_id}
                      className="rounded-lg bg-cyan-600/80 px-3 py-1.5 text-xs text-white hover:bg-cyan-500"
                    >
                      {busyId === d.document_id ? "Loading…" : "Re-load into case"}
                    </button>
                  ) : null}
                  <button
                    onClick={() => void removeDoc(d.document_id)}
                    className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-red-200 hover:bg-red-500/20"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
