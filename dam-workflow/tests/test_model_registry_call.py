# -*- coding: utf-8 -*-
"""测试模型库推理接口调用"""
import sys
import os

# 确保项目根目录在 sys.path 中，并切换工作目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.core.config import settings
from src.dam_workflow.model_registry_client import model_registry_client


def test_get_model_name():
    """测试动态获取模型名称"""
    print("=" * 50)
    print("测试动态获取模型名称")
    print("=" * 50)

    # 测试本地模型
    try:
        local_model_name = model_registry_client.get_model_name(settings.llm_local_model_id)
        print(f"✅ 本地模型 ID={settings.llm_local_model_id}，vLLM 名称: {local_model_name}")
    except Exception as e:
        print(f"❌ 获取本地模型名称失败: {e}")
        return False

    # 测试兜底模型
    try:
        fallback_model_name = model_registry_client.get_model_name(settings.llm_fallback_model_id)
        print(f"✅ 兜底模型 ID={settings.llm_fallback_model_id}，vLLM 名称: {fallback_model_name}")
    except Exception as e:
        print(f"❌ 获取兜底模型名称失败: {e}")
        return False

    return True


def test_model_registry_infer():
    """测试调用模型库推理接口"""
    print()
    print("=" * 50)
    print("测试模型库推理接口调用")
    print("=" * 50)

    print(f"模型库 API 地址: {settings.model_registry_api_base}")
    print(f"本地模型 ID: {settings.llm_local_model_id}")
    print(f"兜底模型 ID: {settings.llm_fallback_model_id}")
    print()

    # 简单测试 prompt
    test_prompt = "你好，请简单介绍一下自己。"

    try:
        print(f"调用推理接口...")
        result = model_registry_client.infer(
            model_id=settings.llm_local_model_id,
            request_data={"prompt": test_prompt},
        )

        # 解析返回结果
        choices = result.get("data", {}).get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            print("✅ 调用成功!")
            print(f"回复: {content[:100]}...")
        else:
            print(f"⚠️ 调用成功但返回格式异常: {result}")
        return True

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


if __name__ == "__main__":
    success1 = test_get_model_name()
    success2 = test_model_registry_infer()

    if success1 and success2:
        print("\n" + "=" * 50)
        print("所有测试通过!")
        print("=" * 50)
        sys.exit(0)
    else:
        sys.exit(1)
