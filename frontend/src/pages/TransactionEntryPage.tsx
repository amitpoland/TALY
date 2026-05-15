import { FormEvent, useEffect, useMemo, useState } from "react";
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

type Lookups = {
  users: ApiRecord[];
  accounts: Account[];
  parties: Party[];
  settlements: Settlement[];
};

const DEFAULT_BASE_CURRENCY = "USD";

const routeHelp: Record<TransactionRouteKey, string> = {
  openingBalance: "Set an initial balance through the posting engine.",
  receipt: "Record money received from a party with optional included commission.",
  payment: "Record money paid out against a settlement.",
  cashHandover: "Move cash or wallet balance between two accounts.",
  bankTransfer: "Move balance between bank accounts.",
  expense: "Record expenses, charges, and settlement-affecting costs.",
  fxConversion: "Convert currency using backend FIFO lot preview and posting."
};

function asId(value: unknown): number | undefined {
  const id = Number(value);
  return Number.isFinite(id) && id > 0 ? id : undefined;
}

function decimal(value: string): number {
  const amount = Number(value || "0");
  return Number.isFinite(amount) ? amount : 0;
}

function money(value: number): string {
  return value.toFixed(2);
}

function settlementId(settlement: Settlement): number | undefined {
  return settlement.id ?? settlement.settlement_id;
}

function accountLabel(account: Account): string {
  return `${account.account_code} - ${account.name} (${account.account_type}, ${account.currency})`;
}

function settlementLabel(settlement: Settlement): string {
  return `${settlement.settlement_no} - ${settlement.title ?? settlement.status} (${settlement.base_currency})`;
}

function partyLabel(party: Party): string {
  return `${party.name} (${party.party_type}${party.default_currency ? `, ${party.default_currency}` : ""})`;
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

function clearingAccount(accounts: Account[], partyId: string, currency: string): Account | undefined {
  const partyAccount = accounts.find((account) => account.party_id === Number(partyId) && account.currency === currency && ["customer_wallet", "agent_wallet", "fx_dealer_wallet"].includes(account.account_type));
  return partyAccount ?? accounts.find((account) => account.account_type === "clearing" && account.currency === currency);
}

function accountSelect(accounts: Account[], value: string, onChange: (value: string) => void, label: string, types: string[], currency?: string, required = true) {
  return (
    <label>
      <span>{label}</span>
      <select required={required} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select {label}</option>
        {options(accounts, types, currency).map((account) => (
          <option key={account.id} value={account.id}>{accountLabel(account)}</option>
        ))}
      </select>
    </label>
  );
}

function partySelect(parties: Party[], value: string, onChange: (value: string) => void, required = false) {
  return (
    <label>
      <span>Party</span>
      <select required={required} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select party</option>
        {parties.map((party) => <option key={party.id} value={party.id}>{partyLabel(party)}</option>)}
      </select>
    </label>
  );
}

function settlementSelect(settlements: Settlement[], value: string, onChange: (value: string) => void) {
  return (
    <label>
      <span>Settlement</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">No settlement selected</option>
        {settlements.map((settlement) => {
          const id = settlementId(settlement);
          return id ? <option key={id} value={id}>{settlementLabel(settlement)}</option> : null;
        })}
      </select>
    </label>
  );
}

function defaultUserId(users: ApiRecord[]): number {
  return asId(users[0]?.id) ?? 1;
}

function PreviewPanel({ preview, onPost, posting }: { preview: PreviewResponse; onPost: () => void; posting: boolean }) {
  const componentRows = preview.components.map((component) => ({
    type: component.component_type,
    amount: `${component.amount ?? ""} ${component.currency ?? ""}`,
    direction: component.direction,
    settlement: component.affects_settlement ? component.settlement_effect_type : "",
    profitability: component.affects_profitability ? component.profitability_effect_type : ""
  }));
  const movementText = preview.account_balance_effects.length ? `${preview.account_balance_effects.length} account balance movement(s)` : "No balance movement";

  return (
    <div className="preview-panel">
      <div className="summary-strip">
        <span>Voucher: <strong>{preview.transaction_type}</strong></span>
        <span>Movement: <strong>{movementText}</strong></span>
        <span>Settlement effect: <strong>{JSON.stringify(preview.settlement_effect)}</strong></span>
        <span>Profitability: <strong>{JSON.stringify(preview.profitability_effect)}</strong></span>
      </div>
      {preview.warnings.length > 0 && <div className="state-block warning">{preview.warnings.join(", ")}</div>}
      <h2>Business Preview</h2>
      <DataTable rows={componentRows} />
      {preview.fx_detail && (
        <>
          <h2>FX Preview</h2>
          <DataTable rows={[preview.fx_detail]} />
        </>
      )}
      <details>
        <summary>Ledger entries</summary>
        <DataTable rows={preview.ledger_entries} />
      </details>
      <details>
        <summary>Balance effects</summary>
        <DataTable rows={preview.account_balance_effects} />
      </details>
      <button className="primary-action" type="button" onClick={onPost} disabled={posting}>
        {posting ? "Posting..." : "Confirm and Post"}
      </button>
    </div>
  );
}

function advancedBlock(children: React.ReactNode) {
  return <details className="advanced-details"><summary>Advanced details</summary><div className="entry-form compact">{children}</div></details>;
}

type VoucherProps = {
  lookups: Lookups;
  routeKey: TransactionRouteKey;
  submit: (payload: ApiRecord) => void;
  busy: boolean;
};

function ReceiptVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({
    party: "",
    receiveIn: "",
    settlement: "",
    currency: "USD",
    amountMode: "gross",
    amount: "",
    commissionType: "none",
    commissionValue: "",
    baseCurrency: DEFAULT_BASE_CURRENCY,
    exchangeRate: "",
    description: ""
  });
  const receiveAccount = findAccount(lookups.accounts, form.receiveIn);
  const commissionValue = decimal(form.commissionValue);
  const amount = decimal(form.amount);
  const commission = form.commissionType === "percentage" ? amount * commissionValue / 100 : form.commissionType === "fixed" ? commissionValue : 0;
  const gross = form.amountMode === "gross" ? amount : amount + commission;
  const principal = form.amountMode === "gross" ? amount - commission : amount;
  const clearing = clearingAccount(lookups.accounts, form.party, form.currency);
  const commissionAccount = lookups.accounts.find((account) => account.account_type === "commission_income" && account.currency === form.currency);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({
      transaction_date: new Date().toISOString().slice(0, 10),
      created_by_user_id: defaultUserId(lookups.users),
      settlement_id: asId(form.settlement),
      receiving_account_id: asId(form.receiveIn),
      clearing_account_id: clearing?.id,
      gross_amount: money(gross),
      principal_amount: money(principal),
      commission_amount: money(commission),
      commission_income_account_id: commission > 0 ? commissionAccount?.id : undefined,
      currency: form.currency,
      base_currency: form.baseCurrency || undefined,
      original_rate: form.exchangeRate || undefined,
      description: form.description || undefined
    });
  }

  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => {
        const selected = findParty(lookups.parties, party);
        setForm({ ...form, party, currency: selected?.default_currency ?? form.currency });
      }, true)}
      {accountSelect(lookups.accounts, form.receiveIn, (receiveIn) => {
        const selected = findAccount(lookups.accounts, receiveIn);
        setForm({ ...form, receiveIn, currency: selected?.currency ?? form.currency });
      }, "Receive In", ["cash", "bank"], form.currency)}
      {settlementSelect(lookups.settlements, form.settlement, (settlement) => setForm({ ...form, settlement }))}
      <label><span>Currency</span><input required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
      <label><span>Amount Mode</span><select value={form.amountMode} onChange={(event) => setForm({ ...form, amountMode: event.target.value })}><option value="gross">Gross amount entered</option><option value="net">Net amount entered</option></select></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Commission Type</span><select value={form.commissionType} onChange={(event) => setForm({ ...form, commissionType: event.target.value })}><option value="none">None</option><option value="fixed">Fixed</option><option value="percentage">Percentage</option></select></label>
      <label><span>Commission Value</span><input value={form.commissionValue} onChange={(event) => setForm({ ...form, commissionValue: event.target.value })} /></label>
      <label><span>Description/Reference</span><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <div className="calculation-card">
        <strong>Calculated voucher</strong>
        <span>Gross {money(gross)} {form.currency}</span>
        <span>Principal {money(principal)} {form.currency}</span>
        <span>Commission {money(commission)} {form.currency}</span>
        <span>Clearing {clearing ? accountLabel(clearing) : "No matching wallet/clearing account"}</span>
        {receiveAccount && <span>Receive in {accountLabel(receiveAccount)}</span>}
      </div>
      {advancedBlock(
        <>
          <label><span>Base Currency</span><input value={form.baseCurrency} onChange={(event) => setForm({ ...form, baseCurrency: event.target.value.toUpperCase() })} /></label>
          <label><span>Exchange Rate</span><input value={form.exchangeRate} onChange={(event) => setForm({ ...form, exchangeRate: event.target.value })} /></label>
          {form.currency !== form.baseCurrency && <div className="calculation-card"><span>Base amount preview {money(gross * decimal(form.exchangeRate))} {form.baseCurrency}</span></div>}
        </>
      )}
      <button type="submit" disabled={busy}>Preview Receipt</button>
    </form>
  );
}

function PaymentVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ party: "", payFrom: "", settlement: "", currency: "USD", amount: "", description: "" });
  const clearing = clearingAccount(lookups.accounts, form.party, form.currency);
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({ transaction_date: new Date().toISOString().slice(0, 10), created_by_user_id: defaultUserId(lookups.users), settlement_id: asId(form.settlement), paying_account_id: asId(form.payFrom), clearing_account_id: clearing?.id, amount: form.amount, currency: form.currency, description: form.description || undefined });
  }
  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {partySelect(lookups.parties, form.party, (party) => setForm({ ...form, party }), true)}
      {accountSelect(lookups.accounts, form.payFrom, (payFrom) => {
        const selected = findAccount(lookups.accounts, payFrom);
        setForm({ ...form, payFrom, currency: selected?.currency ?? form.currency });
      }, "Pay From", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet"], form.currency)}
      {settlementSelect(lookups.settlements, form.settlement, (settlement) => setForm({ ...form, settlement }))}
      <label><span>Currency</span><input required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Description/Reference</span><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <div className="calculation-card"><span>Party clearing {clearing ? accountLabel(clearing) : "No matching wallet/clearing account"}</span></div>
      <button type="submit" disabled={busy}>Preview Payment</button>
    </form>
  );
}

function TransferVoucher({ lookups, routeKey, submit, busy }: VoucherProps) {
  const isBank = routeKey === "bankTransfer";
  const accountTypes = isBank ? ["bank"] : ["cash", "customer_wallet", "agent_wallet"];
  const [form, setForm] = useState({ from: "", to: "", settlement: "", currency: "USD", amount: "", description: "" });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({ transaction_date: new Date().toISOString().slice(0, 10), created_by_user_id: defaultUserId(lookups.users), settlement_id: asId(form.settlement), from_account_id: asId(form.from), to_account_id: asId(form.to), amount: form.amount, currency: form.currency, description: form.description || undefined });
  }
  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.from, (from) => {
        const selected = findAccount(lookups.accounts, from);
        setForm({ ...form, from, currency: selected?.currency ?? form.currency });
      }, isBank ? "Transfer From" : "Hand Over From", accountTypes, form.currency)}
      {accountSelect(lookups.accounts, form.to, (to) => setForm({ ...form, to }), isBank ? "Transfer To" : "Hand Over To", accountTypes, form.currency)}
      {settlementSelect(lookups.settlements, form.settlement, (settlement) => setForm({ ...form, settlement }))}
      <label><span>Currency</span><input required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Description/Reference</span><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <button type="submit" disabled={busy}>Preview {isBank ? "Bank Transfer" : "Cash Handover"}</button>
    </form>
  );
}

function ExpenseVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ paidFrom: "", expense: "", settlement: "", currency: "USD", amount: "", expenseType: "other", affectsSettlement: false, description: "" });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({ transaction_date: new Date().toISOString().slice(0, 10), created_by_user_id: defaultUserId(lookups.users), settlement_id: asId(form.settlement), payment_account_id: asId(form.paidFrom), expense_account_id: asId(form.expense), amount: form.amount, currency: form.currency, expense_type: form.expenseType || "other", affects_settlement: form.affectsSettlement, description: form.description || undefined });
  }
  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.paidFrom, (paidFrom) => {
        const selected = findAccount(lookups.accounts, paidFrom);
        setForm({ ...form, paidFrom, currency: selected?.currency ?? form.currency });
      }, "Paid From", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet"], form.currency)}
      {accountSelect(lookups.accounts, form.expense, (expense) => setForm({ ...form, expense }), "Expense Ledger", ["expense", "bank_charge_expense"], form.currency)}
      {settlementSelect(lookups.settlements, form.settlement, (settlement) => setForm({ ...form, settlement }))}
      <label><span>Currency</span><input required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      <label><span>Expense Type</span><input value={form.expenseType} onChange={(event) => setForm({ ...form, expenseType: event.target.value })} /></label>
      <label className="checkbox-line"><input type="checkbox" checked={form.affectsSettlement} onChange={(event) => setForm({ ...form, affectsSettlement: event.target.checked })} /> <span>Affects settlement</span></label>
      <label><span>Description/Reference</span><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <button type="submit" disabled={busy}>Preview Expense</button>
    </form>
  );
}

function FxVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ from: "", to: "", settlement: "", fromCurrency: "USD", toCurrency: "AED", fromAmount: "", toAmount: "", baseCurrency: "AED", costingMethod: "fifo", fxCharge: "0", chargeAccount: "", description: "" });
  const actualRate = decimal(form.fromAmount) ? decimal(form.toAmount) / decimal(form.fromAmount) : 0;
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({ transaction_date: new Date().toISOString().slice(0, 10), created_by_user_id: defaultUserId(lookups.users), settlement_id: asId(form.settlement), from_account_id: asId(form.from), to_account_id: asId(form.to), source_clearing_account_id: firstId(lookups.accounts, ["clearing"], form.fromCurrency), target_clearing_account_id: firstId(lookups.accounts, ["clearing"], form.baseCurrency), fx_gain_loss_account_id: firstId(lookups.accounts, ["fx_gain_loss"], form.baseCurrency), fx_charge_account_id: form.fxCharge !== "0" ? asId(form.chargeAccount) : undefined, from_amount: form.fromAmount, to_amount: form.toAmount, from_currency: form.fromCurrency, to_currency: form.toCurrency, base_currency: form.baseCurrency, costing_method: form.costingMethod, fx_charge: form.fxCharge || "0", description: form.description || undefined });
  }
  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.from, (from) => {
        const selected = findAccount(lookups.accounts, from);
        setForm({ ...form, from, fromCurrency: selected?.currency ?? form.fromCurrency });
      }, "From Account", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet"], form.fromCurrency)}
      {accountSelect(lookups.accounts, form.to, (to) => {
        const selected = findAccount(lookups.accounts, to);
        setForm({ ...form, to, toCurrency: selected?.currency ?? form.toCurrency, baseCurrency: selected?.currency ?? form.baseCurrency });
      }, "To Account", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet"], form.toCurrency)}
      {settlementSelect(lookups.settlements, form.settlement, (settlement) => setForm({ ...form, settlement }))}
      <label><span>From Currency</span><input required value={form.fromCurrency} onChange={(event) => setForm({ ...form, fromCurrency: event.target.value.toUpperCase() })} /></label>
      <label><span>To Currency</span><input required value={form.toCurrency} onChange={(event) => setForm({ ...form, toCurrency: event.target.value.toUpperCase(), baseCurrency: event.target.value.toUpperCase() })} /></label>
      <label><span>From Amount</span><input required value={form.fromAmount} onChange={(event) => setForm({ ...form, fromAmount: event.target.value })} /></label>
      <label><span>To Amount</span><input required value={form.toAmount} onChange={(event) => setForm({ ...form, toAmount: event.target.value })} /></label>
      <div className="calculation-card"><span>Actual Rate {actualRate ? actualRate.toFixed(6) : "0.000000"}</span><span>Backend preview will show gain/loss.</span></div>
      {advancedBlock(
        <>
          <label><span>Base Currency</span><input value={form.baseCurrency} onChange={(event) => setForm({ ...form, baseCurrency: event.target.value.toUpperCase() })} /></label>
          <label><span>Costing Method</span><select value={form.costingMethod} onChange={(event) => setForm({ ...form, costingMethod: event.target.value })}><option value="fifo">FIFO</option><option value="transaction_wise">Transaction-wise</option></select></label>
          <label><span>FX Charge</span><input value={form.fxCharge} onChange={(event) => setForm({ ...form, fxCharge: event.target.value })} /></label>
          {accountSelect(lookups.accounts, form.chargeAccount, (chargeAccount) => setForm({ ...form, chargeAccount }), "FX Charge Ledger", ["expense", "bank_charge_expense"], form.baseCurrency, false)}
        </>
      )}
      <button type="submit" disabled={busy}>Preview FX Conversion</button>
    </form>
  );
}

function OpeningBalanceVoucher({ lookups, submit, busy }: VoucherProps) {
  const [form, setForm] = useState({ account: "", equity: "", currency: "USD", amount: "", baseCurrency: "USD", exchangeRate: "" });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit({ transaction_date: new Date().toISOString().slice(0, 10), created_by_user_id: defaultUserId(lookups.users), account_id: asId(form.account), equity_account_id: asId(form.equity), amount: form.amount, currency: form.currency, base_currency: form.baseCurrency || undefined, original_rate: form.exchangeRate || undefined });
  }
  return (
    <form className="entry-form voucher-form" onSubmit={onSubmit}>
      {accountSelect(lookups.accounts, form.account, (account) => {
        const selected = findAccount(lookups.accounts, account);
        setForm({ ...form, account, currency: selected?.currency ?? form.currency });
      }, "Opening Account", ["cash", "bank", "customer_wallet", "agent_wallet", "fx_dealer_wallet", "commission_income", "commission_payable", "expense", "bank_charge_expense", "fx_gain_loss", "clearing", "suspense"], form.currency)}
      {accountSelect(lookups.accounts, form.equity, (equity) => setForm({ ...form, equity }), "Equity Ledger", ["owner_equity"], form.currency)}
      <label><span>Currency</span><input required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
      <label><span>Amount</span><input required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
      {advancedBlock(
        <>
          <label><span>Base Currency</span><input value={form.baseCurrency} onChange={(event) => setForm({ ...form, baseCurrency: event.target.value.toUpperCase() })} /></label>
          <label><span>Exchange Rate</span><input value={form.exchangeRate} onChange={(event) => setForm({ ...form, exchangeRate: event.target.value })} /></label>
        </>
      )}
      <button type="submit" disabled={busy}>Preview Opening Balance</button>
    </form>
  );
}

function VoucherForm(props: VoucherProps) {
  if (props.routeKey === "receipt") return <ReceiptVoucher {...props} />;
  if (props.routeKey === "payment") return <PaymentVoucher {...props} />;
  if (props.routeKey === "cashHandover" || props.routeKey === "bankTransfer") return <TransferVoucher {...props} />;
  if (props.routeKey === "expense") return <ExpenseVoucher {...props} />;
  if (props.routeKey === "fxConversion") return <FxVoucher {...props} />;
  return <OpeningBalanceVoucher {...props} />;
}

export default function TransactionEntryPage({ routeKey }: { routeKey: TransactionRouteKey }) {
  const config = transactionRoutes[routeKey];
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [lastPayload, setLastPayload] = useState<ApiRecord | null>(null);
  const [result, setResult] = useState<ApiRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: lookups, loading } = useAsync(async () => {
    const [users, accounts, parties, settlements] = await Promise.all([api.users(), api.accounts(), api.parties(), api.settlements()]);
    return { users, accounts: accounts as Account[], parties: parties as Party[], settlements: settlements as Settlement[] };
  }, []);

  useEffect(() => {
    setPreview(null);
    setLastPayload(null);
    setResult(null);
    setError(null);
  }, [routeKey]);

  async function previewTransaction(payload: ApiRecord) {
    setBusy(true);
    setError(null);
    setResult(null);
    setLastPayload(payload);
    try {
      setPreview(await api.previewTransaction(routeKey, payload));
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function postTransaction() {
    if (!lastPayload) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.postTransaction(routeKey, lastPayload));
      setPreview(null);
      setLastPayload(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <header className="page-header">
        <div><h1>{config.label}</h1><p>{routeHelp[routeKey]} Preview is generated by the backend before posting.</p></div>
      </header>
      <div className="tabs">
        {Object.entries(transactionRoutes).map(([key, route]) => <NavLink key={key} to={`/transactions/${key}`}>{route.label}</NavLink>)}
      </div>
      {loading && <LoadingState label="Loading voucher lists" />}
      {lookups && <VoucherForm lookups={lookups} routeKey={routeKey} submit={previewTransaction} busy={busy} />}
      {error && <ErrorState message={error} />}
      {result && <div className="state-block success">Posted transaction {String(result.transaction_no)}.</div>}
      {preview && <PreviewPanel preview={preview} onPost={postTransaction} posting={busy} />}
    </section>
  );
}
