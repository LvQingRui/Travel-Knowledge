import logging

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.models.schemas import (
    BatchImportResponse,
    DocumentMetadata,
    ImportTaskResponse,
    ImportUploadResponse,
    TaskStatus,
)
from app.services.import_service import (
    get_task,
    get_tasks_by_ids,
    list_tasks,
    process_batch_import,
    process_import_task,
    submit_import_task,
)

router = APIRouter(prefix="/import", tags=["文档导入"])
logger = logging.getLogger("travel.import")


def _to_response(doc: dict) -> ImportTaskResponse:
    metadata = doc.get("metadata") or {}
    return ImportTaskResponse(
        task_id=doc["task_id"],
        status=TaskStatus(doc["status"]),
        filename=doc.get("filename", ""),
        source_path=doc.get("source_path", ""),
        total_chunks=doc.get("total_chunks", 0),
        inserted_chunks=doc.get("inserted_chunks", 0),
        error=doc.get("error"),
        metadata=DocumentMetadata(**metadata),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


def _clean_form(value: Optional[str]) -> str:
    if not value or value.strip().lower() == "string":
        return ""
    return value.strip()


def _build_metadata(
    content_type: Optional[str] = None,
    scenic_name: Optional[str] = None,
    route_name: Optional[str] = None,
    hotel_name: Optional[str] = None,
    restaurant_name: Optional[str] = None,
    region: Optional[str] = None,
) -> DocumentMetadata:
    return DocumentMetadata(
        content_type=_clean_form(content_type),
        scenic_name=_clean_form(scenic_name),
        route_name=_clean_form(route_name),
        hotel_name=_clean_form(hotel_name),
        restaurant_name=_clean_form(restaurant_name),
        region=_clean_form(region),
    )


def _validate_settings(settings):
    if not settings.dashscope_api_key:
        raise HTTPException(status_code=400, detail="请先在 .env 中配置 DASHSCOPE_API_KEY")


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Markdown 文件"),
    content_type: Optional[str] = Form(None),
    scenic_name: Optional[str] = Form(None),
    route_name: Optional[str] = Form(None),
    hotel_name: Optional[str] = Form(None),
    restaurant_name: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
):
    settings = get_settings()
    _validate_settings(settings)

    if not file.filename or not file.filename.endswith((".md", ".markdown")):
        raise HTTPException(status_code=400, detail="仅支持 .md / .markdown 文件")

    raw_bytes = await file.read()
    metadata = _build_metadata(content_type, scenic_name, route_name, hotel_name, restaurant_name, region)
    task_id, raw_text, source_path = submit_import_task(settings, file.filename, raw_bytes, metadata)
    logger.info("文档已接收: filename=%s task_id=%s", file.filename, task_id)

    background_tasks.add_task(
        process_import_task,
        settings,
        task_id,
        raw_text,
        file.filename,
        source_path,
        metadata,
    )

    return ImportUploadResponse(
        task_id=task_id,
        message=f"文档已上传，正在后台处理。请用 GET /import/tasks/{task_id} 查询进度",
        status=TaskStatus.PENDING,
    )


@router.post("/batch", response_model=BatchImportResponse)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="多个 Markdown 文件"),
    content_type: Optional[str] = Form(None),
    scenic_name: Optional[str] = Form(None),
    route_name: Optional[str] = Form(None),
    hotel_name: Optional[str] = Form(None),
    restaurant_name: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
):
    settings = get_settings()
    _validate_settings(settings)

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    metadata = _build_metadata(content_type, scenic_name, route_name, hotel_name, restaurant_name, region)
    task_ids: list[str] = []
    filenames: list[str] = []
    batch_items: list[tuple[str, str, str, str, DocumentMetadata]] = []

    for file in files:
        if not file.filename or not file.filename.endswith((".md", ".markdown")):
            logger.warning("跳过不支持的文件: %s", file.filename)
            continue

        raw_bytes = await file.read()
        task_id, raw_text, source_path = submit_import_task(settings, file.filename, raw_bytes, metadata)
        task_ids.append(task_id)
        filenames.append(file.filename)
        batch_items.append((task_id, raw_text, file.filename, source_path, metadata))

    if not batch_items:
        raise HTTPException(status_code=400, detail="没有有效的 .md / .markdown 文件")

    logger.info("批量上传: %s 个文件, task_ids=%s", len(batch_items), task_ids)
    background_tasks.add_task(process_batch_import, settings, batch_items)

    return BatchImportResponse(
        total=len(batch_items),
        task_ids=task_ids,
        filenames=filenames,
        message=f"已接收 {len(batch_items)} 个文档，正在后台顺序处理。查询: GET /import/batch/status?task_ids=...",
        status=TaskStatus.PENDING,
    )


@router.get("/batch/status", response_model=list[ImportTaskResponse])
def get_batch_status(task_ids: str):
    """查询批量任务状态，task_ids 用逗号分隔。"""
    settings = get_settings()
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="请提供 task_ids 参数")
    docs = get_tasks_by_ids(settings, ids)
    doc_map = {doc["task_id"]: doc for doc in docs}
    return [_to_response(doc_map[tid]) for tid in ids if tid in doc_map]


@router.get("/tasks/{task_id}", response_model=ImportTaskResponse)
def get_import_task(task_id: str):
    settings = get_settings()
    doc = get_task(settings, task_id)
    if not doc:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_response(doc)


@router.get("/tasks", response_model=list[ImportTaskResponse])
def get_import_tasks(limit: int = 50):
    settings = get_settings()
    docs = list_tasks(settings, limit=limit)
    return [_to_response(doc) for doc in docs]
