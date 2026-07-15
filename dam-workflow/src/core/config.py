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
    llm_8b_model_id: Optional[int] = None      # 8B 大模型 ID
    llm_0_8b_model_id: Optional[int] = None    # 0.8B 大模型 ID

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
