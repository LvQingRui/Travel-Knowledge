import dashscope
from dashscope import TextEmbedding

from app.config import Settings


class EmbeddingError(Exception):
    pass


def embed_texts(texts: list[str], settings: Settings, text_type: str = "document") -> list[list[float]]:
    if not settings.dashscope_api_key:
        raise EmbeddingError("未配置 DASHSCOPE_API_KEY")

    if not texts:
        return []

    dashscope.api_key = settings.dashscope_api_key
    response = TextEmbedding.call(
        model=settings.embedding_model,
        input=texts,
        dimension=settings.embedding_dim,
        text_type=text_type,
    )

    if response.status_code != 200:
        raise EmbeddingError(f"Embedding 调用失败: {response.code} - {response.message}")

    items = sorted(response.output["embeddings"], key=lambda x: x["text_index"])
    return [item["embedding"] for item in items]
