from enum import StrEnum


class PartyType(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    FX_DEALER = "fx_dealer"
    VENDOR = "vendor"
    INTERNAL = "internal"


class AccountType(StrEnum):
    CASH = "cash"
    BANK = "bank"
    CUSTOMER_WALLET = "customer_wallet"
    AGENT_WALLET = "agent_wallet"
    FX_DEALER_WALLET = "fx_dealer_wallet"
    COMMISSION_INCOME = "commission_income"
    COMMISSION_PAYABLE = "commission_payable"
    EXPENSE = "expense"
    BANK_CHARGE_EXPENSE = "bank_charge_expense"
    FX_GAIN_LOSS = "fx_gain_loss"
    CLEARING = "clearing"
    SUSPENSE = "suspense"
    OWNER_EQUITY = "owner_equity"


class NormalBalance(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionType(StrEnum):
    OPENING_BALANCE = "opening_balance"
    RECEIPT = "receipt"
    PAYMENT = "payment"
    CASH_HANDOVER = "cash_handover"
    BANK_TRANSFER = "bank_transfer"
    EXPENSE = "expense"
    REVERSAL = "reversal"


class TransactionStatus(StrEnum):
    POSTED = "posted"
    REVERSED = "reversed"


class ComponentType(StrEnum):
    OPENING_BALANCE = "opening_balance"
    GROSS_RECEIPT = "gross_receipt"
    PRINCIPAL = "principal"
    YOUR_COMMISSION = "your_commission"
    CASH_MOVEMENT = "cash_movement"
    BANK_MOVEMENT = "bank_movement"
    EXPENSE = "expense"
    REVERSAL = "reversal"


class Direction(StrEnum):
    IN = "in"
    OUT = "out"
    NEUTRAL = "neutral"


class SettlementEffectType(StrEnum):
    PRINCIPAL_IN = "principal_in"
    PRINCIPAL_OUT = "principal_out"
    CHARGE_IN_SETTLEMENT = "charge_in_settlement"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    NONE = "none"


class ProfitabilityEffectType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    NONE = "none"


ACCOUNT_NORMAL_BALANCE: dict[AccountType, NormalBalance] = {
    AccountType.CASH: NormalBalance.DEBIT,
    AccountType.BANK: NormalBalance.DEBIT,
    AccountType.CUSTOMER_WALLET: NormalBalance.DEBIT,
    AccountType.AGENT_WALLET: NormalBalance.DEBIT,
    AccountType.FX_DEALER_WALLET: NormalBalance.DEBIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
    AccountType.BANK_CHARGE_EXPENSE: NormalBalance.DEBIT,
    AccountType.CLEARING: NormalBalance.DEBIT,
    AccountType.SUSPENSE: NormalBalance.DEBIT,
    AccountType.COMMISSION_INCOME: NormalBalance.CREDIT,
    AccountType.COMMISSION_PAYABLE: NormalBalance.CREDIT,
    AccountType.FX_GAIN_LOSS: NormalBalance.CREDIT,
    AccountType.OWNER_EQUITY: NormalBalance.CREDIT,
}
