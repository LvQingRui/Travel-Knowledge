import re
import uuid
from dataclasses import dataclass

import frontmatter

from app.config import Settings
from app.models.schemas import DocumentMetadata


@dataclass
class ParsedDocument:
    content: str
    metadata: DocumentMetadata
    source_filename: str


CONTENT_TYPES = {
    "景点介绍",
    "线路推荐",
    "酒店信息",
    "美食推荐",
    "交通指南",
    "文化民俗",
}


def _guess_content_type(text: str, filename: str) -> str:
    combined = f"{filename} {text[:200]}"
    rules = [
        ("线路推荐", r"线路|行程|路线|日游|天数"),
        ("酒店信息", r"酒店|住宿|民宿|客栈"),
        ("美食推荐", r"美食|餐厅|小吃|特色菜"),
        ("交通指南", r"交通|地铁|公交|机场|高铁"),
        ("文化民俗", r"文化|民俗|历史|传说"),
        ("景点介绍", r"景点|景区|门票|开放时间"),
    ]
    for content_type, pattern in rules:
        if re.search(pattern, combined):
            return content_type
    return "景点介绍"


def _guess_region(text: str, filename: str) -> str:
    match = re.search(r"(北京|上海|广州|深圳|杭州|成都|重庆|西安|三亚|丽江|大理|桂林|厦门|青岛|苏州|南京|武汉|长沙|昆明|拉萨|哈尔滨)", f"{filename} {text[:300]}")
    return match.group(1) if match else ""


def parse_markdown(raw: str, filename: str, form_meta: DocumentMetadata | None = None) -> ParsedDocument:
    post = frontmatter.loads(raw)
    meta = form_meta or DocumentMetadata()

    front = post.metadata or {}
    field_map = {
        "content_type": "content_type",
        "scenic_name": "scenic_name",
        "route_name": "route_name",
        "hotel_name": "hotel_name",
        "restaurant_name": "restaurant_name",
        "region": "region",
    }
    for model_field, front_key in field_map.items():
        value = front.get(front_key) or front.get(model_field)
        if value and not getattr(meta, model_field):
            setattr(meta, model_field, str(value))

    body = post.content.strip()
    if not meta.content_type:
        meta.content_type = _guess_content_type(body, filename)
    if not meta.region:
        meta.region = _guess_region(body, filename)

    return ParsedDocument(
        content=body,
        metadata=meta,
        source_filename=filename,
    )


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            break_at = text.rfind("\n", start, end)
            if break_at > start + chunk_size // 2:
                end = break_at
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def build_chunk_id(task_id: str, index: int) -> str:
    return f"{task_id}_{index}_{uuid.uuid4().hex[:8]}"


def make_chunks(parsed: ParsedDocument, settings: Settings) -> list[dict]:
    pieces = chunk_text(parsed.content, settings.chunk_size, settings.chunk_overlap)
    results = []
    for idx, piece in enumerate(pieces):
        results.append(
            {
                "chunk_index": idx,
                "content": piece,
                "content_type": parsed.metadata.content_type,
                "scenic_name": parsed.metadata.scenic_name,
                "route_name": parsed.metadata.route_name,
                "hotel_name": parsed.metadata.hotel_name,
                "restaurant_name": parsed.metadata.restaurant_name,
                "region": parsed.metadata.region,
                "source_filename": parsed.source_filename,
            }
        )
    return results
