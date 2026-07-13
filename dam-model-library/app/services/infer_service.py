"""推理服务

提供模型推理接口，支持：
1. 直接推理（容器必须已运行）
2. 一次性运行（自动启动→推理→停止）
3. 可选的输入校验（基于 IO Schema）
"""

import time
import httpx
from typing import Optional, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
from loguru import logger

from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.models.model_io_schema import ModelIOSchema
from app.services.docker_service import docker_service
from app.services.lifecycle_service import lifecycle_service


class InferService:
    """推理服务"""

    def __init__(self):
        self.client = httpx.Client(timeout=300.0)  # 5 分钟超时

    def infer(self, db: Session, model_id: int, request_data: dict, validate: bool = False) -> dict:
        """推理（容器必须已运行）

        Args:
            db: 数据库会话
            model_id: 模型 ID
            request_data: 推理请求数据
            validate: 是否校验输入

        Returns:
            推理结果
        """
        # 获取绑定信息
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="模型未绑定部署配置")

        # 获取模型信息
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 检查模型状态
        if model.runtime_status != "running":
            raise HTTPException(status_code=400, detail=f"模型未运行，当前状态: {model.runtime_status}")

        # 检查容器实际状态
        if not binding.container_id:
            raise HTTPException(status_code=400, detail="容器未创建")

        if not docker_service.is_container_running(binding.container_id):
            # 状态同步
            model.runtime_status = "stopped"
            db.commit()
            raise HTTPException(status_code=400, detail="容器已停止")

        # 校验输入（如果启用）
        if validate:
            request_data = self._validate_and_fill_defaults(db, model_id, request_data)

        # 构建推理 URL
        inference_url = f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path}"

        # 发送推理请求
        try:
            response = self.client.post(inference_url, json=request_data)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail="推理服务不可达")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"推理服务返回错误: {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")

    def run(self, db: Session, model_id: int, request_data: dict, wait_timeout: int = 120, validate: bool = False) -> dict:
        """一次性运行（自动启动→探活→推理→停止）

        Args:
            db: 数据库会话
            model_id: 模型 ID
            request_data: 推理请求数据
            wait_timeout: 等待服务就绪的超时时间（秒）
            validate: 是否校验输入

        Returns:
            推理结果 + 运行信息
        """
        # 获取绑定信息
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="模型未绑定部署配置")

        # 获取模型信息
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 校验输入（如果启用，在启动前校验，避免启动后才发现输入错误）
        if validate:
            request_data = self._validate_and_fill_defaults(db, model_id, request_data)

        auto_started = False
        start_time = None
        stop_time = None

        # 如果未运行，自动启动
        if model.runtime_status != "running":
            logger.info(f"模型 {model_id} 未运行，自动启动...")
            start_time = time.time()
            try:
                lifecycle_service.start_model(db, model_id)
                auto_started = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"自动启动失败: {str(e)}")

        # 探活：等待服务就绪
        logger.info(f"等待推理服务就绪...")
        if not self._wait_for_ready(binding, timeout=wait_timeout):
            # 启动失败，停止容器
            if auto_started:
                try:
                    lifecycle_service.stop_model(db, model_id)
                except Exception:
                    pass
            raise HTTPException(status_code=504, detail="模型启动超时，推理服务未就绪")

        # 执行推理
        inference_url = f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path}"
        try:
            response = self.client.post(inference_url, json=request_data)
            response.raise_for_status()
            inference_result = response.json()
        except httpx.ConnectError:
            if auto_started:
                try:
                    lifecycle_service.stop_model(db, model_id)
                except Exception:
                    pass
            raise HTTPException(status_code=502, detail="推理服务不可达")
        except httpx.HTTPStatusError as e:
            if auto_started:
                try:
                    lifecycle_service.stop_model(db, model_id)
                except Exception:
                    pass
            raise HTTPException(status_code=502, detail=f"推理服务返回错误: {e.response.status_code}")
        except Exception as e:
            if auto_started:
                try:
                    lifecycle_service.stop_model(db, model_id)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")

        # 如果是自动启动的，停止容器
        if auto_started:
            stop_time = time.time()
            logger.info(f"推理完成，停止容器...")
            try:
                lifecycle_service.stop_model(db, model_id)
            except Exception as e:
                logger.warning(f"停止容器失败: {e}")

        # 构建返回结果
        result = {
            "inference_result": inference_result,
            "runtime_info": {
                "auto_started": auto_started,
            }
        }

        if auto_started and start_time:
            result["runtime_info"]["start_time"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time))
            if stop_time:
                result["runtime_info"]["stop_time"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stop_time))
                result["runtime_info"]["duration_ms"] = int((stop_time - start_time) * 1000)

        return result

    def _wait_for_ready(self, binding: ModelDeployBinding, timeout: int = 120) -> bool:
        """探活：等待推理服务就绪

        Args:
            binding: 绑定信息
            timeout: 超时时间（秒）

        Returns:
            是否就绪
        """
        if not binding.health_check_url:
            # 没有配置健康检查，直接检查容器状态
            if binding.container_id:
                return docker_service.is_container_running(binding.container_id)
            return False

        health_url = f"http://{binding.host_ip}:{binding.host_port}{binding.health_check_url}"
        deadline = time.time() + timeout
        interval = 2  # 每 2 秒检查一次

        logger.info(f"探活: {health_url}")

        while time.time() < deadline:
            try:
                response = self.client.get(health_url, timeout=5)
                if response.status_code < 400:
                    logger.info(f"推理服务已就绪")
                    return True
            except Exception:
                pass

            time.sleep(interval)

        logger.warning(f"探活超时: {health_url}")
        return False

    def _validate_and_fill_defaults(self, db: Session, model_id: int, request_data: dict) -> dict:
        """校验输入并填充默认值

        Args:
            db: 数据库会话
            model_id: 模型 ID
            request_data: 原始请求数据

        Returns:
            处理后的请求数据

        Raises:
            HTTPException: 校验失败
        """
        # 获取 IO Schema
        schema = db.query(ModelIOSchema).filter(ModelIOSchema.model_id == model_id).first()
        if not schema:
            logger.warning(f"模型 {model_id} 未设置 IO Schema，跳过校验")
            return request_data

        inputs = schema.inputs or []
        result = request_data.copy()

        # 校验必填字段
        for field_def in inputs:
            field_name = field_def.get("field")
            required = field_def.get("required", True)
            default_value = field_def.get("defaultValue")

            if field_name not in result:
                if required and default_value is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"缺少必填字段: {field_name}"
                    )
                # 填充默认值
                if default_value is not None:
                    result[field_name] = default_value
                    logger.debug(f"填充默认值: {field_name} = {default_value}")

        # 校验字段类型（可选，基本类型检查）
        for field_def in inputs:
            field_name = field_def.get("field")
            field_type = field_def.get("type")

            if field_name not in result:
                continue

            value = result[field_name]

            # 基本类型校验
            if field_type == "integer" and not isinstance(value, int):
                try:
                    result[field_name] = int(value)
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"字段 {field_name} 必须是整数")

            elif field_type == "float" and not isinstance(value, (int, float)):
                try:
                    result[field_name] = float(value)
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"字段 {field_name} 必须是数字")

            elif field_type == "text" and not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"字段 {field_name} 必须是字符串")

            elif field_type == "json" and not isinstance(value, (dict, list)):
                raise HTTPException(status_code=400, detail=f"字段 {field_name} 必须是 JSON 对象或数组")

        logger.info(f"输入校验通过")
        return result


# 全局单例
infer_service = InferService()
