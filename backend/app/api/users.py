from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.username).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.username == payload.username).one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    if db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=400, detail="Role does not exist")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=payload.role_id,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()
    write_audit_log(
        db,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        after={"username": user.username, "full_name": user.full_name, "role_id": user.role_id},
    )
    db.commit()
    db.refresh(user)
    return user

