import logging
import os
from pathlib import Path
from typing import Any

from app.config import Settings

_model = None
logger = logging.getLogger("travel.sparse")


class SparseEmbeddingError(Exception):
    pass


def _setup_hf_env(settings: Settings) -> None:
    if settings.hf_endpoint:
        os.environ["HF_ENDPOINT"] = settings.hf_endpoint
    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token


def _resolve_model_path(settings: Settings) -> str:
    if settings.bge_model_path:
        path = Path(settings.bge_model_path).expanduser().resolve()
        if not path.exists():
            raise SparseEmbeddingError(
                f"本地模型目录不存在: {path}\n"
                "请先运行: bash scripts/download_bge.sh"
            )
        return str(path)
    return settings.bge_model_name


def get_bge_model(settings: Settings):
    global _model
    if _model is None:
        _setup_hf_env(settings)

        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise SparseEmbeddingError(
                "未安装 FlagEmbedding，请执行: pip install FlagEmbedding torch"
            ) from exc

        model_path = _resolve_model_path(settings)
        if settings.bge_model_path:
            logger.info("从本地加载 BGE-M3: %s", model_path)
        else:
            logger.info(
                "首次在线加载 BGE-M3（约 2GB），镜像: %s。"
                "若下载失败，请运行: bash scripts/download_bge.sh",
                settings.hf_endpoint,
            )

        try:
            _model = BGEM3FlagModel(model_path, use_fp16=False)
        except Exception as exc:
            raise SparseEmbeddingError(
                f"BGE-M3 加载失败: {exc}\n"
                "解决方案：\n"
                "  1. 运行 bash scripts/download_bge.sh 下载到本地\n"
                "  2. 在 .env 设置 BGE_MODEL_PATH=./models/bge-m3\n"
                "  3. 确认 .env 中有 HF_ENDPOINT=https://hf-mirror.com"
            ) from exc

        logger.info("BGE-M3 模型加载完成")
    return _model


def _to_milvus_sparse(lexical_weights: dict[str, Any]) -> dict[int, float]:
    sparse: dict[int, float] = {}
    for key, value in lexical_weights.items():
        sparse[int(key)] = float(value)
    return sparse


def encode_sparse_texts(texts: list[str], settings: Settings) -> list[dict[int, float]]:
    if not texts:
        return []

    model = get_bge_model(settings)
    output = model.encode(
        texts,
        batch_size=settings.bge_batch_size,
        return_dense=False,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    lexical_weights = output["lexical_weights"]
    return [_to_milvus_sparse(weights) for weights in lexical_weights]
