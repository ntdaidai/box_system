"""Knowledge-base ingestion and retrieval service."""

from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import re
import threading
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy.exc import OperationalError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.services.document_parser import parse_document_bytes
from app.services.minio_service import minio_service
from app.services.vector_service import knowledge_vector_service


DEFAULT_BASE_NAME = "库坝巡查综合知识库"
SUPPORTED_EXTENSIONS = {"txt", "md", "pdf", "docx", "xlsx", "xls", "csv", "json", "log"}


class KnowledgeService:
    def __init__(self) -> None:
        self._tables_ready = False
        self._tables_lock = threading.Lock()

    def ensure_tables(self) -> None:
        if self._tables_ready:
            return
        with self._tables_lock:
            if self._tables_ready:
                return
            for table in (
                KnowledgeBase.__table__,
                KnowledgeDocument.__table__,
                KnowledgeChunk.__table__,
            ):
                try:
                    table.create(bind=engine, checkfirst=True)
                except OperationalError as exc:
                    if "already exists" not in str(exc).lower():
                        raise
            self._tables_ready = True

    def ensure_default_base(self, db: Session) -> KnowledgeBase:
        self.ensure_tables()
        base = db.query(KnowledgeBase).order_by(KnowledgeBase.id.asc()).first()
        if base:
            return base
        base = KnowledgeBase(
            name=DEFAULT_BASE_NAME,
            description="巡查规范、应急预案、历史案例、设备手册等综合知识。",
            category="general",
            enabled=True,
        )
        db.add(base)
        db.commit()
        db.refresh(base)
        return base

    def list_bases(self, db: Session) -> list[dict[str, Any]]:
        self.ensure_default_base(db)
        rows = db.query(KnowledgeBase).order_by(KnowledgeBase.id.asc()).all()
        return [self._base_dict(row) for row in rows]

    def create_base(self, db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_tables()
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="知识库名称不能为空")
        exists = db.query(KnowledgeBase).filter(KnowledgeBase.name == name).first()
        if exists:
            raise HTTPException(status_code=409, detail="知识库名称已存在")
        base = KnowledgeBase(
            name=name,
            description=str(payload.get("description") or "").strip(),
            category=str(payload.get("category") or "general").strip() or "general",
            enabled=bool(payload.get("enabled", True)),
        )
        db.add(base)
        db.commit()
        db.refresh(base)
        return self._base_dict(base)

    async def upload_document(
        self,
        db: Session,
        *,
        file: UploadFile,
        base_id: Optional[int],
        category: str = "",
        title: str = "",
    ) -> dict[str, Any]:
        base = self._get_base_or_default(db, base_id)
        filename = Path(file.filename or "knowledge.txt").name
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"暂不支持 {ext or '未知'} 文件类型")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="上传文件不能为空")
        checksum = hashlib.sha256(data).hexdigest()
        existing = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.base_id == base.id, KnowledgeDocument.checksum == checksum)
            .first()
        )
        if existing and existing.status == "indexed":
            return self._document_dict(existing)

        object_name = f"knowledge/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex}_{filename}"
        if not minio_service.client:
            minio_service.connect()
        content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        uploaded = minio_service.upload_bytes(data, object_name=object_name, content_type=content_type)
        if not uploaded:
            raise HTTPException(status_code=503, detail="MinIO 不可用，知识文档上传失败")

        document = KnowledgeDocument(
            base_id=base.id,
            title=(title or Path(filename).stem).strip(),
            filename=filename,
            file_type=ext,
            file_size=len(data),
            checksum=checksum,
            minio_bucket=minio_service.bucket_name,
            minio_object=object_name,
            status="uploaded",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            self.index_document_bytes(db, document, data, category=category)
        except Exception as exc:
            logger.exception(f"知识文档索引失败: document_id={document.id}")
            document.status = "failed"
            document.error_message = str(exc)
            db.commit()
            raise HTTPException(status_code=500, detail=f"知识文档索引失败: {exc}") from exc

        self.refresh_base_counters(db, int(base.id))
        db.refresh(document)
        return self._document_dict(document)

    def index_document_bytes(self, db: Session, document: KnowledgeDocument, data: bytes, *, category: str = "") -> None:
        text = parse_document_bytes(data, document.filename)
        if not text:
            raise RuntimeError("文档未解析出有效文本")
        chunks = chunk_text(text)
        if not chunks:
            raise RuntimeError("文档切片为空")

        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
        for index, chunk in enumerate(chunks):
            metadata = {
                "category": category or "",
                "filename": document.filename,
                "file_type": document.file_type,
            }
            row = KnowledgeChunk(
                base_id=document.base_id,
                document_id=document.id,
                chunk_index=index,
                content=chunk["content"],
                section_title=chunk.get("section_title") or "",
                source_page=chunk.get("source_page"),
                token_count=max(1, math.ceil(len(chunk["content"]) / 1.8)),
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(row)
            db.flush()
            vector_payload = {
                "chunk_id": int(row.id),
                "base_id": int(document.base_id),
                "document_id": int(document.id),
                "document_title": document.title,
                "filename": document.filename,
                "section_title": row.section_title or "",
                "source_page": row.source_page,
                "category": category or "",
            }
            if knowledge_vector_service.upsert_chunk(
                chunk_id=int(row.id),
                vector_text=f"{document.title}\n{row.section_title or ''}\n{row.content}",
                payload=vector_payload,
            ):
                row.vector_id = str(row.id)
        document.status = "indexed"
        document.error_message = ""
        db.commit()

    def list_documents(
        self,
        db: Session,
        *,
        base_id: Optional[int] = None,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self.ensure_default_base(db)
        query = db.query(KnowledgeDocument)
        if base_id:
            query = query.filter(KnowledgeDocument.base_id == base_id)
        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(or_(KnowledgeDocument.title.like(like), KnowledgeDocument.filename.like(like)))
        total = query.count()
        rows = (
            query.order_by(KnowledgeDocument.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "records": [self._document_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete_document(self, db: Session, document_id: int) -> None:
        self.ensure_tables()
        document = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="知识文档不存在")
        base_id = int(document.base_id)
        knowledge_vector_service.delete_document(document_id)
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).delete()
        db.delete(document)
        db.commit()
        self.refresh_base_counters(db, base_id)

    def get_document(self, db: Session, document_id: int) -> dict[str, Any]:
        self.ensure_tables()
        row = (
            db.query(KnowledgeDocument, KnowledgeBase)
            .join(KnowledgeBase, KnowledgeDocument.base_id == KnowledgeBase.id)
            .filter(KnowledgeDocument.id == document_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="知识文档不存在")
        document, base = row
        chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
            .all()
        )
        payload = self._document_dict(document)
        payload["base_name"] = base.name
        payload["chunks"] = [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "section_title": chunk.section_title or "",
                "source_page": chunk.source_page,
                "token_count": chunk.token_count or 0,
                "content": chunk.content,
            }
            for chunk in chunks
        ]
        payload["content"] = "\n\n".join(chunk.content for chunk in chunks)
        return payload

    def search(
        self,
        db: Session,
        *,
        query: str,
        base_ids: Optional[list[int]] = None,
        category: str = "",
        top_k: int = 8,
    ) -> dict[str, Any]:
        self.ensure_default_base(db)
        clean_query = query.strip()
        if not clean_query:
            raise HTTPException(status_code=400, detail="检索问题不能为空")
        tokens = tokenize(clean_query)
        if not tokens:
            tokens = [clean_query]
        vector_scores = knowledge_vector_service.search(
            query=clean_query,
            base_ids=base_ids,
            top_k=top_k,
        )

        rows_query = (
            db.query(KnowledgeChunk, KnowledgeDocument, KnowledgeBase)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .join(KnowledgeBase, KnowledgeChunk.base_id == KnowledgeBase.id)
            .filter(KnowledgeDocument.status == "indexed", KnowledgeBase.enabled == True)  # noqa: E712
        )
        if base_ids:
            rows_query = rows_query.filter(KnowledgeChunk.base_id.in_(base_ids))
        if category:
            rows_query = rows_query.filter(KnowledgeChunk.metadata_json.like(f"%{category}%"))

        candidates = rows_query.order_by(KnowledgeChunk.id.desc()).limit(2000).all()
        scored = []
        for chunk, document, base in candidates:
            keyword_score = score_chunk(clean_query, tokens, chunk.content, document.title)
            vector_score = vector_scores.get(int(chunk.id), 0.0)
            score = keyword_score + vector_score * 6.0
            if score > 0:
                scored.append((score, chunk, document, base))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [
            self._search_result(score, chunk, document, base)
            for score, chunk, document, base in scored[: max(1, min(top_k, 20))]
        ]
        return {"query": clean_query, "results": results, "total": len(results)}

    def answer_prompt_context(self, search_result: dict[str, Any]) -> str:
        lines = ["以下是知识库检索结果，只能基于这些内容回答，并给出来源："]
        for index, item in enumerate(search_result.get("results") or [], start=1):
            source = item["source"]
            lines.append(
                f"\n[{index}] 来源：{source['document_title']} / {source.get('section_title') or '未标注章节'}"
            )
            lines.append(item["content"])
        return "\n".join(lines)

    def refresh_base_counters(self, db: Session, base_id: int) -> None:
        base = db.query(KnowledgeBase).filter(KnowledgeBase.id == base_id).first()
        if not base:
            return
        base.document_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.base_id == base_id).count()
        base.chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.base_id == base_id).count()
        db.commit()

    def _get_base_or_default(self, db: Session, base_id: Optional[int]) -> KnowledgeBase:
        if base_id:
            self.ensure_tables()
            base = db.query(KnowledgeBase).filter(KnowledgeBase.id == base_id).first()
            if not base:
                raise HTTPException(status_code=404, detail="知识库不存在")
            return base
        return self.ensure_default_base(db)

    @staticmethod
    def _base_dict(row: KnowledgeBase) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description or "",
            "category": row.category or "general",
            "enabled": bool(row.enabled),
            "document_count": row.document_count or 0,
            "chunk_count": row.chunk_count or 0,
            "create_time": row.create_time.isoformat() if row.create_time else None,
            "update_time": row.update_time.isoformat() if row.update_time else None,
        }

    @staticmethod
    def _document_dict(row: KnowledgeDocument) -> dict[str, Any]:
        return {
            "id": row.id,
            "base_id": row.base_id,
            "title": row.title,
            "filename": row.filename,
            "file_type": row.file_type,
            "file_size": row.file_size or 0,
            "status": row.status,
            "error_message": row.error_message or "",
            "minio_bucket": row.minio_bucket,
            "minio_object": row.minio_object,
            "version": row.version or 1,
            "create_time": row.create_time.isoformat() if row.create_time else None,
            "update_time": row.update_time.isoformat() if row.update_time else None,
        }

    @staticmethod
    def _search_result(score: float, chunk: KnowledgeChunk, document: KnowledgeDocument, base: KnowledgeBase) -> dict[str, Any]:
        return {
            "chunk_id": chunk.id,
            "document_id": document.id,
            "base_id": base.id,
            "score": round(float(score), 4),
            "content": chunk.content,
            "source": {
                "base_name": base.name,
                "document_title": document.title,
                "filename": document.filename,
                "page": chunk.source_page,
                "section_title": chunk.section_title or "",
            },
        }


def chunk_text(text: str, *, chunk_size: int = 700, overlap: int = 100) -> list[dict[str, Any]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if part.strip()]
    chunks: list[dict[str, Any]] = []
    current = ""
    section = ""
    page: Optional[int] = None

    for paragraph in paragraphs:
        page_match = re.match(r"^\[第(\d+)页\]\s*(.*)", paragraph, flags=re.S)
        if page_match:
            page = int(page_match.group(1))
            paragraph = page_match.group(2).strip()
            if not paragraph:
                continue
        if is_section_title(paragraph):
            section = paragraph[:120]
        if len(current) + len(paragraph) + 1 <= chunk_size:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append({"content": current, "section_title": section, "source_page": page})
        prefix = current[-overlap:] if overlap and current else ""
        current = f"{prefix}\n{paragraph}".strip()
        while len(current) > chunk_size * 1.5:
            part = current[:chunk_size]
            chunks.append({"content": part, "section_title": section, "source_page": page})
            current = current[max(0, chunk_size - overlap) :]
    if current:
        chunks.append({"content": current, "section_title": section, "source_page": page})
    return chunks


def is_section_title(text: str) -> bool:
    if len(text) > 80:
        return False
    patterns = [
        r"^第[一二三四五六七八九十百\d]+[章节条]",
        r"^\d+(\.\d+){0,3}\s+",
        r"^[一二三四五六七八九十]+、",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    latin = re.findall(r"[a-z0-9_+-]{2,}", lowered)
    grams: list[str] = []
    for word in chinese:
        if len(word) <= 4:
            grams.append(word)
        else:
            grams.extend(word[i : i + 2] for i in range(len(word) - 1))
            grams.extend(word[i : i + 3] for i in range(len(word) - 2))
    return list(dict.fromkeys(chinese + grams + latin))


def score_chunk(query: str, tokens: list[str], content: str, title: str) -> float:
    haystack = f"{title}\n{content}".lower()
    counter = Counter(token for token in tokens if token and token in haystack)
    if not counter:
        return 0.0
    score = sum(1.0 + min(len(token), 8) / 8 for token, count in counter.items() for _ in range(count))
    if query.lower() in haystack:
        score += 8
    first_hit = min((haystack.find(token) for token in counter if haystack.find(token) >= 0), default=99999)
    score += max(0, 2 - first_hit / 500)
    return score / max(1, math.log(len(content) + 10, 10))


knowledge_service = KnowledgeService()
