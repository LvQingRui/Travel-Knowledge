import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.import_docs import router as import_router
from app.api.search import router as search_router
from app.api.sessions import router as sessions_router
from app.config import get_settings
from app.logging_config import setup_logging
from app.utils.mongo_client import close_mongo_client

setup_logging()
logger = logging.getLogger("travel")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="旅游智能知识库 RAG 系统",
)

app.include_router(health_router)
app.include_router(import_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(sessions_router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info("%s %s -> %s (%.2fs)", request.method, request.url.path, response.status_code, elapsed)
    return response


@app.on_event("startup")
async def on_startup():
    logger.info("=" * 50)
    logger.info("%s v%s 已启动", settings.app_name, settings.app_version)
    logger.info("API 文档: http://localhost:8000/docs")
    logger.info("健康检查: http://localhost:8000/health/services")
    logger.info("文档上传: POST http://localhost:8000/import/upload")
    logger.info("知识检索: POST http://localhost:8000/search")
    logger.info("智能问答: POST http://localhost:8000/chat")
    logger.info("流式问答: POST http://localhost:8000/chat/stream")
    logger.info("会话管理: GET http://localhost:8000/sessions")
    logger.info("聊天界面: http://localhost:8000/chat-ui")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def on_shutdown():
    close_mongo_client()
    logger.info("MongoDB 连接已关闭")


@app.get("/chat-ui")
async def chat_ui():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/")
def root():
    return {
        "message": "旅游知识库 API 运行中",
        "docs": "/docs",
        "health": "/health",
        "services_health": "/health/services",
        "import_upload": "/import/upload",
        "import_tasks": "/import/tasks",
        "search": "/search",
        "chat": "/chat",
        "chat_stream": "/chat/stream",
        "sessions": "/sessions",
        "chat_ui": "/chat-ui",
        "tips": {
            "upload": "上传后访问 /import/tasks/{task_id} 查看导入进度",
            "search": "检索结果为空时，检查 message 字段获取提示",
        },
    }
