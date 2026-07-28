# -*- coding: utf-8 -*-
"""DAM 系统配置"""
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 模型库数据库
    model_registry_db_host: str = "192.168.31.52"
    model_registry_db_port: int = 3306
    model_registry_db_user: str = "root"
    model_registry_db_password: str = "root"
    model_registry_db_name: str = "dam_system"

    # 模型库 API
    model_registry_api_base: str = "http://192.168.31.52:5001"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 5002

    # LLM 模型 ID（在模型库中的记录 ID）
    # 主模型：ID=7，qwen4B（4B 视觉语言模型），用于 DAG 生成等复杂推理任务
    llm_8b_model_id: Optional[int] = None      # 主模型 ID（设计文档中的 8B，实际使用 4B）
    # 兜底模型：ID=8，0.8B 轻量模型，用于 IO 匹配等轻量任务
    llm_0_8b_model_id: Optional[int] = None    # 兜底模型 ID（0.8B）

    # LLM 模型名称（vLLM served-model-name）
    llm_8b_model_name: str = "qwen4B"          # 主模型名称（4B）
    llm_0_8b_model_name: str = "qwen4B"        # 兜底模型名称（暂用 4B，后续可改为 0.8B）

    @field_validator("llm_8b_model_id", "llm_0_8b_model_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """将空字符串转为 None，避免 Pydantic v2 解析失败"""
        if v == "" or v == "None":
            return None
        return v

    @property
    def model_registry_db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.model_registry_db_user}:{self.model_registry_db_password}"
            f"@{self.model_registry_db_host}:{self.model_registry_db_port}"
            f"/{self.model_registry_db_name}?charset=utf8mb4"
        )


settings = Settings()
