"""Knowledge-base management and retrieval APIs."""

from __future__ import annotations

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
from app.models.knowledge import KnowledgeDocument
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
    top_k: int = Field(default=8, ge=1, le=20)


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


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    document = _get_knowledge_document(db, document_id)
    client = _get_minio_client()
    try:
        response = client.get_object(document.minio_bucket, document.minio_object)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="知识文档原始文件不存在") from exc
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
    doc_id = f"knowledge_{document.id}"
    doc_url = f"{BACKEND_PUBLIC_URL}/api/v1/knowledge/documents/{document.id}/file"
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
            "customization": {
                "compactHeader": False,
                "toolbarNoTabs": False,
                "hideRightMenu": False,
                "hideRulers": False,
                "macros": False,
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
        top_k=payload.top_k,
    )


def _get_knowledge_document(db: Session, document_id: int) -> KnowledgeDocument:
    knowledge_service.ensure_tables()
    document = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return document


def _get_minio_client():
    if not minio_service.client:
        minio_service.connect()
    if not minio_service.client:
        raise HTTPException(status_code=503, detail="MinIO 不可用")
    return minio_service.client
