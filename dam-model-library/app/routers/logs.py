"""容器日志接口"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_deploy_binding import ModelDeployBinding
from app.models.model_registry import ModelRegistry
from app.schemas.common import Result
from app.services.docker_service import docker_service

router = APIRouter()


@router.get("/{model_id}/logs")
async def get_logs(
    model_id: int,
    tail: int = Query(100, description="返回最后多少行"),
    follow: bool = Query(False, description="是否流式推送"),
    db: Session = Depends(get_db),
):
    """获取容器日志

    - tail: 返回最后多少行（默认100）
    - follow: true 时返回 SSE 流式推送
    """
    # 查询绑定
    binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
    if not binding or not binding.container_id:
        return Result(code=404, message="模型未绑定容器")

    # 查询模型
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        return Result(code=404, message="模型不存在")

    try:
        if follow:
            # SSE 流式推送
            log_generator = docker_service.get_container_logs(
                binding.container_id, tail=tail, follow=True
            )

            async def event_generator():
                try:
                    for line in log_generator:
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")
                        yield {"data": line.strip()}
                except Exception as e:
                    yield {"data": f"[日志流断开: {str(e)}]"}

            return EventSourceResponse(event_generator())
        else:
            # 一次性返回
            logs = docker_service.get_container_logs(
                binding.container_id, tail=tail, follow=False
            )
            return Result(code=200, data={"logs": logs})

    except ValueError as e:
        return Result(code=404, message=str(e))
    except Exception as e:
        return Result(code=500, message=f"获取日志失败: {str(e)}")
