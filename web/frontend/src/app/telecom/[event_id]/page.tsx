"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import DetailPanel from "@/components/DetailPanel";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import { apiFetch } from "@/lib/api";

type TelecomDetail = {
  event: Record<string, unknown>;
  entity: Record<string, unknown> | null;
  related: { same_msisdn: Array<Record<string, unknown>> };
};

export default function TelecomDetailPage() {
  const params = useParams<{ event_id: string }>();
  const eventId = params?.event_id;
  const [data, setData] = useState<TelecomDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!eventId) return;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const json = await apiFetch<{
          event: Record<string, unknown>;
          entity: Record<string, unknown> | null;
          related: TelecomDetail["related"];
        }>(`/api/telecom/${encodeURIComponent(eventId)}`);
        setData({
          event: json.event,
          entity: json.entity,
          related: json.related,
        });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [eventId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-center text-slate-400">
        Loading telecom record...
      </div>
    );
  }

  if (error || !data) {
    return <div className="text-red-300">{error ?? "Event not found"}</div>;
  }

  const ev = data.event;
  const isCdr = ev.event_type === "CDR";
  const entityId = data.entity?.entity_id as string | undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-slate-400">
            {isCdr ? "Call detail record (CDR)" : "Internet session (IPDR)"}
          </div>
          <h2 className="mt-1 text-2xl font-bold text-white">
            {String(ev.msisdn ?? "—")}
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {String(ev.timestamp ?? "")} · {String(ev.event_type ?? "")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {entityId ? (
            <Link
              href={`/entities/${encodeURIComponent(entityId)}`}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
            >
              View linked person
            </Link>
          ) : null}
          <Link
            href="/telecom"
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            ← All telecom
          </Link>
        </div>
      </div>

      <DetailPanel
        title="Telecom event — full record"
        fields={
          isCdr
            ? [
                { label: "Event ID", value: ev.event_id },
                { label: "Time", value: ev.timestamp },
                { label: "Phone (A-party)", value: ev.msisdn },
                { label: "B-party", value: ev.b_party },
                { label: "Call type", value: ev.call_type },
                { label: "Duration (sec)", value: ev.duration_sec },
                { label: "Cell tower / LAC", value: ev.cell_id },
                { label: "IMEI", value: ev.imei },
                { label: "IMSI", value: ev.imsi },
              ]
            : [
                { label: "Event ID", value: ev.event_id },
                { label: "Time", value: ev.timestamp },
                { label: "Phone", value: ev.msisdn },
                { label: "IP address", value: ev.ip_address },
                { label: "Cell ID", value: ev.cell_id },
                { label: "Upload volume", value: ev.data_volume_up },
                { label: "Download volume", value: ev.data_volume_down },
                { label: "Session duration (sec)", value: ev.duration_sec },
                { label: "End time", value: ev.end_timestamp },
              ]
        }
      />

      {data.entity ? (
        <DetailPanel
          title="Registered to"
          fields={[
            { label: "Name", value: data.entity.entity_name },
            { label: "Entity ID", value: data.entity.entity_id },
            { label: "All phones", value: data.entity.phones },
          ]}
        />
      ) : (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          No entity in database matches this phone number. It may be an unknown contact.
        </div>
      )}

      <div>
        <h3 className="text-lg font-bold text-white">Other events on same phone</h3>
        <div className="mt-3">
          <PaginatedDataTable
            loading={false}
            page={1}
            totalPages={1}
            total={data.related.same_msisdn.length}
            onPageChange={() => {}}
            columns={[
              { key: "timestamp", label: "Time" },
              { key: "event_type", label: "Type" },
              { key: "b_party", label: "B-Party / IP" },
              { key: "duration_sec", label: "Duration" },
            ]}
            rows={data.related.same_msisdn.map((row) => ({
              ...row,
              b_party:
                row.event_type === "IPDR" ? row.ip_address : row.b_party,
            }))}
            rowHref={(row) =>
              row.event_id
                ? `/telecom/${encodeURIComponent(String(row.event_id))}`
                : null
            }
          />
        </div>
      </div>
    </div>
  );
}
