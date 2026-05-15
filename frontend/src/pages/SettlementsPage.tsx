import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorList, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function SettlementsPage() {
  const { data, loading, error, reload } = useAsync(api.settlements, []);
  const [form, setForm] = useState({ settlement_no: "", title: "", primary_party_id: "", base_currency: "USD" });
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    try {
      await api.createSettlement({
        settlement_no: form.settlement_no,
        title: form.title,
        primary_party_id: form.primary_party_id ? Number(form.primary_party_id) : null,
        base_currency: form.base_currency
      });
      setForm({ settlement_no: "", title: "", primary_party_id: "", base_currency: "USD" });
      reload();
    } catch (err) {
      setSubmitError((err as Error).message);
    }
  }

  const rows = (data ?? []).map((row) => ({
    ...row,
    detail: <Link to={`/settlements/${row.id}`}>Open</Link>
  }));

  return (
    <section>
      <header className="page-header"><div><h1>Settlements</h1><p>Create and review settlement chains.</p></div></header>
      <form className="toolbar form-grid" onSubmit={submit}>
        <input required placeholder="Settlement No" value={form.settlement_no} onChange={(event) => setForm({ ...form, settlement_no: event.target.value.toUpperCase() })} />
        <input required placeholder="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
        <input placeholder="Primary Party ID" value={form.primary_party_id} onChange={(event) => setForm({ ...form, primary_party_id: event.target.value })} />
        <input required placeholder="Base Currency" value={form.base_currency} onChange={(event) => setForm({ ...form, base_currency: event.target.value.toUpperCase() })} />
        <button type="submit">Add Settlement</button>
      </form>
      <ErrorList messages={[submitError, error]} />
      {loading && <LoadingState label="Loading settlements" />}
      {data && <DataTable rows={rows} columns={["id", "settlement_no", "title", "primary_party_id", "status", "base_currency", "opened_at", "closed_at", "detail"]} />}
    </section>
  );
}
