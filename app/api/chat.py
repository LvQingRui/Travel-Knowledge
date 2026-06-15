import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse, Citation
from app.processor.qa_graph import run_qa
from app.processor.retriever import multi_path_retrieve
from app.services.session_service import (
    get_chat_history,
    get_or_create_session,
    save_turn,
)
from app.utils.llm_client import build_citations, chat_stream

router = APIRouter(prefix="/chat", tags=["智能问答"])
logger = logging.getLogger("travel.chat")


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    settings = get_settings()
    session_id = get_or_create_session(settings, request.session_id, title=request.query)
    history = get_chat_history(settings, session_id) if request.session_id else []

    logger.info("收到问答请求: session=%s query=%r history_turns=%s", session_id, request.query, len(history) // 2)
    start = time.perf_counter()

    try:
        result = run_qa(
            settings,
            query=request.query,
            region=request.region,
            content_type=request.content_type,
            scenic_name=request.scenic_name,
            top_k=request.top_k,
            history=history,
        )
    except Exception as exc:
        logger.exception("问答失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"问答失败: {exc}") from exc

    elapsed = time.perf_counter() - start
    citations = result.get("citations", [])
    recall_info = result.get("recall_info", {})
    answer = result.get("answer", "")

    save_turn(settings, session_id, request.query, answer, citations, recall_info)

    history_turns = len(history) // 2
    message = f"基于 {len(citations)} 条参考资料生成，历史 {history_turns} 轮，耗时 {elapsed:.2f}s"
    logger.info("问答完成: session=%s citations=%s elapsed=%.2fs", session_id, len(citations), elapsed)

    return ChatResponse(
        session_id=session_id,
        query=request.query,
        answer=answer,
        citations=[Citation(**c) for c in citations],
        recall_info=recall_info,
        message=message,
    )


@router.post("/stream")
async def chat_stream_endpoint(request: ChatRequest):
    settings = get_settings()
    session_id = get_or_create_session(settings, request.session_id, title=request.query)
    history = get_chat_history(settings, session_id) if request.session_id else []

    logger.info("收到流式问答: session=%s query=%r", session_id, request.query)

    try:
        hits, recall_info = multi_path_retrieve(
            settings,
            query=request.query,
            top_k=request.top_k,
            region=request.region,
            content_type=request.content_type,
            scenic_name=request.scenic_name,
        )
        citations = build_citations(hits)
    except Exception as exc:
        logger.exception("检索失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"检索失败: {exc}") from exc

    async def event_generator():
        session_data = json.dumps({"session_id": session_id}, ensure_ascii=False)
        yield f"event: session\ndata: {session_data}\n\n"

        context_data = json.dumps(
            {"citations": citations, "recall_info": recall_info},
            ensure_ascii=False,
        )
        yield f"event: context\ndata: {context_data}\n\n"

        full_answer = []
        try:
            async for token in chat_stream(request.query, hits, settings, history=history):
                full_answer.append(token)
                token_data = json.dumps({"content": token}, ensure_ascii=False)
                yield f"event: token\ndata: {token_data}\n\n"
        except Exception as exc:
            error_data = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"
            return

        answer = "".join(full_answer)
        save_turn(settings, session_id, request.query, answer, citations, recall_info)

        done_data = json.dumps(
            {"answer": answer, "query": request.query, "session_id": session_id},
            ensure_ascii=False,
        )
        yield f"event: done\ndata: {done_data}\n\n"
        logger.info("流式问答完成: session=%s answer_len=%s", session_id, len(full_answer))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
