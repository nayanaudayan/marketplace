from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User, UserAddress
from app.modules.users.schemas import AddressIn, AddressOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(UserAddress).where(UserAddress.user_id == user.id).order_by(UserAddress.is_default.desc(), UserAddress.id)
    ).all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(body: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    has_any = db.scalar(select(UserAddress.id).where(UserAddress.user_id == user.id).limit(1)) is not None
    make_default = body.is_default or not has_any
    if make_default:
        db.execute(update(UserAddress).where(UserAddress.user_id == user.id).values(is_default=False))
    address = UserAddress(user_id=user.id, **body.model_dump(exclude={"is_default"}), is_default=make_default)
    db.add(address)
    db.commit()
    return address
