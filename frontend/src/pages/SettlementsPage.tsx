import { Link } from "react-router-dom";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function SettlementsPage() {
  const { data, loading, error } = useAsync(async () => {
    const [pending, closed] = await Promise.all([
      api.report("/reports/pending-settlements"),
      api.report("/reports/closed-settlements")
    ]);
    return [...pending.rows, ...closed.rows];
  }, []);

  const rows = (data ?? []).map((row) => ({
    ...row,
    detail: <Link to={`/settlements/${row.settlement_id}`}>Open</Link>
  }));

  return (
    <section>
      <header className="page-header"><div><h1>Settlements</h1><p>Open, reopened, and closed settlement chains from report data.</p></div></header>
      {loading && <LoadingState label="Loading settlements" />}
      {error && <ErrorState message={error} />}
      {data && <DataTable rows={rows} columns={["settlement_id", "settlement_no", "title", "status", "base_currency", "opened_at", "closed_at", "detail"]} />}
    </section>
  );
}
