from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务
    app_name: str = "旅游知识库"
    app_version: str = "0.1.0"
    debug: bool = True

    # Milvus
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530

    # MongoDB
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_user: str = "admin"
    mongo_password: str = "mongo123456"

    # MinIO
    minio_host: str = "127.0.0.1"
    minio_port: int = 9000
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_secure: bool = False

    # LLM & Embedding
    dashscope_api_key: str = ""
    deepseek_api_key: str = ""
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    # Milvus 集合
    milvus_collection: str = "travel_knowledge"

    # MinIO 存储桶
    minio_bucket: str = "travel-docs"

    # 文档切分
    chunk_size: int = 500
    chunk_overlap: int = 50

    # BGE-M3 稀疏向量（本地 Mac）
    bge_model_name: str = "BAAI/bge-m3"
    bge_model_path: str = ""
    bge_batch_size: int = 4
    hf_endpoint: str = "https://hf-mirror.com"
    hf_token: str = ""

    # BGE-Reranker 重排序（本地 Mac）
    reranker_model_path: str = "./app/models/bge-reranker-large"
    rerank_batch_size: int = 8
    rerank_candidate_k: int = 20

    # LLM（HyDE 用 DashScope，问答默认 DeepSeek）
    llm_provider: str = "deepseek"
    llm_model: str = "qwen-plus"
    chat_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    hyde_enabled: bool = True

    # Web 搜索（DuckDuckGo 免费）
    web_search_enabled: bool = True
    web_search_max_results: int = 3

    # 检索
    search_top_k: int = 5
    search_candidate_k: int = 20
    cliff_drop_ratio: float = 0.3

    # 会话历史
    chat_history_turns: int = 5

    @property
    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/?authSource=admin"
        )

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
