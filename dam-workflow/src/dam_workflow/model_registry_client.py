# -*- coding: utf-8 -*-
"""模型库推理接口客户端

提供模型推理调用和模型名称动态获取功能。
模型信息查询（list/get/io_schema）通过 SQLAlchemy 直接查库，不走 HTTP。
"""
import logging
from typing import Dict, Optional
from functools import lru_cache
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class ModelRegistryClient:
    """模型库推理 API 客户端"""

    def __init__(self, base_url: str = None, timeout: float = 60.0):
        self.base_url = (base_url or settings.model_registry_api_base).rstrip("/")
        self.timeout = timeout
        self._model_name_cache: Dict[int, str] = {}  # model_id -> vLLM model name

    def get_model_name(self, model_id: int) -> str:
        """动态获取模型的 vLLM served-model-name

        通过调用容器的 /v1/models 接口获取实际的模型名称。

        Args:
            model_id: 模型 ID

        Returns:
            vLLM 模型名称

        Raises:
            RuntimeError: 无法获取模型名称
        """
        # 检查缓存
        if model_id in self._model_name_cache:
            return self._model_name_cache[model_id]

        # 1. 从模型库获取模型信息（含推理地址）
        try:
            response = httpx.get(
                f"{self.base_url}/api/model-registry/{model_id}",
                timeout=10,
            )
            response.raise_for_status()
            model_info = response.json().get("data", {})
        except Exception as e:
            raise RuntimeError(f"无法获取模型 {model_id} 信息: {e}") from e

        binding = model_info.get("binding", {})
        host_ip = binding.get("host_ip", "127.0.0.1")
        host_port = binding.get("host_port")

        if not host_port:
            raise RuntimeError(f"模型 {model_id} 未配置宿主机端口")

        # 2. 调用容器的 /v1/models 接口获取模型名称
        try:
            models_url = f"http://{host_ip}:{host_port}/v1/models"
            response = httpx.get(models_url, timeout=10)
            response.raise_for_status()
            models_data = response.json()

            data = models_data.get("data", [])
            if not data:
                raise RuntimeError(f"模型 {model_id} 的容器返回空模型列表")

            model_name = data[0].get("id")
            if not model_name:
                raise RuntimeError(f"模型 {model_id} 的容器返回的模型缺少 id 字段")

            # 缓存结果
            self._model_name_cache[model_id] = model_name
            logger.info("获取模型 %d 的 vLLM 名称: %s", model_id, model_name)
            return model_name

        except Exception as e:
            raise RuntimeError(f"无法获取模型 {model_id} 的 vLLM 名称: {e}") from e

    def infer(self, model_id: int, request_data: Dict, model_name: str = None) -> Dict:
        """调用模型推理

        Args:
            model_id: 模型 ID
            request_data: 推理请求数据（支持两种格式）：
                - chat 格式：{"messages": [...], "max_tokens": 100}
                - prompt 格式：{"prompt": "...", "max_tokens": 100}（自动转换为 messages 格式）
            model_name: vLLM 模型名称（served-model-name），如果不提供则自动获取

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

        # 自动获取并添加 model 参数
        if "model" not in payload:
            if not model_name:
                model_name = self.get_model_name(model_id)
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
