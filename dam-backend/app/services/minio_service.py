"""
MinIO 对象存储服务

功能：
1. 上传图片到 MinIO
2. 获取图片的访问 URL
3. 生成预签名 URL（临时访问）
"""

import io
import mimetypes
import uuid
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Optional
try:
    from loguru import logger
except ImportError:  # pragma: no cover - standalone tests may not install app deps.
    import logging

    logger = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:  # pragma: no cover - MinIO is optional outside deployment.
    Minio = None

    class S3Error(Exception):
        pass

from app.core.config import settings


class MinioService:
    """MinIO 对象存储服务"""

    def __init__(self):
        self.client: Optional[Minio] = None
        self.bucket_name = "dam"

    def connect(self):
        """连接 MinIO"""
        if Minio is None:
            logger.warning("MinIO 依赖未安装，文件上传功能将不可用")
            self.client = None
            return
        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )

            # 创建桶（如果不存在）
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建 MinIO 桶: {self.bucket_name}")
            else:
                logger.info(f"MinIO 桶已存在: {self.bucket_name}")

            logger.info(f"MinIO 连接成功: {settings.MINIO_ENDPOINT}")

        except Exception as e:
            logger.error(f"MinIO 连接失败: {e}")
            self.client = None

    def upload_image(
        self,
        image_data: bytes,
        content_type: str = "image/jpeg",
        filename: str = None,
        folder: str = "",
    ) -> Optional[str]:
        """
        上传图片到 MinIO

        目录结构：{日期}/{文件名}
        例如：2026-07-09/abc123.jpg

        Args:
            image_data: 图片数据
            content_type: 图片类型
            filename: 文件名（可选，不提供则自动生成）

        Returns:
            Optional[str]: 图片的访问 URL，失败返回 None
        """
        if not self.client:
            logger.error("MinIO 未连接")
            return None

        try:
            # 生成文件路径：{日期}/{UUID}.{ext}
            ext = content_type.split("/")[-1]
            date_str = datetime.now().strftime("%Y-%m-%d")

            if not filename:
                filename = f"{uuid.uuid4().hex}.{ext}"

            object_name = f"{date_str}/{filename}"
            if folder:
                object_name = f"{folder.strip('/')}/{object_name}"

            return self.upload_bytes(
                image_data,
                object_name=object_name,
                content_type=content_type,
            )

        except S3Error as e:
            logger.error(f"MinIO 上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"图片上传异常: {e}")
            return None

    def upload_bytes(
        self,
        data: bytes,
        *,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """上传字节数据到指定对象路径."""
        if not self.client:
            logger.error("MinIO 未连接")
            return None
        try:
            clean_name = object_name.strip("/")
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket_name,
                clean_name,
                data_stream,
                len(data),
                content_type=content_type,
            )
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{clean_name}"
            logger.info(f"文件上传成功: {clean_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO 上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"文件上传异常: {e}")
            return None

    def upload_file(
        self,
        file_path: str,
        *,
        object_name: str,
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """上传本地文件到指定对象路径，适合视频等大文件."""
        if not self.client:
            logger.error("MinIO 未连接")
            return None
        try:
            path = Path(file_path)
            guessed = mimetypes.guess_type(path.name)[0]
            final_content_type = content_type or guessed or "application/octet-stream"
            clean_name = object_name.strip("/")
            with path.open("rb") as data_stream:
                self.client.put_object(
                    self.bucket_name,
                    clean_name,
                    data_stream,
                    path.stat().st_size,
                    content_type=final_content_type,
                )
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{clean_name}"
            logger.info(f"文件上传成功: {clean_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO 上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"文件上传异常: {e}")
            return None

    def get_presigned_url(self, filename: str, expires: timedelta = timedelta(hours=1)) -> Optional[str]:
        """
        获取预签名 URL（临时访问）

        Args:
            filename: 文件名
            expires: 过期时间

        Returns:
            Optional[str]: 预签名 URL
        """
        if not self.client:
            logger.error("MinIO 未连接")
            return None

        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                filename,
                expires=expires,
            )
            return url
        except Exception as e:
            logger.error(f"生成预签名 URL 失败: {e}")
            return None

    def delete_image(self, filename: str) -> bool:
        """
        删除图片

        Args:
            filename: 文件名

        Returns:
            bool: 是否成功
        """
        if not self.client:
            logger.error("MinIO 未连接")
            return False

        try:
            self.client.remove_object(self.bucket_name, filename)
            logger.info(f"图片已删除: {filename}")
            return True
        except Exception as e:
            logger.error(f"删除图片失败: {e}")
            return False

    def list_images(self, prefix: str = "") -> list:
        """
        列出图片

        Args:
            prefix: 前缀过滤

        Returns:
            list: 文件名列表
        """
        if not self.client:
            logger.error("MinIO 未连接")
            return []

        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True,
            )
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"列出图片失败: {e}")
            return []


# 全局单例
minio_service = MinioService()
