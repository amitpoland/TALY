import { FormEvent, useMemo, useState } from "react";
import { NavLink, useParams } from "react-router-dom";

import { ApiRecord, api, reportRoutes } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

type Filters = {
  date_from: string;
  date_to: string;
  currency: string;
  party_id: string;
  account_id: string;
  settlement_id: string;
};

const emptyFilters: Filters = {
  date_from: "",
  date_to: "",
  currency: "",
  party_id: "",
  account_id: "",
  settlement_id: ""
};

function displayAmount(value: unknown): string {
  const text = String(value ?? "0");
  const numeric = Number(text);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : text;
}

function splitTotalKey(key: string): { currency: string; label: string } {
  const [currency, ...rest] = key.split("_");
  return {
    currency,
    label: rest.join(" ").replace("fx", "exchange")
  };
}

function TotalsCards({ totals }: { totals: Record<string, string> }) {
  const entries = Object.entries(totals ?? {}).filter(([, value]) => Number(value || 0) !== 0);
  if (!entries.length) return <div className="summary-strip"><span>No totals for this report.</span></div>;
  return (
    <div className="report-total-grid">
      {entries.map(([key, value]) => {
        const total = splitTotalKey(key);
        return (
          <div className="report-total-card" key={key}>
            <span>{total.currency}</span>
            <strong>{displayAmount(value)}</strong>
            <small>{total.label}</small>
          </div>
        );
      })}
    </div>
  );
}

function optionLabel(record: ApiRecord, fallback: string) {
  return String(record.name ?? record.account_code ?? record.settlement_no ?? record.title ?? fallback);
}

export default function ReportsPage() {
  const { reportId } = useParams();
  const active = useMemo(() => reportRoutes.find((report) => report.id === reportId) ?? reportRoutes[0], [reportId]);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [applied, setApplied] = useState<Filters>(emptyFilters);
  const { data: lookups, loading: lookupLoading } = useAsync(async () => {
    const [parties, accounts, settlements, currencies] = await Promise.all([api.parties(), api.accounts(), api.settlements(), api.currencies()]);
    return { parties, accounts, settlements, currencies };
  }, []);
  const { data, loading, error } = useAsync(() => api.report(active.path, applied), [active.path, applied]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setApplied(filters);
  }

  function clearFilters() {
    setFilters(emptyFilters);
    setApplied(emptyFilters);
  }

  return (
    <section>
      <header className="page-header"><div><h1>Reports</h1><p>Day book, ledgers, cash, bank, and profitability views.</p></div></header>
      <div className="tabs report-tabs">
        {reportRoutes.map((report) => <NavLink key={report.id} to={`/reports/${report.id}`}>{report.label}</NavLink>)}
      </div>
      <form className="report-filter-panel" onSubmit={submit}>
        <label><span>From</span><input type="date" value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} /></label>
        <label><span>To</span><input type="date" value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} /></label>
        <label><span>Currency</span><select value={filters.currency} onChange={(event) => setFilters({ ...filters, currency: event.target.value })}>
          <option value="">All currencies</option>
          {lookups?.currencies.map((currency) => <option key={String(currency.code)} value={String(currency.code)}>{String(currency.code)} - {String(currency.name ?? currency.code)}</option>)}
        </select></label>
        <label><span>Party</span><select value={filters.party_id} onChange={(event) => setFilters({ ...filters, party_id: event.target.value })}>
          <option value="">All parties</option>
          {lookups?.parties.map((party) => <option key={String(party.id)} value={String(party.id)}>{optionLabel(party, `Party ${String(party.id)}`)}</option>)}
        </select></label>
        <label><span>Account</span><select value={filters.account_id} onChange={(event) => setFilters({ ...filters, account_id: event.target.value })}>
          <option value="">All accounts</option>
          {lookups?.accounts.map((account) => <option key={String(account.id)} value={String(account.id)}>{String(account.account_code ?? account.name)} ({String(account.currency ?? "")})</option>)}
        </select></label>
        <label><span>Settlement</span><select value={filters.settlement_id} onChange={(event) => setFilters({ ...filters, settlement_id: event.target.value })}>
          <option value="">All settlements</option>
          {lookups?.settlements.map((settlement) => <option key={String(settlement.id ?? settlement.settlement_id)} value={String(settlement.id ?? settlement.settlement_id)}>{optionLabel(settlement, `Settlement ${String(settlement.id ?? settlement.settlement_id)}`)}</option>)}
        </select></label>
        <div className="report-filter-actions">
          <button type="submit">Apply</button>
          <button type="button" className="secondary-action" onClick={clearFilters}>Reset</button>
        </div>
      </form>
      <h2>{active.label}</h2>
      {lookupLoading && <LoadingState label="Loading filter lists" />}
      {data && <TotalsCards totals={data.totals} />}
      {loading && <LoadingState label="Loading report" />}
      {error && <ErrorState message={error} />}
      {data && <DataTable rows={data.rows} />}
    </section>
  );
}
