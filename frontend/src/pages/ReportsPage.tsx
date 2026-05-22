import { FormEvent, useMemo, useState } from "react";
import { NavLink, useParams } from "react-router-dom";

import { api, reportRoutes } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function ReportsPage() {
  const { reportId } = useParams();
  const active = useMemo(() => reportRoutes.find((report) => report.id === reportId) ?? reportRoutes[0], [reportId]);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", currency: "", party_id: "", account_id: "", settlement_id: "" });
  const [applied, setApplied] = useState(filters);
  const { data, loading, error } = useAsync(() => api.report(active.path, applied), [active.path, applied]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setApplied(filters);
  }

  return (
    <section>
      <header className="page-header"><div><h1>Reports</h1><p>Read-only day book, ledgers, cash, bank, and profitability views.</p></div></header>
      <div className="tabs">
        {reportRoutes.map((report) => <NavLink key={report.id} to={`/reports/${report.id}`}>{report.label}</NavLink>)}
      </div>
      <form className="toolbar form-grid" onSubmit={submit}>
        <input type="date" value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} />
        <input type="date" value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} />
        <input placeholder="Currency" value={filters.currency} onChange={(event) => setFilters({ ...filters, currency: event.target.value.toUpperCase() })} />
        <input placeholder="Party ID" value={filters.party_id} onChange={(event) => setFilters({ ...filters, party_id: event.target.value })} />
        <input placeholder="Account ID" value={filters.account_id} onChange={(event) => setFilters({ ...filters, account_id: event.target.value })} />
        <input placeholder="Settlement ID" value={filters.settlement_id} onChange={(event) => setFilters({ ...filters, settlement_id: event.target.value })} />
        <button type="submit">Apply</button>
      </form>
      <h2>{active.label}</h2>
      {data && <div className="summary-strip"><span>Totals: <strong>{JSON.stringify(data.totals)}</strong></span></div>}
      {loading && <LoadingState label="Loading report" />}
      {error && <ErrorState message={error} />}
      {data && <DataTable rows={data.rows} />}
    </section>
  );
}
