import logging

from app.config import Settings

logger = logging.getLogger("travel.web")


def web_search(query: str, settings: Settings) -> list[dict]:
    if not settings.web_search_enabled:
        return []

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("未安装 duckduckgo-search，跳过 Web 搜索")
        return []

    hits: list[dict] = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=settings.web_search_max_results))
    except Exception as exc:
        logger.warning("Web 搜索失败，跳过: %s", exc)
        return []

    for item in results:
        body = (item.get("body") or "").strip()
        if not body:
            continue
        hits.append(
            {
                "score": 0.0,
                "content": body,
                "content_type": "网络搜索",
                "scenic_name": "",
                "route_name": "",
                "hotel_name": "",
                "restaurant_name": "",
                "region": "",
                "source_filename": item.get("title") or "web",
                "source_path": item.get("href") or "",
                "chunk_index": 0,
                "recall_source": "web",
            }
        )

    logger.info("Web 搜索返回 %s 条", len(hits))
    return hits
