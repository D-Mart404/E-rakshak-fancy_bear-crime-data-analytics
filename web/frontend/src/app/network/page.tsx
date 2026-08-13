"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import PageHeader from "@/components/PageHeader";
import InvestigationGraph from "@/components/graph/InvestigationGraph";
import { apiFetch } from "@/lib/api";

type Entity = { entity_id: string; entity_name?: string; is_seed?: boolean };

function Inner() {
  const seed = useSearchParams().get("seed") || "";
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selected, setSelected] = useState(seed);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (seed) setSelected(seed);
  }, [seed]);

  useEffect(() => {
    apiFetch<{ items: Entity[] }>("/api/entities?limit=100&seed_only=true")
      .then(async (d) => {
        let items = d.items || [];
        if (!items.length) {
          items = (await apiFetch<{ items: Entity[] }>("/api/entities?limit=50")).items || [];
        }
        if (seed && !items.some((e) => e.entity_id === seed)) {
          items = [{ entity_id: seed }, ...items];
        }
        setEntities(items);
        setSelected((p) => p || items[0]?.entity_id || "");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed"));
  }, [seed]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Analysis · connections"
        title="Network map"
        description="Money and telecom links around a person/account."
        dataType="Relationship graph"
        actions={
          selected ? (
            <Link href={`/entities/${encodeURIComponent(selected)}`} className="rounded-lg bg-white/10 px-3 py-2 text-xs font-semibold text-white">
              Entity profile
            </Link>
          ) : null
        }
      />
      {error ? <div className="text-red-300">{error}</div> : null}
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="max-h-[70vh] space-y-1 overflow-y-auto rounded-xl border border-slate-700/50 p-3">
          {entities.map((e) => (
            <button
              key={e.entity_id}
              type="button"
              onClick={() => setSelected(e.entity_id)}
              className={`block w-full rounded-lg px-2 py-2 text-left text-xs ${
                selected === e.entity_id ? "bg-indigo-600/30 text-indigo-100" : "text-slate-300 hover:bg-white/5"
              }`}
            >
              <div className="font-semibold">{e.entity_name || e.entity_id}</div>
              <Link
                href={`/entities/${encodeURIComponent(e.entity_id)}`}
                onClick={(ev) => ev.stopPropagation()}
                className="text-[10px] text-indigo-300 hover:underline"
              >
                {e.entity_id}
              </Link>
            </button>
          ))}
        </aside>
        <section className="min-h-[560px] rounded-xl border border-slate-700/50 bg-slate-900/40 p-2">
          {selected ? (
            <InvestigationGraph entityId={selected} />
          ) : (
            <div className="flex h-[560px] items-center justify-center text-sm text-slate-500">
              Select a person…
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function NetworkPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400">Loading…</div>}>
      <Inner />
    </Suspense>
  );
}
