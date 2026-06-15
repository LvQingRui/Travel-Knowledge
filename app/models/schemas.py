from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    content_type: str = ""
    scenic_name: str = ""
    route_name: str = ""
    hotel_name: str = ""
    restaurant_name: str = ""
    region: str = ""


class ImportTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    filename: str
    source_path: str = ""
    total_chunks: int = 0
    inserted_chunks: int = 0
    error: Optional[str] = None
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImportUploadResponse(BaseModel):
    task_id: str
    message: str
    status: TaskStatus


class BatchImportResponse(BaseModel):
    total: int
    task_ids: list[str]
    filenames: list[str]
    message: str
    status: TaskStatus


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题或关键词")
    top_k: int = Field(default=5, ge=1, le=20)
    region: Optional[str] = Field(default=None, description="按地区过滤")
    content_type: Optional[str] = Field(default=None, description="按内容类型过滤")
    scenic_name: Optional[str] = Field(default=None, description="按景点名过滤")
    enable_hyde: Optional[bool] = Field(default=None, description="是否启用 HyDE 召回")
    enable_web: Optional[bool] = Field(default=None, description="是否启用 Web 搜索")
    enable_rerank: bool = Field(default=True, description="是否启用 Reranker 精排")


class SearchHit(BaseModel):
    score: float
    rerank_score: float = 0.0
    recall_source: str = ""
    content: str
    content_type: str = ""
    scenic_name: str = ""
    route_name: str = ""
    hotel_name: str = ""
    restaurant_name: str = ""
    region: str = ""
    source_filename: str = ""
    source_path: str = ""
    chunk_index: int = 0


class SearchResponse(BaseModel):
    query: str
    total: int
    message: str = ""
    recall_info: dict = Field(default_factory=dict)
    results: list[SearchHit]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话 ID，不传则自动创建")
    top_k: int = Field(default=5, ge=1, le=10)
    region: Optional[str] = Field(default=None)
    content_type: Optional[str] = Field(default=None)
    scenic_name: Optional[str] = Field(default=None)


class Citation(BaseModel):
    index: int
    source_filename: str = ""
    source_path: str = ""
    region: str = ""
    content_type: str = ""
    recall_source: str = ""
    snippet: str = ""


class ChatResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    recall_info: dict = Field(default_factory=dict)
    message: str = ""


class ChatMessage(BaseModel):
    message_id: str
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    recall_info: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SessionDetailResponse(BaseModel):
    session_id: str
    title: str
    message_count: int = 0
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SessionCreateResponse(BaseModel):
    session_id: str
    message: str = "会话已创建"
