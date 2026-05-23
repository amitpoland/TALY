from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.posting import (
    AgentSettlementPayload,
    ExpensePayload,
    FxConversionPayload,
    OpeningBalancePayload,
    PaymentPayload,
    PostingPreviewRead,
    PostingRequest,
    PostingResultRead,
    ReceiptPayload,
    ReversePayload,
    TransferPayload,
)
from app.services.posting import posting_service
from app.services.posting.builders import (
    build_agent_settlement_preview,
    build_bank_transfer_preview,
    build_cash_handover_preview,
    build_expense_preview,
    build_fx_conversion_preview,
    build_opening_balance_preview,
    build_payment_preview,
    build_receipt_preview,
)
from app.services.posting.dtos import PostingPreview

router = APIRouter(prefix="/transactions", tags=["transactions"])

PayloadT = TypeVar("PayloadT")


def _preview_response(preview: PostingPreview) -> PostingPreviewRead:
    return PostingPreviewRead.model_validate(preview, from_attributes=True)


def _post_response(preview: PostingPreview, transaction, audit_log_id: int | None) -> PostingResultRead:
    return PostingResultRead(
        **PostingPreviewRead.model_validate(preview, from_attributes=True).model_dump(),
        transaction_id=transaction.id,
        transaction_no=transaction.transaction_no,
        status=transaction.status,
        posted_at=transaction.posted_at,
        audit_log_id=audit_log_id,
    )


def _payload_from_post(request: PostingRequest, payload_type: type[PayloadT]) -> PayloadT:
    if not request.confirmation.confirmed_by_user:
        raise HTTPException(status_code=400, detail="Posting requires user confirmation")
    return payload_type.model_validate(request.payload)


@router.post("/opening-balance/preview", response_model=PostingPreviewRead)
def preview_opening_balance(payload: OpeningBalancePayload, db: Session = Depends(get_db)):
    return _preview_response(build_opening_balance_preview(db, payload))


@router.post("/opening-balance/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_opening_balance(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, OpeningBalancePayload)
    preview, transaction, audit_id = posting_service.post_opening_balance(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/receipt/preview", response_model=PostingPreviewRead)
def preview_receipt(payload: ReceiptPayload, db: Session = Depends(get_db)):
    return _preview_response(build_receipt_preview(db, payload))


@router.post("/receipt/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_receipt(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, ReceiptPayload)
    preview, transaction, audit_id = posting_service.post_receipt(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/payment/preview", response_model=PostingPreviewRead)
def preview_payment(payload: PaymentPayload, db: Session = Depends(get_db)):
    return _preview_response(build_payment_preview(db, payload))


@router.post("/payment/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_payment(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, PaymentPayload)
    preview, transaction, audit_id = posting_service.post_payment(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/agent-settlement/preview", response_model=PostingPreviewRead)
def preview_agent_settlement(payload: AgentSettlementPayload, db: Session = Depends(get_db)):
    return _preview_response(build_agent_settlement_preview(db, payload))


@router.post("/agent-settlement/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_agent_settlement(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, AgentSettlementPayload)
    preview, transaction, audit_id = posting_service.post_agent_settlement(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/cash-handover/preview", response_model=PostingPreviewRead)
def preview_cash_handover(payload: TransferPayload, db: Session = Depends(get_db)):
    return _preview_response(build_cash_handover_preview(db, payload))


@router.post("/cash-handover/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_cash_handover(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, TransferPayload)
    preview, transaction, audit_id = posting_service.post_cash_handover(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/bank-transfer/preview", response_model=PostingPreviewRead)
def preview_bank_transfer(payload: TransferPayload, db: Session = Depends(get_db)):
    return _preview_response(build_bank_transfer_preview(db, payload))


@router.post("/bank-transfer/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_bank_transfer(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, TransferPayload)
    preview, transaction, audit_id = posting_service.post_bank_transfer(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/expense/preview", response_model=PostingPreviewRead)
def preview_expense(payload: ExpensePayload, db: Session = Depends(get_db)):
    return _preview_response(build_expense_preview(db, payload))


@router.post("/expense/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_expense(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, ExpensePayload)
    preview, transaction, audit_id = posting_service.post_expense(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/fx-conversion/preview", response_model=PostingPreviewRead)
def preview_fx_conversion(payload: FxConversionPayload, db: Session = Depends(get_db)):
    return _preview_response(build_fx_conversion_preview(db, payload))


@router.post("/fx-conversion/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_fx_conversion(request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, FxConversionPayload)
    preview, transaction, audit_id = posting_service.post_fx_conversion(db, payload)
    return _post_response(preview, transaction, audit_id)


@router.post("/{transaction_id}/reverse/preview", response_model=PostingPreviewRead)
def preview_reversal(transaction_id: int, payload: ReversePayload, db: Session = Depends(get_db)):
    return _preview_response(posting_service.build_reversal_preview(db, transaction_id, payload))


@router.post("/{transaction_id}/reverse/post", response_model=PostingResultRead, status_code=status.HTTP_201_CREATED)
def post_reversal(transaction_id: int, request: PostingRequest, db: Session = Depends(get_db)):
    payload = _payload_from_post(request, ReversePayload)
    preview, transaction, audit_id = posting_service.post_reversal(db, transaction_id, payload)
    return _post_response(preview, transaction, audit_id)
