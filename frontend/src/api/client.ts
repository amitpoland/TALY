export type ApiRecord = Record<string, unknown>;

export type ReportResponse = {
  filters: ApiRecord;
  rows: ApiRecord[];
  totals: Record<string, string>;
};

export type DashboardResponse = {
  filters: ApiRecord;
  cash_balances: Record<string, string>;
  bank_balances: Record<string, string>;
  pending_settlements: number;
  closed_settlements: number;
  commission_earned: Record<string, string>;
  expenses: Record<string, string>;
  fx_profit_loss: Record<string, string>;
  net_profitability: Record<string, string>;
};

export type PreviewResponse = {
  transaction_type: string;
  gross_amount: string | null;
  gross_currency: string | null;
  components: ApiRecord[];
  ledger_entries: ApiRecord[];
  account_balance_effects: ApiRecord[];
  settlement_effect: Record<string, string>;
  profitability_effect: Record<string, string>;
  warnings: string[];
  errors: string[];
  fx_detail?: ApiRecord | null;
};

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  const base = configured || "http://127.0.0.1:8000";
  return base.replace(/\/api\/?$/, "").replace(/\/$/, "");
}

const API_BASE = apiBaseUrl();

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail;
    const backendMessage = Array.isArray(detail) ? detail.map((item) => item.msg ?? JSON.stringify(item)).join(", ") : detail;
    const message = backendMessage ? `${backendMessage} (${response.status} at ${url})` : `${response.status} ${response.statusText} at ${url}`;
    throw new Error(message);
  }
  return data as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

export const transactionRoutes = {
  openingBalance: { label: "Opening Balance", preview: "/transactions/opening-balance/preview", post: "/transactions/opening-balance/post" },
  receipt: { label: "Receipt", preview: "/transactions/receipt/preview", post: "/transactions/receipt/post" },
  payment: { label: "Payment", preview: "/transactions/payment/preview", post: "/transactions/payment/post" },
  cashHandover: { label: "Cash Handover", preview: "/transactions/cash-handover/preview", post: "/transactions/cash-handover/post" },
  bankTransfer: { label: "Bank Transfer", preview: "/transactions/bank-transfer/preview", post: "/transactions/bank-transfer/post" },
  expense: { label: "Expense", preview: "/transactions/expense/preview", post: "/transactions/expense/post" },
  fxConversion: { label: "FX Conversion", preview: "/transactions/fx-conversion/preview", post: "/transactions/fx-conversion/post" }
} as const;

export type TransactionRouteKey = keyof typeof transactionRoutes;

export const reportRoutes = [
  { id: "cash", label: "Cash", path: "/reports/cash" },
  { id: "bank", label: "Bank", path: "/reports/bank" },
  { id: "customer-ledger", label: "Customer Ledger", path: "/reports/customer-ledger" },
  { id: "agent-ledger", label: "Agent Ledger", path: "/reports/agent-ledger" },
  { id: "settlement-chain", label: "Settlement Chain", path: "/reports/settlement-chain" },
  { id: "commission-earned", label: "Commission Earned", path: "/reports/commission-earned" },
  { id: "commission-paid", label: "Commission Paid", path: "/reports/commission-paid" },
  { id: "expenses", label: "Expenses", path: "/reports/expenses" },
  { id: "bank-charges", label: "Bank Charges", path: "/reports/bank-charges" },
  { id: "fx-profit-loss", label: "FX Profit/Loss", path: "/reports/fx-profit-loss" },
  { id: "currency-exposure", label: "Currency Exposure", path: "/reports/currency-exposure" },
  { id: "pending-settlements", label: "Pending Settlements", path: "/reports/pending-settlements" },
  { id: "closed-settlements", label: "Closed Settlements", path: "/reports/closed-settlements" },
  { id: "daily-cash-closing", label: "Daily Cash Closing", path: "/reports/daily-cash-closing" },
  { id: "monthly-profitability", label: "Monthly Profitability", path: "/reports/monthly-profitability" }
] as const;

export type ReportRouteId = (typeof reportRoutes)[number]["id"];

export const api = {
  dashboard: () => request<DashboardResponse>("/reports/dashboard"),
  parties: () => request<ApiRecord[]>("/parties"),
  createParty: (payload: ApiRecord) => request<ApiRecord>("/parties", { method: "POST", body: JSON.stringify(payload) }),
  accounts: () => request<ApiRecord[]>("/accounts"),
  createAccount: (payload: ApiRecord) => request<ApiRecord>("/accounts", { method: "POST", body: JSON.stringify(payload) }),
  currencies: () => request<ApiRecord[]>("/currencies"),
  users: () => request<ApiRecord[]>("/users"),
  auditLogs: () => request<ApiRecord[]>("/audit-logs"),
  settlements: () => request<ApiRecord[]>("/settlements"),
  settlement: (id: string | number) => request<ApiRecord>(`/settlements/${id}`),
  createSettlement: (payload: ApiRecord) => request<ApiRecord>("/settlements", { method: "POST", body: JSON.stringify(payload) }),
  updateSettlement: (id: string | number, payload: ApiRecord) => request<ApiRecord>(`/settlements/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  report: (path: string, filters: ApiRecord = {}) => request<ReportResponse>(`${path}${query(filters as Record<string, string | number>)}`),
  settlementBalance: (id: string | number) => request<ApiRecord>(`/settlements/${id}/balance`),
  previewTransaction: (key: TransactionRouteKey, payload: ApiRecord) =>
    request<PreviewResponse>(transactionRoutes[key].preview, { method: "POST", body: JSON.stringify(payload) }),
  postTransaction: (key: TransactionRouteKey, payload: ApiRecord) =>
    request<PreviewResponse & ApiRecord>(transactionRoutes[key].post, {
      method: "POST",
      body: JSON.stringify({ payload, confirmation: { confirmed_by_user: true } })
    })
};
