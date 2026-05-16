import { ApiRecord, api } from "../api/client";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

function moneyMap(values: Record<string, string>) {
  const entries = Object.entries(values);
  if (!entries.length) return <span className="muted">0</span>;
  return entries.map(([currency, amount]) => (
    <span key={currency} className="money-pill">
      {currency} {amount}
    </span>
  ));
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function addByCurrency(rows: ApiRecord[], transactionType: string) {
  const totals: Record<string, number> = {};
  for (const row of rows) {
    if (row.transaction_type !== transactionType || row.component_type !== "principal") continue;
    const currency = String(row.currency ?? "");
    const amount = Number(row.amount ?? 0);
    if (!currency || !Number.isFinite(amount)) continue;
    totals[currency] = (totals[currency] ?? 0) + amount;
  }
  return Object.fromEntries(Object.entries(totals).map(([currency, amount]) => [currency, amount.toFixed(2)]));
}

export default function DashboardPage() {
  const { data, loading, error } = useAsync(async () => {
    const today = todayIso();
    const [dashboard, dailyWork] = await Promise.all([
      api.dashboard(),
      api.report("/reports/settlement-chain", { date_from: today, date_to: today })
    ]);
    return {
      ...dashboard,
      todaysReceipts: addByCurrency(dailyWork.rows, "receipt"),
      todaysPayments: addByCurrency(dailyWork.rows, "payment")
    };
  }, []);

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Daily operating view from posted records.</p>
        </div>
      </header>
      {loading && <LoadingState label="Loading dashboard" />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="metric-grid">
          <div className="metric"><span>Cash Balances</span><strong>{moneyMap(data.cash_balances)}</strong></div>
          <div className="metric"><span>Bank Balances</span><strong>{moneyMap(data.bank_balances)}</strong></div>
          <div className="metric"><span>Today's Receipts</span><strong>{moneyMap(data.todaysReceipts)}</strong></div>
          <div className="metric"><span>Today's Payments</span><strong>{moneyMap(data.todaysPayments)}</strong></div>
          <div className="metric"><span>Open Work</span><strong>{data.pending_settlements}</strong></div>
          <div className="metric"><span>Exchange Difference Today</span><strong>{moneyMap(data.fx_profit_loss)}</strong></div>
        </div>
      )}
    </section>
  );
}
