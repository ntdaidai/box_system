"""
OnlyOffice document editing API backed by MinIO.

The browser loads DocsAPI from OnlyOffice, while OnlyOffice Document Server
downloads and saves documents through these FastAPI endpoints.
"""

import hashlib
import io
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from jose import jwt
from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/onlyoffice", tags=["OnlyOffice 文档编辑"])


ONLYOFFICE_SERVER_URL = settings.ONLYOFFICE_PUBLIC_URL.rstrip("/")
BACKEND_PUBLIC_URL = settings.BACKEND_PUBLIC_URL.rstrip("/")
JWT_SECRET = settings.ONLYOFFICE_JWT_SECRET
BUCKET_NAME = settings.DOCUMENT_BUCKET
OBJECT_PREFIX = "editable"
EDITOR_KEY_VERSION = "download-v3"

minio_client: Optional[Minio] = None


class CallbackData(BaseModel):
    key: str
    status: int
    url: Optional[str] = None
    changesurl: Optional[str] = None
    history: Optional[dict] = None
    users: Optional[list] = None
    actions: Optional[list] = None
    token: Optional[str] = None


class ForceSaveRequest(BaseModel):
    user_id: str = "user_001"


class ExportRequest(BaseModel):
    user_id: str = "user_001"
    document_ids: list[str] = []
    month: Optional[str] = None


def get_minio_client() -> Minio:
    global minio_client
    if minio_client is None:
        minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
    return minio_client


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def get_document_type(file_extension: str) -> str:
    type_map = {
        "docx": "word", "doc": "word", "odt": "word", "rtf": "word", "txt": "word",
        "xlsx": "cell", "xls": "cell", "ods": "cell", "csv": "cell",
        "pptx": "slide", "ppt": "slide", "odp": "slide",
        "pdf": "pdf",
    }
    return type_map.get(file_extension, "word")


def get_content_type(file_extension: str) -> str:
    content_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "pdf": "application/pdf",
        "odt": "application/vnd.oasis.opendocument.text",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "csv": "text/csv",
        "txt": "text/plain",
    }
    return content_types.get(file_extension, "application/octet-stream")


def build_object_name(user_id: str, document_id: str, ext: str) -> str:
    safe_user = user_id.replace("/", "_")
    return f"{OBJECT_PREFIX}/{safe_user}/{document_id}.{ext}"


def parse_object_name(object_name: str) -> tuple[str, str, str]:
    filename = object_name.rsplit("/", 1)[-1]
    document_id, ext = filename.rsplit(".", 1)
    return document_id, filename, ext.lower()


def document_key(document_id: str) -> str:
    key_source = f"{document_id}:{EDITOR_KEY_VERSION}"
    return hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:32]


def find_document_object(document_id: str, user_id: Optional[str] = None) -> Optional[str]:
    client = get_minio_client()
    prefix = f"{OBJECT_PREFIX}/{user_id}/" if user_id else f"{OBJECT_PREFIX}/"
    for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True):
        try:
            found_id, _, _ = parse_object_name(obj.object_name)
        except ValueError:
            continue
        if found_id == document_id and not obj.object_name.endswith(".bak"):
            return obj.object_name
    return None


def make_editor_token(config: dict) -> str:
    return jwt.encode(config, JWT_SECRET, algorithm="HS256")


def get_original_title(stat, fallback: str) -> str:
    return get_metadata_value(stat, "original-name", fallback)


def get_metadata_value(stat, key: str, fallback: str = "") -> str:
    metadata = getattr(stat, "metadata", None) or {}
    header_key = f"X-Amz-Meta-{key.title()}"
    value = (
        metadata.get(header_key)
        or metadata.get(header_key.lower())
        or metadata.get(key)
        or metadata.get(key.lower())
        or fallback
    )
    return unquote(value)


def get_document_created_at(stat, fallback: str = "") -> str:
    return get_metadata_value(stat, "created-at", fallback)


def encode_metadata_value(value: str) -> str:
    # S3-compatible metadata is carried in HTTP headers, so non-ASCII values
    # such as Chinese filenames must be encoded before upload.
    return quote(value or "", safe="")


def content_disposition_inline(filename: str) -> str:
    quoted = quote(filename)
    return f"inline; filename*=UTF-8''{quoted}"


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("user_001"),
    user_name: str = Form("用户"),
):
    ext = get_file_extension(file.filename or "")
    allowed_extensions = {
        "docx", "doc", "odt", "rtf", "txt",
        "xlsx", "xls", "ods", "csv",
        "pptx", "ppt", "odp",
        "pdf",
    }
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    content = await file.read()
    document_id = f"doc_{user_id}_{int(time.time() * 1000)}"
    object_name = build_object_name(user_id, document_id, ext)
    now = datetime.now(timezone.utc).isoformat()

    try:
        get_minio_client().put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(content),
            len(content),
            content_type=get_content_type(ext),
            metadata={
                "original-name": encode_metadata_value(file.filename or f"{document_id}.{ext}"),
                "owner-id": encode_metadata_value(user_id),
                "owner-name": encode_metadata_value(user_name),
                "created-at": encode_metadata_value(now),
            },
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"上传到 MinIO 失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传到 MinIO 失败: {exc}") from exc

    return {
        "success": True,
        "data": {
            "document_id": document_id,
            "document_key": document_key(document_id),
            "title": file.filename,
            "url": f"{BACKEND_PUBLIC_URL}/api/onlyoffice/document/{document_id}",
            "file_type": ext,
            "file_size": len(content),
            "document_type": get_document_type(ext),
            "created_at": now,
            "updated_at": now,
            "owner_id": user_id,
            "owner_name": user_name,
        },
    }


@router.get("/document/{document_id}")
async def get_document(document_id: str):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        client = get_minio_client()
        response = client.get_object(BUCKET_NAME, object_name)
        _, filename, ext = parse_object_name(object_name)
        stat = client.stat_object(BUCKET_NAME, object_name)
        title = get_original_title(stat, filename)
        headers = {"Content-Disposition": content_disposition_inline(title)}
        return StreamingResponse(
            response.stream(32 * 1024),
            media_type=get_content_type(ext),
            headers=headers,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取文档失败: {exc}") from exc


@router.post("/callback/{document_id}")
async def document_callback_for_document(document_id: str, callback_data: CallbackData):
    return await handle_callback(document_id, callback_data)


@router.post("/callback")
async def document_callback(callback_data: CallbackData):
    object_name = find_document_object_by_key(callback_data.key)
    if not object_name:
        return {"error": 1, "message": "document key not found"}
    document_id, _, _ = parse_object_name(object_name)
    return await handle_callback(document_id, callback_data)


def find_document_object_by_key(key: str) -> Optional[str]:
    client = get_minio_client()
    for obj in client.list_objects(BUCKET_NAME, prefix=f"{OBJECT_PREFIX}/", recursive=True):
        try:
            document_id, _, _ = parse_object_name(obj.object_name)
        except ValueError:
            continue
        if document_key(document_id) == key and not obj.object_name.endswith(".bak"):
            return obj.object_name
    return None


async def handle_callback(document_id: str, callback_data: CallbackData):
    try:
        print(
            f"[OnlyOffice callback] document_id={document_id} "
            f"status={callback_data.status} has_url={bool(callback_data.url)}"
        )
        if callback_data.status == 6 and callback_data.url:
            saved = await save_updated_document(document_id, callback_data.url)
            if not saved:
                print(f"[OnlyOffice callback] save failed document_id={document_id}")
                return {"error": 1, "message": "save failed"}
            print(f"[OnlyOffice callback] saved document_id={document_id}")
        return {"error": 0}
    except Exception as exc:
        print(f"[OnlyOffice callback] error document_id={document_id}: {exc}")
        return {"error": 1, "message": str(exc)}


async def save_updated_document(document_id: str, url: str) -> bool:
    object_name = find_document_object(document_id)
    if not object_name:
        return False

    client = get_minio_client()
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        updated = await http_client.get(url)
        updated.raise_for_status()
        original_metadata = {}
        try:
            stat = client.stat_object(BUCKET_NAME, object_name)
            original_title = get_original_title(stat, object_name.rsplit("/", 1)[-1])
            previous_updated_at = stat.last_modified.isoformat() if stat.last_modified else ""
            original_metadata = {
                "original-name": encode_metadata_value(original_title),
                "created-at": encode_metadata_value(get_document_created_at(stat, previous_updated_at)),
            }
            owner_id = get_metadata_value(stat, "owner-id")
            owner_name = get_metadata_value(stat, "owner-name")
            if owner_id:
                original_metadata["owner-id"] = encode_metadata_value(owner_id)
            if owner_name:
                original_metadata["owner-name"] = encode_metadata_value(owner_name)
            current = client.get_object(BUCKET_NAME, object_name).read()
            client.put_object(
                BUCKET_NAME,
                f"{object_name}.bak",
                io.BytesIO(current),
                len(current),
                content_type=stat.content_type,
                metadata=original_metadata,
            )
        except Exception:
            pass

        _, _, ext = parse_object_name(object_name)
        client.put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(updated.content),
            len(updated.content),
            content_type=get_content_type(ext),
            metadata=original_metadata,
        )
        return True


@router.post("/force-save/{document_id}")
async def force_save_document(document_id: str, payload: ForceSaveRequest):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    key = document_key(document_id)
    command = {
        "c": "forcesave",
        "key": key,
        "userdata": payload.user_id,
    }
    token = jwt.encode(command, JWT_SECRET, algorithm="HS256")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{ONLYOFFICE_SERVER_URL}/command?shardkey={key}",
                json={"token": token},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        response.raise_for_status()
        data = response.json()
        error_code = data.get("error")
        # OnlyOffice returns error=4 when there are no pending changes to force-save.
        # This can happen after the user presses Ctrl+S inside the editor and then
        # clicks our save button. Treat it as an idempotent success.
        if error_code == 4:
            return {"success": True, "data": data, "already_saved": True}
        if error_code not in (0, None):
            raise HTTPException(status_code=502, detail=f"OnlyOffice 强制保存失败: {data}")
        return {"success": True, "data": data, "already_saved": False}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用 OnlyOffice 强制保存失败: {exc}") from exc


@router.get("/editor-config/{document_id}")
async def get_editor_config(
    document_id: str,
    user_id: str = "user_001",
    user_name: str = "用户",
    mode: str = "edit",
):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        stat = get_minio_client().stat_object(BUCKET_NAME, object_name)
        _, filename, ext = parse_object_name(object_name)
        title = get_original_title(stat, filename)
        # OnlyOffice Document Server downloads the document server-side, so the
        # document URL must be absolute and reachable from that service.
        doc_url = f"{BACKEND_PUBLIC_URL}/api/onlyoffice/document/{document_id}"
        # callback_url 必须使用完整 URL，OnlyOffice Document Server 需要它来回调保存文档
        callback_url = f"{BACKEND_PUBLIC_URL}/api/onlyoffice/callback/{document_id}"
        document_type = get_document_type(ext)

        config = {
            "document": {
                "fileType": ext,
                "key": document_key(document_id),
                "title": title,
                "url": doc_url,
                "permissions": {
                    "comment": mode == "edit",
                    "download": True,
                    "edit": mode == "edit",
                    "fillForms": mode == "edit",
                    "print": True,
                    "review": mode == "edit",
                },
            },
            "documentType": document_type,
            "editorConfig": {
                "callbackUrl": callback_url,
                "lang": "zh-CN",
                "mode": mode,
                "user": {"id": user_id, "name": user_name},
                "customization": {
                    "autosave": True,
                    "forcesave": True,
                    "compactHeader": False,
                    "toolbarNoTabs": False,
                    "hideRightMenu": False,
                    "hideRulers": False,
                    "macros": False,
                    "plugins": True,
                },
            },
            "height": "100%",
            "width": "100%",
            "type": "desktop",
        }
        config["token"] = make_editor_token(config)

        return {
            "success": True,
            "data": {
                **config,
                "onlyoffice_server_url": ONLYOFFICE_SERVER_URL,
                "file_size": stat.size,
                "updated_at": stat.last_modified.isoformat() if stat.last_modified else "",
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取编辑器配置失败: {exc}") from exc


@router.delete("/document/{document_id}")
async def delete_document(document_id: str):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    client = get_minio_client()
    client.remove_object(BUCKET_NAME, object_name)
    try:
        client.remove_object(BUCKET_NAME, f"{object_name}.bak")
    except Exception:
        pass
    return {"success": True, "message": "文档已删除"}


@router.get("/documents")
async def list_documents(
    user_id: str = "user_001",
    page: int = 1,
    page_size: int = 20,
):
    client = get_minio_client()
    docs = []
    prefix = f"{OBJECT_PREFIX}/{user_id}/"
    for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True):
        if obj.object_name.endswith(".bak"):
            continue
        try:
            document_id, filename, ext = parse_object_name(obj.object_name)
        except ValueError:
            continue
        try:
            stat = client.stat_object(BUCKET_NAME, obj.object_name)
            title = get_original_title(stat, filename)
            updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
            created_at = get_document_created_at(stat, updated_at)
        except Exception:
            title = filename
            updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
            created_at = updated_at
        docs.append({
            "document_id": document_id,
            "title": title,
            "file_type": ext,
            "file_size": obj.size or 0,
            "document_type": get_document_type(ext),
            "created_at": created_at,
            "updated_at": updated_at,
        })

    docs.sort(key=lambda item: item["updated_at"], reverse=True)
    total = len(docs)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "documents": docs[start:end],
        },
    }


@router.post("/documents/export")
async def export_documents(payload: ExportRequest):
    client = get_minio_client()
    selected_ids = set(payload.document_ids or [])
    prefix = f"{OBJECT_PREFIX}/{payload.user_id}/"
    archive = io.BytesIO()
    added_names: set[str] = set()
    added_count = 0

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True):
            if obj.object_name.endswith(".bak"):
                continue
            try:
                document_id, filename, _ = parse_object_name(obj.object_name)
            except ValueError:
                continue
            if selected_ids and document_id not in selected_ids:
                continue
            updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
            if payload.month and not updated_at.startswith(payload.month):
                continue
            try:
                stat = client.stat_object(BUCKET_NAME, obj.object_name)
                title = get_original_title(stat, filename)
                content = client.get_object(BUCKET_NAME, obj.object_name).read()
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"导出文档失败: {exc}") from exc

            archive_name = Path(title).name or filename
            if archive_name in added_names:
                stem = Path(archive_name).stem
                suffix = Path(archive_name).suffix
                archive_name = f"{stem}_{document_id}{suffix}"
            added_names.add(archive_name)
            zip_file.writestr(archive_name, content)
            added_count += 1

    if added_count == 0:
        raise HTTPException(status_code=404, detail="没有找到可导出的文档")

    archive.seek(0)
    suffix = payload.month or datetime.now().strftime("%Y-%m-%d")
    filename = f"documents_{suffix}.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ONLYOFFICE_SERVER_URL}/healthcheck")
        minio_ok = get_minio_client().bucket_exists(BUCKET_NAME)
        return {
            "status": "healthy" if response.status_code == 200 and minio_ok else "unhealthy",
            "onlyoffice_server": ONLYOFFICE_SERVER_URL,
            "backend_public_url": BACKEND_PUBLIC_URL,
            "document_bucket": BUCKET_NAME,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "onlyoffice_server": ONLYOFFICE_SERVER_URL,
            "backend_public_url": BACKEND_PUBLIC_URL,
            "document_bucket": BUCKET_NAME,
            "error": str(exc),
        }
