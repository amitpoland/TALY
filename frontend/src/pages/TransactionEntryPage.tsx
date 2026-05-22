import { FormEvent, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiRecord, api, PreviewResponse, TransactionRouteKey, transactionRoutes } from "../api/client";
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

function settlementId(settlement: Settlement): number | undefined {
  return settlement.id ?? settlement.settlement_id;
}

function autoSettlementId(settlements: Settlement[]): number | undefined {
  const active = settlements.filter((item) => ["open", "reopened"].includes(String(item.status).toLowerCase()));
  return active.length === 1 ? settlementId(active[0]) : undefined;
}

function cleanAccountName(name: string): string {
  return name.replace(/\bwallet\b/gi, "Balance").replace(/\bledger\b/gi, "Account");
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

function partyWallet(accounts: Account[], party?: Party, currency?: string): Account | undefined {
  if (!party || !currency) return undefined;
  const type = walletTypeForParty(party);
  return accounts.find((account) => account.party_id === party.id && account.currency === currency && account.account_type === type);
}

function walletCode(party: Party, currency: string): string {
  return `${party.name.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toUpperCase()}-${currency}-BALANCE`;
}

function options(accounts: Account[], types: string[], currency?: string) {
  return accounts.filter((account) => types.includes(account.account_type) && (!currency || account.currency === currency));
}

function firstId(accounts: Account[], types: string[], currency?: string): number | undefined {
  return options(accounts, types, currency)[0]?.id;
}

function findAccount(accounts: Account[], id: string) {
  return accounts.find((account) => account.id === Number(id));
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
  const listId = useMemo(() => `search-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Math.random().toString(36).slice(2)}`, [label]);

  useEffect(() => {
    setText(selected?.label ?? "");
  }, [selected?.label]);

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

  return (
    <label data-searchable="true">
      <span>{label}</span>
      <input
        required={required}
        list={listId}
        value={text}
        placeholder={placeholder ?? `Search ${label.toLowerCase()}`}
        onChange={(event) => choose(event.target.value)}
        onBlur={() => setText(selected?.label ?? text)}
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
  } else if (previewRouteKey === "payment") {
    summaryRows.push(
      { label: "Money paid from cash/bank", value: amountWithCurrency(payload?.amount) },
      { label: "Client/vendor balance affected", value: amountWithCurrency(payload?.amount) }
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
  const [walletBusy, setWalletBusy] = useState(false);
  const receiveAccount = findAccount(lookups.accounts, form.receiveIn);
  const currency = receiveAccount?.currency ?? form.currency;
  const selectedParty = findParty(lookups.parties, form.party);
  const commissionValue = decimal(form.commissionValue);
  const amount = decimal(form.amount);
  const commission = form.commissionType === "percentage" ? amount * commissionValue / 100 : form.commissionType === "fixed" ? commissionValue : 0;
  const gross = form.amountMode === "gross" ? amount : amount + commission;
  const principal = form.amountMode === "gross" ? amount - commission : amount;
  const clientBalance = partyWallet(lookups.accounts, selectedParty, currency);
  const commissionAccount = lookups.accounts.find((account) => account.account_type === "commission_income" && account.currency === currency);
  const canPreview = Boolean(clientBalance && receiveAccount && principal >= 0 && gross > 0);

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
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      receiving_account_id: asId(form.receiveIn),
      clearing_account_id: clientBalance?.id,
      gross_amount: money(gross),
      principal_amount: money(principal),
      commission_amount: money(commission),
      commission_income_account_id: commission > 0 ? commissionAccount?.id : undefined,
      currency,
      base_currency: DEFAULT_BASE_CURRENCY,
      original_rate: form.exchangeRate || undefined,
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
      <label><span>Amount Type</span><select value={form.amountMode} onChange={(event) => setForm({ ...form, amountMode: event.target.value })}><option value="net">Net Received</option><option value="gross">Gross Received</option></select></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Commission</span><select value={form.commissionType} onChange={(event) => setForm({ ...form, commissionType: event.target.value })}><option value="none">none</option><option value="percentage">%</option><option value="fixed">fixed</option></select></label>
      <label><span>Commission Value</span><input value={form.commissionValue} onChange={(event) => setForm({ ...form, commissionValue: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>You are receiving {money(gross)} {currency}</span>
        <span>Client credited {money(principal)} {currency}</span>
        <span>Commission earned {money(commission)} {currency}</span>
        {receiveAccount && <span>Money received in {accountLabel(receiveAccount)}</span>}
        <span>Client balance {clientBalance ? accountLabel(clientBalance) : "Missing"}</span>
      </div>
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={currency} onCreate={quickCreateBalance} busy={walletBusy} />}
      {currency !== DEFAULT_BASE_CURRENCY && advancedBlock(
        <>
          <label><span>Exchange Rate</span><input value={form.exchangeRate} onChange={(event) => setForm({ ...form, exchangeRate: event.target.value })} /></label>
          <div className="voucher-plain-summary"><span>Approx. base value {money(gross * decimal(form.exchangeRate))} {DEFAULT_BASE_CURRENCY}</span></div>
        </>
      )}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

function PaymentVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ party: "", payFrom: "", currency: "USD", amount: "", reference: "" });
  const selectedParty = findParty(lookups.parties, form.party);
  const payAccount = findAccount(lookups.accounts, form.payFrom);
  const currency = payAccount?.currency ?? form.currency;
  const clientBalance = partyWallet(lookups.accounts, selectedParty, currency);
  const [walletBusy, setWalletBusy] = useState(false);
  const amount = decimal(form.amount);
  const canPreview = Boolean(clientBalance && payAccount && amount > 0);

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
      transaction_date: new Date().toISOString().slice(0, 10),
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
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>Money paid from cash/bank {money(amount)} {currency}</span>
        <span>Client/vendor balance affected {money(amount)} {currency}</span>
        <span>Client balance {clientBalance ? accountLabel(clientBalance) : "Missing"}</span>
      </div>
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={currency} onCreate={quickCreateBalance} busy={walletBusy} />}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

const emptyCashBankEntryForm = {
  entryType: "receipt",
  cashBank: "",
  party: "",
  currency: "USD",
  amount: "",
  amountMode: "net",
  commissionType: "none",
  commissionValue: "",
  reference: ""
};

function CashBankEntryVoucher({ lookups, submit, refreshLookups, resetPreview, busy }: VoucherProps) {
  const [form, setForm] = useState(emptyCashBankEntryForm);
  const [walletBusy, setWalletBusy] = useState(false);
  const cashBankAccount = findAccount(lookups.accounts, form.cashBank);
  const currency = cashBankAccount?.currency ?? form.currency;
  const selectedParty = findParty(lookups.parties, form.party);
  const clientBalance = partyWallet(lookups.accounts, selectedParty, currency);
  const clientBalances = selectedParty
    ? lookups.accounts.filter((account) => account.party_id === selectedParty.id && ["customer_wallet", "agent_wallet", "fx_dealer_wallet", "clearing"].includes(account.account_type))
    : [];
  const amount = decimal(form.amount);
  const commissionValue = decimal(form.commissionValue);
  const isReceipt = form.entryType === "receipt";
  const commission = isReceipt && form.commissionType === "percentage" ? amount * commissionValue / 100 : isReceipt && form.commissionType === "fixed" ? commissionValue : 0;
  const gross = form.amountMode === "gross" ? amount : amount + commission;
  const principal = form.amountMode === "gross" ? amount - commission : amount;
  const commissionAccount = lookups.accounts.find((account) => account.account_type === "commission_income" && account.currency === currency);
  const canPreview = Boolean(cashBankAccount && clientBalance && amount > 0 && principal >= 0);

  function updateForm(next: Partial<typeof emptyCashBankEntryForm>) {
    setForm((current) => ({ ...current, ...next }));
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
      await createPartyWallet(selectedParty, currency);
      refreshLookups();
    } finally {
      setWalletBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canPreview) return;
    const common = {
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      clearing_account_id: clientBalance?.id,
      currency,
      description: form.reference || undefined
    };
    if (isReceipt) {
      submit({
        ...common,
        __routeKey: "receipt",
        receiving_account_id: asId(form.cashBank),
        gross_amount: money(gross),
        principal_amount: money(principal),
        commission_amount: money(commission),
        commission_income_account_id: commission > 0 ? commissionAccount?.id : undefined,
        base_currency: DEFAULT_BASE_CURRENCY
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
      <label><span>Date</span><input type="date" value={new Date().toISOString().slice(0, 10)} readOnly /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => updateForm({ amount: event.target.value })} /></label>
      {isReceipt && <label><span>Amount Type</span><select value={form.amountMode} onChange={(event) => updateForm({ amountMode: event.target.value })}><option value="net">Net Received</option><option value="gross">Gross Received</option></select></label>}
      {isReceipt && <label><span>Commission</span><select value={form.commissionType} onChange={(event) => updateForm({ commissionType: event.target.value })}><option value="none">none</option><option value="percentage">%</option><option value="fixed">fixed</option></select></label>}
      {isReceipt && <label><span>Commission Value</span><input value={form.commissionValue} onChange={(event) => updateForm({ commissionValue: event.target.value })} /></label>}
      <label><span>Reference</span><input value={form.reference} onChange={(event) => updateForm({ reference: event.target.value })} /></label>
      <div className="voucher-plain-summary">
        <span>{accountLabel(cashBankAccount ?? ({ name: "Cash/Bank", currency } as Account))} {isReceipt ? "+" : "-"}{money(isReceipt ? gross : amount)} {currency}</span>
        <span>{selectedParty?.name ?? "Party"} balance {isReceipt ? "+" : "-"}{money(isReceipt ? principal : amount)} {currency}</span>
        {isReceipt && commission > 0 && <span>Commission +{money(commission)} {currency}</span>}
      </div>
      {clientBalances.length > 0 && (
        <div className="client-currency-strip">
          {clientBalances.map((account) => <span key={account.id}>{account.currency}: {String(account.current_balance ?? "0.00")}</span>)}
        </div>
      )}
      {!clientBalance && <MissingBalanceNotice party={selectedParty} currency={currency} onCreate={quickCreateBalance} busy={walletBusy} />}
      <div className="voucher-action-row">
        <button type="submit" disabled={busy || !canPreview}>Preview</button>
        <button type="button" className="secondary-action" onClick={resetPreview}>Edit</button>
        <button type="button" className="danger-action" onClick={deleteDraft}>Delete Draft</button>
      </div>
    </form>
  );
}

function TransferVoucher({ lookups, routeKey, submit, busy }: VoucherProps) {
  const isBank = routeKey === "bankTransfer";
  const accountTypes = isBank ? ["bank"] : ["cash"];
  const [form, setForm] = useState({ from: "", to: "", currency: "USD", amount: "", reference: "" });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({
      transaction_date: new Date().toISOString().slice(0, 10),
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
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <button type="submit" disabled={busy}>Preview</button>
    </form>
  );
}

function ExpenseVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ paidFrom: "", expense: "", currency: "USD", amount: "", expenseType: "other", affectsSettlement: false, reference: "" });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      payment_account_id: asId(form.paidFrom),
      expense_account_id: asId(form.expense),
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
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Category</span><input value={form.expenseType} onChange={(event) => setForm({ ...form, expenseType: event.target.value })} /></label>
      <label className="checkbox-line"><input type="checkbox" checked={form.affectsSettlement} onChange={(event) => setForm({ ...form, affectsSettlement: event.target.checked })} /> <span>Charge to client</span></label>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      <button type="submit" disabled={busy}>Preview</button>
    </form>
  );
}

function FxVoucher({ lookups, submit, refreshLookups, busy }: VoucherProps) {
  const [form, setForm] = useState({ party: "", fromCurrency: "EUR", toCurrency: "USD", fromAmount: "", toAmount: "", fxCharge: "0", chargeAccount: "", reference: "" });
  const [walletBusy, setWalletBusy] = useState<"from" | "to" | null>(null);
  const selectedParty = findParty(lookups.parties, form.party);
  const fromWallet = partyWallet(lookups.accounts, selectedParty, form.fromCurrency);
  const toWallet = partyWallet(lookups.accounts, selectedParty, form.toCurrency);
  const actualRate = decimal(form.fromAmount) ? decimal(form.toAmount) / decimal(form.fromAmount) : 0;
  const canPreview = Boolean(selectedParty && fromWallet && toWallet && firstId(lookups.accounts, ["clearing"], form.fromCurrency) && firstId(lookups.accounts, ["clearing"], form.toCurrency) && firstId(lookups.accounts, ["fx_gain_loss"], form.toCurrency));

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
    submit({
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: autoSettlementId(lookups.settlements),
      from_account_id: fromWallet?.id,
      to_account_id: toWallet?.id,
      source_clearing_account_id: firstId(lookups.accounts, ["clearing"], form.fromCurrency),
      target_clearing_account_id: firstId(lookups.accounts, ["clearing"], form.toCurrency),
      fx_gain_loss_account_id: firstId(lookups.accounts, ["fx_gain_loss"], form.toCurrency),
      fx_charge_account_id: form.fxCharge !== "0" ? asId(form.chargeAccount) : undefined,
      from_amount: form.fromAmount,
      to_amount: form.toAmount,
      from_currency: form.fromCurrency,
      to_currency: form.toCurrency,
      base_currency: form.toCurrency,
      costing_method: "fifo",
      fx_charge: form.fxCharge || "0",
      description: form.reference || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => setForm({ ...form, party }), true, "Client")}
      {currencySelect(lookups.currencies, form.fromCurrency, (fromCurrency) => setForm({ ...form, fromCurrency }), "From")}
      {currencySelect(lookups.currencies, form.toCurrency, (toCurrency) => setForm({ ...form, toCurrency }), "To")}
      <div className="voucher-plain-summary"><span>From {fromWallet ? accountLabel(fromWallet) : "Missing Client Balance"}</span><span>To {toWallet ? accountLabel(toWallet) : "Missing Client Balance"}</span></div>
      {!fromWallet && <MissingBalanceNotice party={selectedParty} currency={form.fromCurrency} onCreate={() => quickCreateBalance(form.fromCurrency, "from")} busy={walletBusy === "from"} />}
      {!toWallet && <MissingBalanceNotice party={selectedParty} currency={form.toCurrency} onCreate={() => quickCreateBalance(form.toCurrency, "to")} busy={walletBusy === "to"} />}
      <label><span>Given Amount</span><input required value={form.fromAmount} onChange={(event) => setForm({ ...form, fromAmount: event.target.value })} /></label>
      <label><span>Received Amount</span><input required value={form.toAmount} onChange={(event) => setForm({ ...form, toAmount: event.target.value })} /></label>
      <div className="voucher-plain-summary"><span>Exchange Rate {actualRate ? actualRate.toFixed(6) : "0.000000"}</span><span>Exchange Difference appears after preview.</span></div>
      <label><span>Reference</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
      {advancedBlock(
        <>
          <label><span>Exchange Fee</span><input value={form.fxCharge} onChange={(event) => setForm({ ...form, fxCharge: event.target.value })} /></label>
          {accountSelect(lookups.accounts, form.chargeAccount, (chargeAccount) => setForm({ ...form, chargeAccount }), "Fee Type", ["expense", "bank_charge_expense"], form.toCurrency, false)}
        </>
      )}
      <button type="submit" disabled={busy || !canPreview}>Preview</button>
    </form>
  );
}

function OpeningBalanceVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ account: "", equity: "", currency: "USD", amount: "", exchangeRate: "" });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      account_id: asId(form.account),
      equity_account_id: asId(form.equity),
      amount: form.amount,
      currency: form.currency,
      base_currency: DEFAULT_BASE_CURRENCY,
      original_rate: form.exchangeRate || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.account, (account) => {
        const selected = findAccount(lookups.accounts, account);
        setForm({ ...form, account, currency: selected?.currency ?? form.currency });
      }, "Balance For", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet", "commission_income", "commission_payable", "expense", "bank_charge_expense", "fx_gain_loss", "clearing", "suspense"])}
      {accountSelect(lookups.accounts, form.equity, (equity) => setForm({ ...form, equity }), "Funding Source", ["owner_equity"], form.currency)}
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      {form.currency !== DEFAULT_BASE_CURRENCY && advancedBlock(
        <>
          <label><span>Exchange Rate</span><input value={form.exchangeRate} onChange={(event) => setForm({ ...form, exchangeRate: event.target.value })} /></label>
        </>
      )}
      <button type="submit" disabled={busy}>Preview</button>
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
      <header className="page-header voucher-page-header">
        <div><h1>{title}</h1></div>
        <div className="voucher-meta-bar">
          <span>Date: <strong>{new Date().toISOString().slice(0, 10)}</strong></span>
          {routeShortcut[routeKey] && <span>Shortcut: <strong>{routeShortcut[routeKey]}</strong></span>}
        </div>
      </header>
      <div className="tabs voucher-type-strip">
        {Object.entries(transactionRoutes).map(([key]) => <NavLink key={key} to={`/transactions/${key}`}>{routeTitles[key as TransactionRouteKey]}</NavLink>)}
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
