"""Qdrant-backed vector indexing for knowledge chunks.

The current embedding is a deterministic lexical feature hash. It keeps the
vector pipeline fully local and lightweight; replacing `embed_text` with a BGE
or text2vec model later does not change the storage/search contract.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

from loguru import logger

from app.core.config import settings


VECTOR_SIZE = 384
_embedding_model = None
_embedding_model_failed = False


def embed_text(text: str) -> list[float]:
    semantic = _semantic_embed_text(text)
    if semantic:
        return semantic
    vector = [0.0] * VECTOR_SIZE
    tokens = _tokens(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + min(len(token), 8) / 8.0)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def _semantic_embed_text(text: str) -> list[float]:
    """Use an optional local Chinese embedding model, folded to VECTOR_SIZE.

    Set KNOWLEDGE_EMBEDDING_MODEL to a local sentence-transformers/BGE/text2vec
    model path or model name. The fallback hash embedding keeps edge deployments
    working when the model or dependency is absent.
    """
    global _embedding_model, _embedding_model_failed
    model_name = os.getenv("KNOWLEDGE_EMBEDDING_MODEL", "").strip()
    if not model_name or _embedding_model_failed:
        return []
    try:
        if _embedding_model is None:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(model_name)
            logger.info(f"知识库启用语义向量模型: {model_name}")
        raw = _embedding_model.encode([text], normalize_embeddings=True)[0]
        values = [float(value) for value in raw]
        if not values:
            return []
        if len(values) != VECTOR_SIZE:
            values = _fold_vector(values, VECTOR_SIZE)
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values] if norm > 0 else values
    except Exception as exc:
        logger.warning(f"语义向量模型不可用，知识库回退到本地 hash embedding: {exc}")
        _embedding_model_failed = True
        return []


def _fold_vector(values: list[float], size: int) -> list[float]:
    folded = [0.0] * size
    for index, value in enumerate(values):
        folded[index % size] += value
    return folded


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_+-]{2,}", lowered)
    tokens: list[str] = []
    for chunk in chunks:
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk) and len(chunk) > 4:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
            tokens.extend(chunk[i : i + 3] for i in range(len(chunk) - 2))
        tokens.append(chunk)
    return tokens


class QdrantKnowledgeVectorService:
    def __init__(self) -> None:
        self.collection_name = settings.QDRANT_KNOWLEDGE_COLLECTION
        self.url = settings.QDRANT_URL.rstrip("/")
        self.enabled = settings.QDRANT_ENABLED
        self._client = None
        self._ready = False

    def is_available(self) -> bool:
        return bool(self.enabled and self.client)

    @property
    def client(self):
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, timeout=settings.QDRANT_TIMEOUT)
            return self._client
        except Exception as exc:
            logger.warning(f"Qdrant 客户端不可用，知识库降级为关键词检索: {exc}")
            self.enabled = False
            return None

    def ensure_collection(self) -> None:
        if self._ready or not self.client:
            return
        try:
            from qdrant_client import models

            collections = self.client.get_collections().collections
            exists = any(item.name == self.collection_name for item in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._ready = True
        except Exception as exc:
            logger.warning(f"Qdrant collection 初始化失败，知识库降级为关键词检索: {exc}")
            self.enabled = False

    def upsert_chunk(self, *, chunk_id: int, vector_text: str, payload: dict[str, Any]) -> bool:
        if not self.is_available():
            return False
        self.ensure_collection()
        if not self.is_available():
            return False
        try:
            from qdrant_client import models

            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=int(chunk_id),
                        vector=embed_text(vector_text),
                        payload=payload,
                    )
                ],
            )
            return True
        except Exception as exc:
            logger.warning(f"Qdrant 写入失败: chunk_id={chunk_id}, error={exc}")
            return False

    def delete_document(self, document_id: int) -> None:
        if not self.is_available():
            return
        self.ensure_collection()
        if not self.is_available():
            return
        try:
            from qdrant_client import models

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=int(document_id)),
                            )
                        ]
                    )
                ),
            )
        except Exception as exc:
            logger.warning(f"Qdrant 删除文档向量失败: document_id={document_id}, error={exc}")

    def search(self, *, query: str, base_ids: list[int] | None, top_k: int) -> dict[int, float]:
        if not self.is_available():
            return {}
        self.ensure_collection()
        if not self.is_available():
            return {}
        try:
            query_filter = self._base_filter(base_ids)
            results = self._search_points(query=query, limit=max(top_k, 20), query_filter=query_filter)
            return {int(item.id): float(item.score) for item in results}
        except Exception as exc:
            logger.warning(f"Qdrant 检索失败，知识库降级为关键词检索: {exc}")
            return {}

    def _search_points(self, *, query: str, limit: int, query_filter):
        query_vector = embed_text(query)
        if hasattr(self.client, "search"):
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
        )
        return getattr(result, "points", result)

    @staticmethod
    def _base_filter(base_ids: list[int] | None):
        if not base_ids:
            return None
        try:
            from qdrant_client import models

            return models.Filter(
                must=[
                    models.FieldCondition(
                        key="base_id",
                        match=models.MatchAny(any=[int(value) for value in base_ids]),
                    )
                ]
            )
        except Exception:
            return None


knowledge_vector_service = QdrantKnowledgeVectorService()
