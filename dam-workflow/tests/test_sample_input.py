# -*- coding: utf-8 -*-
"""测试样例输入的完整工作流生成"""
import sys
import os
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.core.config import settings
from src.dam_workflow.dam_subgraph import run_dam_workflow


def main():
    """测试样例输入"""
    # 用户提供的输入样例
    user_prompt = """你是一名库坝应急巡查智能感知系统中的工作流规划智能体。

你的职责是根据**已确定的事件类型**和现场图片，自动规划最合理的视觉分析流程，并生成专业的事件分析报告。

注意：事件类型已经由系统确定，你不需要重新判断事件是否发生，也不要对事件类型进行分类。

输入

1. 当前触发事件：滑坡事件。
2. 现场图片（1张或多张）。
3. 传感器信息、设备信息等辅助数据（可选）

工作原则

根据当前事件，首先分析完成本次事件分析所需要的视觉任务，例如目标检测、区域分割、变化检测、裂缝识别、场景理解等，而不是重新识别事件类型。

随后，根据视觉任务自动规划最优的模型调用流程，并遵循以下原则：

1. **专有模型优先**。优先调用针对具体任务微调后的专有模型完成视觉识别。
2. **小模型优先**。能够由轻量模型完成的任务，不调用多模态大模型。
3. **大模型负责理解与推理**。仅在需要综合分析时，调用多模态大模型结合专有模型输出进行场景理解、风险推理、结果解释、影响分析及处置建议生成，而不是重复执行目标检测或目标识别。
4. **避免重复分析**。已经由专有模型完成识别的目标，大模型不得再次识别，应直接利用识别结果完成高层语义分析。
5. **工作流应尽量简洁高效**。仅调用完成当前事件分析所必需的模型，减少不必要的模型调用，提高边缘计算效率。

输出要求

内部需要自动完成工作流规划，但**不要输出模型调用过程、模型名称、工作流步骤或推理过程**。

最终仅输出一份完整的事件分析报告。"""

    images = ["landslide_001.jpg", "landslide_002.jpg"]
    sensor_data = {
        "位移量": 15.2,
        "降雨量": 85.0,
        "水位": 32.5
    }

    print("=" * 70)
    print("输入样例测试")
    print("=" * 70)
    print()
    print("【输入信息】")
    print(f"  事件类型: 滑坡事件")
    print(f"  图片数量: {len(images)}")
    print(f"  传感器数据: {sensor_data}")
    print()

    # 运行工作流生成
    print("【开始生成工作流...】")
    print()

    result = run_dam_workflow(
        user_prompt=user_prompt,
        images=images,
        sensor_data=sensor_data,
    )

    # 输出结果
    print("=" * 70)
    print("输出结果")
    print("=" * 70)
    print()

    if result["success"]:
        print("✅ 工作流生成成功!")
        print()
        print(f"【事件类型】: {result['event_type']}")
        print(f"【视觉任务】: {result['visual_tasks']}")
        print()

        final_dag = result["final_dag"]
        print("【DAG 结构】")
        print(f"  节点数量: {len(final_dag['nodes'])}")
        print(f"  边数量: {len(final_dag['edges'])}")
        print()

        print("【节点详情】")
        for node in final_dag['nodes']:
            node_class = node['node_class']
            node_type = node['node_type']
            model_name = node.get('model_name', 'N/A')
            print(f"  - {node['node_id']}: [{node_class}] {node_type}")
            if node_class == 'ACTION':
                print(f"    模型: {model_name}")
                if node.get('inference_url'):
                    print(f"    推理地址: {node['inference_url']}")
        print()

        print("【边及数据流】")
        for edge in final_dag['edges']:
            source = edge['source']
            target = edge['target']
            data_flow = edge.get('data_flow', {})
            print(f"  - {source} → {target}")
            if data_flow.get('inputs'):
                print(f"    数据流: {data_flow['inputs']}")
        print()

        # 保存完整 DAG 到文件
        output_file = os.path.join(project_root, "tests", "output_dag.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_dag, f, ensure_ascii=False, indent=2)
        print(f"【DAG 已保存到】: {output_file}")

    else:
        print(f"❌ 工作流生成失败: {result['error']}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
