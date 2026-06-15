import logging
from pathlib import Path

from app.config import Settings

logger = logging.getLogger("travel.reranker")
_reranker = None


class RerankerError(Exception):
    pass


def get_reranker(settings: Settings):
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerError(
                "未安装 sentence-transformers，请执行: pip install sentence-transformers"
            ) from exc

        model_path = Path(settings.reranker_model_path).expanduser().resolve()
        if not model_path.exists():
            raise RerankerError(
                f"Reranker 模型目录不存在: {model_path}\n"
                "请在 .env 设置 RERANKER_MODEL_PATH=./app/models/bge-reranker-large"
            )

        logger.info("加载 BGE-Reranker (CrossEncoder): %s", model_path)
        _reranker = CrossEncoder(str(model_path), max_length=512)
        logger.info("BGE-Reranker 加载完成")
    return _reranker


def rerank_pairs(query: str, passages: list[str], settings: Settings) -> list[float]:
    if not passages:
        return []

    reranker = get_reranker(settings)
    pairs = [[query, passage] for passage in passages]
    scores = reranker.predict(pairs, batch_size=settings.rerank_batch_size)
    return [float(s) for s in scores]


def cliff_truncate(
    ranked: list[dict],
    drop_ratio: float,
    top_k: int,
    min_keep: int = 1,
) -> list[dict]:
    """断崖检测：相邻分数跌幅超过阈值时截断尾部。"""
    if len(ranked) <= min_keep:
        return ranked[:top_k]

    cutoff = len(ranked)
    for i in range(1, len(ranked)):
        prev_score = ranked[i - 1]["rerank_score"]
        curr_score = ranked[i]["rerank_score"]
        if prev_score > 0 and (prev_score - curr_score) / prev_score > drop_ratio:
            cutoff = max(i, min_keep)
            logger.info(
                "断崖检测截断: 位置=%s, 前=%.4f, 后=%.4f, 跌幅=%.1f%%",
                i,
                prev_score,
                curr_score,
                (prev_score - curr_score) / prev_score * 100,
            )
            break

    return ranked[: min(cutoff, top_k)]
