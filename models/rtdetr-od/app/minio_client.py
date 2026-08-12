"""MinIO 客户端模块。"""

import tempfile
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from cp.service.rtdetr.app.config import MinIOConfig


class MinIOClient:
    """MinIO 客户端封装。"""

    def __init__(self, config: MinIOConfig):
        self.config = config
        self.client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )

    def download_file(self, bucket: str, object_key: str, suffix: str = "") -> Path:
        """从 MinIO 下载文件到临时路径。"""

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = Path(temp_file.name)
        temp_file.close()

        try:
            self.client.fget_object(bucket, object_key, str(temp_path))
            return temp_path
        except S3Error as exc:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"MinIO 下载失败: {exc}")

    def file_exists(self, bucket: str, object_key: str) -> bool:
        """检查文件是否存在。"""

        try:
            self.client.stat_object(bucket, object_key)
            return True
        except S3Error:
            return False

    def cleanup_temp_file(self, file_path: Path) -> None:
        """清理临时文件。"""

        file_path.unlink(missing_ok=True)
