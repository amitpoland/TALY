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

