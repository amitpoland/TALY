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

console.log("Frontend smoke check passed");
