import logging

import io
import uuid
from datetime import datetime, timezone

from minio.error import S3Error

from app.config import Settings
from app.models.schemas import DocumentMetadata, TaskStatus
from app.utils.minio_client import get_minio_client
from app.utils.mongo_client import get_mongo_db

TASKS_COLLECTION = "import_tasks"
BATCH_SIZE = 10
logger = logging.getLogger("travel.import")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_minio_bucket(settings: Settings) -> None:
    client = get_minio_client(settings)
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_markdown(settings: Settings, filename: str, content: bytes) -> str:
    ensure_minio_bucket(settings)
    client = get_minio_client(settings)
    object_name = f"markdown/{uuid.uuid4().hex}_{filename}"
    client.put_object(
        settings.minio_bucket,
        object_name,
        io.BytesIO(content),
        length=len(content),
        content_type="text/markdown",
    )
    return object_name


def create_task(
    settings: Settings,
    filename: str,
    source_path: str,
    metadata: DocumentMetadata,
) -> str:
    db = get_mongo_db(settings)
    task_id = uuid.uuid4().hex
    now = _utcnow()
    db[TASKS_COLLECTION].insert_one(
        {
            "_id": task_id,
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "filename": filename,
            "source_path": source_path,
            "total_chunks": 0,
            "inserted_chunks": 0,
            "error": None,
            "metadata": metadata.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
    )
    return task_id


def update_task(settings: Settings, task_id: str, **fields) -> None:
    db = get_mongo_db(settings)
    fields["updated_at"] = _utcnow()
    db[TASKS_COLLECTION].update_one({"_id": task_id}, {"$set": fields})


def get_task(settings: Settings, task_id: str) -> dict | None:
    db = get_mongo_db(settings)
    return db[TASKS_COLLECTION].find_one({"_id": task_id})


def list_tasks(settings: Settings, limit: int = 20) -> list[dict]:
    db = get_mongo_db(settings)
    cursor = db[TASKS_COLLECTION].find().sort("created_at", -1).limit(limit)
    return list(cursor)


def get_tasks_by_ids(settings: Settings, task_ids: list[str]) -> list[dict]:
    db = get_mongo_db(settings)
    cursor = db[TASKS_COLLECTION].find({"_id": {"$in": task_ids}})
    return list(cursor)


def decode_markdown(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("gbk")


def submit_import_task(
    settings: Settings,
    filename: str,
    raw_bytes: bytes,
    metadata: DocumentMetadata,
) -> tuple[str, str, str]:
    raw_text = decode_markdown(raw_bytes)
    source_path = upload_markdown(settings, filename, raw_bytes)
    task_id = create_task(settings, filename, source_path, metadata)
    return task_id, raw_text, source_path


def process_import_task(
    settings: Settings,
    task_id: str,
    raw_content: str,
    filename: str,
    source_path: str,
    metadata: DocumentMetadata,
) -> None:
    from app.processor.document import make_chunks, parse_markdown
    from app.processor.embedder import embed_texts
    from app.processor.indexer import insert_chunks
    from app.processor.sparse_embedder import encode_sparse_texts

    try:
        update_task(settings, task_id, status=TaskStatus.PROCESSING.value)
        logger.info("[%s] 开始处理文档: %s", task_id, filename)

        parsed = parse_markdown(raw_content, filename, metadata)
        chunks = make_chunks(parsed, settings)
        if not chunks:
            raise ValueError("文档内容为空，无法切分")

        update_task(settings, task_id, total_chunks=len(chunks))
        logger.info("[%s] 文档切分完成，共 %s 个片段", task_id, len(chunks))

        all_dense: list[list[float]] = []
        all_sparse: list[dict[int, float]] = []
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c["content"] for c in batch]
            logger.info("[%s] 向量化进度: %s/%s", task_id, min(i + BATCH_SIZE, len(chunks)), len(chunks))
            all_dense.extend(embed_texts(texts, settings))
            all_sparse.extend(encode_sparse_texts(texts, settings))

        inserted = insert_chunks(
            settings, task_id, source_path, chunks, all_dense, all_sparse
        )
        update_task(
            settings,
            task_id,
            status=TaskStatus.COMPLETED.value,
            inserted_chunks=inserted,
            metadata=parsed.metadata.model_dump(),
        )
        logger.info("[%s] 导入完成，写入 %s 条", task_id, inserted)
    except (S3Error, ValueError, Exception) as exc:
        logger.exception("[%s] 导入失败: %s", task_id, exc)
        update_task(
            settings,
            task_id,
            status=TaskStatus.FAILED.value,
            error=str(exc),
        )


def process_batch_import(
    settings: Settings,
    items: list[tuple[str, str, str, str, DocumentMetadata]],
) -> None:
    """顺序处理多个文档，共享已加载的模型。"""
    total = len(items)
    for idx, (task_id, raw_text, filename, source_path, metadata) in enumerate(items, 1):
        logger.info("批量导入进度: %s/%s - %s", idx, total, filename)
        process_import_task(settings, task_id, raw_text, filename, source_path, metadata)
