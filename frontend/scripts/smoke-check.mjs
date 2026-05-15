import { existsSync, readFileSync } from "node:fs";

const requiredFiles = [
  "src/main.tsx",
  "src/App.tsx",
  "src/api/client.ts",
  "src/pages/DashboardPage.tsx",
  "src/pages/TransactionEntryPage.tsx",
  "src/pages/ReportsPage.tsx"
];

const requiredRoutes = [
  "/transactions/receipt/preview",
  "/transactions/receipt/post",
  "/transactions/fx-conversion/preview",
  "/reports/dashboard",
  "/audit-logs"
];

for (const file of requiredFiles) {
  if (!existsSync(new URL(`../${file}`, import.meta.url))) {
    throw new Error(`Missing ${file}`);
  }
}

const source = readFileSync(new URL("../src/api/client.ts", import.meta.url), "utf8");
for (const route of requiredRoutes) {
  if (!source.includes(route)) {
    throw new Error(`Missing API route ${route}`);
  }
}

console.log("Frontend smoke check passed");
