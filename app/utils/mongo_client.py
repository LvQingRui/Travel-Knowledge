from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import Settings

DB_NAME = "travel_kb"

_client: MongoClient | None = None
_client_uri: str | None = None


def get_mongo_client(settings: Settings) -> MongoClient:
    global _client, _client_uri
    uri = settings.mongo_uri
    if _client is None or _client_uri != uri:
        if _client is not None:
            _client.close()
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _client_uri = uri
    return _client


def get_mongo_db(settings: Settings) -> Database:
    return get_mongo_client(settings)[DB_NAME]


def close_mongo_client() -> None:
    global _client, _client_uri
    if _client is not None:
        _client.close()
        _client = None
        _client_uri = None


def check_mongodb(settings: Settings) -> dict:
    try:
        client = get_mongo_client(settings)
        result = client.admin.command("ping")
        return {"status": "ok", "ping": result.get("ok") == 1}
    except PyMongoError as exc:
        return {"status": "error", "message": str(exc)}
