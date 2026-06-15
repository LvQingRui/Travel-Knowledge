import logging
import time

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import SearchHit, SearchRequest, SearchResponse
from app.processor.indexer import hybrid_search
from app.processor.retriever import multi_path_retrieve

router = APIRouter(prefix="/search", tags=["知识检索"])
logger = logging.getLogger("travel.search")


@router.post("", response_model=SearchResponse)
def search_knowledge(request: SearchRequest):
    settings = get_settings()
    logger.info(
        "收到检索请求: query=%r rerank=%s hyde=%s web=%s",
        request.query,
        request.enable_rerank,
        request.enable_hyde,
        request.enable_web,
    )
    start = time.perf_counter()
    recall_info: dict = {}

    try:
        if request.enable_rerank:
            hits, recall_info = multi_path_retrieve(
                settings,
                query=request.query,
                top_k=request.top_k,
                region=request.region,
                content_type=request.content_type,
                scenic_name=request.scenic_name,
                enable_hyde=request.enable_hyde,
                enable_web=request.enable_web,
            )
        else:
            hits = hybrid_search(
                settings,
                query=request.query,
                top_k=request.top_k,
                region=request.region,
                content_type=request.content_type,
                scenic_name=request.scenic_name,
            )
            for hit in hits:
                hit["recall_source"] = "vector"
                hit["rerank_score"] = hit.get("score", 0.0)
            recall_info = {"vector": len(hits), "hyde": 0, "web": 0}
    except Exception as exc:
        logger.exception("检索失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"检索失败: {exc}") from exc

    elapsed = time.perf_counter() - start
    if hits:
        sources = ", ".join(f"{k}={v}" for k, v in recall_info.items() if v > 0)
        message = f"找到 {len(hits)} 条（召回: {sources}），耗时 {elapsed:.2f}s"
    else:
        message = (
            "未找到相关内容。请确认："
            "1) 已上传文档且导入 completed；"
            "2) 过滤条件是否过严；"
            "3) Milvus 中是否有数据。"
        )

    logger.info("检索完成: total=%s recall=%s elapsed=%.2fs", len(hits), recall_info, elapsed)
    return SearchResponse(
        query=request.query,
        total=len(hits),
        message=message,
        recall_info=recall_info,
        results=[SearchHit(**hit) for hit in hits],
    )
