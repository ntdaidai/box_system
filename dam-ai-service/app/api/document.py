"""
文档管理 API - 集成 MinIO 对象存储
"""

import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/document", tags=["文档管理"])

# MinIO 客户端
minio_client = None

# 文档存储桶名称
BUCKET_NAME = "documents"


def get_minio_client():
    """获取 MinIO 客户端实例"""
    global minio_client
    if minio_client is None:
        try:
            from minio import Minio
            minio_client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            # 确保存储桶存在
            if not minio_client.bucket_exists(BUCKET_NAME):
                minio_client.make_bucket(BUCKET_NAME)
        except Exception as e:
            print(f"MinIO 连接失败: {e}")
            raise HTTPException(status_code=500, detail=f"存储服务连接失败: {str(e)}")
    return minio_client


# ========== 数据模型 ==========

class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    name: str
    size: int
    type: str
    url: str
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    success: bool
    data: List[DocumentInfo]
    total: int


# ========== 工具函数 ==========

def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def get_file_type(extension: str) -> str:
    """根据扩展名判断文件类型"""
    type_map = {
        "docx": "word", "doc": "word", "odt": "word", "rtf": "word",
        "xlsx": "excel", "xls": "excel", "ods": "excel", "csv": "excel",
        "pptx": "powerpoint", "ppt": "powerpoint", "odp": "powerpoint",
        "pdf": "pdf",
        "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "bmp": "image", "webp": "image",
        "txt": "text", "log": "text", "md": "text", "json": "text", "xml": "text", "yaml": "text", "yml": "text",
        "zip": "archive", "rar": "archive", "7z": "archive", "tar": "archive", "gz": "archive",
    }
    return type_map.get(extension, "other")


def get_content_type(extension: str) -> str:
    """获取文件的 MIME 类型"""
    content_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "pdf": "application/pdf",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
        "txt": "text/plain", "csv": "text/csv",
        "json": "application/json", "xml": "application/xml",
        "zip": "application/zip", "rar": "application/x-rar-compressed",
    }
    return content_types.get(extension, "application/octet-stream")


# ========== API 路由 ==========

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("未分类")
):
    """
    上传文档到 MinIO
    """
    try:
        # 获取文件信息
        filename = file.filename
        extension = get_file_extension(filename)
        file_type = get_file_type(extension)
        file_id = str(uuid.uuid4())

        # 构建存储路径：documents/{年}/{月}/{文件ID}.{扩展名}
        now = datetime.now()
        object_name = f"{now.year}/{now.month:02d}/{file_id}.{extension}"

        # 读取文件内容
        content = await file.read()
        file_size = len(content)

        # 上传到 MinIO
        from io import BytesIO
        client = get_minio_client()
        client.put_object(
            BUCKET_NAME,
            object_name,
            BytesIO(content),
            file_size,
            content_type=get_content_type(extension)
        )

        # 生成访问 URL
        url = f"/api/document/file/{object_name}"

        # 返回文档信息
        return {
            "success": True,
            "data": {
                "id": file_id,
                "name": filename,
                "size": file_size,
                "type": file_type,
                "extension": extension,
                "category": category,
                "url": url,
                "object_name": object_name,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/file/{path:path}")
async def get_file(path: str):
    """
    从 MinIO 获取文件
    """
    try:
        client = get_minio_client()

        # 获取文件对象
        response = client.get_object(BUCKET_NAME, path)

        # 获取文件扩展名
        extension = get_file_extension(path)
        content_type = get_content_type(extension)

        # 返回文件流
        return StreamingResponse(
            response.stream(32 * 1024),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename={path.split('/')[-1]}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"文件不存在: {str(e)}")


@router.get("/list")
async def list_documents(
    category: Optional[str] = Query(None, description="文档分类"),
    file_type: Optional[str] = Query(None, description="文件类型"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取文档列表
    """
    try:
        client = get_minio_client()

        # 列出所有文件
        objects = client.list_objects(BUCKET_NAME, recursive=True)

        documents = []
        for obj in objects:
            # 解析文件信息
            object_name = obj.object_name
            extension = get_file_extension(object_name)
            file_type_detected = get_file_type(extension)

            # 应用过滤条件
            if file_type and file_type_detected != file_type:
                continue

            # 生成文档信息
            file_id = object_name.split("/")[-1].split(".")[0]
            documents.append({
                "id": file_id,
                "name": f"文档_{file_id[:8]}.{extension}",
                "size": obj.size,
                "type": file_type_detected,
                "extension": extension,
                "url": f"/api/document/file/{object_name}",
                "object_name": object_name,
                "created_at": obj.last_modified.isoformat() if obj.last_modified else "",
                "updated_at": obj.last_modified.isoformat() if obj.last_modified else ""
            })

        # 排序（按时间倒序）
        documents.sort(key=lambda x: x["updated_at"], reverse=True)

        # 分页
        total = len(documents)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_docs = documents[start:end]

        return {
            "success": True,
            "data": paginated_docs,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.delete("/{object_name:path}")
async def delete_document(object_name: str):
    """
    删除文档
    """
    try:
        client = get_minio_client()
        client.remove_object(BUCKET_NAME, object_name)

        return {"success": True, "message": "文档已删除"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/categories")
async def get_categories():
    """
    获取文档分类列表
    """
    # 返回预设的分类
    categories = [
        {"name": "巡检报告", "icon": "Document", "color": "#409eff"},
        {"name": "设备文档", "icon": "Setting", "color": "#67c23a"},
        {"name": "规章制度", "icon": "Document", "color": "#e6a23c"},
        {"name": "培训资料", "icon": "Document", "color": "#f56c6c"},
        {"name": "其他", "icon": "Document", "color": "#909399"},
    ]
    return {"success": True, "data": categories}


@router.get("/stats")
async def get_stats():
    """
    获取文档统计信息
    """
    try:
        client = get_minio_client()

        # 统计文件数量和大小
        objects = client.list_objects(BUCKET_NAME, recursive=True)
        total_count = 0
        total_size = 0
        type_stats = {}

        for obj in objects:
            total_count += 1
            total_size += obj.size or 0

            extension = get_file_extension(obj.object_name)
            file_type = get_file_type(extension)
            type_stats[file_type] = type_stats.get(file_type, 0) + 1

        return {
            "success": True,
            "data": {
                "total_count": total_count,
                "total_size": total_size,
                "type_stats": type_stats
            }
        }

    except Exception as e:
        return {
            "success": True,
            "data": {
                "total_count": 0,
                "total_size": 0,
                "type_stats": {}
            }
        }


@router.get("/health")
async def health_check():
    """
    文档服务健康检查
    """
    try:
        client = get_minio_client()
        # 尝试列出存储桶
        buckets = client.list_buckets()
        return {
            "status": "healthy",
            "minio_endpoint": settings.MINIO_ENDPOINT,
            "bucket": BUCKET_NAME
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
