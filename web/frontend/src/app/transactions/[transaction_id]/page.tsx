"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import DetailPanel from "@/components/DetailPanel";
import PaginatedDataTable from "@/components/PaginatedDataTable";
import { apiFetch } from "@/lib/api";

type TransactionDetail = {
  transaction: Record<string, unknown>;
  entity: Record<string, unknown> | null;
  related: {
    same_account: Array<Record<string, unknown>>;
    same_counterparty_name: Array<Record<string, unknown>>;
  };
};

export default function TransactionDetailPage() {
  const params = useParams<{ transaction_id: string }>();
  const transactionId = params?.transaction_id;
  const [data, setData] = useState<TransactionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!transactionId) return;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const json = await apiFetch<{
          transaction: Record<string, unknown>;
          entity: Record<string, unknown> | null;
          related: TransactionDetail["related"];
        }>(`/api/transactions/${encodeURIComponent(transactionId)}`);
        setData({
          transaction: json.transaction,
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
  }, [transactionId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-8 text-center text-slate-400">
        Loading transaction details...
      </div>
    );
  }

  if (error || !data) {
    return <div className="text-red-300">{error ?? "Transaction not found"}</div>;
  }

  const tx = data.transaction;
  const entityId = data.entity?.entity_id as string | undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-slate-400">Transaction detail</div>
          <h2 className="mt-1 text-2xl font-bold text-white">
            {String(tx.transaction_id ?? transactionId)}
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {String(tx.transaction_date ?? "")} · {String(tx.direction ?? "")} ₹
            {String(tx.amount ?? "")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {entityId ? (
            <>
              <Link
                href={`/entities/${encodeURIComponent(entityId)}`}
                className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15"
              >
                View account holder
              </Link>
              <Link
                href={`/investigation/${encodeURIComponent(entityId)}`}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
              >
                Full investigation
              </Link>
            </>
          ) : null}
          <Link
            href="/transactions"
            className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
          >
            ← All transactions
          </Link>
        </div>
      </div>

      <DetailPanel
        title="Bank transaction record"
        subtitle="Complete fields from bank statement ingestion"
        fields={[
          { label: "Transaction ID", value: tx.transaction_id },
          { label: "Date", value: tx.transaction_date },
          { label: "Account ID", value: tx.account_id },
          { label: "Direction", value: tx.direction },
          { label: "Amount (₹)", value: tx.amount },
          { label: "Balance after", value: tx.balance_after },
          { label: "Mode", value: tx.mode },
          { label: "Counterparty name", value: tx.counterparty_name },
          { label: "Counterparty account", value: tx.counterparty_account },
          { label: "Narration", value: tx.narration },
          { label: "Reference", value: tx.reference },
          { label: "Branch", value: tx.branch },
        ]}
      />

      {data.entity ? (
        <DetailPanel
          title="Linked person / entity"
          fields={[
            { label: "Entity ID", value: data.entity.entity_id },
            { label: "Name", value: data.entity.entity_name },
            { label: "Phones", value: data.entity.phones },
            { label: "Accounts", value: data.entity.accounts },
          ]}
        />
      ) : null}

      <div>
        <h3 className="text-lg font-bold text-white">Other transactions on same account</h3>
        <p className="mt-1 text-sm text-slate-400">
          Recent movements on this bank account — click any row for details.
        </p>
        <div className="mt-3">
          <PaginatedDataTable
            loading={false}
            page={1}
            totalPages={1}
            total={data.related.same_account.length}
            onPageChange={() => {}}
            columns={[
              { key: "transaction_date", label: "Date" },
              { key: "transaction_id", label: "ID" },
              { key: "direction", label: "Dir" },
              { key: "amount", label: "Amount" },
              { key: "counterparty_name", label: "Counterparty" },
            ]}
            rows={data.related.same_account}
            rowHref={(row) =>
              row.transaction_id
                ? `/transactions/${encodeURIComponent(String(row.transaction_id))}`
                : null
            }
          />
        </div>
      </div>

      {data.related.same_counterparty_name.length > 0 ? (
        <div>
          <h3 className="text-lg font-bold text-white">
            Same counterparty elsewhere
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Other accounts that paid or received from &quot;{String(tx.counterparty_name ?? "")}&quot;
          </p>
          <div className="mt-3">
            <PaginatedDataTable
              loading={false}
              page={1}
              totalPages={1}
              total={data.related.same_counterparty_name.length}
              onPageChange={() => {}}
              columns={[
                { key: "transaction_date", label: "Date" },
                { key: "account_id", label: "Account" },
                { key: "direction", label: "Dir" },
                { key: "amount", label: "Amount" },
              ]}
              rows={data.related.same_counterparty_name}
              rowHref={(row) =>
                row.transaction_id
                  ? `/transactions/${encodeURIComponent(String(row.transaction_id))}`
                  : null
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
