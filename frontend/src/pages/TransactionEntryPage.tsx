import { FormEvent, useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiRecord, api, PreviewResponse, TransactionRouteKey, transactionRoutes } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: string[];
};

const commonFields: Field[] = [
  { name: "transaction_date", label: "Date", type: "date", required: true },
  { name: "created_by_user_id", label: "User ID", required: true },
  { name: "settlement_id", label: "Settlement ID" },
  { name: "description", label: "Description" }
];

const fieldsByRoute: Record<TransactionRouteKey, Field[]> = {
  openingBalance: [
    { name: "transaction_date", label: "Date", type: "date", required: true },
    { name: "created_by_user_id", label: "User ID", required: true },
    { name: "account_id", label: "Account ID", required: true },
    { name: "equity_account_id", label: "Equity Account ID", required: true },
    { name: "amount", label: "Amount", required: true },
    { name: "currency", label: "Currency", required: true },
    { name: "base_currency", label: "Base Currency" },
    { name: "original_rate", label: "Original FX Rate" }
  ],
  receipt: [
    ...commonFields,
    { name: "receiving_account_id", label: "Receiving Account ID", required: true },
    { name: "clearing_account_id", label: "Clearing Account ID", required: true },
    { name: "gross_amount", label: "Gross Amount", required: true },
    { name: "principal_amount", label: "Principal Amount", required: true },
    { name: "commission_amount", label: "Commission Included" },
    { name: "commission_income_account_id", label: "Commission Income Account ID" },
    { name: "currency", label: "Currency", required: true },
    { name: "base_currency", label: "Base Currency" },
    { name: "original_rate", label: "Original FX Rate" }
  ],
  payment: [
    ...commonFields,
    { name: "paying_account_id", label: "Paying Account ID", required: true },
    { name: "clearing_account_id", label: "Clearing Account ID", required: true },
    { name: "amount", label: "Amount", required: true },
    { name: "currency", label: "Currency", required: true }
  ],
  cashHandover: [
    ...commonFields,
    { name: "from_account_id", label: "From Account ID", required: true },
    { name: "to_account_id", label: "To Account ID", required: true },
    { name: "amount", label: "Amount", required: true },
    { name: "currency", label: "Currency", required: true }
  ],
  bankTransfer: [
    ...commonFields,
    { name: "from_account_id", label: "From Bank Account ID", required: true },
    { name: "to_account_id", label: "To Bank Account ID", required: true },
    { name: "amount", label: "Amount", required: true },
    { name: "currency", label: "Currency", required: true }
  ],
  expense: [
    ...commonFields,
    { name: "payment_account_id", label: "Payment Account ID", required: true },
    { name: "expense_account_id", label: "Expense Account ID", required: true },
    { name: "amount", label: "Amount", required: true },
    { name: "currency", label: "Currency", required: true },
    { name: "expense_type", label: "Expense Type" },
    { name: "affects_settlement", label: "Affects Settlement", type: "checkbox" }
  ],
  fxConversion: [
    ...commonFields,
    { name: "from_account_id", label: "From Account ID", required: true },
    { name: "to_account_id", label: "To Account ID", required: true },
    { name: "source_clearing_account_id", label: "Source Clearing Account ID", required: true },
    { name: "target_clearing_account_id", label: "Target Clearing Account ID", required: true },
    { name: "fx_gain_loss_account_id", label: "FX Gain/Loss Account ID", required: true },
    { name: "fx_charge_account_id", label: "FX Charge Account ID" },
    { name: "from_amount", label: "From Amount", required: true },
    { name: "to_amount", label: "To Amount", required: true },
    { name: "from_currency", label: "From Currency", required: true },
    { name: "to_currency", label: "To Currency", required: true },
    { name: "base_currency", label: "Base Currency", required: true },
    { name: "costing_method", label: "Costing Method", options: ["fifo", "transaction_wise"] },
    { name: "source_lot_id", label: "Source Lot ID" },
    { name: "fx_charge", label: "FX Charge" },
    { name: "allow_insufficient_lots", label: "Allow Insufficient Lots", type: "checkbox" }
  ]
};

const numericFields = new Set(["created_by_user_id", "settlement_id", "account_id", "equity_account_id", "receiving_account_id", "clearing_account_id", "commission_income_account_id", "paying_account_id", "from_account_id", "to_account_id", "payment_account_id", "expense_account_id", "source_clearing_account_id", "target_clearing_account_id", "fx_gain_loss_account_id", "fx_charge_account_id", "source_lot_id"]);
const defaultValues: Record<string, string | boolean> = {
  transaction_date: new Date().toISOString().slice(0, 10),
  currency: "USD",
  base_currency: "USD",
  from_currency: "USD",
  to_currency: "AED",
  costing_method: "fifo",
  commission_amount: "0",
  fx_charge: "0",
  expense_type: "other",
  affects_settlement: false,
  allow_insufficient_lots: false
};

function buildInitial(routeKey: TransactionRouteKey): Record<string, string | boolean> {
  const values: Record<string, string | boolean> = {};
  fieldsByRoute[routeKey].forEach((field) => {
    values[field.name] = defaultValues[field.name] ?? "";
  });
  return values;
}

function toPayload(form: Record<string, string | boolean>): ApiRecord {
  const payload: ApiRecord = {};
  Object.entries(form).forEach(([key, value]) => {
    if (typeof value === "boolean") {
      payload[key] = value;
      return;
    }
    if (value === "") return;
    payload[key] = numericFields.has(key) ? Number(value) : value;
  });
  return payload;
}

function PreviewPanel({ preview, onPost, posting }: { preview: PreviewResponse; onPost: () => void; posting: boolean }) {
  return (
    <div className="preview-panel">
      <div className="summary-strip">
        <span>Type: <strong>{preview.transaction_type}</strong></span>
        <span>Gross: <strong>{preview.gross_amount ?? "-"} {preview.gross_currency ?? ""}</strong></span>
        <span>Settlement: <strong>{JSON.stringify(preview.settlement_effect)}</strong></span>
        <span>Profitability: <strong>{JSON.stringify(preview.profitability_effect)}</strong></span>
      </div>
      {preview.warnings.length > 0 && <div className="state-block warning">{preview.warnings.join(", ")}</div>}
      <h2>Components</h2>
      <DataTable rows={preview.components} />
      <h2>Ledger Entries</h2>
      <DataTable rows={preview.ledger_entries} />
      <h2>Balance Effects</h2>
      <DataTable rows={preview.account_balance_effects} />
      {preview.fx_detail && (
        <>
          <h2>FX Detail</h2>
          <DataTable rows={[preview.fx_detail]} />
        </>
      )}
      <button className="primary-action" type="button" onClick={onPost} disabled={posting}>
        {posting ? "Posting..." : "Confirm and Post"}
      </button>
    </div>
  );
}

export default function TransactionEntryPage({ routeKey }: { routeKey: TransactionRouteKey }) {
  const config = transactionRoutes[routeKey];
  const [form, setForm] = useState<Record<string, string | boolean>>(() => buildInitial(routeKey));
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<ApiRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: lookups } = useAsync(async () => {
    const [users, accounts, pending, closed] = await Promise.all([api.users(), api.accounts(), api.report("/reports/pending-settlements"), api.report("/reports/closed-settlements")]);
    return { users, accounts, settlements: [...pending.rows, ...closed.rows] };
  }, []);
  const fields = useMemo(() => fieldsByRoute[routeKey], [routeKey]);

  useEffect(() => {
    setForm(buildInitial(routeKey));
    setPreview(null);
    setResult(null);
    setError(null);
  }, [routeKey]);

  async function previewTransaction(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setPreview(await api.previewTransaction(routeKey, toPayload(form)));
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function postTransaction() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.postTransaction(routeKey, toPayload(form)));
      setPreview(null);
      setForm(buildInitial(routeKey));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <header className="page-header">
        <div><h1>{config.label}</h1><p>Preview first, then confirm posting. The UI displays backend components and ledger entries without recalculating them.</p></div>
      </header>
      <div className="tabs">
        {Object.entries(transactionRoutes).map(([key, route]) => <NavLink key={key} to={`/transactions/${key}`}>{route.label}</NavLink>)}
      </div>
      <div className="helper-grid">
        <details><summary>Users</summary><DataTable rows={lookups?.users ?? []} columns={["id", "username", "full_name", "is_active"]} /></details>
        <details><summary>Accounts</summary><DataTable rows={lookups?.accounts ?? []} columns={["id", "account_code", "account_type", "currency", "current_balance"]} /></details>
        <details><summary>Settlements</summary><DataTable rows={lookups?.settlements ?? []} columns={["settlement_id", "settlement_no", "status", "base_currency"]} /></details>
      </div>
      <form className="entry-form" onSubmit={previewTransaction}>
        {fields.map((field) => (
          <label key={field.name}>
            <span>{field.label}</span>
            {field.type === "checkbox" ? (
              <input type="checkbox" checked={Boolean(form[field.name])} onChange={(event) => setForm({ ...form, [field.name]: event.target.checked })} />
            ) : field.options ? (
              <select value={String(form[field.name] ?? "")} onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}>
                {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            ) : (
              <input required={field.required} type={field.type ?? "text"} value={String(form[field.name] ?? "")} onChange={(event) => setForm({ ...form, [field.name]: event.target.value })} />
            )}
          </label>
        ))}
        <button type="submit" disabled={busy}>{busy ? "Working..." : "Preview"}</button>
      </form>
      {error && <ErrorState message={error} />}
      {result && <div className="state-block success">Posted transaction {String(result.transaction_no)}.</div>}
      {preview && <PreviewPanel preview={preview} onPost={postTransaction} posting={busy} />}
    </section>
  );
}
