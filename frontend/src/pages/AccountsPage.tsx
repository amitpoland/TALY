import { FormEvent, useState } from "react";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

const accountTypes = ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet", "commission_income", "commission_payable", "expense", "bank_charge_expense", "fx_gain_loss", "clearing", "suspense", "owner_equity"];

export default function AccountsPage() {
  const { data, loading, error, reload } = useAsync(api.accounts, []);
  const [form, setForm] = useState({ account_code: "", name: "", account_type: "cash", currency: "USD", party_id: "" });
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    try {
      await api.createAccount({ ...form, party_id: form.party_id ? Number(form.party_id) : null });
      setForm({ account_code: "", name: "", account_type: "cash", currency: "USD", party_id: "" });
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  return (
    <section>
      <header className="page-header"><div><h1>Accounts</h1><p>Cash, bank, wallets, clearing, income, expense, and control accounts.</p></div></header>
      <form className="toolbar form-grid" onSubmit={submit}>
        <input required placeholder="Code" value={form.account_code} onChange={(event) => setForm({ ...form, account_code: event.target.value.toUpperCase() })} />
        <input required placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <select value={form.account_type} onChange={(event) => setForm({ ...form, account_type: event.target.value })}>{accountTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select>
        <input required placeholder="Currency" value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} />
        <input placeholder="Party ID" value={form.party_id} onChange={(event) => setForm({ ...form, party_id: event.target.value })} />
        <button type="submit">Add Account</button>
      </form>
      {submitError && <ErrorState message={submitError} />}
      {loading && <LoadingState label="Loading accounts" />}
      {error && <ErrorState message={error} />}
      {data && <DataTable rows={data} columns={["id", "account_code", "name", "account_type", "currency", "party_id", "current_balance", "is_active"]} />}
    </section>
  );
}
