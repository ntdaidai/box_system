"""容器名称生成工具

提供容器名称生成功能，支持从模型名称生成可读的容器名称。
"""

import re


def generate_container_name(model_id: int, model_name: str) -> str:
    """生成容器名称：dam-{name_slug}-{id}

    规则：
    1. 添加 "dam-" 前缀，便于过滤识别
    2. 模型名称转小写，特殊字符转连字符
    3. 保留中文字符
    4. 名称过长时截断（最多30字符）
    5. 末尾添加模型ID确保唯一性

    Args:
        model_id: 模型ID
        model_name: 模型名称

    Returns:
        容器名称，例如：dam-qwen3-vl-4b-instruct-5

    Examples:
        >>> generate_container_name(5, "Qwen3-VL-4B-Instruct")
        'dam-qwen3-vl-4b-instruct-5'
        >>> generate_container_name(2, "nginx测试模型")
        'dam-nginx测试模型-2'
    """
    # 转小写
    name = model_name.lower()

    # 将非字母数字中文字符替换为连字符
    name = re.sub(r'[^a-z0-9一-鿿]+', '-', name)

    # 去除首尾连字符
    name = name.strip('-')

    # 压缩连续连字符
    name = re.sub(r'-+', '-', name)

    # 截断过长名称（保留30字符）
    if len(name) > 30:
        name = name[:30].rstrip('-')
        # 确保不在连字符中间截断
        if name.endswith('-'):
            name = name[:-1]

    # 空名称时使用 id 作为后备
    if not name:
        name = str(model_id)

    return f"dam-{name}-{model_id}"


def is_dam_container(container_name: str) -> bool:
    """判断是否为 DAM 系统管理的容器

    Args:
        container_name: 容器名称

    Returns:
        是否为 DAM 容器
    """
    return container_name.startswith("dam-")
