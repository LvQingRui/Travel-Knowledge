from minio import Minio
from minio.error import S3Error

from app.config import Settings


def get_minio_client(settings: Settings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def check_minio(settings: Settings) -> dict:
    try:
        client = get_minio_client(settings)
        buckets = client.list_buckets()
        return {
            "status": "ok",
            "bucket_count": len(buckets),
        }
    except S3Error as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
