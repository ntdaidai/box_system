"""
OnlyOffice 文档编辑器 API 集成
提供文档上传、下载、回调处理等功能
"""

import os
import json
import hashlib
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/onlyoffice", tags=["OnlyOffice 文档编辑"])

# 配置
ONLYOFFICE_SERVER_URL = os.getenv("ONLYOFFICE_SERVER_URL", "http://localhost:8080")
DOCUMENT_STORAGE_PATH = os.getenv("DOCUMENT_STORAGE_PATH", "/var/www/onlyoffice/Data")
JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "mysecretkey")

# 确保存储目录存在
os.makedirs(DOCUMENT_STORAGE_PATH, exist_ok=True)


# ========== 数据模型 ==========

class DocumentInfo(BaseModel):
    """文档信息"""
    document_id: str
    title: str
    url: str
    file_type: str
    file_size: int
    created_at: str
    updated_at: str
    owner_id: str


class CallbackData(BaseModel):
    """OnlyOffice 回调数据"""
    key: str
    status: int
    url: Optional[str] = None
    changesurl: Optional[str] = None
    history: Optional[dict] = None
    users: Optional[list] = None
    actions: Optional[list] = None
    token: Optional[str] = None


class EditorConfig(BaseModel):
    """编辑器配置请求"""
    document_url: str
    document_title: str = "未命名文档"
    document_type: str = "word"
    mode: str = "edit"
    user_id: str = "user_001"
    user_name: str = "用户"
    callback_url: Optional[str] = None


# ========== 工具函数 ==========

def generate_document_key(file_path: str) -> str:
    """
    生成文档的唯一 key
    用于 OnlyOffice 协同编辑识别同一文档
    """
    # 使用文件路径 + 修改时间生成唯一 key
    stat = os.stat(file_path)
    unique_str = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
    return hashlib.md5(unique_str.encode()).hexdigest()


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lstrip(".").lower()


def get_document_type(file_extension: str) -> str:
    """根据文件扩展名获取文档类型"""
    type_map = {
        "docx": "word", "doc": "word", "odt": "word", "rtf": "word", "txt": "word",
        "xlsx": "cell", "xls": "cell", "ods": "cell", "csv": "cell",
        "pptx": "slide", "ppt": "slide", "odp": "slide",
        "pdf": "word"
    }
    return type_map.get(file_extension, "word")


def get_content_type(file_extension: str) -> str:
    """获取文件的 MIME 类型"""
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
        "txt": "text/plain"
    }
    return content_types.get(file_extension, "application/octet-stream")


# ========== API 路由 ==========

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("user_001"),
    user_name: str = Form("用户")
):
    """
    上传文档到 OnlyOffice 存储

    返回文档 ID 和访问 URL
    """
    try:
        # 验证文件类型
        ext = get_file_extension(file.filename)
        allowed_extensions = [
            "docx", "doc", "odt", "rtf", "txt", "html",
            "xlsx", "xls", "ods", "csv",
            "pptx", "ppt", "odp",
            "pdf"
        ]

        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {ext}。支持的类型: {', '.join(allowed_extensions)}"
            )

        # 生成文档 ID
        timestamp = int(time.time() * 1000)
        document_id = f"doc_{user_id}_{timestamp}"

        # 创建用户目录
        user_dir = os.path.join(DOCUMENT_STORAGE_PATH, user_id)
        os.makedirs(user_dir, exist_ok=True)

        # 保存文件
        file_path = os.path.join(user_dir, f"{document_id}.{ext}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 生成文档 key
        document_key = generate_document_key(file_path)

        # 构建文档访问 URL
        # 注意：这里需要根据实际部署情况调整
        # 生产环境应该使用 Nginx 反向代理
        document_url = f"http://localhost:8090/api/onlyoffice/document/{document_id}"

        # 返回文档信息
        return {
            "success": True,
            "data": {
                "document_id": document_id,
                "document_key": document_key,
                "title": file.filename,
                "url": document_url,
                "file_type": ext,
                "file_size": len(content),
                "document_type": get_document_type(ext),
                "created_at": datetime.now().isoformat(),
                "owner_id": user_id,
                "owner_name": user_name
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/document/{document_id}")
async def get_document(document_id: str):
    """
    获取文档文件（供 OnlyOffice Server 读取）

    OnlyOffice Server 会通过此接口下载文档进行编辑
    """
    try:
        # 在存储目录中查找文档
        for user_dir in os.listdir(DOCUMENT_STORAGE_PATH):
            user_path = os.path.join(DOCUMENT_STORAGE_PATH, user_dir)
            if not os.path.isdir(user_path):
                continue

            # 查找匹配的文档文件
            for filename in os.listdir(user_path):
                if filename.startswith(document_id):
                    file_path = os.path.join(user_path, filename)
                    ext = get_file_extension(filename)
                    content_type = get_content_type(ext)

                    return FileResponse(
                        path=file_path,
                        media_type=content_type,
                        filename=filename
                    )

        raise HTTPException(status_code=404, detail="文档不存在")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档失败: {str(e)}")


@router.post("/callback")
async def document_callback(callback_data: CallbackData):
    """
    处理 OnlyOffice 文档编辑回调

    OnlyOffice Server 在文档状态变化时会调用此接口
    状态码说明：
    - 0: 正在编辑
    - 1: 文档已保存
    - 2: 文档保存错误
    - 3: 文档关闭
    - 4: 正在协同编辑
    - 6: 正在编辑（强制保存后）
    - 7: 文档已保存（强制保存后）
    """
    try:
        status = callback_data.status
        document_key = callback_data.key

        print(f"[OnlyOffice 回调] 文档: {document_key}, 状态: {status}")

        if status == 1 or status == 7:
            # 文档已保存，下载最新版本
            if callback_data.url:
                # 从 OnlyOffice Server 下载更新后的文档
                await download_updated_document(document_key, callback_data.url)
                print(f"[OnlyOffice 回调] 文档 {document_key} 已更新")

        elif status == 2:
            # 文档保存错误
            print(f"[OnlyOffice 回调] 文档 {document_key} 保存错误")

        elif status == 3:
            # 文档关闭
            print(f"[OnlyOffice 回调] 文档 {document_key} 已关闭")

        # 返回成功响应（必须返回 {"error": 0} 表示处理成功）
        return {"error": 0}

    except Exception as e:
        print(f"[OnlyOffice 回调] 处理失败: {str(e)}")
        return {"error": 1, "message": str(e)}


async def download_updated_document(document_key: str, url: str):
    """
    从 OnlyOffice Server 下载更新后的文档
    """
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                # 查找并更新文档文件
                for user_dir in os.listdir(DOCUMENT_STORAGE_PATH):
                    user_path = os.path.join(DOCUMENT_STORAGE_PATH, user_dir)
                    if not os.path.isdir(user_path):
                        continue

                    for filename in os.listdir(user_path):
                        file_path = os.path.join(user_path, filename)
                        # 通过 key 匹配文档
                        if generate_document_key(file_path) == document_key:
                            # 备份原文件
                            backup_path = f"{file_path}.bak"
                            if os.path.exists(file_path):
                                os.rename(file_path, backup_path)

                            # 保存新版本
                            with open(file_path, "wb") as f:
                                f.write(response.content)

                            print(f"[OnlyOffice] 文档已更新: {file_path}")
                            return True

        return False

    except Exception as e:
        print(f"[OnlyOffice] 下载更新文档失败: {str(e)}")
        return False


@router.get("/editor-config/{document_id}")
async def get_editor_config(
    document_id: str,
    user_id: str = "user_001",
    user_name: str = "用户",
    mode: str = "edit"
):
    """
    获取 OnlyOffice 编辑器配置

    前端调用此接口获取初始化编辑器所需的配置
    """
    try:
        # 查找文档
        document_path = None
        for user_dir in os.listdir(DOCUMENT_STORAGE_PATH):
            user_path = os.path.join(DOCUMENT_STORAGE_PATH, user_dir)
            if not os.path.isdir(user_path):
                continue

            for filename in os.listdir(user_path):
                if filename.startswith(document_id):
                    document_path = os.path.join(user_path, filename)
                    break

        if not document_path:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 获取文档信息
        filename = os.path.basename(document_path)
        ext = get_file_extension(filename)
        document_key = generate_document_key(document_path)
        document_type = get_document_type(ext)

        # 构建文档 URL（供 OnlyOffice Server 访问）
        document_url = f"http://localhost:8090/api/onlyoffice/document/{document_id}"

        # 构建回调 URL
        callback_url = f"http://localhost:8090/api/onlyoffice/callback"

        # 返回编辑器配置
        return {
            "success": True,
            "data": {
                "document": {
                    "fileType": ext,
                    "key": document_key,
                    "title": filename,
                    "url": document_url,
                    "permissions": {
                        "comment": mode == "edit",
                        "download": True,
                        "edit": mode == "edit",
                        "fillForms": mode == "edit",
                        "print": True,
                        "review": mode == "edit"
                    }
                },
                "documentType": document_type,
                "editorConfig": {
                    "callbackUrl": callback_url,
                    "lang": "zh-CN",
                    "mode": mode,
                    "user": {
                        "id": user_id,
                        "name": user_name
                    },
                    "customization": {
                        "forcesave": True,
                        "compactHeader": False,
                        "toolbarNoTabs": False,
                        "hideRightMenu": False,
                        "hideRulers": False,
                        "macros": False,
                        "plugins": True
                    }
                },
                "onlyoffice_server_url": ONLYOFFICE_SERVER_URL
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取编辑器配置失败: {str(e)}")


@router.delete("/document/{document_id}")
async def delete_document(
    document_id: str,
    user_id: str = "user_001"
):
    """
    删除文档
    """
    try:
        # 查找并删除文档
        for user_dir in os.listdir(DOCUMENT_STORAGE_PATH):
            user_path = os.path.join(DOCUMENT_STORAGE_PATH, user_dir)
            if not os.path.isdir(user_path):
                continue

            for filename in os.listdir(user_path):
                if filename.startswith(document_id):
                    file_path = os.path.join(user_path, filename)
                    os.remove(file_path)

                    # 同时删除备份文件
                    backup_path = f"{file_path}.bak"
                    if os.path.exists(backup_path):
                        os.remove(backup_path)

                    return {"success": True, "message": "文档已删除"}

        raise HTTPException(status_code=404, detail="文档不存在")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@router.get("/documents")
async def list_documents(
    user_id: str = "user_001",
    page: int = 1,
    page_size: int = 20
):
    """
    获取用户的文档列表
    """
    try:
        documents = []
        user_dir = os.path.join(DOCUMENT_STORAGE_PATH, user_id)

        if os.path.exists(user_dir):
            for filename in os.listdir(user_dir):
                if filename.endswith(".bak"):
                    continue

                file_path = os.path.join(user_dir, filename)
                stat = os.stat(file_path)
                ext = get_file_extension(filename)

                documents.append({
                    "document_id": filename.split(".")[0],
                    "title": filename,
                    "file_type": ext,
                    "file_size": stat.st_size,
                    "document_type": get_document_type(ext),
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # 按更新时间倒序排列
        documents.sort(key=lambda x: x["updated_at"], reverse=True)

        # 分页
        total = len(documents)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_docs = documents[start:end]

        return {
            "success": True,
            "data": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "documents": paginated_docs
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.get("/health")
async def health_check():
    """
    OnlyOffice 服务健康检查
    """
    import httpx

    try:
        # 检查 OnlyOffice Document Server 是否可达
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ONLYOFFICE_SERVER_URL}/healthcheck",
                timeout=5.0
            )

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "onlyoffice_server": ONLYOFFICE_SERVER_URL,
                    "document_server_status": "running",
                    "storage_path": DOCUMENT_STORAGE_PATH
                }
            else:
                return {
                    "status": "unhealthy",
                    "onlyoffice_server": ONLYOFFICE_SERVER_URL,
                    "document_server_status": "error",
                    "error": f"HTTP {response.status_code}"
                }

    except httpx.ConnectError:
        return {
            "status": "unhealthy",
            "onlyoffice_server": ONLYOFFICE_SERVER_URL,
            "document_server_status": "unreachable",
            "error": "无法连接到 OnlyOffice Document Server"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "onlyoffice_server": ONLYOFFICE_SERVER_URL,
            "document_server_status": "error",
            "error": str(e)
        }
