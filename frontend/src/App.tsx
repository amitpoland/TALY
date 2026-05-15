import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import AccountsPage from "./pages/AccountsPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import DashboardPage from "./pages/DashboardPage";
import PartiesPage from "./pages/PartiesPage";
import ReportsPage from "./pages/ReportsPage";
import SettlementDetailPage from "./pages/SettlementDetailPage";
import SettlementsPage from "./pages/SettlementsPage";
import TransactionEntryPage from "./pages/TransactionEntryPage";
import { transactionRoutes } from "./api/client";

const navItems = [
  ["Dashboard", "/"],
  ["Parties", "/parties"],
  ["Accounts", "/accounts"],
  ["Settlements", "/settlements"],
  ["Transactions", "/transactions/receipt"],
  ["Reports", "/reports"],
  ["Audit Logs", "/audit-logs"]
];

function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">M</span>
          <div>
            <strong>Clearing Ledger</strong>
            <span>Local brokerage desk</span>
          </div>
        </div>
        <nav>
          {navItems.map(([label, path]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/parties" element={<PartiesPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/settlements" element={<SettlementsPage />} />
          <Route path="/settlements/:settlementId" element={<SettlementDetailPage />} />
          <Route path="/transactions" element={<Navigate to="/transactions/receipt" replace />} />
          {Object.keys(transactionRoutes).map((key) => (
            <Route key={key} path={`/transactions/${key}`} element={<TransactionEntryPage routeKey={key as keyof typeof transactionRoutes} />} />
          ))}
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:reportId" element={<ReportsPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
