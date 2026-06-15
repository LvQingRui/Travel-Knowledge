from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    RRFRanker,
    connections,
    utility,
)

from app.config import Settings
from app.processor.embedder import embed_texts
from app.processor.sparse_embedder import encode_sparse_texts

MILVUS_ALIAS = "default"
OUTPUT_FIELDS = [
    "content",
    "content_type",
    "scenic_name",
    "route_name",
    "hotel_name",
    "restaurant_name",
    "region",
    "source_filename",
    "source_path",
    "chunk_index",
]


def connect_milvus(settings: Settings, alias: str = MILVUS_ALIAS) -> str:
    if not connections.has_connection(alias):
        connections.connect(
            alias=alias,
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            timeout=10,
        )
    return alias


def _collection_has_sparse(collection: Collection) -> bool:
    return any(field.name == "sparse_vector" for field in collection.schema.fields)


def _create_collection(settings: Settings, alias: str) -> Collection:
    name = settings.milvus_collection
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding_dim),
        FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="scenic_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="route_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="hotel_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="restaurant_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="region", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="source_filename", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="source_path", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields=fields, description="旅游知识库混合检索")
    collection = Collection(name=name, schema=schema, using=alias)

    collection.create_index(
        field_name="dense_vector",
        index_params={
            "metric_type": "COSINE",
            "index_type": "AUTOINDEX",
            "params": {},
        },
    )
    collection.create_index(
        field_name="sparse_vector",
        index_params={
            "metric_type": "IP",
            "index_type": "SPARSE_INVERTED_INDEX",
            "params": {},
        },
    )
    collection.load()
    return collection


def ensure_collection(settings: Settings) -> Collection:
    alias = connect_milvus(settings)
    name = settings.milvus_collection

    if utility.has_collection(name, using=alias):
        collection = Collection(name, using=alias)
        if _collection_has_sparse(collection):
            collection.load()
            return collection
        collection.release()
        utility.drop_collection(name, using=alias)

    return _create_collection(settings, alias)


def insert_chunks(
    settings: Settings,
    task_id: str,
    source_path: str,
    chunks: list[dict],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict[int, float]],
) -> int:
    collection = ensure_collection(settings)
    from app.processor.document import build_chunk_id

    data = {
        "id": [],
        "dense_vector": [],
        "sparse_vector": [],
        "content": [],
        "content_type": [],
        "scenic_name": [],
        "route_name": [],
        "hotel_name": [],
        "restaurant_name": [],
        "region": [],
        "source_filename": [],
        "source_path": [],
        "chunk_index": [],
    }

    for chunk, dense_vector, sparse_vector in zip(chunks, dense_vectors, sparse_vectors):
        data["id"].append(build_chunk_id(task_id, chunk["chunk_index"]))
        data["dense_vector"].append(dense_vector)
        data["sparse_vector"].append(sparse_vector)
        data["content"].append(chunk["content"])
        data["content_type"].append(chunk["content_type"])
        data["scenic_name"].append(chunk["scenic_name"])
        data["route_name"].append(chunk["route_name"])
        data["hotel_name"].append(chunk["hotel_name"])
        data["restaurant_name"].append(chunk["restaurant_name"])
        data["region"].append(chunk["region"])
        data["source_filename"].append(chunk["source_filename"])
        data["source_path"].append(source_path)
        data["chunk_index"].append(chunk["chunk_index"])

    collection.insert([
        data["id"],
        data["dense_vector"],
        data["sparse_vector"],
        data["content"],
        data["content_type"],
        data["scenic_name"],
        data["route_name"],
        data["hotel_name"],
        data["restaurant_name"],
        data["region"],
        data["source_filename"],
        data["source_path"],
        data["chunk_index"],
    ])
    collection.flush()
    return len(chunks)


def _build_filter_expr(
    region: str | None = None,
    content_type: str | None = None,
    scenic_name: str | None = None,
) -> str | None:
    conditions: list[str] = []
    if region:
        conditions.append(f'region == "{region}"')
    if content_type:
        conditions.append(f'content_type == "{content_type}"')
    if scenic_name:
        conditions.append(f'scenic_name like "%{scenic_name}%"')
    if not conditions:
        return None
    return " and ".join(conditions)


def hybrid_search(
    settings: Settings,
    query: str,
    top_k: int | None = None,
    region: str | None = None,
    content_type: str | None = None,
    scenic_name: str | None = None,
) -> list[dict]:
    top_k = top_k or settings.search_top_k
    candidate_k = max(settings.search_candidate_k, top_k * 2)
    filter_expr = _build_filter_expr(region, content_type, scenic_name)

    dense_vector = embed_texts([query], settings, text_type="query")[0]
    sparse_vector = encode_sparse_texts([query], settings)[0]
    collection = ensure_collection(settings)

    dense_req = AnnSearchRequest(
        data=[dense_vector],
        anns_field="dense_vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=candidate_k,
        expr=filter_expr,
    )
    sparse_req = AnnSearchRequest(
        data=[sparse_vector],
        anns_field="sparse_vector",
        param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
        limit=candidate_k,
        expr=filter_expr,
    )

    results = collection.hybrid_search(
        reqs=[dense_req, sparse_req],
        rerank=RRFRanker(k=60),
        limit=top_k,
        output_fields=OUTPUT_FIELDS,
    )

    hits = []
    for hit in results[0]:
        entity = hit.entity
        hits.append(
            {
                "score": float(hit.score),
                "content": entity.get("content"),
                "content_type": entity.get("content_type"),
                "scenic_name": entity.get("scenic_name"),
                "route_name": entity.get("route_name"),
                "hotel_name": entity.get("hotel_name"),
                "restaurant_name": entity.get("restaurant_name"),
                "region": entity.get("region"),
                "source_filename": entity.get("source_filename"),
                "source_path": entity.get("source_path"),
                "chunk_index": entity.get("chunk_index"),
            }
        )
    return hits
