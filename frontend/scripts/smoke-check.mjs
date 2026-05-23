import { existsSync, readFileSync } from "node:fs";

const requiredFiles = [
  "index.html",
  "src/main.tsx",
  "src/App.tsx",
  "src/api/client.ts",
  "src/components/AppErrorBoundary.tsx",
  "src/pages/DashboardPage.tsx",
  "src/pages/TransactionEntryPage.tsx",
  "src/pages/ReportsPage.tsx"
];

const requiredRoutes = [
  "/transactions/receipt/preview",
  "/transactions/receipt/post",
  "/transactions/agent-settlement/preview",
  "/transactions/agent-settlement/post",
  "/transactions/cross-currency-receipt/preview",
  "/transactions/cross-currency-payment/preview",
  "/transactions/fx-conversion/preview",
  "/currencies",
  "/settlements",
  "/settlements/${id}",
  "/reports/day-book",
  "/reports/dashboard",
  "/audit-logs"
];

for (const file of requiredFiles) {
  if (!existsSync(new URL(`../${file}`, import.meta.url))) {
    throw new Error(`Missing ${file}`);
  }
}

const apiSource = readFileSync(new URL("../src/api/client.ts", import.meta.url), "utf8");
for (const route of requiredRoutes) {
  if (!apiSource.includes(route)) {
    throw new Error(`Missing API route ${route}`);
  }
}

const indexSource = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const mainSource = readFileSync(new URL("../src/main.tsx", import.meta.url), "utf8");
const appSource = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const dashboardSource = readFileSync(new URL("../src/pages/DashboardPage.tsx", import.meta.url), "utf8");
const transactionSource = readFileSync(new URL("../src/pages/TransactionEntryPage.tsx", import.meta.url), "utf8");
const reportsSource = readFileSync(new URL("../src/pages/ReportsPage.tsx", import.meta.url), "utf8");
const partiesSource = readFileSync(new URL("../src/pages/PartiesPage.tsx", import.meta.url), "utf8");
const accountsSource = readFileSync(new URL("../src/pages/AccountsPage.tsx", import.meta.url), "utf8");
const styleSource = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const viteSource = readFileSync(new URL("../vite.config.ts", import.meta.url), "utf8");
const envExampleSource = readFileSync(new URL("../.env.example", import.meta.url), "utf8");
const envDevelopmentSource = readFileSync(new URL("../.env.development", import.meta.url), "utf8");

if (!indexSource.includes('id="root"')) {
  throw new Error("Missing root element in index.html");
}
if (!mainSource.includes("ReactDOM.createRoot") || !mainSource.includes("AppErrorBoundary")) {
  throw new Error("Missing guarded React root render");
}
if (!appSource.includes("app-shell") || !appSource.includes("sidebar") || !appSource.includes("Dashboard")) {
  throw new Error("Missing visible application shell");
}
for (const required of ["navGroups", "Masters", "Vouchers", "System", "CommandPalette", "Search voucher, report, party, account", "Day Book", "Agent Settlement", "Alt+C", "Alt+R", "Alt+P", "Alt+E", "Alt+X"]) {
  if (!appSource.includes(required)) {
    throw new Error(`Tally-style operator shell missing ${required}`);
  }
}
if (!dashboardSource.includes("<h1>Dashboard</h1>")) {
  throw new Error("Missing dashboard header");
}
for (const forbidden of ["User ID", "Receiving Account ID", "Clearing Account ID", "<span>Settlement</span>", "Party wallet", "Ledger entries", "Balance effects", "Base Currency", "Costing Method", "FX Charge Ledger"]) {
  if (transactionSource.includes(forbidden)) {
    throw new Error(`Transaction UI exposes internal label: ${forbidden}`);
  }
}
for (const required of ["Cash / Bank Entry", "Cash/Bank", "Entry Type", "Party", "Date", "Receipt", "Payment", "Delete Draft", "client-currency-strip", "Receive Money", "Client", "Receive In", "Amount Type", "Net Received", "Gross Received", "Amount", "Commission", "Commission Value", "Reference", "Preview Voucher", "previewBlockedReason"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Receipt voucher missing ${required}`);
  }
}
for (const required of ["todayDate()", "type=\"date\"", "transaction_date: form.date", "Date can be changed for back-dated entries"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Back-dated voucher entry support missing ${required}`);
  }
}
for (const forbidden of ["readOnly /></label>", "transaction_date: new Date().toISOString().slice(0, 10)"]) {
  if (transactionSource.includes(forbidden)) {
    throw new Error(`Back-dated voucher entry still blocked by ${forbidden}`);
  }
}
for (const required of ["receiptAmounts", "amount / (1 + rate)", "amount - principal"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Receipt commission reverse calculation missing ${required}`);
  }
}
for (const required of ["CrossCurrencyRateBox", "Currency exchange required", "baseValueFromQuotedRate", "amount / quoteRate", "storedOriginalRateFromQuote", "1 / quoteRate", "Rate: 1", "Client balance will use"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Receipt exchange-rate direction missing ${required}`);
  }
}
for (const required of ["operatorTransactionRouteKeys", "cashBankEntry", "agentSettlement", "fxConversion"]) {
  if (!transactionSource.includes(required) && !apiSource.includes(required)) {
    throw new Error(`Operator voucher tab setup missing ${required}`);
  }
}
if (transactionSource.includes("Object.entries(transactionRoutes).map")) {
  throw new Error("Voucher tabs still expose internal cross-currency routes");
}
for (const required of ["crossCurrencyReceipt", "crossCurrencyPayment", "settlement_currency", "received_currency", "payment_currency", "source_clearing_account_id"]) {
  if (!transactionSource.includes(required) && !apiSource.includes(required)) {
    throw new Error(`Cross-currency voucher support missing ${required}`);
  }
}
for (const required of ["ensureCommissionIncomeAccount", "COMMISSION-${currency}", "commission_income", "commission_income_account_id: commissionAccountId"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Receipt commission auto-account setup missing ${required}`);
  }
}
for (const forbidden of ["Charges/Commission", "Charges Value", "Charges shown", "Total cash/bank impact", "Net Sent", "Gross Sent"]) {
  if (transactionSource.includes(forbidden)) {
    throw new Error(`Payment UI still suggests unsupported charge posting: ${forbidden}`);
  }
}
for (const required of ["Pay Money", "Money paid from cash/bank", "Client/vendor balance affected", "Currency Exchange", "Given Amount", "Received Amount", "Exchange Rate", "Exchange Difference"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Compressed operator workflow missing ${required}`);
  }
}
for (const required of ["allowNegativeBalance", "allow_negative_balance", "Allow temporary negative balance"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`FX negative balance permission UI missing ${required}`);
  }
}
for (const required of ["allowMissingRateHistory", "allow_insufficient_lots", "Use entered rate when old FX history is missing"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`FX missing-rate-history permission UI missing ${required}`);
  }
}
for (const required of ["Agent Settlement", "Agent / Vendor", "Principal Amount", "Agent Commission", "Paid to agent", "Delivered by agent", "Earlier commission", "ensureAgentCommissionExpenseAccount"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Agent Settlement voucher missing ${required}`);
  }
}
for (const required of ["ensureOpenSettlement", "api.createSettlement", "New settlement will be created automatically"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Agent Settlement auto-settlement support missing ${required}`);
  }
}
if (transactionSource.includes("One open settlement is required for Agent Settlement")) {
  throw new Error("Agent Settlement still blocks when no open settlement exists");
}
for (const required of ["payment_principal_amount", "payment_currency", "settlement_currency", "original_rate", "CrossCurrencyRateBox"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Cross-currency Agent Settlement UI missing ${required}`);
  }
}
for (const required of ["cashShortageMessage", "Add opening balance or choose Bank", "Available {money(accountBalance"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Cash negative balance guard missing ${required}`);
  }
}
for (const required of ["Opening Balance Source", "Source / Note", "ensureOpeningSourceAccount", "Create Source"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Opening balance source support missing ${required}`);
  }
}
for (const required of ["report-filter-panel", "report-total-card", "All parties", "All accounts", "All settlements", "TotalsCards"]) {
  if (!reportsSource.includes(required) && !styleSource.includes(required)) {
    throw new Error(`Report UX polish missing ${required}`);
  }
}
for (const forbidden of ["JSON.stringify(data.totals)", "placeholder=\"Party ID\"", "placeholder=\"Account ID\"", "placeholder=\"Settlement ID\""]) {
  if (reportsSource.includes(forbidden)) {
    throw new Error(`Report UI still exposes raw ID/JSON control: ${forbidden}`);
  }
}
for (const required of ['data-searchable="true"', "onKeyDown", "ctrlKey", "metaKey", "api.previewTransaction(targetRoute, cleanPayload)", "api.postTransaction(targetRoute, cleanPayload)"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Voucher workflow behavior missing ${required}`);
  }
}
for (const required of ["beginSearch", "setText(\"\")", "onFocus={beginSearch}", "onClick={beginSearch}"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Searchable dropdown reopen behavior missing ${required}`);
  }
}
for (const required of ["marg-voucher-shell", "voucher-workbench", "voucher-meta-bar", "Escape"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Compact voucher workflow missing ${required}`);
  }
}
if (transactionSource.includes("Quick Check") || transactionSource.includes("Preview waits here")) {
  throw new Error("Voucher screen still contains bulky helper copy");
}
if (!transactionSource.includes("No active local user found. Run seed command.")) {
  throw new Error("Voucher UI must block preview when no active local user exists");
}
for (const required of ["No {currency} Client Balance exists", "Create Client Balance", "createPartyWallet", "partyWallet", "api.currencies()"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Client balance voucher logic missing ${required}`);
  }
}
for (const required of ["Cash Balances", "Bank Balances", "Today's Receipts", "Today's Payments", "Open Work", "Exchange Difference Today"]) {
  if (!dashboardSource.includes(required)) {
    throw new Error(`Operational dashboard missing ${required}`);
  }
}
for (const required of ["Save Party", "Cancel Edit", "Delete", "Restore", "api.updateParty"]) {
  if (!partiesSource.includes(required)) {
    throw new Error(`Parties edit/delete UI missing ${required}`);
  }
}
for (const required of ["Save Account", "Cancel Edit", "Delete", "Restore", "api.updateAccount", "api.deleteAccount"]) {
  if (!accountsSource.includes(required)) {
    throw new Error(`Accounts edit/delete UI missing ${required}`);
  }
}
for (const required of ["disabled={Boolean(editingId)}", "{ name: form.name }", "window.confirm", "Old vouchers stay safe"]) {
  if (!accountsSource.includes(required)) {
    throw new Error(`Accounts safe edit/deactivate behavior missing ${required}`);
  }
}
if (!envExampleSource.includes("VITE_API_BASE_URL=http://127.0.0.1:8010")) {
  throw new Error("Missing clear backend API base URL setting");
}
if (!envDevelopmentSource.includes("VITE_API_BASE_URL=http://127.0.0.1:8010")) {
  throw new Error("Missing development backend API base URL setting");
}
if (!apiSource.includes('replace(/\\/api\\/?$/, "")')) {
  throw new Error("API client must strip accidental /api suffix from base URL");
}
if (!viteSource.includes('"/api"') || !viteSource.includes("path.replace")) {
  throw new Error("Missing Vite API proxy fallback");
}

console.log("Frontend smoke check passed");
