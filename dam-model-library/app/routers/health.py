from fastapi import APIRouter
from sqlalchemy import text
from app.services.docker_service import check_docker_connection
from app.database import engine
from loguru import logger

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查 — 验证服务、MySQL、Docker 连通性"""
    result = {
        "service": "ok",
        "mysql": "unknown",
        "docker": "unknown",
    }

    # 检查 MySQL 连接
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["mysql"] = "ok"
    except Exception as e:
        result["mysql"] = f"error: {str(e)}"
        logger.warning(f"MySQL 连接检查失败: {e}")

    # 检查 Docker 连接
    result["docker"] = check_docker_connection()

    return {"code": 200, "data": result}
