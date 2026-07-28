# -*- coding: utf-8 -*-
"""模型库推理接口客户端

仅保留 infer() 方法，用于通过模型库的 /api/model-registry/{id}/infer 接口调用大模型。
模型信息查询（list/get/io_schema）通过 SQLAlchemy 直接查库，不走 HTTP。
"""
import logging
from typing import Dict
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class ModelRegistryClient:
    """模型库推理 API 客户端"""

    def __init__(self, base_url: str = None, timeout: float = 60.0):
        self.base_url = (base_url or settings.model_registry_api_base).rstrip("/")
        self.timeout = timeout

    def infer(self, model_id: int, request_data: Dict, model_name: str = None) -> Dict:
        """调用模型推理

        Args:
            model_id: 模型 ID
            request_data: 推理请求数据（支持两种格式）：
                - chat 格式：{"messages": [...], "max_tokens": 100}
                - prompt 格式：{"prompt": "...", "max_tokens": 100}（自动转换为 messages 格式）
            model_name: vLLM 模型名称（served-model-name），如果提供则自动添加到请求中

        Returns:
            推理结果

        Raises:
            httpx.ConnectError: 模型库服务不可达
            httpx.TimeoutException: 请求超时
            httpx.HTTPStatusError: HTTP 错误状态码
        """
        url = f"{self.base_url}/api/model-registry/{model_id}/infer"

        # 构建请求数据
        payload = request_data.copy()

        # 自动添加 model 参数
        if model_name and "model" not in payload:
            payload["model"] = model_name

        # 自动将 prompt 格式转换为 messages 格式
        if "prompt" in payload and "messages" not in payload:
            prompt = payload.pop("prompt")
            payload["messages"] = [{"role": "user", "content": prompt}]

        try:
            response = httpx.post(
                url,
                json={"request_data": payload},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            logger.error("模型库服务不可达: %s", url)
            raise
        except httpx.TimeoutException:
            logger.error("模型库推理请求超时: %s (timeout=%ss)", url, self.timeout)
            raise
        except httpx.HTTPStatusError as e:
            logger.error("模型库推理请求失败: %s -> %s", url, e.response.status_code)
            raise


# 全局客户端实例
model_registry_client = ModelRegistryClient()
