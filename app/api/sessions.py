from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import (
    ChatMessage,
    Citation,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionSummary,
)
from app.services.session_service import (
    create_session,
    delete_session,
    get_session,
    get_session_messages,
    list_sessions,
)

router = APIRouter(prefix="/sessions", tags=["会话管理"])


@router.post("", response_model=SessionCreateResponse)
def create_new_session(title: str = "新对话"):
    settings = get_settings()
    session_id = create_session(settings, title=title)
    return SessionCreateResponse(session_id=session_id)


@router.get("", response_model=list[SessionSummary])
def get_sessions(limit: int = 20):
    settings = get_settings()
    docs = list_sessions(settings, limit=limit)
    return [
        SessionSummary(
            session_id=doc["session_id"],
            title=doc.get("title", ""),
            message_count=doc.get("message_count", 0),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )
        for doc in docs
    ]


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str):
    settings = get_settings()
    session = get_session(settings, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = get_session_messages(settings, session_id)
    return SessionDetailResponse(
        session_id=session_id,
        title=session.get("title", ""),
        message_count=session.get("message_count", 0),
        messages=[
            ChatMessage(
                message_id=msg["message_id"],
                role=msg["role"],
                content=msg["content"],
                citations=[Citation(**c) for c in msg.get("citations", [])],
                recall_info=msg.get("recall_info", {}),
                created_at=msg.get("created_at"),
            )
            for msg in messages
        ],
        created_at=session.get("created_at"),
        updated_at=session.get("updated_at"),
    )


@router.delete("/{session_id}")
def remove_session(session_id: str):
    settings = get_settings()
    if not delete_session(settings, session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "会话已删除", "session_id": session_id}
