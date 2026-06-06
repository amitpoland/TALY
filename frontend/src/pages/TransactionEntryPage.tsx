import { FormEvent, KeyboardEvent, ReactNode, RefObject, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiRecord, api, operatorTransactionRouteKeys, PreviewResponse, TransactionRouteKey, transactionRoutes } from "../api/client";
import DataTable from "../components/DataTable";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsync } from "../hooks/useAsync";

type Account = ApiRecord & {
  id: number;
  account_code: string;
  name: string;
  account_type: string;
  currency: string;
  party_id?: number | null;
};

type Party = ApiRecord & {
  id: number;
  name: string;
  party_type: string;
  default_currency?: string | null;
};

type Settlement = ApiRecord & {
  id?: number;
  settlement_id?: number;
  settlement_no: string;
  title?: string;
  status: string;
  base_currency: string;
};

type Currency = ApiRecord & {
  code: string;
  name: string;
  decimal_places: number;
  is_active: boolean;
};

type Lookups = {
  users: ApiRecord[];
  accounts: Account[];
  parties: Party[];
  settlements: Settlement[];
  currencies: Currency[];
};

type SearchOption = {
  value: string;
  label: string;
  keywords?: string;
};

const DEFAULT_BASE_CURRENCY = "USD";

const routeTitles: Record<TransactionRouteKey, string> = {
  cashBankEntry: "Cash / Bank Entry",
  openingBalance: "Opening Balance",
  receipt: "Receive Money",
  payment: "Pay Money",
  crossCurrencyReceipt: "Receive Money",
  crossCurrencyPayment: "Pay Money",
  agentSettlement: "Agent Settlement",
  cashHandover: "Cash Handover",
  bankTransfer: "Bank Transfer",
  expense: "Expense",
  fxConversion: "Currency Exchange"
};

const routeHelp: Record<TransactionRouteKey, string> = {
  cashBankEntry: "Select cash or bank first, then party and amount.",
  openingBalance: "Set the starting amount for a cash, bank, or client balance.",
  receipt: "Record money received. The system prepares the accounting preview before posting.",
  payment: "Record money paid out. The system prepares the accounting preview before posting.",
  crossCurrencyReceipt: "Record money received in one currency and client balance in another.",
  crossCurrencyPayment: "Record money paid in one currency and client balance in another.",
  agentSettlement: "Pay agent/vendor, settle principal, and record agent commission.",
  cashHandover: "Move cash from one place to another.",
  bankTransfer: "Move money between bank accounts.",
  expense: "Record fees, charges, and operating costs.",
  fxConversion: "Exchange one currency into another and preview the exchange difference."
};

const routeShortcut: Partial<Record<TransactionRouteKey, string>> = {
  cashBankEntry: "Alt+C",
  receipt: "Alt+R",
  payment: "Alt+P",
  expense: "Alt+E",
  fxConversion: "Alt+X"
};

function asId(value: unknown): number | undefined {
  const id = Number(value);
  return Number.isFinite(id) && id > 0 ? id : undefined;
}

function decimal(value: string): number {
  const normalized = String(value || "0").trim().replace("%", "").replace(",", ".");
  const amount = Number(normalized);
  return Number.isFinite(amount) ? amount : 0;
}

function money(value: number): string {
  return value.toFixed(2);
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function preciseRate(value: number): string {
  return value.toFixed(10).replace(/0+$/, "").replace(/\.$/, "");
}

function baseValueFromQuotedRate(amount: number, quoteRate: number): number {
  return quoteRate > 0 ? amount / quoteRate : 0;
}

function storedOriginalRateFromQuote(quoteRate: number): string | undefined {
  return quoteRate > 0 ? preciseRate(1 / quoteRate) : undefined;
}

function CrossCurrencyRateBox({
  moneyCurrency,
  clientCurrency,
  amount,
  exchangeRate,
  action,
  onRateChange,
  inputRef
}: {
  moneyCurrency: string;
  clientCurrency: string;
  amount: number;
  exchangeRate: string;
  action: "receiving" | "paying";
  onRateChange: (value: string) => void;
  inputRef?: RefObject<HTMLInputElement | null>;
}) {
  const rate = decimal(exchangeRate);
  const clientAmount = baseValueFromQuotedRate(amount, rate);
  return (
    <div className="exchange-rate-prompt" role="alert">
      <div>
        <strong>Exchange rate</strong>
        <span>{action === "receiving" ? "Money received" : "Money paid"}: {moneyCurrency}. Client: {clientCurrency}.</span>
      </div>
      <label>
        <span>Rate: 1 {clientCurrency} =</span>
        <input
          ref={inputRef}
          required
          inputMode="decimal"
          placeholder={`e.g. 3.65 ${moneyCurrency}`}
          value={exchangeRate}
          onChange={(event) => onRateChange(event.target.value)}
        />
        <span>{moneyCurrency}</span>
      </label>
      <p>
        Client amount {rate > 0 ? `${money(amount)} ${moneyCurrency} / ${exchangeRate} = ${money(clientAmount)} ${clientCurrency}` : `will show after you enter the rate`}.
      </p>
    </div>
  );
}

function receiptAmounts(amount: number, amountMode: string, commissionType: string, commissionValue: number) {
  if (commissionType === "percentage") {
    const rate = commissionValue / 100;
    if (amountMode === "gross") {
      const principal = rate > -1 ? amount / (1 + rate) : 0;
      return { gross: amount, principal, commission: amount - principal };
    }
    const commission = amount * rate;
    return { gross: amount + commission, principal: amount, commission };
  }
  const commission = commissionType === "fixed" ? commissionValue : 0;
  return {
    gross: amountMode === "gross" ? amount : amount + commission,
    principal: amountMode === "gross" ? amount - commission : amount,
    commission
  };
}

function splitCommissionAmount(amount: number, amountMode: string, commissionType: string, commissionValue: number) {
  return receiptAmounts(amount, amountMode, commissionType, commissionValue);
}

function accountBalance(account?: Account): number {
  const balance = Number(String(account?.current_balance ?? "0").replace(",", "."));
  return Number.isFinite(balance) ? balance : 0;
}

function cashShortageMessage(account: Account | undefined, amount: number): string | null {
  if (!account || account.account_type !== "cash" || amount <= 0) return null;
  const balance = accountBalance(account);
  if (balance >= amount) return null;
  return `${accountLabel(account)} has only ${money(balance)} ${account.currency}. Add opening balance or choose Bank.`;
}

function balanceShortageMessage(account: Account | undefined, amount: number, action = "Choose another source or add opening balance."): string | null {
  if (!account || amount <= 0) return null;
  const balance = accountBalance(account);
  if (balance >= amount) return null;
  return `${accountLabel(account)} has only ${money(balance)} ${account.currency}. ${action}`;
}

function settlementId(settlement: Settlement): number | undefined {
  return settlement.id ?? settlement.settlement_id;
}

function autoSettlementId(settlements: Settlement[]): number | undefined {
  const active = settlements.filter((item) => ["open", "reopened"].includes(String(item.status).toLowerCase()));
  return active.length >= 1 ? settlementId(active[0]) : undefined;
}

async function ensureOpenSettlement(
  lookups: Lookups,
  refreshLookups: () => void,
  party: Party | undefined,
  currency: string
): Promise<number | undefined> {
  const existing = autoSettlementId(lookups.settlements);
  if (existing) return existing;
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  const created = await api.createSettlement({
    settlement_no: `AUTO-${stamp}`,
    title: party ? `${party.name} settlement` : "Auto settlement",
    primary_party_id: party?.id ?? null,
    base_currency: currency
  });
  refreshLookups();
  return asId(created.id);
}

function cleanAccountName(name: string): string {
  return name.replace(/\bagent advance\b/gi, "Agent Balance").replace(/\bwallet\b/gi, "Balance").replace(/\bledger\b/gi, "Account");
}

function accountLabel(account: Account): string {
  return `${cleanAccountName(account.name)} (${account.currency})`;
}

function partyLabel(party: Party): string {
  return party.default_currency ? `${party.name} (${party.default_currency})` : party.name;
}

function walletTypeForParty(party?: Party): string {
  if (!party) return "clearing";
  if (party.party_type === "customer") return "customer_wallet";
  if (party.party_type === "agent") return "agent_wallet";
  if (party.party_type === "fx_dealer") return "fx_dealer_wallet";
  return "clearing";
}

function isActiveAccount(account?: Account): account is Account {
  return Boolean(account && account.is_active !== false);
}

function partyWallet(accounts: Account[], party?: Party, currency?: string): Account | undefined {
  if (!party || !currency) return undefined;
  const type = walletTypeForParty(party);
  return accounts.find((account) => isActiveAccount(account) && account.party_id === party.id && account.currency === currency && account.account_type === type);
}

function agentAdvanceAccount(accounts: Account[], party?: Party, currency?: string): Account | undefined {
  if (!party || !currency) return undefined;
  return accounts.find((account) => account.party_id === party.id && account.currency === currency && account.account_type === "agent_wallet" && account.is_active !== false);
}

function walletCode(party: Party, currency: string): string {
  return `${party.name.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toUpperCase()}-${currency}-BALANCE`;
}

function options(accounts: Account[], types: string[], currency?: string) {
  return accounts.filter((account) => isActiveAccount(account) && types.includes(account.account_type) && (!currency || account.currency === currency));
}

function commissionIncomeAccount(accounts: Account[], currency: string): Account | undefined {
  return accounts.find((account) => account.account_type === "commission_income" && account.currency === currency && account.is_active !== false);
}

async function ensureCommissionIncomeAccount(lookups: Lookups, currency: string, refreshLookups: () => void): Promise<number | undefined> {
  const existing = commissionIncomeAccount(lookups.accounts, currency);
  if (existing) return existing.id;
  const accountCode = `COMMISSION-${currency}`;
  try {
    const created = await api.createAccount({
      account_code: accountCode,
      name: `Commission ${currency}`,
      account_type: "commission_income",
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = commissionIncomeAccount(latestAccounts as Account[], currency);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

function agentCommissionExpenseAccount(accounts: Account[], currency: string): Account | undefined {
  return accounts.find((account) => account.account_type === "expense" && account.currency === currency && account.account_code === `AGENT-COMMISSION-${currency}` && account.is_active !== false)
    ?? accounts.find((account) => account.account_type === "expense" && account.currency === currency && account.name.toLowerCase().includes("agent commission") && account.is_active !== false);
}

function expenseAccount(accounts: Account[], currency: string, type: "expense" | "bank_charge_expense" = "expense"): Account | undefined {
  const code = type === "bank_charge_expense" ? `BANK-CHARGE-${currency}` : `EXPENSE-${currency}`;
  return accounts.find((account) => account.account_type === type && account.currency === currency && account.account_code === code && account.is_active !== false)
    ?? accounts.find((account) => account.account_type === type && account.currency === currency && account.is_active !== false);
}

async function ensureExpenseAccount(lookups: Lookups, currency: string, refreshLookups: () => void, type: "expense" | "bank_charge_expense" = "expense"): Promise<number | undefined> {
  const existing = expenseAccount(lookups.accounts, currency, type);
  if (existing) return existing.id;
  const accountCode = type === "bank_charge_expense" ? `BANK-CHARGE-${currency}` : `EXPENSE-${currency}`;
  const name = type === "bank_charge_expense" ? `Bank Charges ${currency}` : `General Expense ${currency}`;
  try {
    const created = await api.createAccount({
      account_code: accountCode,
      name,
      account_type: type,
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = expenseAccount(latestAccounts as Account[], currency, type);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

function fxGainLossAccount(accounts: Account[], currency: string): Account | undefined {
  return accounts.find((account) => account.account_type === "fx_gain_loss" && account.currency === currency && account.account_code === `FX-GAIN-LOSS-${currency}` && account.is_active !== false)
    ?? accounts.find((account) => account.account_type === "fx_gain_loss" && account.currency === currency && account.is_active !== false);
}

async function ensureFxGainLossAccount(lookups: Lookups, currency: string, refreshLookups: () => void): Promise<number | undefined> {
  const existing = fxGainLossAccount(lookups.accounts, currency);
  if (existing) return existing.id;
  try {
    const created = await api.createAccount({
      account_code: `FX-GAIN-LOSS-${currency}`,
      name: `Exchange Difference ${currency}`,
      account_type: "fx_gain_loss",
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = fxGainLossAccount(latestAccounts as Account[], currency);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

async function ensureAgentCommissionExpenseAccount(lookups: Lookups, currency: string, refreshLookups: () => void): Promise<number | undefined> {
  const existing = agentCommissionExpenseAccount(lookups.accounts, currency);
  if (existing) return existing.id;
  const accountCode = `AGENT-COMMISSION-${currency}`;
  try {
    const created = await api.createAccount({
      account_code: accountCode,
      name: `Agent Commission ${currency}`,
      account_type: "expense",
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = agentCommissionExpenseAccount(latestAccounts as Account[], currency);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

function findAccount(accounts: Account[], id: string) {
  return accounts.find((account) => account.id === Number(id) && isActiveAccount(account));
}

function inactiveAccountSelection(accounts: Account[], id: string, label: string): string | null {
  if (!id) return null;
  const account = accounts.find((item) => item.id === Number(id));
  if (!account || account.is_active !== false) return null;
  return `${label} ${accountLabel(account)} is inactive. Choose an active account or restore it from Accounts.`;
}

function findParty(parties: Party[], id: string) {
  return parties.find((party) => party.id === Number(id));
}

function defaultUserId(users: ApiRecord[]): number {
  const activeUser = users.find((user) => user.is_active !== false && asId(user.id));
  const id = asId(activeUser?.id);
  if (!id) {
    throw new Error("No active local user found. Run seed command.");
  }
  return id;
}

function SearchSelect({
  label,
  value,
  onChange,
  options: selectOptions,
  placeholder,
  required = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SearchOption[];
  placeholder?: string;
  required?: boolean;
}) {
  const selected = selectOptions.find((option) => option.value === value);
  const [text, setText] = useState(selected?.label ?? "");
  const [searching, setSearching] = useState(false);
  const listId = useMemo(() => `search-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Math.random().toString(36).slice(2)}`, [label]);

  useEffect(() => {
    if (!searching) setText(selected?.label ?? "");
  }, [searching, selected?.label]);

  function choose(nextText: string) {
    setText(nextText);
    const normalized = nextText.trim().toLowerCase();
    const exact = selectOptions.find((option) => option.label.toLowerCase() === normalized);
    if (exact) {
      onChange(exact.value);
    } else if (!nextText.trim()) {
      onChange("");
    }
  }

  function beginSearch() {
    if (searching) return;
    setSearching(true);
    setText("");
  }

  function finishSearch() {
    setSearching(false);
    setText(selected?.label ?? text);
  }

  return (
    <label data-searchable="true">
      <span>{label}</span>
      <input
        required={required}
        list={listId}
        value={text}
        placeholder={placeholder ?? `Search ${label.toLowerCase()}`}
        onFocus={beginSearch}
        onClick={beginSearch}
        onChange={(event) => choose(event.target.value)}
        onBlur={finishSearch}
      />
      <datalist id={listId}>
        {selectOptions.map((option) => (
          <option key={option.value} value={option.label}>{option.keywords}</option>
        ))}
      </datalist>
    </label>
  );
}

function currencySelect(currencies: Currency[], value: string, onChange: (value: string) => void, label = "Currency") {
  return (
    <SearchSelect
      label={label}
      value={value}
      onChange={onChange}
      options={currencies.map((currency) => ({ value: currency.code, label: `${currency.code} - ${currency.name}`, keywords: currency.code }))}
      required
    />
  );
}

function accountSelect(accounts: Account[], value: string, onChange: (value: string) => void, label: string, types: string[], currency?: string, required = true) {
  return (
    <SearchSelect
      label={label}
      value={value}
      onChange={onChange}
      options={options(accounts, types, currency).map((account) => ({
        value: String(account.id),
        label: accountLabel(account),
        keywords: `${account.account_code} ${account.currency}`
      }))}
      required={required}
    />
  );
}

function partySelect(parties: Party[], value: string, onChange: (value: string) => void, required = false, label = "Client") {
  return (
    <SearchSelect
      label={label}
      value={value}
      onChange={onChange}
      options={parties.map((party) => ({
        value: String(party.id),
        label: partyLabel(party),
        keywords: `${party.name} ${party.party_type} ${party.default_currency ?? ""}`
      }))}
      required={required}
    />
  );
}

function PreviewPanel({
  preview,
  payload,
  routeKey,
  onPost,
  posting
}: {
  preview: PreviewResponse;
  payload: ApiRecord | null;
  routeKey: TransactionRouteKey;
  onPost: () => void;
  posting: boolean;
}) {
  const currency = String(payload?.currency ?? payload?.to_currency ?? preview.gross_currency ?? "");
  const component = (type: string) => preview.components.find((item) => item.component_type === type);
  const amountWithCurrency = (value: unknown, fallbackCurrency = currency) => `${value ?? "0.00"} ${fallbackCurrency}`;
  const summaryRows: { label: string; value: string }[] = [];

  const previewRouteKey = String(payload?.__routeKey ?? routeKey);

  if (previewRouteKey === "receipt") {
    summaryRows.push(
      { label: "You are receiving", value: amountWithCurrency(payload?.gross_amount) },
      { label: "Client credited", value: amountWithCurrency(payload?.principal_amount) },
      { label: "Commission earned", value: amountWithCurrency(payload?.commission_amount) }
    );
  } else if (previewRouteKey === "crossCurrencyReceipt") {
    summaryRows.push(
      { label: "You are receiving", value: amountWithCurrency(payload?.gross_amount, String(payload?.received_currency ?? "")) },
      { label: "Client credited", value: amountWithCurrency(payload?.principal_amount, String(payload?.settlement_currency ?? "")) },
      { label: "Commission earned", value: amountWithCurrency(payload?.commission_amount, String(payload?.settlement_currency ?? "")) }
    );
  } else if (previewRouteKey === "payment") {
    summaryRows.push(
      { label: "Money paid from cash/bank", value: amountWithCurrency(payload?.amount) },
      { label: "Client/vendor balance affected", value: amountWithCurrency(payload?.amount) }
    );
  } else if (previewRouteKey === "crossCurrencyPayment") {
    summaryRows.push(
      { label: "Money paid from cash/bank", value: amountWithCurrency(payload?.payment_amount, String(payload?.payment_currency ?? "")) },
      { label: "Client/vendor balance affected", value: amountWithCurrency(payload?.settlement_amount, String(payload?.settlement_currency ?? "")) }
    );
  } else if (previewRouteKey === "agentSettlement") {
    const paymentCurrency = String(payload?.payment_currency ?? currency);
    const settlementCurrency = String(payload?.settlement_currency ?? currency);
    summaryRows.push(
      { label: "Client settled", value: amountWithCurrency(payload?.principal_amount, settlementCurrency) },
      { label: "Agent fee", value: amountWithCurrency(payload?.agent_commission_amount, paymentCurrency) },
      { label: String(payload?.payment_source) === "agent_advance" ? "Previous payment used" : "Pay agent now", value: amountWithCurrency(preview.gross_amount, paymentCurrency) }
    );
  } else if (previewRouteKey === "fxConversion") {
    const fxDifference = component("fx_gain") ?? component("fx_loss");
    summaryRows.push(
      { label: "Given amount", value: amountWithCurrency(payload?.from_amount, String(payload?.from_currency ?? "")) },
      { label: "Received amount", value: amountWithCurrency(payload?.to_amount, String(payload?.to_currency ?? "")) },
      { label: "Exchange Difference", value: amountWithCurrency(fxDifference?.amount ?? "0.00", String(fxDifference?.currency ?? payload?.to_currency ?? "")) }
    );
  } else {
    summaryRows.push({ label: "Amount", value: amountWithCurrency(payload?.amount) });
  }

  const accountingRows = preview.components.map((item) => ({
    item: item.component_type,
    amount: `${item.amount ?? ""} ${item.currency ?? ""}`,
    direction: item.direction
  }));

  return (
    <div className="preview-panel">
      {preview.warnings.length > 0 && <div className="state-block warning">{preview.warnings.join(", ")}</div>}
      <h2>Preview</h2>
      <div className="operator-preview">
        {summaryRows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
      <details>
        <summary>Show accounting details</summary>
        <h2>Voucher details</h2>
        <DataTable rows={accountingRows} />
        {preview.fx_detail && (
          <>
            <h2>Exchange details</h2>
            <DataTable rows={[preview.fx_detail]} />
          </>
        )}
        <h2>Posting entries</h2>
        <DataTable rows={preview.ledger_entries} />
        <h2>Account changes</h2>
        <DataTable rows={preview.account_balance_effects} />
      </details>
      <button className="primary-action" type="button" onClick={onPost} disabled={posting}>
        {posting ? "Posting..." : "Confirm Post"}
      </button>
    </div>
  );
}

function advancedBlock(children: ReactNode) {
  return <details className="advanced-details"><summary>Advanced details</summary><div className="entry-form compact">{children}</div></details>;
}

function MissingBalanceNotice({ party, currency, onCreate, busy }: { party?: Party; currency: string; onCreate: () => void; busy: boolean }) {
  if (!party || !currency) return null;
  return (
    <div className="state-block warning wallet-warning">
      <span>No {currency} Client Balance exists for {party.name}. Create {party.name} {currency} Client Balance.</span>
      <button type="button" onClick={onCreate} disabled={busy}>{busy ? "Creating..." : "Create Client Balance"}</button>
    </div>
  );
}

async function createPartyWallet(party: Party, currency: string) {
  const accountCode = walletCode(party, currency);
  return api.createAccount({
    account_code: accountCode,
    name: `${party.name} ${currency} Balance`,
    account_type: walletTypeForParty(party),
    currency,
    party_id: party.id
  });
}

async function createAgentAdvance(party: Party, currency: string) {
  const accountCode = `${walletCode(party, currency)}-ADVANCE`;
  return api.createAccount({
    account_code: accountCode,
    name: `${party.name} ${currency} Agent Advance`,
    account_type: "agent_wallet",
    currency,
    party_id: party.id
  });
}

function hiddenClearingAccount(accounts: Account[], currency: string): Account | undefined {
  return accounts.find((account) => account.account_type === "clearing" && account.currency === currency && account.account_code === `FX-CLEARING-${currency}` && account.is_active !== false)
    ?? accounts.find((account) => account.account_type === "clearing" && account.currency === currency && account.is_active !== false);
}

async function ensureHiddenClearingAccount(lookups: Lookups, currency: string, refreshLookups: () => void): Promise<number | undefined> {
  const existing = hiddenClearingAccount(lookups.accounts, currency);
  if (existing) return existing.id;
  try {
    const created = await api.createAccount({
      account_code: `FX-CLEARING-${currency}`,
      name: `FX Clearing ${currency}`,
      account_type: "clearing",
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = hiddenClearingAccount(latestAccounts as Account[], currency);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

function openingSourceAccount(accounts: Account[], currency: string): Account | undefined {
  return accounts.find((account) => account.account_type === "owner_equity" && account.currency === currency && account.account_code === `OPENING-SOURCE-${currency}` && account.is_active !== false)
    ?? accounts.find((account) => account.account_type === "owner_equity" && account.currency === currency && account.is_active !== false);
}

async function ensureOpeningSourceAccount(lookups: Lookups, currency: string, refreshLookups: () => void): Promise<number | undefined> {
  const existing = openingSourceAccount(lookups.accounts, currency);
  if (existing) return existing.id;
  try {
    const created = await api.createAccount({
      account_code: `OPENING-SOURCE-${currency}`,
      name: `Opening Balance Source ${currency}`,
      account_type: "owner_equity",
      currency
    });
    refreshLookups();
    return asId(created.id);
  } catch (err) {
    const latestAccounts = await api.accounts();
    const latest = openingSourceAccount(latestAccounts as Account[], currency);
    if (latest) {
      refreshLookups();
      return latest.id;
    }
    throw err;
  }
}

type VoucherProps = {
  lookups: Lookups;
  routeKey: TransactionRouteKey;
  submit: (payload: ApiRecord) => void;
  refreshLookups: () => void;
  resetPreview: () => void;
  busy: boolean;
};

function ReceiptVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({
    date: todayDate(),
    party: "",
    receiveIn: "",
    currency: "USD",
    amountMode: "net",
    amount: "",
    commissionType: "none",
    commissionValue: "",
    exchangeRate: "",
    reference: ""
  });
  const exchangeRateInputRef = useRef<HTMLInputElement>(null);
  const [walletBusy, setWalletBusy] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const receiveAccount = findAccount(lookups.accounts, form.receiveIn);
  const moneyCurrency = receiveAccount?.currency ?? form.currency;
  const selectedParty = findParty(lookups.parties, form.party);
  const clientCurrency = selectedParty?.default_currency ?? moneyCurrency;
  const isCrossCurrency = moneyCurrency !== clientCurrency;
  const commissionValue = decimal(form.commissionValue);
  const amount = decimal(form.amount);
  const exchangeRate = decimal(form.exchangeRate);
  const clientAmount = isCrossCurrency ? baseValueFromQuotedRate(amount, exchangeRate) : amount;
  const { gross, principal, commission } = receiptAmounts(clientAmount, form.amountMode, form.commissionType, commissionValue);
  const approxBaseValue = baseValueFromQuotedRate(amount, exchangeRate);
  const clientBalance = partyWallet(lookups.accounts, selectedParty, clientCurrency);
  const inactiveReceiveIn = inactiveAccountSelection(lookups.accounts, form.receiveIn, "Receive In");
  const canPreview = Boolean(clientBalance && receiveAccount && principal >= 0 && amount > 0 && (!isCrossCurrency || exchangeRate > 0));

  useEffect(() => {
    if (isCrossCurrency) exchangeRateInputRef.current?.focus();
  }, [isCrossCurrency, moneyCurrency, clientCurrency]);

  async function quickCreateBalance() {
    if (!selectedParty) return;
    setWalletBusy(true);
    try {
      await createPartyWallet(selectedParty, clientCurrency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    setSetupError(null);
    let commissionAccountId: number | undefined;
    try {
      commissionAccountId = commission > 0 ? await ensureCommissionIncomeAccount(lookups, clientCurrency, refreshLookups) : undefined;
    } catch (err) {
      setSetupError((err as Error).message);
      return;
    }
    if (isCrossCurrency) {
      let sourceClearingId: number | undefined;
      let targetClearingId: number | undefined;
      try {
        sourceClearingId = await ensureHiddenClearingAccount(lookups, moneyCurrency, refreshLookups);
        targetClearingId = await ensureHiddenClearingAccount(lookups, clientCurrency, refreshLookups);
      } catch (err) {
        setSetupError((err as Error).message);
        return;
      }
      submit({
        transaction_date: form.date,
        created_by_user_id: defaultUserId(lookups.users),
        settlement_id: autoSettlementId(lookups.settlements),
        __routeKey: "crossCurrencyReceipt",
        receiving_account_id: asId(form.receiveIn),
        clearing_account_id: clientBalance?.id,
        source_clearing_account_id: sourceClearingId,
        target_clearing_account_id: targetClearingId,
        gross_amount: money(amount),
        principal_amount: money(principal),
        commission_amount: money(commission),
        commission_income_account_id: commissionAccountId,
        received_currency: moneyCurrency,
        settlement_currency: clientCurrency,
        base_currency: clientCurrency,
        original_rate: storedOriginalRateFromQuote(exchangeRate),
        description: form.reference || undefined
      });
      return;
    }
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      receiving_account_id: asId(form.receiveIn),
      clearing_account_id: clientBalance?.id,
      gross_amount: money(isCrossCurrency ? amount : gross),
      principal_amount: money(principal),
      commission_amount: money(commission),
      commission_income_account_id: commissionAccountId,
      currency: clientCurrency,
      base_currency: clientCurrency,
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => {
        const selected = findParty(lookups.parties, party);
        setForm({ ...form, party, currency: selected?.default_currency ?? form.currency });
      }, true, "Client")}
      {accountSelect(lookups.accounts, form.receiveIn, (receiveIn) => {
        const selected = findAccount(lookups.accounts, receiveIn);
        setForm({ ...form, receiveIn, currency: selected?.currency ?? form.currency });
      }, "Receive In", ["cash", "bank"])}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      {isCrossCurrency && (
        <CrossCurrencyRateBox
          moneyCurrency={moneyCurrency}
          clientCurrency={clientCurrency}
          amount={amount}
          exchangeRate={form.exchangeRate}
          action="receiving"
          inputRef={exchangeRateInputRef}
          onRateChange={(exchangeRate) => setForm({ ...form, exchangeRate })}
        />
      )}
      <label><span>Amount Type</span><select value={form.amountMode} onChange={(event) => setForm({ ...form, amountMode: event.target.value })}><option value="net">Net Received</option><option value="gross">Gross Received</option></select></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Commission</span><select value={form.commissionType} onChange={(event) => setForm({ ...form, commissionType: event.target.value })}><option value="none">none</option><option value="percentage">%</option><option value="fixed">fixed</option></select></label>
      <label><span>Commission Value</span><input value={form.commissionValue} onChange={(event) => setForm({ ...form, commissionValue: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>You are receiving {money(isCrossCurrency ? amount : gross)} {moneyCurrency}</span>
        {isCrossCurrency && <span>Rate 1 {clientCurrency} = {form.exchangeRate || "0"} {moneyCurrency}</span>}
        <span>Client credited {money(principal)} {clientCurrency}</span>
        <span>Commission earned {money(commission)} {clientCurrency}</span>
        {receiveAccount && <span>Money received in {accountLabel(receiveAccount)}</span>}
        <span>Client balance {clientBalance ? accountLabel(clientBalance) : "Missing"}</span>
      </div>
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactiveReceiveIn && <p className="form-note danger-note">{inactiveReceiveIn}</p>}
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={clientCurrency} onCreate={quickCreateBalance} busy={walletBusy} />}
      {isCrossCurrency && advancedBlock(
        <>
          <div className="voucher-plain-summary">
            <span>Client amount {money(approxBaseValue)} {clientCurrency}</span>
          </div>
        </>
      )}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

function PaymentVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ date: todayDate(), party: "", payFrom: "", currency: "USD", amount: "", reference: "" });
  const selectedParty = findParty(lookups.parties, form.party);
  const payAccount = findAccount(lookups.accounts, form.payFrom);
  const currency = payAccount?.currency ?? form.currency;
  const clientBalance = partyWallet(lookups.accounts, selectedParty, currency);
  const [walletBusy, setWalletBusy] = useState(false);
  const amount = decimal(form.amount);
  const cashWarning = cashShortageMessage(payAccount, amount);
  const inactivePayFrom = inactiveAccountSelection(lookups.accounts, form.payFrom, "Pay From");
  const canPreview = Boolean(clientBalance && payAccount && amount > 0 && !cashWarning);

  async function quickCreateBalance() {
    if (!selectedParty) return;
    setWalletBusy(true);
    try {
      await createPartyWallet(selectedParty, currency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      paying_account_id: asId(form.payFrom),
      clearing_account_id: clientBalance?.id,
      amount: money(amount),
      currency,
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => setForm({ ...form, party }), true, "Client / Vendor")}
      {accountSelect(lookups.accounts, form.payFrom, (payFrom) => {
        const selected = findAccount(lookups.accounts, payFrom);
        setForm({ ...form, payFrom, currency: selected?.currency ?? form.currency });
      }, "Pay From", ["cash", "bank"])}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>Money paid from cash/bank {money(amount)} {currency}</span>
        {payAccount && <span>Available {money(accountBalance(payAccount))} {currency}</span>}
        <span>Client/vendor balance affected {money(amount)} {currency}</span>
        <span>Client balance {clientBalance ? accountLabel(clientBalance) : "Missing"}</span>
      </div>
      {cashWarning && <p className="form-note danger-note">{cashWarning}</p>}
      {inactivePayFrom && <p className="form-note danger-note">{inactivePayFrom}</p>}
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={currency} onCreate={quickCreateBalance} busy={walletBusy} />}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

function AgentSettlementVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ date: todayDate(), client: "", agent: "", paymentSource: "agent_advance", payFrom: "", advanceCurrency: "USD", amountMode: "net", amount: "", commissionType: "fixed", agentCommission: "", exchangeRate: "", reference: "" });
  const exchangeRateInputRef = useRef<HTMLInputElement>(null);
  const [walletBusy, setWalletBusy] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const selectedClient = findParty(lookups.parties, form.client);
  const selectedAgent = findParty(lookups.parties, form.agent);
  const payAccount = findAccount(lookups.accounts, form.payFrom);
  const usesAdvance = form.paymentSource === "agent_advance";
  const paymentCurrency = usesAdvance ? form.advanceCurrency : (payAccount?.currency ?? selectedClient?.default_currency ?? "USD");
  const advanceAccount = agentAdvanceAccount(lookups.accounts, selectedAgent, paymentCurrency);
  const paymentSourceAccount = usesAdvance ? advanceAccount : payAccount;
  const settlementCurrency = selectedClient?.default_currency ?? paymentCurrency;
  const isCrossCurrency = paymentCurrency !== settlementCurrency;
  const exchangeRate = decimal(form.exchangeRate);
  const clientBalance = partyWallet(lookups.accounts, selectedClient, settlementCurrency);
  const amount = decimal(form.amount);
  const split = splitCommissionAmount(amount, form.amountMode, form.commissionType, decimal(form.agentCommission));
  const paymentPrincipal = split.principal;
  const agentCommission = split.commission;
  const paidToAgent = split.gross;
  const principal = isCrossCurrency ? baseValueFromQuotedRate(paymentPrincipal, exchangeRate) : paymentPrincipal;
  const settlementIdValue = autoSettlementId(lookups.settlements);
  const cashWarning = usesAdvance
    ? balanceShortageMessage(advanceAccount, paidToAgent, "Add opening balance first, or change Payment to Pay now.")
    : cashShortageMessage(payAccount, paidToAgent);
  const sourceBalance = paymentSourceAccount ? accountBalance(paymentSourceAccount) : 0;
  const showSourceBalance = Boolean(paymentSourceAccount && !cashWarning);
  const inactivePayFrom = inactiveAccountSelection(lookups.accounts, form.payFrom, "Pay From");
  const previewBlockedReason = !usesAdvance && inactivePayFrom
    ? inactivePayFrom
    : !selectedClient
    ? "Select Client."
    : !selectedAgent
      ? "Select Agent / Vendor."
      : usesAdvance && !advanceAccount
        ? `No ${paymentCurrency} balance exists for ${selectedAgent.name}.`
      : !usesAdvance && !payAccount
        ? "Select Pay From."
        : isCrossCurrency && exchangeRate <= 0
          ? `Enter Exchange Rate. Rate means 1 ${settlementCurrency} = ? ${paymentCurrency}.`
          : !clientBalance
            ? `Create ${settlementCurrency} Client Balance for ${selectedClient.name}.`
            : principal <= 0
                ? "Enter Amount."
                : agentCommission < 0
                  ? "Agent Commission cannot be negative."
                  : cashWarning;
  const canPreview = !previewBlockedReason;

  useEffect(() => {
    if (isCrossCurrency) exchangeRateInputRef.current?.focus();
  }, [isCrossCurrency, paymentCurrency, settlementCurrency]);

  function updateForm(next: Partial<typeof form>) {
    setForm((current) => ({ ...current, ...next }));
    setSetupError(null);
  }

  async function quickCreateBalance() {
    if (!selectedClient) return;
    setWalletBusy(true);
    try {
      await createPartyWallet(selectedClient, settlementCurrency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  async function quickCreateAgentAdvance() {
    if (!selectedAgent) return;
    setWalletBusy(true);
    try {
      await createAgentAdvance(selectedAgent, paymentCurrency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    setSetupError(null);
    let expenseAccountId: number | undefined;
    let activeSettlementId = settlementIdValue;
    try {
      activeSettlementId = await ensureOpenSettlement(lookups, refreshLookups, selectedClient, settlementCurrency);
    } catch (err) {
      setSetupError((err as Error).message);
      return;
    }
    try {
      expenseAccountId = await ensureAgentCommissionExpenseAccount(lookups, paymentCurrency, refreshLookups);
    } catch (err) {
      setSetupError((err as Error).message);
      return;
    }
    let sourceClearingId: number | undefined;
    let targetClearingId: number | undefined;
    if (isCrossCurrency) {
      try {
        sourceClearingId = await ensureHiddenClearingAccount(lookups, paymentCurrency, refreshLookups);
        targetClearingId = await ensureHiddenClearingAccount(lookups, settlementCurrency, refreshLookups);
      } catch (err) {
        setSetupError((err as Error).message);
        return;
      }
    }
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: activeSettlementId,
      paying_account_id: usesAdvance ? undefined : asId(form.payFrom),
      agent_advance_account_id: usesAdvance ? advanceAccount?.id : undefined,
      clearing_account_id: clientBalance?.id,
      agent_commission_expense_account_id: expenseAccountId,
      source_clearing_account_id: sourceClearingId,
      target_clearing_account_id: targetClearingId,
      agent_party_id: asId(form.agent),
      principal_amount: money(principal),
      payment_principal_amount: money(paymentPrincipal),
      agent_commission_amount: money(agentCommission),
      currency: settlementCurrency,
      payment_currency: paymentCurrency,
      settlement_currency: settlementCurrency,
      payment_source: usesAdvance ? "agent_advance" : "cash_bank",
      original_rate: isCrossCurrency ? storedOriginalRateFromQuote(exchangeRate) : undefined,
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.client, (client) => updateForm({ client }), true, "Client")}
      {partySelect(lookups.parties, form.agent, (agent) => updateForm({ agent }), true, "Agent / Vendor")}
      <label><span>Payment</span><select value={form.paymentSource} onChange={(event) => updateForm({ paymentSource: event.target.value })}><option value="agent_advance">Adjust previous payment</option><option value="cash_bank">Pay now from Cash/Bank</option></select></label>
      {usesAdvance
        ? currencySelect(lookups.currencies, form.advanceCurrency, (advanceCurrency) => updateForm({ advanceCurrency }), "Currency")
        : accountSelect(lookups.accounts, form.payFrom, (payFrom) => updateForm({ payFrom }), "Pay From", ["cash", "bank"])}
      {usesAdvance && selectedAgent && !advanceAccount && (
        <div className="state-block warning">
          <span>No {paymentCurrency} balance exists for {selectedAgent?.name}. Create it to adjust money already paid.</span>
          <button type="button" onClick={quickCreateAgentAdvance} disabled={walletBusy}>{walletBusy ? "Creating..." : "Create Agent Balance"}</button>
        </div>
      )}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => updateForm({ date: event.target.value })} /></label>
      <label><span>Amount Type</span><select value={form.amountMode} onChange={(event) => updateForm({ amountMode: event.target.value })}><option value="net">Principal Amount</option><option value="gross">Paid to Agent</option></select></label>
      <label><span>Amount ({paymentCurrency})</span><input required value={form.amount} onChange={(event) => updateForm({ amount: event.target.value })} /></label>
      {isCrossCurrency && (
        <CrossCurrencyRateBox
          moneyCurrency={paymentCurrency}
          clientCurrency={settlementCurrency}
          amount={paymentPrincipal}
          exchangeRate={form.exchangeRate}
          action="paying"
          inputRef={exchangeRateInputRef}
          onRateChange={(exchangeRate) => updateForm({ exchangeRate })}
        />
      )}
      <label><span>Agent Commission</span><select value={form.commissionType} onChange={(event) => updateForm({ commissionType: event.target.value })}><option value="fixed">fixed</option><option value="percentage">%</option><option value="none">none</option></select></label>
      <label><span>Commission Value</span><input value={form.agentCommission} onChange={(event) => updateForm({ agentCommission: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => updateForm({ reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>Client settled: {money(principal)} {settlementCurrency}</span>
        <span>Agent fee: {money(agentCommission)} {paymentCurrency}</span>
        <span>{usesAdvance ? "Previous payment used" : "Pay agent now"}: {money(paidToAgent)} {paymentCurrency}</span>
        {isCrossCurrency && <span>Rate 1 {settlementCurrency} = {form.exchangeRate || "0"} {paymentCurrency}</span>}
        {showSourceBalance && <span>Agent balance: {money(sourceBalance)} {paymentCurrency}</span>}
      </div>
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactivePayFrom && !usesAdvance && <p className="form-note danger-note">{inactivePayFrom}</p>}
      {!clientBalance && <MissingBalanceNotice party={selectedClient} currency={settlementCurrency} onCreate={quickCreateBalance} busy={walletBusy} />}
      <div className="voucher-action-row">
        <button type="submit" className="primary-action" disabled={busy || !canPreview}>Preview Voucher</button>
        {!canPreview && <span className="action-hint">{previewBlockedReason}</span>}
      </div>
    </form>
  );
}

const emptyCashBankEntryForm = {
  date: todayDate(),
  entryType: "receipt",
  cashBank: "",
  party: "",
  currency: "USD",
  amount: "",
  amountMode: "net",
  commissionType: "none",
  commissionValue: "",
  exchangeRate: "",
  reference: ""
};

function CashBankEntryVoucher({ lookups, submit, refreshLookups, resetPreview, busy }: VoucherProps) {
  const [form, setForm] = useState(emptyCashBankEntryForm);
  const exchangeRateInputRef = useRef<HTMLInputElement>(null);
  const [walletBusy, setWalletBusy] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const cashBankAccount = findAccount(lookups.accounts, form.cashBank);
  const moneyCurrency = cashBankAccount?.currency ?? form.currency;
  const selectedParty = findParty(lookups.parties, form.party);
  const clientCurrency = selectedParty?.default_currency ?? moneyCurrency;
  const isReceipt = form.entryType === "receipt";
  const isCrossCurrency = moneyCurrency !== clientCurrency;
  const exchangeRate = decimal(form.exchangeRate);
  const convertedClientAmount = isCrossCurrency ? baseValueFromQuotedRate(decimal(form.amount), exchangeRate) : decimal(form.amount);
  const clientBalance = partyWallet(lookups.accounts, selectedParty, clientCurrency);
  const clientBalances = selectedParty
    ? lookups.accounts.filter((account) => account.is_active !== false && account.party_id === selectedParty.id && ["customer_wallet", "agent_wallet", "fx_dealer_wallet", "clearing"].includes(account.account_type))
    : [];
  const amount = decimal(form.amount);
  const commissionValue = decimal(form.commissionValue);
  const receipt = isReceipt ? receiptAmounts(convertedClientAmount, form.amountMode, form.commissionType, commissionValue) : { gross: amount, principal: amount, commission: 0 };
  const { gross, principal, commission } = receipt;
  const cashWarning = !isReceipt ? cashShortageMessage(cashBankAccount, amount) : null;
  const inactiveCashBank = inactiveAccountSelection(lookups.accounts, form.cashBank, "Cash/Bank");
  const previewBlockedReason = inactiveCashBank
    ? inactiveCashBank
    : !cashBankAccount
    ? "Select Cash/Bank."
    : !selectedParty
      ? "Select Party."
      : isCrossCurrency && exchangeRate <= 0
        ? `Enter Exchange Rate. Rate means 1 ${clientCurrency} = ? ${moneyCurrency}.`
      : !clientBalance
        ? `Create ${clientCurrency} Client Balance for ${selectedParty.name}.`
        : amount <= 0
          ? "Enter Amount."
          : principal < 0
            ? "Commission cannot be more than amount."
            : cashWarning;
  const canPreview = !previewBlockedReason;

  useEffect(() => {
    if (isCrossCurrency) exchangeRateInputRef.current?.focus();
  }, [isCrossCurrency, moneyCurrency, clientCurrency]);

  function updateForm(next: Partial<typeof emptyCashBankEntryForm>) {
    setForm((current) => ({ ...current, ...next }));
    setSetupError(null);
    resetPreview();
  }

  function deleteDraft() {
    setForm(emptyCashBankEntryForm);
    resetPreview();
  }

  async function quickCreateBalance() {
    if (!selectedParty) return;
    setWalletBusy(true);
    try {
      await createPartyWallet(selectedParty, clientCurrency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    setSetupError(null);
    let commissionAccountId: number | undefined;
    try {
      commissionAccountId = isReceipt && commission > 0 ? await ensureCommissionIncomeAccount(lookups, clientCurrency, refreshLookups) : undefined;
    } catch (err) {
      setSetupError((err as Error).message);
      return;
    }
    const common = {
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      clearing_account_id: clientBalance?.id,
      currency: isCrossCurrency ? clientCurrency : moneyCurrency,
      description: form.reference || undefined
    };
    if (isReceipt) {
      if (isCrossCurrency) {
        let sourceClearingId: number | undefined;
        let targetClearingId: number | undefined;
        try {
          sourceClearingId = await ensureHiddenClearingAccount(lookups, moneyCurrency, refreshLookups);
          targetClearingId = await ensureHiddenClearingAccount(lookups, clientCurrency, refreshLookups);
        } catch (err) {
          setSetupError((err as Error).message);
          return;
        }
        submit({
          ...common,
          __routeKey: "crossCurrencyReceipt",
          receiving_account_id: asId(form.cashBank),
          source_clearing_account_id: sourceClearingId,
          target_clearing_account_id: targetClearingId,
          gross_amount: money(amount),
          principal_amount: money(principal),
          commission_amount: money(commission),
          commission_income_account_id: commissionAccountId,
          received_currency: moneyCurrency,
          settlement_currency: clientCurrency,
          base_currency: clientCurrency,
          original_rate: storedOriginalRateFromQuote(exchangeRate)
        });
        return;
      }
      submit({
        ...common,
        __routeKey: "receipt",
        receiving_account_id: asId(form.cashBank),
        gross_amount: money(gross),
        principal_amount: money(principal),
        commission_amount: money(commission),
        commission_income_account_id: commissionAccountId,
        base_currency: DEFAULT_BASE_CURRENCY
      });
      return;
    }
    if (isCrossCurrency) {
      let sourceClearingId: number | undefined;
      let targetClearingId: number | undefined;
      try {
        sourceClearingId = await ensureHiddenClearingAccount(lookups, moneyCurrency, refreshLookups);
        targetClearingId = await ensureHiddenClearingAccount(lookups, clientCurrency, refreshLookups);
      } catch (err) {
        setSetupError((err as Error).message);
        return;
      }
      submit({
        ...common,
        __routeKey: "crossCurrencyPayment",
        paying_account_id: asId(form.cashBank),
        source_clearing_account_id: sourceClearingId,
        target_clearing_account_id: targetClearingId,
        payment_amount: money(amount),
        settlement_amount: money(convertedClientAmount),
        payment_currency: moneyCurrency,
        settlement_currency: clientCurrency,
        base_currency: clientCurrency,
        original_rate: storedOriginalRateFromQuote(exchangeRate)
      });
      return;
    }
    submit({
      ...common,
      __routeKey: "payment",
      paying_account_id: asId(form.cashBank),
      amount: money(amount)
    });
  }

  return (
    <form className="entry-form voucher-form cash-bank-entry-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.cashBank, (cashBank) => {
        const selected = findAccount(lookups.accounts, cashBank);
        updateForm({ cashBank, currency: selected?.currency ?? form.currency });
      }, "Cash/Bank", ["cash", "bank"])}
      <label><span>Entry Type</span><select value={form.entryType} onChange={(event) => updateForm({ entryType: event.target.value })}><option value="receipt">Receipt</option><option value="payment">Payment</option></select></label>
      {partySelect(lookups.parties, form.party, (party) => updateForm({ party }), true, "Party")}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => updateForm({ date: event.target.value })} /></label>
      <label><span>{isReceipt ? "Amount Received" : "Amount Paid"}</span><input required value={form.amount} onChange={(event) => updateForm({ amount: event.target.value })} /></label>
      {isCrossCurrency && (
        <CrossCurrencyRateBox
          moneyCurrency={moneyCurrency}
          clientCurrency={clientCurrency}
          amount={amount}
          exchangeRate={form.exchangeRate}
          action={isReceipt ? "receiving" : "paying"}
          inputRef={exchangeRateInputRef}
          onRateChange={(exchangeRate) => updateForm({ exchangeRate })}
        />
      )}
      {isReceipt && <label><span>Amount Type</span><select value={form.amountMode} onChange={(event) => updateForm({ amountMode: event.target.value })}><option value="net">Net Received</option><option value="gross">Gross Received</option></select></label>}
      {isReceipt && <label><span>Commission</span><select value={form.commissionType} onChange={(event) => updateForm({ commissionType: event.target.value })}><option value="none">none</option><option value="percentage">%</option><option value="fixed">fixed</option></select></label>}
      {isReceipt && <label><span>Commission Value</span><input value={form.commissionValue} onChange={(event) => updateForm({ commissionValue: event.target.value })} /></label>}
      <label><span>Reference</span><input value={form.reference} onChange={(event) => updateForm({ reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>{accountLabel(cashBankAccount ?? ({ name: "Cash/Bank", currency: moneyCurrency } as Account))} {isReceipt ? "+" : "-"}{money(amount)} {moneyCurrency}</span>
        {cashBankAccount && <span>Available {money(accountBalance(cashBankAccount))} {moneyCurrency}</span>}
        {isCrossCurrency && <span>Rate 1 {clientCurrency} = {form.exchangeRate || "0"} {moneyCurrency}</span>}
        <span>{selectedParty?.name ?? "Party"} balance {isReceipt ? "+" : "-"}{money(isReceipt ? principal : convertedClientAmount)} {clientCurrency}</span>
        {isReceipt && commission > 0 && <span>Commission +{money(commission)} {clientCurrency}</span>}
      </div>
      {clientBalances.length > 0 && (
        <div className="client-currency-strip">
          {clientBalances.map((account) => <span key={account.id}>{account.currency}: {String(account.current_balance ?? "0.00")}</span>)}
        </div>
      )}
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactiveCashBank && <p className="form-note danger-note">{inactiveCashBank}</p>}
      {cashWarning && <p className="form-note danger-note">{cashWarning}</p>}
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={clientCurrency} onCreate={quickCreateBalance} busy={walletBusy} />}
      <div className="voucher-action-row">
        <button type="submit" className="primary-action" disabled={busy || !canPreview}>Preview Voucher</button>
        <button type="button" className="secondary-action" onClick={resetPreview}>Edit</button>
        <button type="button" className="danger-action" onClick={deleteDraft}>Delete Draft</button>
        {!canPreview && <span className="action-hint">{previewBlockedReason}</span>}
      </div>
    </form>
  );
}

function TransferVoucher({ lookups, routeKey, submit, busy }: VoucherProps) {
  const isBank = routeKey === "bankTransfer";
  const accountTypes = isBank ? ["bank"] : ["cash"];
  const [form, setForm] = useState({ date: todayDate(), from: "", to: "", currency: "USD", amount: "", reference: "" });
  const fromAccount = findAccount(lookups.accounts, form.from);
  const amount = decimal(form.amount);
  const cashWarning = cashShortageMessage(fromAccount, amount);
  const inactiveFrom = inactiveAccountSelection(lookups.accounts, form.from, isBank ? "Transfer From" : "Hand Over From");
  const inactiveTo = inactiveAccountSelection(lookups.accounts, form.to, isBank ? "Transfer To" : "Hand Over To");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (cashWarning || inactiveFrom || inactiveTo) return;
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      from_account_id: asId(form.from),
      to_account_id: asId(form.to),
      amount: form.amount,
      currency: form.currency,
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.from, (from) => {
        const selected = findAccount(lookups.accounts, from);
        setForm({ ...form, from, currency: selected?.currency ?? form.currency });
      }, isBank ? "Transfer From" : "Hand Over From", accountTypes)}
      {accountSelect(lookups.accounts, form.to, (to) => setForm({ ...form, to }), isBank ? "Transfer To" : "Hand Over To", accountTypes, form.currency)}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      {fromAccount && <div className="voucher-plain-summary"><span>Available {money(accountBalance(fromAccount))} {form.currency}</span></div>}
      {inactiveFrom && <p className="form-note danger-note">{inactiveFrom}</p>}
      {inactiveTo && <p className="form-note danger-note">{inactiveTo}</p>}
      {cashWarning && <p className="form-note danger-note">{cashWarning}</p>}
      <button type="submit" disabled={busy || Boolean(cashWarning || inactiveFrom || inactiveTo)}>Preview</button>
    </form>
  );
}

function ExpenseVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ date: todayDate(), paidFrom: "", expense: "", currency: "USD", amount: "", expenseType: "other", affectsSettlement: false, reference: "" });
  const [setupError, setSetupError] = useState<string | null>(null);
  const paidFromAccount = findAccount(lookups.accounts, form.paidFrom);
  const amount = decimal(form.amount);
  const cashWarning = cashShortageMessage(paidFromAccount, amount);
  const selectedExpense = findAccount(lookups.accounts, form.expense) ?? expenseAccount(lookups.accounts, form.currency);
  const inactivePaidFrom = inactiveAccountSelection(lookups.accounts, form.paidFrom, "Paid From");
  const inactiveExpense = inactiveAccountSelection(lookups.accounts, form.expense, "Expense Type");

  async function quickCreateExpense() {
    setSetupError(null);
    try {
      const id = await ensureExpenseAccount(lookups, form.currency, refreshLookups);
      if (id) setForm((current) => ({ ...current, expense: String(id) }));
    } catch (err) {
      setSetupError((err as Error).message);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (cashWarning || inactivePaidFrom || inactiveExpense || amount <= 0 || !paidFromAccount) return;
    setSetupError(null);
    let expenseAccountId = asId(form.expense) ?? selectedExpense?.id;
    if (!expenseAccountId) {
      try {
        expenseAccountId = await ensureExpenseAccount(lookups, form.currency, refreshLookups);
        if (expenseAccountId) setForm((current) => ({ ...current, expense: String(expenseAccountId) }));
      } catch (err) {
        setSetupError((err as Error).message);
        return;
      }
    }
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      payment_account_id: asId(form.paidFrom),
      expense_account_id: expenseAccountId,
      amount: form.amount,
      currency: form.currency,
      expense_type: form.expenseType || "other",
      affects_settlement: form.affectsSettlement,
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.paidFrom, (paidFrom) => {
        const selected = findAccount(lookups.accounts, paidFrom);
        setForm({ ...form, paidFrom, currency: selected?.currency ?? form.currency });
      }, "Paid From", ["cash", "bank"])}
      {accountSelect(lookups.accounts, form.expense, (expense) => setForm({ ...form, expense }), "Expense Type", ["expense", "bank_charge_expense"], form.currency)}
      {!selectedExpense && (
        <div className="state-block warning">
          <span>No expense type exists for {form.currency}.</span>
          <button type="button" onClick={quickCreateExpense}>Create Expense Type</button>
        </div>
      )}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Category</span><input value={form.expenseType} onChange={(event) => setForm({ ...form, expenseType: event.target.value })} /></label>
      <label className="checkbox-line"><input type="checkbox" checked={form.affectsSettlement} onChange={(event) => setForm({ ...form, affectsSettlement: event.target.checked })} /> <span>Charge to client</span></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      {paidFromAccount && <div className="voucher-plain-summary"><span>Available {money(accountBalance(paidFromAccount))} {form.currency}</span></div>}
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactivePaidFrom && <p className="form-note danger-note">{inactivePaidFrom}</p>}
      {inactiveExpense && <p className="form-note danger-note">{inactiveExpense}</p>}
      {cashWarning && <p className="form-note danger-note">{cashWarning}</p>}
      <button type="submit" disabled={busy || Boolean(cashWarning || inactivePaidFrom || inactiveExpense) || amount <= 0 || !paidFromAccount}>Preview</button>
    </form>
  );
}

function FxVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ date: todayDate(), party: "", fromCurrency: "EUR", toCurrency: "USD", fromAmount: "", toAmount: "", fxCharge: "0", chargeAccount: "", allowNegativeBalance: false, allowMissingRateHistory: true, reference: "" });
  const [walletBusy, setWalletBusy] = useState<"from" | "to" | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const selectedParty = findParty(lookups.parties, form.party);
  const fromWallet = partyWallet(lookups.accounts, selectedParty, form.fromCurrency);
  const toWallet = partyWallet(lookups.accounts, selectedParty, form.toCurrency);
  const actualRate = decimal(form.fromAmount) ? decimal(form.toAmount) / decimal(form.fromAmount) : 0;
  const sourceShortfall = fromWallet ? decimal(form.fromAmount) - accountBalance(fromWallet) : 0;
  const inactiveChargeAccount = inactiveAccountSelection(lookups.accounts, form.chargeAccount, "Fee Type");
  const canPreview = Boolean(selectedParty && fromWallet && toWallet && decimal(form.fromAmount) > 0 && decimal(form.toAmount) > 0);

  async function quickCreateBalance(currency: string, target: "from" | "to") {
    if (!selectedParty) return;
    setWalletBusy(target);
    try {
      await createPartyWallet(selectedParty, currency);
      refreshLookups();
    } finally {
      setWalletBusy(null);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    setSetupError(null);
    void (async () => {
      try {
        const sourceClearingId = await ensureHiddenClearingAccount(lookups, form.fromCurrency, refreshLookups);
        const targetClearingId = await ensureHiddenClearingAccount(lookups, form.toCurrency, refreshLookups);
        const fxGainLossAccountId = await ensureFxGainLossAccount(lookups, form.toCurrency, refreshLookups);
        const fxChargeAccountId = decimal(form.fxCharge) > 0
          ? (asId(form.chargeAccount) ?? await ensureExpenseAccount(lookups, form.toCurrency, refreshLookups, "bank_charge_expense"))
          : undefined;
        if (!sourceClearingId || !targetClearingId || !fxGainLossAccountId) {
          setSetupError("Exchange setup is missing. Please try Preview again after setup finishes.");
          return;
        }
        submit({
          transaction_date: form.date,
          created_by_user_id: defaultUserId(lookups.users),
          settlement_id: autoSettlementId(lookups.settlements),
          from_account_id: fromWallet?.id,
          to_account_id: toWallet?.id,
          source_clearing_account_id: sourceClearingId,
          target_clearing_account_id: targetClearingId,
          fx_gain_loss_account_id: fxGainLossAccountId,
          fx_charge_account_id: fxChargeAccountId,
          from_amount: form.fromAmount,
          to_amount: form.toAmount,
          from_currency: form.fromCurrency,
          to_currency: form.toCurrency,
          base_currency: form.toCurrency,
          costing_method: "fifo",
          fx_charge: form.fxCharge || "0",
          allow_negative_balance: form.allowNegativeBalance,
          allow_insufficient_lots: form.allowMissingRateHistory,
          description: form.reference || undefined
        });
      } catch (err) {
        setSetupError((err as Error).message);
      }
    })();
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => setForm({ ...form, party }), true, "Client")}
      {currencySelect(lookups.currencies, form.fromCurrency, (fromCurrency) => setForm({ ...form, fromCurrency }), "From")}
      {currencySelect(lookups.currencies, form.toCurrency, (toCurrency) => setForm({ ...form, toCurrency }), "To")}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      <div className="voucher-plain-summary"><span>From {fromWallet ? accountLabel(fromWallet) : "Missing Client Balance"}</span><span>To {toWallet ? accountLabel(toWallet) : "Missing Client Balance"}</span></div>
      {!fromWallet && <MissingBalanceNotice party={selectedParty} currency={form.fromCurrency} onCreate={() => quickCreateBalance(form.fromCurrency, "from")} busy={walletBusy === "from"} />}
      {!toWallet && <MissingBalanceNotice party={selectedParty} currency={form.toCurrency} onCreate={() => quickCreateBalance(form.toCurrency, "to")} busy={walletBusy === "to"} />}
      <label><span>Given Amount</span><input required value={form.fromAmount} onChange={(event) => setForm({ ...form, fromAmount: event.target.value })} /></label>
      <label><span>Received Amount</span><input required value={form.toAmount} onChange={(event) => setForm({ ...form, toAmount: event.target.value })} /></label>
      <div className="voucher-plain-summary"><span>Exchange Rate {actualRate ? actualRate.toFixed(6) : "0.000000"}</span><span>Exchange Difference appears after preview.</span></div>
      {fromWallet && sourceShortfall > 0 && (
        <div className="state-block warning">
          <span>{accountLabel(fromWallet)} has only {money(accountBalance(fromWallet))} {form.fromCurrency}. This exchange needs {money(decimal(form.fromAmount))} {form.fromCurrency}.</span>
          <label className="checkbox-line">
            <input type="checkbox" checked={form.allowNegativeBalance} onChange={(event) => setForm({ ...form, allowNegativeBalance: event.target.checked })} />
            <span>Allow temporary negative balance for this preview</span>
          </label>
        </div>
      )}
      <div className="state-block warning">
        <span>If old FX purchase history is missing, use this entered rate as the original cost for this exchange.</span>
        <label className="checkbox-line">
          <input type="checkbox" checked={form.allowMissingRateHistory} onChange={(event) => setForm({ ...form, allowMissingRateHistory: event.target.checked })} />
          <span>Use entered rate when old FX history is missing</span>
        </label>
      </div>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      {advancedBlock(
        <>
          <label><span>Exchange Fee</span><input value={form.fxCharge} onChange={(event) => setForm({ ...form, fxCharge: event.target.value })} /></label>
          {accountSelect(lookups.accounts, form.chargeAccount, (chargeAccount) => setForm({ ...form, chargeAccount }), "Fee Type", ["expense", "bank_charge_expense"], form.toCurrency, false)}
        </>
      )}
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactiveChargeAccount && <p className="form-note danger-note">{inactiveChargeAccount}</p>}
      <button type="submit" disabled={busy || !canPreview || Boolean(inactiveChargeAccount)}>Preview</button>
    </form>
  );
}

function OpeningBalanceVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ date: todayDate(), account: "", equity: "", currency: "USD", amount: "", exchangeRate: "", sourceNote: "" });
  const [setupError, setSetupError] = useState<string | null>(null);
  const balanceAccount = findAccount(lookups.accounts, form.account);
  const sourceAccount = findAccount(lookups.accounts, form.equity) ?? openingSourceAccount(lookups.accounts, form.currency);
  const inactiveBalanceAccount = inactiveAccountSelection(lookups.accounts, form.account, "Balance For");
  const inactiveSourceAccount = inactiveAccountSelection(lookups.accounts, form.equity, "Funding Source");
  const canPreview = Boolean(balanceAccount && decimal(form.amount) > 0 && !inactiveSourceAccount);

  async function createOpeningSource() {
    setSetupError(null);
    try {
      const id = await ensureOpeningSourceAccount(lookups, form.currency, refreshLookups);
      if (id) setForm((current) => ({ ...current, equity: String(id) }));
    } catch (err) {
      setSetupError((err as Error).message);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    setSetupError(null);
    let equityAccountId = asId(form.equity) ?? sourceAccount?.id;
    if (!equityAccountId) {
      try {
        equityAccountId = await ensureOpeningSourceAccount(lookups, form.currency, refreshLookups);
        if (equityAccountId) setForm((current) => ({ ...current, equity: String(equityAccountId) }));
      } catch (err) {
        setSetupError((err as Error).message);
        return;
      }
    }
    submit({
      transaction_date: form.date,
      created_by_user_id: defaultUserId(lookups.users),
      account_id: asId(form.account),
      equity_account_id: equityAccountId,
      amount: form.amount,
      currency: form.currency,
      base_currency: DEFAULT_BASE_CURRENCY,
      original_rate: form.exchangeRate || undefined,
      description: form.sourceNote || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.account, (account) => {
        const selected = findAccount(lookups.accounts, account);
        const currency = selected?.currency ?? form.currency;
        const source = openingSourceAccount(lookups.accounts, currency);
        setForm({ ...form, account, currency, equity: source ? String(source.id) : "" });
      }, "Balance For", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet", "commission_income", "commission_payable", "expense", "bank_charge_expense", "fx_gain_loss", "clearing", "suspense"])}
      {accountSelect(lookups.accounts, form.equity, (equity) => setForm({ ...form, equity }), "Funding Source", ["owner_equity"], form.currency)}
      {!sourceAccount && (
        <div className="state-block warning">
          <span>No Opening Balance Source exists for {form.currency}.</span>
          <button type="button" onClick={createOpeningSource}>Create Source</button>
        </div>
      )}
      <label><span>Date</span><input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Source / Note</span><input placeholder="Opening cash, bank start, previous balance" value={form.sourceNote} onChange={(event) => setForm({ ...form, sourceNote: event.target.value })} /></label>
      {form.currency !== DEFAULT_BASE_CURRENCY && advancedBlock(
        <>
          <label><span>Exchange Rate</span><input value={form.exchangeRate} onChange={(event) => setForm({ ...form, exchangeRate: event.target.value })} /></label>
        </>
      )}
      {setupError && <p className="form-note danger-note">{setupError}</p>}
      {inactiveBalanceAccount && <p className="form-note danger-note">{inactiveBalanceAccount}</p>}
      {inactiveSourceAccount && <p className="form-note danger-note">{inactiveSourceAccount}</p>}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

function VoucherForm(props: VoucherProps) {
  if (!props.lookups.users.some((user) => user.is_active !== false && asId(user.id))) {
    return <ErrorState message="No active local user found. Run seed command." />;
  }
  if (props.routeKey === "cashBankEntry") return <CashBankEntryVoucher {...props} />;
  if (props.routeKey === "receipt") return <ReceiptVoucher {...props} />;
  if (props.routeKey === "payment") return <PaymentVoucher {...props} />;
  if (props.routeKey === "agentSettlement") return <AgentSettlementVoucher {...props} />;
  if (props.routeKey === "cashHandover" || props.routeKey === "bankTransfer") return <TransferVoucher {...props} />;
  if (props.routeKey === "expense") return <ExpenseVoucher {...props} />;
  if (props.routeKey === "fxConversion") return <FxVoucher {...props} />;
  return <OpeningBalanceVoucher {...props} />;
}

export default function TransactionEntryPage({ routeKey }: { routeKey: TransactionRouteKey }) {
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [lastPayload, setLastPayload] = useState<ApiRecord | null>(null);
  const [result, setResult] = useState<ApiRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const formAreaRef = useRef<HTMLDivElement>(null);
  const { data: lookups, loading, reload } = useAsync(async () => {
    const [users, accounts, parties, settlements, currencies] = await Promise.all([api.users(), api.accounts(), api.parties(), api.settlements(), api.currencies()]);
    return { users, accounts: accounts as Account[], parties: parties as Party[], settlements: settlements as Settlement[], currencies: currencies as Currency[] };
  }, []);

  useEffect(() => {
    setPreview(null);
    setLastPayload(null);
    setResult(null);
    setError(null);
  }, [routeKey]);

  async function previewTransaction(payload: ApiRecord) {
    const targetRoute = (payload.__routeKey as TransactionRouteKey | undefined) ?? routeKey;
    const { __routeKey, ...cleanPayload } = payload;
    setBusy(true);
    setError(null);
    setResult(null);
    setLastPayload({ ...cleanPayload, __routeKey: targetRoute });
    try {
      setPreview(await api.previewTransaction(targetRoute, cleanPayload));
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function postTransaction() {
    if (!lastPayload) return;
    const targetRoute = (lastPayload.__routeKey as TransactionRouteKey | undefined) ?? routeKey;
    const { __routeKey, ...cleanPayload } = lastPayload;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.postTransaction(targetRoute, cleanPayload));
      setPreview(null);
      setLastPayload(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onShortcut(event: KeyboardEvent<HTMLElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && preview && !busy) {
      event.preventDefault();
      void postTransaction();
      return;
    }
    if (event.key === "Escape") {
      if (preview || error || result) {
        event.preventDefault();
        setPreview(null);
        setError(null);
        setResult(null);
      }
      const firstInput = formAreaRef.current?.querySelector("input, select, button") as HTMLElement | null;
      firstInput?.focus();
    }
  }

  const title = routeTitles[routeKey];

  return (
    <section className="marg-voucher-shell" onKeyDown={onShortcut}>
      <header className="page-header voucher-page-header tally-voucher-header">
        <div>
          <span className="screen-path">Gateway / Vouchers</span>
          <h1>{title}</h1>
        </div>
        <div className="voucher-meta-bar">
          <span>Date can be changed for back-dated entries</span>
          {routeShortcut[routeKey] && <span>Shortcut: <strong>{routeShortcut[routeKey]}</strong></span>}
        </div>
      </header>
      <div className="voucher-keybar" aria-label="Voucher shortcuts">
        <span><kbd>F2</kbd>Date</span>
        <span><kbd>Alt C</kbd>Cash/Bank</span>
        <span><kbd>Alt R</kbd>Receipt</span>
        <span><kbd>Alt P</kbd>Payment</span>
        <span><kbd>Alt E</kbd>Expense</span>
        <span><kbd>Alt X</kbd>Exchange</span>
        <span><kbd>Enter</kbd>Preview</span>
        <span><kbd>Ctrl Enter</kbd>Post</span>
        <span><kbd>Esc</kbd>Edit</span>
      </div>
      <div className="tabs voucher-type-strip">
        {operatorTransactionRouteKeys.map((key) => <NavLink key={key} to={`/transactions/${key}`}>{routeTitles[key]}</NavLink>)}
      </div>
      {loading && <LoadingState label="Loading entry lists" />}
      <div className="voucher-workbench">
        <div className="voucher-entry-pane" ref={formAreaRef}>
          {lookups && <VoucherForm lookups={lookups} routeKey={routeKey} submit={previewTransaction} refreshLookups={reload} resetPreview={() => {
            setPreview(null);
            setError(null);
            setResult(null);
            setLastPayload(null);
          }} busy={busy} />}
          {error && <ErrorState message={error} />}
          {result && <div className="state-block success">{title} posted successfully<br /><strong>{String(result.transaction_no)}</strong></div>}
        </div>
        {preview && <aside className="voucher-preview-pane"><PreviewPanel preview={preview} payload={lastPayload} routeKey={routeKey} onPost={postTransaction} posting={busy} /></aside>}
      </div>
    </section>
  );
}
