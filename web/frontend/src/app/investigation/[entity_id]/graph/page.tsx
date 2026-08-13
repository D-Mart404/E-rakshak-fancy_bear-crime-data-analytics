"use client";

import { useParams, useRouter } from "next/navigation";
import InvestigationGraph from "@/components/graph/InvestigationGraph";

export default function InvestigationGraphPage() {
  const router = useRouter();
  const params = useParams<{ entity_id: string }>();
  const entityId = params?.entity_id ?? "";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-200">
            Network graph
          </div>
          <div className="mt-1 text-xs text-slate-500">entity_id: {entityId}</div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() =>
              router.push(`/investigation/${encodeURIComponent(entityId)}`)
            }
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            Report view
          </button>
          <button
            onClick={() => router.push("/")}
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            Dashboard
          </button>
        </div>
      </div>

      <InvestigationGraph entityId={entityId} />
    </div>
  );
}
