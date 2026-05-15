import { FormEvent, useState } from "react";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorList, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function PartiesPage() {
  const { data, loading, error, reload } = useAsync(api.parties, []);
  const [form, setForm] = useState({ party_type: "customer", name: "", phone: "", email: "", default_currency: "USD" });
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    try {
      await api.createParty({ ...form, phone: form.phone || null, email: form.email || null, default_currency: form.default_currency || null });
      setForm({ party_type: "customer", name: "", phone: "", email: "", default_currency: "USD" });
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

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
        <button type="submit">Add Party</button>
      </form>
      <ErrorList messages={[submitError, error]} />
      {loading && <LoadingState label="Loading parties" />}
      {data && <DataTable rows={data} columns={["id", "party_type", "name", "phone", "email", "default_currency", "is_active"]} />}
    </section>
  );
}
