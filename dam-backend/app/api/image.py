"""
图片上传 API

功能：
1. 上传图片到 MinIO
2. 获取图片访问 URL
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from app.core.security import require_auth
from app.models.user import User
from app.services.minio_service import minio_service

router = APIRouter()


class UploadResponse(BaseModel):
    code: int
    data: Optional[dict] = None
    message: Optional[str] = None


@router.post("/upload", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    _user: User = Depends(require_auth),
):
    """
    上传图片到 MinIO

    返回图片的访问 URL，可用于 ECA 流程中的 image_url 参数。
    """
    # 验证文件类型
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.content_type}，支持: {', '.join(allowed_types)}"
        )

    # 验证文件大小（最大 10MB）
    max_size = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制: {len(content)} > {max_size}"
        )

    # 上传到 MinIO
    url = minio_service.upload_image(
        image_data=content,
        content_type=file.content_type,
        filename=file.filename,
    )

    if not url:
        raise HTTPException(status_code=500, detail="图片上传失败")

    return UploadResponse(
        code=200,
        data={
            "url": url,
            "filename": file.filename,
            "size": len(content),
        },
        message="图片上传成功"
    )


@router.post("/upload/base64", response_model=UploadResponse)
async def upload_image_base64(
    request: dict,
    _user: User = Depends(require_auth),
):
    """
    上传 base64 编码的图片

    请求格式：
    {
        "image": "base64编码的图片数据",
        "filename": "可选的文件名"
    }
    """
    import base64

    image_data = request.get("image")
    filename = request.get("filename")

    if not image_data:
        raise HTTPException(status_code=400, detail="缺少图片数据")

    try:
        # 解码 base64
        if "," in image_data:
            # 处理 data:image/jpeg;base64,... 格式
            image_data = image_data.split(",")[1]

        content = base64.b64decode(image_data)

        # 推断 content_type
        content_type = "image/jpeg"
        if filename and filename.endswith(".png"):
            content_type = "image/png"
        elif filename and filename.endswith(".gif"):
            content_type = "image/gif"
        elif filename and filename.endswith(".webp"):
            content_type = "image/webp"

        # 上传到 MinIO
        url = minio_service.upload_image(
            image_data=content,
            content_type=content_type,
            filename=filename,
        )

        if not url:
            raise HTTPException(status_code=500, detail="图片上传失败")

        return UploadResponse(
            code=200,
            data={
                "url": url,
                "filename": filename,
                "size": len(content),
            },
            message="图片上传成功"
        )

    except Exception as e:
        logger.error(f"图片上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"图片上传失败: {str(e)}")


@router.get("/list")
async def list_images(
    prefix: str = "",
    _user: User = Depends(require_auth),
):
    """列出已上传的图片"""
    images = minio_service.list_images(prefix)
    return {"code": 200, "data": {"images": images}}
