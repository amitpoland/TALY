import { useParams } from "react-router-dom";

import { api } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

export default function SettlementDetailPage() {
  const { settlementId } = useParams();
  const { data, loading, error } = useAsync(async () => {
    if (!settlementId) throw new Error("Settlement ID is required");
    const [balance, chain] = await Promise.all([
      api.settlementBalance(settlementId),
      api.report("/reports/settlement-chain", { settlement_id: settlementId })
    ]);
    return { balance, chain };
  }, [settlementId]);

  return (
    <section>
      <header className="page-header"><div><h1>Settlement {settlementId}</h1><p>Balance and chain components from posted records.</p></div></header>
      {loading && <LoadingState label="Loading settlement" />}
      {error && <ErrorState message={error} />}
      {data && (
        <>
          <div className="summary-strip">
            <span>Status: <strong>{String(data.balance.status)}</strong></span>
            <span>Balanced: <strong>{String(data.balance.is_balanced_by_currency)}</strong></span>
            <span>Balances: <strong>{JSON.stringify(data.balance.balances ?? {})}</strong></span>
          </div>
          <DataTable rows={data.chain.rows} columns={["transaction_date", "transaction_no", "transaction_type", "component_type", "amount", "currency", "affects_settlement", "settlement_amount"]} />
        </>
      )}
    </section>
  );
}
