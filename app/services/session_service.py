import logging
import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.utils.mongo_client import get_mongo_db

logger = logging.getLogger("travel.session")

SESSIONS_COLLECTION = "chat_sessions"
MESSAGES_COLLECTION = "chat_messages"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_session(settings: Settings, title: str = "新对话") -> str:
    db = get_mongo_db(settings)
    session_id = uuid.uuid4().hex
    now = _utcnow()
    db[SESSIONS_COLLECTION].insert_one(
        {
            "_id": session_id,
            "session_id": session_id,
            "title": title[:50],
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    logger.info("创建会话: %s", session_id)
    return session_id


def get_or_create_session(settings: Settings, session_id: str | None, title: str) -> str:
    if session_id:
        session = get_session(settings, session_id)
        if session:
            return session_id
    return create_session(settings, title=title)


def get_session(settings: Settings, session_id: str) -> dict | None:
    db = get_mongo_db(settings)
    return db[SESSIONS_COLLECTION].find_one({"_id": session_id})


def list_sessions(settings: Settings, limit: int = 20) -> list[dict]:
    db = get_mongo_db(settings)
    cursor = db[SESSIONS_COLLECTION].find().sort("updated_at", -1).limit(limit)
    return list(cursor)


def delete_session(settings: Settings, session_id: str) -> bool:
    db = get_mongo_db(settings)
    result = db[SESSIONS_COLLECTION].delete_one({"_id": session_id})
    db[MESSAGES_COLLECTION].delete_many({"session_id": session_id})
    return result.deleted_count > 0


def get_chat_history(settings: Settings, session_id: str) -> list[dict]:
    """获取 LLM 可用的对话历史（user/assistant 交替）。"""
    db = get_mongo_db(settings)
    max_messages = settings.chat_history_turns * 2
    cursor = (
        db[MESSAGES_COLLECTION]
        .find({"session_id": session_id})
        .sort("created_at", -1)
        .limit(max_messages)
    )
    messages = list(cursor)
    messages.reverse()

    history = []
    for msg in messages:
        history.append({"role": msg["role"], "content": msg["content"]})
    return history


def get_session_messages(settings: Settings, session_id: str) -> list[dict]:
    db = get_mongo_db(settings)
    cursor = db[MESSAGES_COLLECTION].find({"session_id": session_id}).sort("created_at", 1)
    return list(cursor)


def save_message(
    settings: Settings,
    session_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    recall_info: dict | None = None,
) -> str:
    db = get_mongo_db(settings)
    msg_id = uuid.uuid4().hex
    now = _utcnow()
    db[MESSAGES_COLLECTION].insert_one(
        {
            "_id": msg_id,
            "message_id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "citations": citations or [],
            "recall_info": recall_info or {},
            "created_at": now,
        }
    )
    db[SESSIONS_COLLECTION].update_one(
        {"_id": session_id},
        {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
    )
    return msg_id


def save_turn(
    settings: Settings,
    session_id: str,
    query: str,
    answer: str,
    citations: list[dict],
    recall_info: dict,
) -> None:
    save_message(settings, session_id, "user", query)
    save_message(settings, session_id, "assistant", answer, citations, recall_info)
    logger.info("保存对话轮次: session=%s", session_id)
