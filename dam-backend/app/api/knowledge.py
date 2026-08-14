"""Knowledge-base management and retrieval APIs."""

from __future__ import annotations

import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.onlyoffice import (
    BACKEND_PUBLIC_URL,
    ONLYOFFICE_SERVER_URL,
    content_disposition_inline,
    document_key,
    get_content_type,
    get_document_type,
    make_editor_token,
)
from app.core.database import get_db
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.knowledge_service import knowledge_service
from app.services.minio_service import minio_service


router = APIRouter()

ONLYOFFICE_PREVIEW_EXTENSIONS = {
    "doc",
    "docx",
    "odt",
    "rtf",
    "txt",
    "xls",
    "xlsx",
    "ods",
    "csv",
    "ppt",
    "pptx",
    "odp",
    "pdf",
}


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    category: str = "general"
    enabled: bool = True


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    base_ids: list[int] = Field(default_factory=list)
    category: str = ""
    source_type: str = ""
    event_type: str = ""
    risk_level: str = ""
    top_k: int = Field(default=8, ge=1, le=20)


class KnowledgeTraceClaimRequest(BaseModel):
    claim: str = Field(..., min_length=1)
    candidate_chunk_ids: list[int] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/bases")
def list_bases(db: Session = Depends(get_db)):
    return {"code": 200, "data": knowledge_service.list_bases(db)}


@router.post("/bases")
def create_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    return {"code": 200, "data": knowledge_service.create_base(db, payload.model_dump())}


@router.get("/documents")
def list_documents(
    base_id: Optional[int] = Query(None),
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {
        "code": 200,
        "data": knowledge_service.list_documents(
            db,
            base_id=base_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
        ),
    }


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    base_id: Optional[int] = Form(None),
    category: str = Form(""),
    title: str = Form(""),
    db: Session = Depends(get_db),
):
    document = await knowledge_service.upload_document(
        db,
        file=file,
        base_id=base_id,
        category=category,
        title=title,
    )
    return {"code": 200, "data": document}


@router.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    return {"code": 200, "data": knowledge_service.get_document(db, document_id)}


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    return {"code": 200, "data": knowledge_service.get_chunk(db, chunk_id)}


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: int,
    target_chunk_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    document = _get_knowledge_document(db, document_id)
    client = _get_minio_client()
    try:
        response = client.get_object(document.minio_bucket, document.minio_object)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="知识文档原始文件不存在") from exc

    if target_chunk_id and (document.file_type or "").lower() == "docx":
        chunk = _get_document_chunk(db, document_id, target_chunk_id)
        try:
            data = response.read()
            data = add_target_bookmark_to_docx(data, chunk, bookmark_name_for_chunk(chunk.id))
        finally:
            response.close()
            response.release_conn()
        return StreamingResponse(
            io.BytesIO(data),
            media_type=get_content_type(document.file_type),
            headers={"Content-Disposition": content_disposition_inline(document.filename)},
        )

    return StreamingResponse(
        response.stream(32 * 1024),
        media_type=get_content_type(document.file_type),
        headers={"Content-Disposition": content_disposition_inline(document.filename)},
    )


@router.get("/documents/{document_id}/onlyoffice-config")
def get_document_onlyoffice_config(
    document_id: int,
    user_id: str = "knowledge_user",
    user_name: str = "知识库用户",
    chunk_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    document = _get_knowledge_document(db, document_id)
    ext = (document.file_type or "").lower()
    if ext not in ONLYOFFICE_PREVIEW_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"{ext or '未知'} 文件暂不支持 OnlyOffice 预览")

    client = _get_minio_client()
    try:
        stat = client.stat_object(document.minio_bucket, document.minio_object)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="知识文档原始文件不存在") from exc

    version = getattr(stat, "last_modified", None)
    version_key = version.isoformat() if version else str(document.update_time or document.checksum or document.id)
    target_chunk = None
    if chunk_id:
        target_chunk = _get_document_chunk(db, document_id, chunk_id)
        version_key = f"{version_key}:chunk:{target_chunk.id}"
    doc_id = f"knowledge_{document.id}"
    doc_url = f"{BACKEND_PUBLIC_URL}/api/v1/knowledge/documents/{document.id}/file"
    if target_chunk:
        doc_url = f"{doc_url}?target_chunk_id={target_chunk.id}"
    config = {
        "document": {
            "fileType": ext,
            "key": document_key(doc_id, version_key),
            "title": document.filename or document.title,
            "url": doc_url,
            "permissions": {
                "comment": False,
                "download": True,
                "edit": False,
                "fillForms": False,
                "print": True,
                "review": False,
            },
        },
        "documentType": get_document_type(ext),
        "editorConfig": {
            "lang": "zh-CN",
            "mode": "view",
            "user": {"id": user_id, "name": user_name},
            **({
                "actionLink": {
                    "action": {
                        "type": "bookmark",
                        "data": bookmark_name_for_chunk(target_chunk.id),
                    }
                }
            } if target_chunk else {}),
            "customization": {
                "compactHeader": False,
                "toolbarNoTabs": False,
                "hideRightMenu": False,
                "hideRulers": False,
                "macros": False,
                "spellcheck": False,
                "plugins": False,
            },
        },
        "height": "100%",
        "width": "100%",
        "type": "desktop",
    }
    config["token"] = make_editor_token(config)
    return {
        "code": 200,
        "data": {
            "success": True,
            **config,
            "onlyoffice_server_url": ONLYOFFICE_SERVER_URL,
            "file_size": stat.size,
            "updated_at": stat.last_modified.isoformat() if stat.last_modified else "",
        },
    }


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    knowledge_service.delete_document(db, document_id)
    return {"code": 200, "data": {"success": True}}


@router.post("/search")
def search_knowledge(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)):
    result = knowledge_service.search(
        db,
        query=payload.query,
        base_ids=payload.base_ids or None,
        category=payload.category,
        source_type=payload.source_type,
        event_type=payload.event_type,
        risk_level=payload.risk_level,
        top_k=payload.top_k,
    )
    return {"code": 200, "data": result}


@router.post("/mcp/search_knowledge")
def mcp_search_knowledge(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)):
    """MCP-friendly shape: direct result without the frontend response envelope."""
    return knowledge_service.search(
        db,
        query=payload.query,
        base_ids=payload.base_ids or None,
        category=payload.category,
        source_type=payload.source_type,
        event_type=payload.event_type,
        risk_level=payload.risk_level,
        top_k=payload.top_k,
    )


@router.post("/mcp/trace_report_claim")
def mcp_trace_report_claim(payload: KnowledgeTraceClaimRequest, db: Session = Depends(get_db)):
    return knowledge_service.trace_claim(
        db,
        claim=payload.claim,
        candidate_chunk_ids=payload.candidate_chunk_ids or None,
        top_k=payload.top_k,
    )


def _get_knowledge_document(db: Session, document_id: int) -> KnowledgeDocument:
    knowledge_service.ensure_tables()
    document = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return document


def _get_document_chunk(db: Session, document_id: int, chunk_id: int) -> KnowledgeChunk:
    chunk = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.id == chunk_id, KnowledgeChunk.document_id == document_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="知识片段不存在或不属于该文档")
    return chunk


def bookmark_name_for_chunk(chunk_id: int) -> str:
    return f"kb_chunk_{int(chunk_id)}"


def add_target_bookmark_to_docx(data: bytes, chunk: KnowledgeChunk, bookmark_name: str) -> bytes:
    try:
        from docx import Document
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except Exception as exc:
        raise HTTPException(status_code=500, detail="缺少 python-docx，无法定位知识片段") from exc

    document = Document(io.BytesIO(data))
    paragraph = find_target_paragraph(document, chunk)
    if paragraph is None:
        return data

    bookmark_id = str(900000 + (int(chunk.id) % 99999))
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), bookmark_name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)

    paragraph._p.insert(0, start)
    paragraph._p.append(end)

    output = io.BytesIO()
    document.save(output)
    output.seek(0)
    return output.read()


def find_target_paragraph(document, chunk: KnowledgeChunk):
    paragraphs = list(document.paragraphs)
    anchors = build_anchor_candidates(chunk)
    scroll_offset = 8
    for anchor in anchors:
        for index, paragraph in enumerate(paragraphs):
            text = normalize_anchor_text(paragraph.text)
            if anchor and anchor in text:
                return paragraphs[min(index + scroll_offset, len(paragraphs) - 1)]
    return paragraphs[0] if paragraphs else None


def build_anchor_candidates(chunk: KnowledgeChunk) -> list[str]:
    metadata = parse_metadata_json(chunk.metadata_json)
    candidates = [
        metadata.get("clause_id"),
        last_section_name(metadata.get("section_path") or chunk.section_title),
        chunk.section_title,
    ]
    for line in str(chunk.content or "").splitlines():
        cleaned = normalize_anchor_text(line)
        if len(cleaned) >= 8:
            candidates.append(cleaned[:80])
            break
    seen = set()
    result = []
    for value in candidates:
        cleaned = normalize_anchor_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def parse_metadata_json(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def last_section_name(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.split(">")[-1].strip()


def normalize_anchor_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _get_minio_client():
    if not minio_service.client:
        minio_service.connect()
    if not minio_service.client:
        raise HTTPException(status_code=503, detail="MinIO 不可用")
    return minio_service.client
