# -*- coding: utf-8 -*-
"""测试模型库推理接口调用"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.dam_workflow.model_registry_client import model_registry_client


def test_model_registry_infer():
    """测试调用模型库推理接口"""
    print(f"模型库 API 地址: {settings.model_registry_api_base}")
    print(f"LLM 模型 ID: {settings.llm_8b_model_id}")
    print(f"LLM 模型名称: {settings.llm_8b_model_name}")
    print()

    # 简单测试 prompt
    test_prompt = "你好，请简单介绍一下自己。"

    try:
        print(f"调用推理接口...")
        print(f"请求 URL: {settings.model_registry_api_base}/api/model-registry/{settings.llm_8b_model_id}/infer")
        print(f"请求数据: {{'prompt': '{test_prompt}', 'model': '{settings.llm_8b_model_name}'}}")
        print()

        result = model_registry_client.infer(
            model_id=settings.llm_8b_model_id,
            request_data={"prompt": test_prompt},
            model_name=settings.llm_8b_model_name,
        )

        print("✅ 调用成功!")
        print(f"响应: {result}")
        return True

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


if __name__ == "__main__":
    success = test_model_registry_infer()
    sys.exit(0 if success else 1)
