"""
MinIO 对象存储服务

功能：
1. 上传图片到 MinIO
2. 获取图片的访问 URL
3. 生成预签名 URL（临时访问）
"""

import io
import uuid
from datetime import timedelta
from typing import Optional
from loguru import logger

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class MinioService:
    """MinIO 对象存储服务"""

    def __init__(self):
        self.client: Optional[Minio] = None
        self.bucket_name = "dam"

    def connect(self):
        """连接 MinIO"""
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
        filename: str = None
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
            from datetime import datetime

            # 生成文件路径：{日期}/{UUID}.{ext}
            ext = content_type.split("/")[-1]
            date_str = datetime.now().strftime("%Y-%m-%d")

            if not filename:
                filename = f"{uuid.uuid4().hex}.{ext}"

            object_name = f"{date_str}/{filename}"

            # 上传文件
            data_stream = io.BytesIO(image_data)
            self.client.put_object(
                self.bucket_name,
                object_name,
                data_stream,
                len(image_data),
                content_type=content_type,
            )

            # 生成访问 URL
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
            logger.info(f"图片上传成功: {object_name}")
            return url

        except S3Error as e:
            logger.error(f"MinIO 上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"图片上传异常: {e}")
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
