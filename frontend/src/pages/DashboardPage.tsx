import { api } from "../api/client";
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

export default function DashboardPage() {
  const { data, loading, error } = useAsync(api.dashboard, []);

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Cash, bank, settlements, and profitability from posted records.</p>
        </div>
      </header>
      {loading && <LoadingState label="Loading dashboard" />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="metric-grid">
          <div className="metric"><span>Cash</span><strong>{moneyMap(data.cash_balances)}</strong></div>
          <div className="metric"><span>Bank</span><strong>{moneyMap(data.bank_balances)}</strong></div>
          <div className="metric"><span>Pending Settlements</span><strong>{data.pending_settlements}</strong></div>
          <div className="metric"><span>Closed Settlements</span><strong>{data.closed_settlements}</strong></div>
          <div className="metric"><span>Commission Earned</span><strong>{moneyMap(data.commission_earned)}</strong></div>
          <div className="metric"><span>Expenses</span><strong>{moneyMap(data.expenses)}</strong></div>
          <div className="metric"><span>FX Profit/Loss</span><strong>{moneyMap(data.fx_profit_loss)}</strong></div>
          <div className="metric"><span>Net Profitability</span><strong>{moneyMap(data.net_profitability)}</strong></div>
        </div>
      )}
    </section>
  );
}
