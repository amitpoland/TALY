import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function AuditLogsPage() {
  const { data, loading, error } = useAsync(api.auditLogs, []);
  return (
    <section>
      <header className="page-header"><div><h1>Audit Logs</h1><p>Recent audit trail entries from the backend.</p></div></header>
      {loading && <LoadingState label="Loading audit logs" />}
      {error && <ErrorState message={error} />}
      {data && <DataTable rows={data} columns={["id", "created_at", "action", "entity_type", "entity_id", "user_id", "reason"]} />}
    </section>
  );
}
