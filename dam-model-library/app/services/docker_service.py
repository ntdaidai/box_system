"""Docker 服务封装

封装所有 Docker 操作，提供统一的容器管理接口。
"""

from typing import Optional
import docker
from docker.errors import NotFound, APIError
from loguru import logger


class DockerService:
    """Docker 服务"""

    def __init__(self):
        self.client = docker.from_env()

    def check_connection(self) -> str:
        """检查 Docker daemon 连接状态"""
        try:
            self.client.ping()
            return "ok"
        except Exception as e:
            logger.warning(f"Docker 连接失败: {e}")
            return f"error: {str(e)}"

    def list_containers(self, all: bool = False) -> list[dict]:
        """列出容器

        Args:
            all: 是否包含已停止的容器
        """
        containers = self.client.containers.list(all=all)
        return [
            {
                "id": c.id[:12],
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else str(c.image.id[:12]),
            }
            for c in containers
        ]

    def inspect_container(self, container_id: str) -> dict:
        """查询容器详情"""
        try:
            container = self.client.containers.get(container_id)
            return {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else str(container.image.id),
                "started_at": container.attrs["State"].get("StartedAt"),
                "created_at": container.attrs.get("Created"),
            }
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")

    def start_container(self, container_id: str) -> None:
        """启动已有容器"""
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"容器已启动: {container_id}")
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")
        except APIError as e:
            raise ValueError(f"启动容器失败: {e}")

    def stop_container(self, container_id: str, timeout: int = 30) -> None:
        """停止容器（不删除）"""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"容器已停止: {container_id}")
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")
        except APIError as e:
            raise ValueError(f"停止容器失败: {e}")

    def create_and_start_container(
        self,
        image_name: str,
        container_name: str,
        host_port: int,
        container_port: int,
        gpu_device: Optional[str] = None,
        extra_mounts: Optional[list[dict]] = None,
        extra_env: Optional[dict] = None,
    ) -> str:
        """创建并启动容器，返回容器 ID"""
        # 端口映射
        ports = {f"{container_port}/tcp": host_port}

        # 挂载卷
        volumes = {}
        if extra_mounts:
            for m in extra_mounts:
                volumes[m["host"]] = {"bind": m["container"], "mode": "rw"}

        # 环境变量
        environment = extra_env or {}

        # GPU 设备请求
        device_requests = None
        if gpu_device and gpu_device.strip():
            device_requests = [
                docker.types.DeviceRequest(
                    device_ids=[g.strip() for g in gpu_device.split(",") if g.strip()],
                    capabilities=[["gpu"]]
                )
            ]

        try:
            container = self.client.containers.run(
                image=image_name,
                name=container_name,
                detach=True,
                ports=ports,
                volumes=volumes,
                environment=environment,
                device_requests=device_requests,
            )
            logger.info(f"容器已创建并启动: {container.name} ({container.id[:12]})")
            return container.id
        except APIError as e:
            raise ValueError(f"创建容器失败: {e}")

    def remove_container(self, container_id: str) -> None:
        """强制删除容器"""
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            logger.info(f"容器已删除: {container_id}")
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")
        except APIError as e:
            raise ValueError(f"删除容器失败: {e}")

    def get_container_logs(self, container_id: str, tail: int = 100, follow: bool = False):
        """获取容器日志

        Args:
            container_id: 容器 ID
            tail: 返回最后多少行
            follow: 是否流式返回

        Returns:
            follow=False 时返回字符串，follow=True 时返回生成器
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, follow=follow, stream=follow, timestamps=True)
            if follow:
                return logs
            return logs.decode("utf-8", errors="replace")
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")

    def get_container_stats(self, container_id: str) -> dict:
        """获取容器资源使用快照"""
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)

            # 解析 CPU
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            num_cpus = stats["cpu_stats"]["online_cpus"]
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0

            # 解析内存
            mem_usage = stats["memory_stats"]["usage"]
            mem_limit = stats["memory_stats"]["limit"]
            mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage_bytes": mem_usage,
                "memory_limit_bytes": mem_limit,
                "memory_percent": round(mem_percent, 2),
            }
        except NotFound:
            raise ValueError(f"容器不存在: {container_id}")

    def is_container_running(self, container_id: str) -> bool:
        """检查容器是否在运行"""
        try:
            info = self.inspect_container(container_id)
            return info["status"] == "running"
        except (NotFound, ValueError):
            return False


# 全局单例
docker_service = DockerService()


# 兼容旧的 check_docker_connection 函数
def check_docker_connection() -> str:
    return docker_service.check_connection()
