"""Docker 测试接口（阶段 2 验证用）"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from app.services.docker_service import docker_service
from app.schemas.common import Result

router = APIRouter()


class BuildImageRequest(BaseModel):
    """镜像构建请求"""

    context_path: str = Field(..., min_length=1, description="Docker build 上下文目录")
    image_name: str = Field(..., min_length=1, max_length=256, description="目标镜像名")


@router.get("/containers")
async def list_containers(all: bool = Query(False, description="是否包含已停止的容器")):
    """列出容器"""
    containers = docker_service.list_containers(all=all)
    return Result(code=200, data=containers)


@router.post("/images/build")
async def build_image(data: BuildImageRequest):
    """从本地目录构建镜像"""
    try:
        result = await run_in_threadpool(docker_service.build_image, data.context_path, data.image_name)
        return Result(code=200, message="镜像构建成功", data=result)
    except ValueError as e:
        return Result(code=400, message=str(e))


@router.get("/containers/{container_id}")
async def inspect_container(container_id: str):
    """查询容器详情"""
    try:
        info = docker_service.inspect_container(container_id)
        return Result(code=200, data=info)
    except ValueError as e:
        return Result(code=404, message=str(e))


@router.get("/containers/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = Query(100, description="返回最后多少行")):
    """获取容器日志"""
    try:
        logs = docker_service.get_container_logs(container_id, tail=tail)
        return Result(code=200, data={"logs": logs})
    except ValueError as e:
        return Result(code=404, message=str(e))


@router.get("/containers/{container_id}/stats")
async def get_container_stats(container_id: str):
    """获取容器资源使用"""
    try:
        stats = docker_service.get_container_stats(container_id)
        return Result(code=200, data=stats)
    except ValueError as e:
        return Result(code=404, message=str(e))
