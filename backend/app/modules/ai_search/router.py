from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.modules.ai_search import service
from app.modules.ai_search.models import AIConversation, AIMessage
from app.modules.ai_search.schemas import (
    AISearchRequest,
    AISearchResponse,
    CompareRequest,
    CompareResponse,
    ConversationCreate,
    ConversationOut,
    MessageOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/search", response_model=AISearchResponse)
def ai_search(
    body: AISearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Open to anonymous shoppers (stateless, rate-limited per IP). Signed-in users also get conversation memory."""
    client_key = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    return service.run_search(db, user, body, client_key)


@router.post("/compare", response_model=CompareResponse)
def ai_compare(body: CompareRequest, db: Session = Depends(get_db)):
    return service.compare(db, body.product_ids)


@router.post("/search/explain", response_model=AISearchResponse, include_in_schema=False)
def explain_alias(body: AISearchRequest, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    return ai_search(body, request, db, user)


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(body: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = AIConversation(user_id=user.id, title=body.title, context={})
    db.add(conv)
    db.commit()
    return ConversationOut(id=conv.id, title=conv.title, created_at=conv.created_at)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = service.get_conversation(db, conversation_id, user)
    return ConversationOut(id=conv.id, title=conv.title, created_at=conv.created_at)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.get_conversation(db, conversation_id, user)
    rows = db.scalars(select(AIMessage).where(AIMessage.conversation_id == conversation_id).order_by(AIMessage.id)).all()
    return [MessageOut(id=m.id, role=m.role, message=m.message, created_at=m.created_at) for m in rows]
