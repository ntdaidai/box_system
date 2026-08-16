"""
OnlyOffice document editing API backed by MinIO.

The browser loads DocsAPI from OnlyOffice, while OnlyOffice Document Server
downloads and saves documents through these FastAPI endpoints.
"""

import asyncio
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote, unquote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from jose import jwt
from minio import Minio
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.models.analysis_report import AnalysisReportKnowledgeCitation
from app.models.event_library import EventLibrary
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.safety_integration import SafetyEventInstance

router = APIRouter(prefix="/api/onlyoffice", tags=["OnlyOffice 文档编辑"])


ONLYOFFICE_SERVER_URL = settings.ONLYOFFICE_PUBLIC_URL.rstrip("/")
BACKEND_PUBLIC_URL = settings.BACKEND_PUBLIC_URL.rstrip("/")
JWT_SECRET = settings.ONLYOFFICE_JWT_SECRET
BUCKET_NAME = settings.DOCUMENT_BUCKET
OBJECT_PREFIX = "editable"
EDITOR_KEY_VERSION = "download-v3"
RISK_LABELS = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}

minio_client: Optional[Minio] = None


# docx 知识索引解析缓存：key=对象名，value=(对象 etag, 解析结果列表)
# 按 etag 判断文件是否变更，变更后自动重新解析，避免每次列表都下载解析
_docx_index_cache: dict[str, tuple[str, list[dict]]] = {}
_docx_index_cache_lock = threading.Lock()


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
    output_format: Literal["source", "pdf"] = "source"


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


def event_instance_no_from_document_id(document_id: str) -> str:
    prefix = "dam_event_report_"
    text = str(document_id or "")
    return text[len(prefix):] if text.startswith(prefix) else ""


def date_token_from_text(value: str) -> str:
    matched = re.search(r"20\d{6}", str(value or ""))
    return matched.group(0) if matched else ""


def instance_sequence_token(value: str) -> str:
    matched = re.search(r"_(\d{1,4})$", str(value or ""))
    return matched.group(1) if matched else ""


def normalize_event_instance_no(value: str, fallback_date: str = "", fallback_sequence: int = 1) -> str:
    text = str(value or "").strip()
    date_token = date_token_from_text(text) or date_token_from_text(fallback_date)
    if not date_token:
        return text
    sequence = instance_sequence_token(text) or str(fallback_sequence or 1)
    return f"EVT_{date_token}_{int(sequence):03d}"


def display_instance_no_for_event(db: Session, event: SafetyEventInstance) -> str:
    if not event.started_at:
        return event.instance_no
    day_start = datetime.combine(event.started_at.date(), datetime.min.time())
    day_end = day_start + timedelta(days=1)
    sequence = (
        db.query(func.count(SafetyEventInstance.id))
        .filter(
            SafetyEventInstance.started_at >= day_start,
            SafetyEventInstance.started_at < day_end,
            or_(
                SafetyEventInstance.started_at < event.started_at,
                and_(
                    SafetyEventInstance.started_at == event.started_at,
                    SafetyEventInstance.id <= event.id,
                ),
            ),
        )
        .scalar()
        or 1
    )
    return f"EVT_{event.started_at:%Y%m%d}_{int(sequence):03d}"


def normalize_event_report_title(title: str, document_id: str, fallback_date: str = "", fallback_sequence: int = 1) -> str:
    raw_title = Path(str(title or "未命名文档")).name
    if not (str(document_id or "").startswith("dam_event_report_") or "处置报告" in raw_title):
        return raw_title
    suffix = Path(raw_title).suffix
    stem = raw_title[:-len(suffix)] if suffix else raw_title
    instance_source = event_instance_no_from_document_id(document_id)
    if not instance_source:
        matched = re.search(r"(?:EVT_)?20\d{6}_[0-9a-fA-F-]+$", stem)
        instance_source = matched.group(0) if matched else ""
    base = re.sub(r"_?(?:EVT_)?20\d{6}_[0-9a-fA-F-]+$", "", stem).strip("_") or "事件处置报告"
    instance_no = normalize_event_instance_no(instance_source, fallback_date, fallback_sequence)
    return f"{base}_{instance_no}{suffix}" if instance_no else raw_title


def parse_metadata_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def find_knowledge_ref(
    db: Session,
    *,
    title: str,
    clause_id: str,
    section_path: str,
) -> dict:
    query = db.query(KnowledgeChunk, KnowledgeDocument).join(
        KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id
    )
    clean_title = str(title or "").replace(".docx", "").strip()
    if clean_title:
        query = query.filter(or_(
            KnowledgeDocument.title == clean_title,
            KnowledgeDocument.title.like(f"%{clean_title}%"),
            KnowledgeDocument.filename.like(f"%{clean_title}%"),
        ))
    if clause_id:
        query = query.filter(KnowledgeChunk.metadata_json.like(f"%{clause_id}%"))
    rows = query.order_by(KnowledgeChunk.id.asc()).limit(20).all()
    if not rows:
        return {}
    section_text = str(section_path or "").strip()
    selected_chunk, selected_doc = rows[0]
    for chunk, document in rows:
        metadata = parse_metadata_json(chunk.metadata_json)
        if clause_id and str(metadata.get("clause_id") or "").strip() == clause_id:
            selected_chunk, selected_doc = chunk, document
            if not section_text or section_text in str(metadata.get("section_path") or chunk.section_title or ""):
                break
    metadata = parse_metadata_json(selected_chunk.metadata_json)
    return {
        "evidence_id": f"K{selected_chunk.id}",
        "chunk_id": selected_chunk.id,
        "document_id": selected_doc.id,
        "document_title": selected_doc.title or clean_title,
        "section_path": metadata.get("section_path") or selected_chunk.section_title or section_path,
        "clause_id": metadata.get("clause_id") or clause_id,
    }


def parse_docx_knowledge_indexes(content: bytes, db: Session) -> list[dict]:
    try:
        from docx import Document
    except Exception:
        return []
    try:
        document = Document(io.BytesIO(content))
    except Exception:
        return []

    items: list[dict] = []
    in_knowledge_section = False
    for paragraph in document.paragraphs:
        text = re.sub(r"\s+", " ", paragraph.text or "").strip()
        normalized = re.sub(r"\s+", "", text)
        if normalized in {"6知识依据", "06知识依据"}:
            in_knowledge_section = True
            continue
        if in_knowledge_section and paragraph.style and str(paragraph.style.name or "").startswith("Heading") and normalized:
            break
        if not in_knowledge_section:
            continue
        matched = re.match(r"^\[(\d+)\]\s*《([^》]+)》\s*[，,]?\s*(.*)$", text)
        if not matched:
            continue
        display_index = int(matched.group(1))
        title = matched.group(2).strip()
        rest = matched.group(3).strip()
        clause_match = re.search(r"(?:^|[，,]\s*)条款\s+([A-Za-z0-9_-]+)", rest)
        clause_id = clause_match.group(1).strip() if clause_match else ""
        section_path = rest[:clause_match.start()].strip(" ，,") if clause_match else rest
        ref = find_knowledge_ref(db, title=title, clause_id=clause_id, section_path=section_path)
        items.append({
            "display_index": display_index,
            "evidence_id": ref.get("evidence_id") or "",
            "chunk_id": ref.get("chunk_id"),
            "document_id": ref.get("document_id"),
            "document_title": ref.get("document_title") or title,
            "section_path": ref.get("section_path") or section_path,
            "clause_id": ref.get("clause_id") or clause_id,
            "support_type": "report_section",
            "confidence": "",
        })
    return items


def merge_knowledge_indexes(existing: list[dict], parsed: list[dict]) -> list[dict]:
    source = parsed if parsed else existing
    merged: list[dict] = []
    seen: set[tuple] = set()
    for item in source or []:
        key = (
            item.get("document_id") or item.get("document_title"),
            item.get("clause_id") or item.get("evidence_id") or item.get("chunk_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        current = dict(item)
        current["display_index"] = len(merged) + 1
        merged.append(current)
    return merged


def _load_docx_indexes(client: Minio, object_name: str, etag: str) -> list[dict]:
    """并发下载并解析 docx 知识索引，按对象 etag 缓存结果。

    使用独立的数据库会话（请求级 db 不能跨线程使用），
    文件内容变更（etag 变化）后自动重新解析。
    """
    with _docx_index_cache_lock:
        cached = _docx_index_cache.get(object_name)
        if cached and cached[0] == etag:
            return cached[1]
    session = SessionLocal()
    try:
        response = client.get_object(BUCKET_NAME, object_name)
        try:
            items = parse_docx_knowledge_indexes(response.read(), session)
        finally:
            response.close()
            response.release_conn()
    except Exception:
        items = []
    finally:
        session.close()
    with _docx_index_cache_lock:
        _docx_index_cache[object_name] = (etag, items)
    return items


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


def document_key(document_id: str, version: str = "") -> str:
    key_source = f"{document_id}:{version}:{EDITOR_KEY_VERSION}"
    return hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:32]


def get_document_version(stat) -> str:
    return stat.last_modified.isoformat() if getattr(stat, "last_modified", None) else ""


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


def infer_created_at_from_document_id(document_id: str, fallback: str = "") -> str:
    for value in reversed(re.findall(r"(?<!\d)(1\d{12})(?!\d)", document_id or "")):
        try:
            timestamp = int(value) / 1000
            created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if 2020 <= created_at.year <= 2100:
                return created_at.isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            continue
    return fallback


def encode_metadata_value(value: str) -> str:
    # S3-compatible metadata is carried in HTTP headers, so non-ASCII values
    # such as Chinese filenames must be encoded before upload.
    return quote(value or "", safe="")


def content_disposition_inline(filename: str) -> str:
    quoted = quote(filename)
    return f"inline; filename*=UTF-8''{quoted}"


def content_disposition_attachment(filename: str) -> str:
    quoted = quote(filename)
    return f"attachment; filename*=UTF-8''{quoted}"


PDF_CONVERTIBLE_EXTENSIONS = {
    "docx", "doc", "odt", "rtf", "txt",
    "xlsx", "xls", "ods", "csv",
    "pptx", "ppt", "odp",
}


def convert_document_to_pdf(content: bytes, title: str, extension: str) -> tuple[bytes, str]:
    """Convert an office document to PDF in an isolated LibreOffice profile."""
    safe_title = Path(title).name or f"document.{extension}"
    if extension == "pdf":
        return content, safe_title
    if extension not in PDF_CONVERTIBLE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"{safe_title} 暂不支持导出为 PDF")

    with tempfile.TemporaryDirectory(prefix="document_pdf_export_") as temp_dir:
        work_dir = Path(temp_dir)
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        profile_dir = work_dir / "profile"
        runtime_dir = work_dir / "runtime"
        for directory in (input_dir, output_dir, profile_dir, runtime_dir):
            directory.mkdir(parents=True, exist_ok=True)
        runtime_dir.chmod(0o700)

        ascii_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(safe_title).stem).strip("_") or "document"
        input_path = input_dir / f"{ascii_stem}.{extension}"
        input_path.write_bytes(content)
        environment = os.environ.copy()
        environment["XDG_RUNTIME_DIR"] = str(runtime_dir)
        command = [
            "libreoffice",
            "--headless",
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_path),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=work_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=500, detail=f"{safe_title} 转换为 PDF 失败") from exc

        output_files = list(output_dir.glob("*.pdf"))
        if result.returncode != 0 or not output_files:
            detail = (result.stderr or result.stdout or "").strip()
            message = f"{safe_title} 转换为 PDF 失败"
            if detail:
                message = f"{message}: {detail[-240:]}"
            raise HTTPException(status_code=500, detail=message)
        return output_files[0].read_bytes(), f"{Path(safe_title).stem}.pdf"


@router.post("/upload")
async def upload_document():
    raise HTTPException(status_code=403, detail="文档中心不开放用户上传")


@router.get("/document/{document_id}")
async def get_document(document_id: str):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        client = get_minio_client()
        object_name = repair_legacy_ooxml_object(document_id, object_name)
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
        if obj.object_name.endswith(".bak"):
            continue
        try:
            stat = client.stat_object(BUCKET_NAME, obj.object_name)
            keys = {
                document_key(document_id, get_document_version(stat)),
                document_key(document_id),
            }
        except Exception:
            keys = {document_key(document_id)}
        if key in keys:
            return obj.object_name
    return None


def detect_ooxml_extension(content: bytes, current_ext: str) -> str:
    legacy_map = {"doc": "docx", "xls": "xlsx", "ppt": "pptx"}
    if current_ext not in legacy_map:
        return current_ext
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return current_ext

    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    return legacy_map.get(current_ext, current_ext)


def title_with_extension(title: str, ext: str) -> str:
    path = Path(title or "")
    if path.suffix:
        return f"{path.with_suffix(f'.{ext}')}"
    return f"{title}.{ext}" if title else f"document.{ext}"


def metadata_for_saved_document(stat, document_id: str, title: str) -> dict[str, str]:
    previous_updated_at = stat.last_modified.isoformat() if stat.last_modified else ""
    metadata = {
        "original-name": encode_metadata_value(title),
        "created-at": encode_metadata_value(
            get_document_created_at(
                stat,
                infer_created_at_from_document_id(document_id, previous_updated_at),
            )
        ),
    }
    owner_id = get_metadata_value(stat, "owner-id")
    owner_name = get_metadata_value(stat, "owner-name")
    if owner_id:
        metadata["owner-id"] = encode_metadata_value(owner_id)
    if owner_name:
        metadata["owner-name"] = encode_metadata_value(owner_name)
    return metadata


def repair_legacy_ooxml_object(document_id: str, object_name: str) -> str:
    _, _, ext = parse_object_name(object_name)
    if ext not in {"doc", "xls", "ppt"}:
        return object_name

    client = get_minio_client()
    stat = client.stat_object(BUCKET_NAME, object_name)
    content = client.get_object(BUCKET_NAME, object_name).read()
    detected_ext = detect_ooxml_extension(content, ext)
    if detected_ext == ext:
        return object_name

    target_object_name = object_name.rsplit(".", 1)[0] + f".{detected_ext}"
    title = title_with_extension(get_original_title(stat, object_name.rsplit("/", 1)[-1]), detected_ext)
    metadata = metadata_for_saved_document(stat, document_id, title)
    client.put_object(
        BUCKET_NAME,
        target_object_name,
        io.BytesIO(content),
        len(content),
        content_type=get_content_type(detected_ext),
        metadata=metadata,
    )
    client.remove_object(BUCKET_NAME, object_name)
    return target_object_name


async def handle_callback(document_id: str, callback_data: CallbackData):
    try:
        print(
            f"[OnlyOffice callback] document_id={document_id} "
            f"status={callback_data.status} has_url={bool(callback_data.url)}"
        )
        if callback_data.status in (2, 6) and callback_data.url:
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
        target_ext = detect_ooxml_extension(updated.content, ext)
        target_object_name = object_name
        target_title = original_title if "original_title" in locals() else object_name.rsplit("/", 1)[-1]
        if target_ext != ext:
            target_object_name = object_name.rsplit(".", 1)[0] + f".{target_ext}"
            target_title = title_with_extension(target_title, target_ext)

        if not original_metadata:
            try:
                stat = client.stat_object(BUCKET_NAME, object_name)
                original_metadata = metadata_for_saved_document(stat, document_id, target_title)
            except Exception:
                original_metadata = {"original-name": encode_metadata_value(target_title)}
        else:
            original_metadata["original-name"] = encode_metadata_value(target_title)

        client.put_object(
            BUCKET_NAME,
            target_object_name,
            io.BytesIO(updated.content),
            len(updated.content),
            content_type=get_content_type(target_ext),
            metadata=original_metadata,
        )
        if target_object_name != object_name:
            try:
                client.remove_object(BUCKET_NAME, object_name)
            except Exception:
                pass
        return True


@router.post("/force-save/{document_id}")
async def force_save_document(document_id: str, payload: ForceSaveRequest):
    object_name = find_document_object(document_id)
    if not object_name:
        raise HTTPException(status_code=404, detail="文档不存在")

    stat = get_minio_client().stat_object(BUCKET_NAME, object_name)
    key = document_key(document_id, get_document_version(stat))
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
        object_name = repair_legacy_ooxml_object(document_id, object_name)
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
                "key": document_key(document_id, get_document_version(stat)),
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
                    "forcesave": False,
                    "compactHeader": False,
                    "toolbarNoTabs": False,
                    "hideRightMenu": False,
                    "hideRulers": False,
                    "macros": False,
                    "spellcheck": False,
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
    db: Session = Depends(get_db),
):
    client = get_minio_client()
    prefix = f"{OBJECT_PREFIX}/{user_id}/"
    # 先完整收集对象列表，再并发处理，避免串行遍历+逐对象 stat
    objects = [
        obj
        for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
        if not obj.object_name.endswith(".bak")
    ]

    event_instance_nos: set[str] = set()
    for obj in objects:
        try:
            document_id, _, _ = parse_object_name(obj.object_name)
        except ValueError:
            continue
        event_instance_no = event_instance_no_from_document_id(document_id)
        if event_instance_no:
            event_instance_nos.add(event_instance_no)

    def build_doc(obj):
        """并发获取对象元数据（stat），构建基础文档记录"""
        try:
            document_id, filename, ext = parse_object_name(obj.object_name)
        except ValueError:
            return None
        try:
            stat = client.stat_object(BUCKET_NAME, obj.object_name)
            title = get_original_title(stat, filename)
            updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
            created_at = get_document_created_at(
                stat,
                infer_created_at_from_document_id(document_id, updated_at),
            )
            etag = getattr(stat, "etag", None) or ""
        except Exception:
            title = filename
            updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
            created_at = infer_created_at_from_document_id(document_id, updated_at)
            etag = ""
        return {
            "document_id": document_id,
            "title": title,
            "file_type": ext,
            "file_size": obj.size or 0,
            "document_type": get_document_type(ext),
            "created_at": created_at,
            "updated_at": updated_at,
            "_object_name": obj.object_name,
            "_etag": etag,
        }

    # 并发 stat：把 189 次串行网络往返压到 1 轮
    docs = []
    with ThreadPoolExecutor(max_workers=24) as pool:
        for result in pool.map(build_doc, objects):
            if result:
                docs.append(result)

    event_by_instance_no = {}
    knowledge_indexes_by_report_id: dict[int, list[dict]] = {}
    if event_instance_nos:
        rows = db.query(SafetyEventInstance, EventLibrary).outerjoin(
            EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id
        ).filter(
            SafetyEventInstance.instance_no.in_(event_instance_nos)
        ).all()
        event_by_instance_no = {
            instance.instance_no: (instance, event)
            for instance, event in rows
        }
        report_ids = [
            instance.analysis_report_id
            for instance, _ in rows
            if instance.analysis_report_id
        ]
        if report_ids:
            citation_rows = (
                db.query(AnalysisReportKnowledgeCitation)
                .filter(AnalysisReportKnowledgeCitation.report_id.in_(report_ids))
                .order_by(
                    AnalysisReportKnowledgeCitation.report_id.asc(),
                    AnalysisReportKnowledgeCitation.id.asc(),
                )
                .all()
            )
            seen_keys: set[tuple] = set()
            for citation in citation_rows:
                key = (
                    citation.report_id,
                    citation.document_id,
                    citation.document_title,
                    citation.section_path,
                    citation.clause_id,
                    citation.evidence_id,
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                items = knowledge_indexes_by_report_id.setdefault(citation.report_id, [])
                items.append({
                    "display_index": len(items) + 1,
                    "evidence_id": citation.evidence_id,
                    "chunk_id": citation.chunk_id,
                    "document_id": citation.document_id,
                    "document_title": citation.document_title,
                    "section_path": citation.section_path,
                    "clause_id": citation.clause_id,
                    "support_type": citation.support_type,
                    "confidence": citation.confidence,
                })

    # 并发解析 docx 知识索引（带 etag 缓存），之后在组装阶段统一合并
    docx_indexes_by_object: dict[str, list[dict]] = {}
    parse_jobs: list[dict] = []
    for doc in docs:
        if str(doc.get("file_type") or "").lower() != "docx":
            continue
        event_instance_no = event_instance_no_from_document_id(doc["document_id"])
        event_pair = event_by_instance_no.get(event_instance_no) if event_instance_no else None
        if not event_pair:
            continue
        event, _ = event_pair
        citation_indexes = knowledge_indexes_by_report_id.get(event.analysis_report_id or 0, [])
        if not citation_indexes:
            continue
        parse_jobs.append(doc)
    if parse_jobs:
        # 并发解析 docx（连接池上限约 15，12 并发留出余量给其他请求）
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [
                pool.submit(_load_docx_indexes, client, doc["_object_name"], doc.get("_etag") or "")
                for doc in parse_jobs
            ]
            for doc, future in zip(parse_jobs, futures):
                docx_indexes_by_object[doc["_object_name"]] = future.result()

    for doc in docs:
        event_instance_no = event_instance_no_from_document_id(doc["document_id"])
        if not event_instance_no:
            continue
        event_pair = event_by_instance_no.get(event_instance_no)
        doc["event_instance_no"] = event_instance_no
        if event_pair:
            event, event_def = event_pair
            display_instance_no = display_instance_no_for_event(db, event)
            doc["source_event_instance_no"] = event_instance_no
            doc["event_instance_no"] = display_instance_no
            doc["event_instance_id"] = event.id
            doc["event_started_at"] = event.started_at.isoformat() if event.started_at else None
            doc["event_name"] = event_def.event_name if event_def else event.summary
            doc["event_summary"] = event.summary
            doc["risk_level"] = event.risk_level
            doc["risk_label"] = RISK_LABELS.get(event.risk_level, event.risk_level)
            citation_indexes = knowledge_indexes_by_report_id.get(event.analysis_report_id or 0, [])
            docx_indexes = docx_indexes_by_object.get(doc["_object_name"], [])
            doc["knowledge_indexes"] = merge_knowledge_indexes(citation_indexes, docx_indexes)
            doc["title"] = normalize_event_report_title(
                doc["title"],
                f"dam_event_report_{display_instance_no}",
                doc["event_started_at"] or doc["created_at"] or doc["updated_at"],
                event.id,
            )
        else:
            doc["event_instance_no"] = normalize_event_instance_no(
                event_instance_no,
                doc.get("created_at") or doc.get("updated_at") or "",
                1,
            )
            doc["title"] = normalize_event_report_title(
                doc["title"],
                f"dam_event_report_{doc['event_instance_no']}",
                doc.get("created_at") or doc.get("updated_at") or "",
                1,
            )
        doc.pop("_object_name", None)
        doc.pop("_etag", None)

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
async def export_documents(payload: ExportRequest, db: Session = Depends(get_db)):
    client = get_minio_client()
    selected_ids = set(payload.document_ids or [])
    prefix = f"{OBJECT_PREFIX}/{payload.user_id}/"
    documents: list[dict] = []

    for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True):
        if obj.object_name.endswith(".bak"):
            continue
        try:
            document_id, filename, extension = parse_object_name(obj.object_name)
        except ValueError:
            continue
        if selected_ids and document_id not in selected_ids:
            continue
        updated_at = obj.last_modified.isoformat() if obj.last_modified else ""
        if payload.month and not updated_at.startswith(payload.month):
            continue
        try:
            stat = client.stat_object(BUCKET_NAME, obj.object_name)
            title = Path(get_original_title(stat, filename)).name or filename
            event_instance_no = event_instance_no_from_document_id(document_id)
            normalized_title = False
            if event_instance_no:
                event = (
                    db.query(SafetyEventInstance)
                    .filter(SafetyEventInstance.instance_no == event_instance_no)
                    .first()
                )
                if event:
                    display_instance_no = display_instance_no_for_event(db, event)
                    title = normalize_event_report_title(title, f"dam_event_report_{display_instance_no}", event.started_at.isoformat() if event.started_at else updated_at, event.id)
                    normalized_title = True
                else:
                    title = normalize_event_report_title(title, document_id, updated_at, len(documents) + 1)
                    normalized_title = True
            if not normalized_title:
                title = normalize_event_report_title(title, document_id, updated_at, len(documents) + 1)
            response = client.get_object(BUCKET_NAME, obj.object_name)
            try:
                content = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"导出文档失败: {exc}") from exc
        documents.append({
            "document_id": document_id,
            "title": title,
            "extension": extension,
            "content": content,
        })

    if not documents:
        raise HTTPException(status_code=404, detail="没有找到可导出的文档")

    exported_documents = []
    for document in documents:
        content = document["content"]
        title = document["title"]
        extension = document["extension"]
        if payload.output_format == "pdf":
            content, title = convert_document_to_pdf(content, title, extension)
            extension = "pdf"
        exported_documents.append({
            **document,
            "content": content,
            "title": title,
            "extension": extension,
        })

    if len(exported_documents) == 1 and not payload.month:
        document = exported_documents[0]
        return StreamingResponse(
            io.BytesIO(document["content"]),
            media_type=get_content_type(document["extension"]),
            headers={"Content-Disposition": content_disposition_attachment(document["title"])},
        )

    archive = io.BytesIO()
    added_names: set[str] = set()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for document in exported_documents:
            archive_name = document["title"]
            if archive_name in added_names:
                stem = Path(archive_name).stem
                suffix = Path(archive_name).suffix
                archive_name = f"{stem}_{document['document_id']}{suffix}"
            added_names.add(archive_name)
            zip_file.writestr(archive_name, document["content"])

    archive.seek(0)
    suffix = payload.month or datetime.now().strftime("%Y-%m-%d")
    filename = f"documents_{suffix}_{payload.output_format}.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition_attachment(filename)},
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
