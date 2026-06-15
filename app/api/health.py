from fastapi import APIRouter

from app.config import get_settings
from app.utils.milvus_client import check_milvus
from app.utils.minio_client import check_minio
from app.utils.mongo_client import check_mongodb

router = APIRouter(tags=["健康检查"])


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/health/services")
def health_services():
    settings = get_settings()
    services = {
        "milvus": check_milvus(settings),
        "mongodb": check_mongodb(settings),
        "minio": check_minio(settings),
    }
    all_ok = all(s["status"] == "ok" for s in services.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
    }
