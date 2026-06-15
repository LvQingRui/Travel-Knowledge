from pymilvus import connections, utility

from app.config import Settings


def check_milvus(settings: Settings) -> dict:
    alias = "health_check"
    try:
        connections.connect(
            alias=alias,
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            timeout=5,
        )
        version = utility.get_server_version(using=alias)
        return {"status": "ok", "version": version}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    finally:
        try:
            connections.disconnect(alias)
        except Exception:
            pass
