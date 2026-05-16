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
  "/transactions/fx-conversion/preview",
  "/currencies",
  "/settlements",
  "/settlements/${id}",
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
if (!dashboardSource.includes("<h1>Dashboard</h1>")) {
  throw new Error("Missing dashboard header");
}
for (const forbidden of ["User ID", "Receiving Account ID", "Clearing Account ID", "<span>Settlement</span>", "Party wallet", "Ledger entries", "Balance effects", "Base Currency", "Costing Method", "FX Charge Ledger"]) {
  if (transactionSource.includes(forbidden)) {
    throw new Error(`Transaction UI exposes internal label: ${forbidden}`);
  }
}
for (const required of ["Receive Money", "Client", "Receive In", "Amount Type", "Net Received", "Gross Received", "Amount", "Commission", "Commission Value", "Reference"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Receipt voucher missing ${required}`);
  }
}
for (const required of ["Pay Money", "Net Sent", "Gross Sent", "Charges/Commission", "Currency Exchange", "Given Amount", "Received Amount", "Exchange Rate", "Exchange Difference"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Compressed operator workflow missing ${required}`);
  }
}
for (const required of ['data-searchable="true"', "onKeyDown", "ctrlKey", "metaKey", "api.previewTransaction(routeKey, payload)", "api.postTransaction(routeKey, lastPayload)"]) {
  if (!transactionSource.includes(required)) {
    throw new Error(`Voucher workflow behavior missing ${required}`);
  }
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
if (!envExampleSource.includes("VITE_API_BASE_URL=http://127.0.0.1:8000")) {
  throw new Error("Missing clear backend API base URL setting");
}
if (!envDevelopmentSource.includes("VITE_API_BASE_URL=http://127.0.0.1:8000")) {
  throw new Error("Missing development backend API base URL setting");
}
if (!apiSource.includes('replace(/\\/api\\/?$/, "")')) {
  throw new Error("API client must strip accidental /api suffix from base URL");
}
if (!viteSource.includes('"/api"') || !viteSource.includes("path.replace")) {
  throw new Error("Missing Vite API proxy fallback");
}

console.log("Frontend smoke check passed");
