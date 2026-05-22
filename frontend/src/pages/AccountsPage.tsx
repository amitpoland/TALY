import { FormEvent, useState } from "react";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorList, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

const accountTypes = ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet", "commission_income", "commission_payable", "expense", "bank_charge_expense", "fx_gain_loss", "clearing", "suspense", "owner_equity"];
const blankForm = { account_code: "", name: "", account_type: "cash", currency: "USD", party_id: "" };

type AccountRow = {
  id: number;
  account_code: string;
  name: string;
  account_type: string;
  currency: string;
  party_id: number | null;
  current_balance: string;
  is_active: boolean;
};

export default function AccountsPage() {
  const { data, loading, error, reload } = useAsync<AccountRow[]>(api.accounts as () => Promise<AccountRow[]>, []);
  const [form, setForm] = useState(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    setStatusMessage(null);
    try {
      if (editingId) {
        await api.updateAccount(editingId, { name: form.name });
        setStatusMessage("Account saved");
      } else {
        await api.createAccount({ ...form, party_id: form.party_id ? Number(form.party_id) : null });
        setStatusMessage("Account added");
      }
      resetForm();
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  function resetForm() {
    setForm(blankForm);
    setEditingId(null);
  }

  function editAccount(account: AccountRow) {
    setSubmitError(null);
    setStatusMessage("Editing account name. Code, type, currency, and party stay locked.");
    setEditingId(account.id);
    setForm({
      account_code: account.account_code,
      name: account.name,
      account_type: account.account_type,
      currency: account.currency,
      party_id: account.party_id ? String(account.party_id) : ""
    });
  }

  async function setAccountActive(account: AccountRow, isActive: boolean) {
    setSubmitError(null);
    setStatusMessage(null);
    try {
      if (isActive) {
        await api.updateAccount(account.id, { is_active: true });
        setStatusMessage("Account restored");
      } else {
        const confirmed = window.confirm(`Delete ${account.account_code}? Old vouchers stay safe. The account will be marked inactive.`);
        if (!confirmed) return;
        await api.deleteAccount(account.id);
        setStatusMessage("Account deleted");
      }
      if (editingId === account.id) {
        resetForm();
      }
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  const rows = data?.map((account) => ({
    ...account,
    actions: (
      <div className="row-actions">
        <button type="button" className="secondary-action" onClick={() => editAccount(account)}>Edit</button>
        {account.is_active ? (
          <button type="button" className="danger-action" onClick={() => setAccountActive(account, false)}>Delete</button>
        ) : (
          <button type="button" className="secondary-action" onClick={() => setAccountActive(account, true)}>Restore</button>
        )}
      </div>
    )
  }));

  return (
    <section>
      <header className="page-header"><div><h1>Accounts</h1><p>Cash, bank, wallets, clearing, income, expense, and control accounts.</p></div></header>
      <form className="toolbar form-grid" onSubmit={submit}>
        <input required placeholder="Code" value={form.account_code} disabled={Boolean(editingId)} onChange={(event) => setForm({ ...form, account_code: event.target.value.toUpperCase() })} />
        <input required placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <select value={form.account_type} disabled={Boolean(editingId)} onChange={(event) => setForm({ ...form, account_type: event.target.value })}>{accountTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select>
        <input required placeholder="Currency" value={form.currency} disabled={Boolean(editingId)} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} />
        <input placeholder="Party ID" value={form.party_id} disabled={Boolean(editingId)} onChange={(event) => setForm({ ...form, party_id: event.target.value })} />
        <button type="submit">{editingId ? "Save Account" : "Add Account"}</button>
        {editingId && <button type="button" className="secondary-action" onClick={resetForm}>Cancel Edit</button>}
      </form>
      {statusMessage && <p className="form-note">{statusMessage}</p>}
      <ErrorList messages={[submitError, error]} />
      {loading && <LoadingState label="Loading accounts" />}
      {rows && <DataTable rows={rows} columns={["id", "account_code", "name", "account_type", "currency", "party_id", "current_balance", "is_active", "actions"]} />}
    </section>
  );
}
