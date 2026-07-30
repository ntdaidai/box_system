"""
边缘侧本地大模型推理接口

功能：
1. 调用本地 Qwen-VL-4B 模型进行多模态场景理解
2. 将关键数据同步至 A100 MinIO
3. 输出标准化任务 JSON，作为 cloud-inference 节点输入
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.local_inference_service import (
    local_inference_service,
    LocalInferenceRequest,
    LocalInferenceResponse,
)

router = APIRouter()


@router.post(
    "/",
    response_model=LocalInferenceResponse,
    summary="边缘侧本地大模型推理",
    description="调用本地 Qwen-VL-4B 模型进行多模态场景理解推理，并将关键数据同步至 A100 MinIO"
)
async def local_inference(request: LocalInferenceRequest):
    """
    边缘侧本地大模型推理接口

    作为工作流中的核心推理节点，执行以下步骤：
    1. 从 AGX MinIO 读取输入数据（图像/视频）
    2. 调用本地 Qwen-VL-4B 模型进行场景理解
    3. 筛选云端增强所需数据
    4. 上传关键数据至 A100 MinIO
    5. 返回标准化任务 JSON，作为 cloud-inference 节点输入

    Args:
        request: 本地推理请求

    Returns:
        LocalInferenceResponse: 本地推理响应，包含：
        - task_id: 任务编号
        - minio_context: A100 MinIO 数据位置
        - specialized_model_result: 专有模型检测结果
        - sensor_data: 环境感知数据
        - local_llm_result: 本地 Qwen4B 分析结果
        - cloud_task: 云端增强任务描述
    """
    try:
        logger.info(
            f"收到本地推理请求: task_id={request.task_id}, "
            f"task_type={request.task_type}, "
            f"device={request.device_context.device_id}"
        )

        # 参数校验
        if not request.input_data.image_objects and not request.input_data.video_objects:
            raise HTTPException(
                status_code=400,
                detail="输入数据不能为空，至少需要一个图像或视频对象"
            )

        # 执行推理
        result = await local_inference_service.inference(request)

        # 检查结果状态
        if result.status == "error":
            logger.error(f"本地推理失败: {result.error_message}")
            raise HTTPException(
                status_code=500,
                detail=result.error_message
            )

        logger.info(
            f"本地推理成功: task_id={request.task_id}, "
            f"risk_level={result.local_llm_result.risk_level if result.local_llm_result else 'N/A'}, "
            f"cloud_enhancement={result.cloud_task.need_enhancement if result.cloud_task else False}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"本地推理异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    summary="健康检查",
    description="检查本地推理服务和依赖服务的健康状态"
)
async def health_check():
    """
    健康检查接口

    检查：
    1. 本地推理服务是否正常
    2. vLLM 服务是否可达
    3. AGX MinIO 是否可达
    4. A100 MinIO 是否可达
    """
    try:
        import httpx
        from app.core.config import settings

        health_status = {
            "service": "local-inference",
            "status": "healthy",
            "dependencies": {}
        }

        # 检查 vLLM 服务
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.LOCAL_LLM_URL}/health")
                health_status["dependencies"]["vllm"] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": settings.LOCAL_LLM_URL,
                }
        except Exception as e:
            health_status["dependencies"]["vllm"] = {
                "status": "unreachable",
                "url": settings.LOCAL_LLM_URL,
                "error": str(e),
            }

        # 检查 AGX MinIO
        try:
            from minio import Minio
            agx_minio = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            agx_minio.list_buckets()
            health_status["dependencies"]["agx_minio"] = {
                "status": "healthy",
                "endpoint": settings.MINIO_ENDPOINT,
            }
        except Exception as e:
            health_status["dependencies"]["agx_minio"] = {
                "status": "unreachable",
                "endpoint": settings.MINIO_ENDPOINT,
                "error": str(e),
            }

        # 检查 A100 MinIO
        try:
            from minio import Minio
            a100_minio = Minio(
                settings.A100_MINIO_ENDPOINT,
                access_key=settings.A100_MINIO_ACCESS_KEY,
                secret_key=settings.A100_MINIO_SECRET_KEY,
                secure=settings.A100_MINIO_SECURE,
            )
            a100_minio.list_buckets()
            health_status["dependencies"]["a100_minio"] = {
                "status": "healthy",
                "endpoint": settings.A100_MINIO_ENDPOINT,
            }
        except Exception as e:
            health_status["dependencies"]["a100_minio"] = {
                "status": "unreachable",
                "endpoint": settings.A100_MINIO_ENDPOINT,
                "error": str(e),
            }

        # 判断整体状态
        unhealthy_deps = [
            k for k, v in health_status["dependencies"].items()
            if v["status"] != "healthy"
        ]
        if unhealthy_deps:
            health_status["status"] = "degraded"
            health_status["unhealthy_dependencies"] = unhealthy_deps

        return health_status

    except Exception as e:
        logger.error(f"健康检查异常: {e}")
        return {
            "service": "local-inference",
            "status": "unhealthy",
            "error": str(e),
        }
