import { FormEvent, useEffect, useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import AccountsPage from "./pages/AccountsPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import DashboardPage from "./pages/DashboardPage";
import PartiesPage from "./pages/PartiesPage";
import ReportsPage from "./pages/ReportsPage";
import SettlementDetailPage from "./pages/SettlementDetailPage";
import SettlementsPage from "./pages/SettlementsPage";
import TransactionEntryPage from "./pages/TransactionEntryPage";
import { reportRoutes, transactionRoutes } from "./api/client";

const voucherLinks = [
  ["Cash / Bank Entry", "/transactions/cashBankEntry", "Alt+C"],
  ["Receive Money", "/transactions/receipt", "Alt+R"],
  ["Pay Money", "/transactions/payment", "Alt+P"],
  ["Agent Settlement", "/transactions/agentSettlement", ""],
  ["Cash Handover", "/transactions/cashHandover", ""],
  ["Bank Transfer", "/transactions/bankTransfer", ""],
  ["Expense", "/transactions/expense", "Alt+E"],
  ["Currency Exchange", "/transactions/fxConversion", "Alt+X"],
  ["Opening Balance", "/transactions/openingBalance", ""]
];

const navGroups = [
  { title: "Dashboard", items: [["Dashboard", "/", ""]] },
  { title: "Masters", items: [["Parties", "/parties", ""], ["Accounts", "/accounts", ""]] },
  { title: "Vouchers", items: voucherLinks },
  {
    title: "Reports",
    items: [
      ["Day Book", "/reports/day-book", ""],
      ["Cash", "/reports/cash", ""],
      ["Bank", "/reports/bank", ""],
      ["Client Ledger", "/reports/customer-ledger", ""],
      ["Agent Ledger", "/reports/agent-ledger", ""],
      ["Profitability", "/reports/monthly-profitability", ""],
      ["Settlements", "/settlements", ""]
    ]
  },
  { title: "System", items: [["Audit Logs", "/audit-logs", ""]] }
];

const shortcutRoutes: Record<string, string> = {
  c: "/transactions/cashBankEntry",
  r: "/transactions/receipt",
  p: "/transactions/payment",
  e: "/transactions/expense",
  x: "/transactions/fxConversion"
};

type Command = {
  label: string;
  path: string;
  group: string;
  hint?: string;
};

function useOperatorShortcuts(openCommands: () => void) {
  const navigate = useNavigate();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      if ((event.ctrlKey || event.metaKey) && key === "k") {
        event.preventDefault();
        openCommands();
        return;
      }
      if (event.altKey && shortcutRoutes[key]) {
        event.preventDefault();
        navigate(shortcutRoutes[key]);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, openCommands]);
}

function CommandPalette({ commands, open, onClose }: { commands: Command[]; open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const visible = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return commands.slice(0, 10);
    return commands.filter((command) => `${command.label} ${command.group}`.toLowerCase().includes(value)).slice(0, 12);
  }, [commands, query]);

  useEffect(() => {
    if (open) setQuery("");
  }, [open]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const selected = visible[0];
    if (!selected) return;
    navigate(selected.path);
    onClose();
  }

  if (!open) return null;

  return (
    <div className="command-backdrop" role="presentation" onMouseDown={onClose}>
      <form className="command-palette" onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
        <input autoFocus placeholder="Search voucher, report, party, account..." value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }} />
        <div className="command-list">
          {visible.map((command) => (
            <button key={`${command.group}-${command.path}-${command.label}`} type="button" onClick={() => {
              navigate(command.path);
              onClose();
            }}>
              <span>{command.label}</span>
              <small>{command.group}{command.hint ? ` · ${command.hint}` : ""}</small>
            </button>
          ))}
          {!visible.length && <span className="muted">No command found</span>}
        </div>
      </form>
    </div>
  );
}

function App() {
  const [commandOpen, setCommandOpen] = useState(false);
  const location = useLocation();
  const commands = useMemo<Command[]>(() => [
    ...navGroups.flatMap((group) => group.items.map(([label, path, hint]) => ({ label, path, group: group.title, hint }))),
    ...reportRoutes.map((report) => ({ label: report.label, path: `/reports/${report.id}`, group: "Reports" }))
  ], []);

  useOperatorShortcuts(() => setCommandOpen(true));

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
        <button className="command-trigger" type="button" onClick={() => setCommandOpen(true)}>
          <span>Search</span>
          <kbd>Ctrl K</kbd>
        </button>
        <nav className="grouped-nav">
          {navGroups.map((group) => (
            <section key={group.title} className="nav-group">
              <h2>{group.title}</h2>
              {group.items.map(([label, path, hint]) => (
                <NavLink key={path} to={path} end={path === "/"} className={({ isActive }) => isActive || (path !== "/" && location.pathname.startsWith(path)) ? "active" : undefined}>
                  <span>{label}</span>
                  {hint && <small>{hint}</small>}
                </NavLink>
              ))}
            </section>
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
      <CommandPalette commands={commands} open={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  );
}

export default App;
