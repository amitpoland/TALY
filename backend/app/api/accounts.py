from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import AccountType
from app.db.session import get_db
from app.models.account import Account
from app.models.currency import Currency
from app.models.party import Party
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/accounts", tags=["accounts"])

WALLET_TYPES = {
    AccountType.CUSTOMER_WALLET,
    AccountType.AGENT_WALLET,
    AccountType.FX_DEALER_WALLET,
}


def _account_snapshot(account: Account) -> dict[str, object]:
    return {
        "id": account.id,
        "account_code": account.account_code,
        "name": account.name,
        "account_type": account.account_type,
        "currency": account.currency,
        "party_id": account.party_id,
        "opening_balance": str(account.opening_balance),
        "current_balance": str(account.current_balance),
        "is_active": account.is_active,
    }


def _validate_account_payload(db: Session, payload: AccountCreate) -> None:
    if db.query(Account).filter(Account.account_code == payload.account_code).one_or_none():
        raise HTTPException(status_code=409, detail="Account code already exists")
    if db.get(Currency, payload.currency) is None:
        raise HTTPException(status_code=400, detail=f"Currency {payload.currency} does not exist")
    if payload.party_id is not None and db.get(Party, payload.party_id) is None:
        raise HTTPException(status_code=400, detail="Party does not exist")
    if payload.account_type in WALLET_TYPES and payload.party_id is None:
        raise HTTPException(status_code=400, detail="Wallet accounts must be linked to a party")


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)) -> list[Account]:
    return db.query(Account).order_by(Account.account_code).all()


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    _validate_account_payload(db, payload)
    account = Account(
        **payload.model_dump(mode="json", exclude={"opening_balance"}),
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
    )
    db.add(account)
    db.flush()
    write_audit_log(
        db,
        action="create_account",
        entity_type="account",
        entity_id=account.id,
        after=_account_snapshot(account),
    )
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    before = _account_snapshot(account)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.flush()
    write_audit_log(
        db,
        action="update_account",
        entity_type="account",
        entity_id=account.id,
        before=before,
        after=_account_snapshot(account),
    )
    db.commit()
    db.refresh(account)
    return account

