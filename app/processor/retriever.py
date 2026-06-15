import logging

from app.config import Settings
from app.processor.hyde import generate_hyde_document
from app.processor.indexer import hybrid_search
from app.processor.reranker import cliff_truncate, rerank_pairs
from app.processor.web_search import web_search

logger = logging.getLogger("travel.retriever")


def _dedup_candidates(candidates: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in candidates:
        key = item.get("content", "")[:100]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def multi_path_retrieve(
    settings: Settings,
    query: str,
    top_k: int | None = None,
    region: str | None = None,
    content_type: str | None = None,
    scenic_name: str | None = None,
    enable_hyde: bool | None = None,
    enable_web: bool | None = None,
) -> tuple[list[dict], dict]:
    top_k = top_k or settings.search_top_k
    candidate_k = settings.rerank_candidate_k
    use_hyde = settings.hyde_enabled if enable_hyde is None else enable_hyde
    use_web = settings.web_search_enabled if enable_web is None else enable_web

    recall_info = {"vector": 0, "hyde": 0, "web": 0}
    candidates: list[dict] = []

    # 路径 1：原始查询 → 混合向量检索
    vector_hits = hybrid_search(
        settings,
        query=query,
        top_k=candidate_k,
        region=region,
        content_type=content_type,
        scenic_name=scenic_name,
    )
    for hit in vector_hits:
        hit["recall_source"] = "vector"
    candidates.extend(vector_hits)
    recall_info["vector"] = len(vector_hits)
    logger.info("向量召回: %s 条", len(vector_hits))

    # 路径 2：HyDE 假设文档 → 混合向量检索
    if use_hyde:
        try:
            hyde_doc = generate_hyde_document(query, settings)
            hyde_hits = hybrid_search(
                settings,
                query=hyde_doc,
                top_k=candidate_k,
                region=region,
                content_type=content_type,
                scenic_name=scenic_name,
            )
            for hit in hyde_hits:
                hit["recall_source"] = "hyde"
            candidates.extend(hyde_hits)
            recall_info["hyde"] = len(hyde_hits)
            logger.info("HyDE 召回: %s 条", len(hyde_hits))
        except Exception as exc:
            logger.warning("HyDE 召回跳过: %s", exc)

    # 路径 3：Web 免费搜索
    if use_web:
        web_hits = web_search(query, settings)
        candidates.extend(web_hits)
        recall_info["web"] = len(web_hits)

    candidates = _dedup_candidates(candidates)
    logger.info("去重后候选: %s 条", len(candidates))

    if not candidates:
        return [], recall_info

    # Reranker 精排
    passages = [c["content"] for c in candidates]
    scores = rerank_pairs(query, passages, settings)
    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = score
        candidate["score"] = score

    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

    # 断崖检测动态截断
    final = cliff_truncate(
        candidates,
        drop_ratio=settings.cliff_drop_ratio,
        top_k=top_k,
    )
    logger.info("精排+断崖截断后: %s 条", len(final))
    return final, recall_info
