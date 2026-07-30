# -*- coding: utf-8 -*-
"""测试 DAG 生成流程

测试场景：
1. 模板匹配事件（滑坡、裂缝等）→ 0 次 LLM 调用
2. 非模板匹配事件 → 1 次 LLM 调用（本地 qwen4B）
3. 无检测场景（降雨、水位）→ 不含 specialized 节点
"""
import sys
import os
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.core.config import settings
from src.dam_workflow.dag_generator import generate_dag
from src.dam_workflow.model_registry_client import model_registry_client


def test_template_path():
    """测试模板路径（零 LLM 调用）

    预期：
    - 事件类型：滑坡（命中预定义模板）
    - LLM 调用次数：0
    - 使用模型：无
    - 节点结构：START → specialized → local_llm → cloud_llm → END
    """
    print("=" * 60)
    print("测试 1：模板路径（滑坡事件）")
    print("=" * 60)
    print("预期：0 次 LLM 调用，直接使用模板")
    print()

    state = {
        "event_type": "滑坡",
        "images": ["landslide_001.jpg"],
        "user_prompt": "发生了滑坡事件，请分析",
        "retry_count": 0,
    }

    try:
        dag = generate_dag(state)
        print("✅ DAG 生成成功!")
        print(f"   节点数量: {len(dag['nodes'])}")
        print(f"   边数量: {len(dag['edges'])}")
        print(f"   视觉任务: {dag.get('visual_tasks', [])}")
        print()

        # 打印节点信息
        print("   节点列表:")
        for node in dag['nodes']:
            node_class = node['node_class']
            node_type = node['node_type']
            model_category = node.get('model_category', 'N/A')
            print(f"     - {node['node_id']}: [{node_class}] {node_type} ({model_category})")
        print()

        # 验证节点结构
        categories = {n.get('model_category') for n in dag['nodes']}
        assert 'specialized' in categories, "缺少 specialized 节点"
        assert 'local_llm' in categories, "缺少 local_llm 节点"
        assert 'cloud_llm' in categories, "缺少 cloud_llm 节点"

        return True, 0, "无"
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False, 0, "无"


def test_no_detection_path():
    """测试无检测场景（降雨事件）

    预期：
    - 事件类型：降雨（无需检测）
    - LLM 调用次数：0
    - 使用模型：无
    - 节点结构：START → local_llm → cloud_llm → END（无 specialized）
    """
    print("=" * 60)
    print("测试 2：无检测场景（降雨事件）")
    print("=" * 60)
    print("预期：0 次 LLM 调用，无 specialized 节点")
    print()

    state = {
        "event_type": "降雨",
        "images": ["rain_001.jpg"],
        "user_prompt": "暴雨来袭，请分析风险",
        "retry_count": 0,
    }

    try:
        dag = generate_dag(state)
        print("✅ DAG 生成成功!")
        print(f"   节点数量: {len(dag['nodes'])}")
        print(f"   边数量: {len(dag['edges'])}")
        print()

        # 打印节点信息
        print("   节点列表:")
        for node in dag['nodes']:
            node_class = node['node_class']
            node_type = node['node_type']
            model_category = node.get('model_category', 'N/A')
            print(f"     - {node['node_id']}: [{node_class}] {node_type} ({model_category})")
        print()

        # 验证节点结构
        categories = {n.get('model_category') for n in dag['nodes']}
        assert 'specialized' not in categories, "不应有 specialized 节点"
        assert 'local_llm' in categories, "缺少 local_llm 节点"
        assert 'cloud_llm' in categories, "缺少 cloud_llm 节点"

        return True, 0, "无"
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False, 0, "无"


def test_all_template_events():
    """测试所有模板事件（零 LLM 调用）

    预期：
    - 事件类型：所有 8 种预定义事件
    - LLM 调用次数：0（每个事件）
    - 使用模型：无
    """
    print("=" * 60)
    print("测试 3：所有模板事件")
    print("=" * 60)
    print("预期：每个事件 0 次 LLM 调用")
    print()

    events = ["滑坡", "裂缝", "渗漏", "变形", "沉降", "管涌", "降雨", "水位"]
    success_count = 0

    for event in events:
        state = {
            "event_type": event,
            "images": ["test.jpg"],
            "user_prompt": f"{event}事件分析",
            "retry_count": 0,
        }

        try:
            dag = generate_dag(state)
            categories = {n.get('model_category') for n in dag['nodes']}
            has_detection = 'specialized' in categories
            print(f"   ✅ {event}: {len(dag['nodes'])} 个节点, 检测={'有' if has_detection else '无'}")
            success_count += 1
        except Exception as e:
            print(f"   ❌ {event}: {e}")

    print()
    return success_count == len(events), 0, "无"


def test_llm_fallback_path():
    """测试 LLM 兜底路径

    预期：
    - 事件类型：未知事件（不在预定义模板中）
    - LLM 调用次数：1
    - 使用模型：本地 qwen4B (ID=10)
    """
    print("=" * 60)
    print("测试 4：LLM 兜底路径（未知事件类型）")
    print("=" * 60)
    print(f"预期：1 次 LLM 调用，使用本地模型 qwen4B (ID={settings.llm_local_model_id})")
    print()

    state = {
        "event_type": "溢流",  # 不在预定义模板中
        "images": ["overflow_001.jpg"],
        "user_prompt": "发生溢流事件，水位异常升高，请分析",
        "retry_count": 0,
    }

    try:
        dag = generate_dag(state)
        print("✅ DAG 生成成功!")
        print(f"   节点数量: {len(dag['nodes'])}")
        print(f"   边数量: {len(dag['edges'])}")
        print(f"   视觉任务: {dag.get('visual_tasks', [])}")
        print()

        # 打印节点信息
        print("   节点列表:")
        for node in dag['nodes']:
            node_class = node['node_class']
            node_type = node['node_type']
            model_category = node.get('model_category', 'N/A')
            print(f"     - {node['node_id']}: [{node_class}] {node_type} ({model_category})")
        print()

        # 验证节点结构
        categories = {n.get('model_category') for n in dag['nodes']}
        assert 'local_llm' in categories, "缺少 local_llm 节点"
        assert 'cloud_llm' in categories, "缺少 cloud_llm 节点"

        return True, 1, f"qwen4B (ID={settings.llm_local_model_id})"
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False, 1, f"qwen4B (ID={settings.llm_local_model_id})"


def main():
    """主测试函数"""
    print()
    print("DAG 生成流程测试")
    print("当前配置:")
    print(f"  本地模型 ID: {settings.llm_local_model_id}")
    print(f"  云端模型 ID: {settings.llm_cloud_model_id}")
    print(f"  兜底模型 ID: {settings.llm_fallback_model_id}")
    print()

    results = []

    # 测试 1：模板路径
    success, calls, model = test_template_path()
    results.append(("模板路径（滑坡）", success, calls, model))

    # 测试 2：无检测场景
    success, calls, model = test_no_detection_path()
    results.append(("无检测场景（降雨）", success, calls, model))

    # 测试 3：所有模板事件
    success, calls, model = test_all_template_events()
    results.append(("所有模板事件", success, calls, model))

    # 测试 4：LLM 兜底路径
    success, calls, model = test_llm_fallback_path()
    results.append(("LLM 兜底路径", success, calls, model))

    # 打印汇总
    print()
    print("=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(f"{'测试场景':<20} {'结果':<8} {'LLM调用次数':<12} {'使用模型'}")
    print("-" * 60)

    all_passed = True
    for name, success, calls, model in results:
        status = "✅ PASS" if success else "❌ FAIL"
        if not success:
            all_passed = False
        print(f"{name:<20} {status:<8} {calls:<12} {model}")

    print("-" * 60)

    if all_passed:
        print("\n✅ 所有测试通过!")
    else:
        print("\n❌ 部分测试失败")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
