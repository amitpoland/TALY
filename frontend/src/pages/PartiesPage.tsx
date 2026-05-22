import { FormEvent, useState } from "react";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorList, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

type PartyRow = {
  id: number;
  party_type: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  default_currency?: string | null;
  is_active?: boolean;
};

const blankForm = { party_type: "customer", name: "", phone: "", email: "", default_currency: "USD" };

export default function PartiesPage() {
  const { data, loading, error, reload } = useAsync(api.parties, []);
  const [form, setForm] = useState(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    try {
      const payload = { ...form, phone: form.phone || null, email: form.email || null, default_currency: form.default_currency || null };
      if (editingId) {
        await api.updateParty(editingId, payload);
      } else {
        await api.createParty(payload);
      }
      setForm(blankForm);
      setEditingId(null);
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  function editParty(row: PartyRow) {
    setEditingId(row.id);
    setForm({
      party_type: row.party_type || "customer",
      name: row.name || "",
      phone: row.phone || "",
      email: row.email || "",
      default_currency: row.default_currency || "USD"
    });
    setSubmitError(null);
  }

  async function toggleParty(row: PartyRow) {
    setSubmitError(null);
    try {
      await api.updateParty(row.id, { is_active: !row.is_active });
      if (editingId === row.id) {
        setEditingId(null);
        setForm(blankForm);
      }
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  const rows = (data ?? []).map((row) => {
    const party = row as PartyRow;
    return {
      ...row,
      actions: (
        <div className="row-actions">
          <button type="button" className="secondary-action" onClick={() => editParty(party)}>Edit</button>
          <button type="button" className={party.is_active ? "danger-action" : "secondary-action"} onClick={() => toggleParty(party)}>
            {party.is_active ? "Delete" : "Restore"}
          </button>
        </div>
      )
    };
  });

  return (
    <section>
      <header className="page-header"><div><h1>Parties</h1><p>Customers, agents, FX dealers, vendors, and internal parties.</p></div></header>
      <form className="toolbar form-grid" onSubmit={submit}>
        <select value={form.party_type} onChange={(event) => setForm({ ...form, party_type: event.target.value })}>
          <option value="customer">Customer</option><option value="agent">Agent</option><option value="fx_dealer">FX Dealer</option><option value="vendor">Vendor</option><option value="internal">Internal</option>
        </select>
        <input required placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input placeholder="Phone" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
        <input placeholder="Email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        <input placeholder="Currency" value={form.default_currency} onChange={(event) => setForm({ ...form, default_currency: event.target.value.toUpperCase() })} />
        <button type="submit">{editingId ? "Save Party" : "Add Party"}</button>
        {editingId && <button type="button" className="secondary-action" onClick={() => {
          setEditingId(null);
          setForm(blankForm);
          setSubmitError(null);
        }}>Cancel Edit</button>}
      </form>
      <ErrorList messages={[submitError, error]} />
      {loading && <LoadingState label="Loading parties" />}
      {data && <DataTable rows={rows} columns={["id", "party_type", "name", "phone", "email", "default_currency", "is_active", "actions"]} />}
    </section>
  );
}
