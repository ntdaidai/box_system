# -*- coding: utf-8 -*-
"""冒烟测试：验证基本模块导入和模板匹配"""
import sys
import os

# 确保项目根目录在 sys.path 中，并切换工作目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)


def test_config_loads():
    """配置模块能正常加载"""
    from src.core.config import settings
    assert settings.host == "0.0.0.0"
    assert settings.port == 5002
    assert settings.model_registry_db_host == "192.168.31.52"
    assert settings.llm_local_model_id == 10
    assert settings.llm_fallback_model_id == 9
    print("PASS: config loads")


def test_keyword_extractor():
    """关键词提取能正常工作"""
    from src.dam_workflow.tools.keyword_extractor import extract_event_type
    assert extract_event_type("发生了滑坡事件") == "滑坡"
    assert extract_event_type("检测到裂缝") == "裂缝"
    assert extract_event_type("渗漏严重") == "渗漏"
    assert extract_event_type("暴雨来袭") == "降雨"
    assert extract_event_type("水位异常") == "水位"
    assert extract_event_type("无关文本") is None
    print("PASS: keyword extractor")


def test_event_templates():
    """8 种事件模板都存在"""
    from src.dam_workflow.tools.event_templates import get_template, get_supported_event_types
    types = get_supported_event_types()
    assert len(types) == 8
    for t in types:
        tpl = get_template(t)
        assert tpl is not None, f"模板缺失: {t}"
        assert "nodes" in tpl
        assert "edges" in tpl
        classes = {n["node_class"] for n in tpl["nodes"]}
        assert "START" in classes, f"{t} 缺少 START"
        assert "END" in classes, f"{t} 缺少 END"
        # 检查是否有 local_llm 和 cloud_llm 节点
        categories = {n.get("model_category") for n in tpl["nodes"]}
        assert "local_llm" in categories, f"{t} 缺少 local_llm 节点"
        assert "cloud_llm" in categories, f"{t} 缺少 cloud_llm 节点"
    print("PASS: event templates")


def test_dag_generation_template_path():
    """模板路径 DAG 生成（零 LLM）"""
    from src.dam_workflow.dag_generator import generate_dag
    state = {
        "event_type": "滑坡",
        "images": ["test.jpg"],
        "user_prompt": "滑坡事件分析",
        "retry_count": 0,
    }
    dag = generate_dag(state)
    assert dag is not None
    assert "nodes" in dag
    assert "edges" in dag
    classes = {n["node_class"] for n in dag["nodes"]}
    assert "START" in classes
    assert "END" in classes
    # 检查是否有 local_llm 和 cloud_llm 节点
    categories = {n.get("model_category") for n in dag["nodes"]}
    assert "local_llm" in categories, "缺少 local_llm 节点"
    assert "cloud_llm" in categories, "缺少 cloud_llm 节点"
    print("PASS: DAG generation (template path)")


def test_input_parser():
    """输入解析"""
    from src.dam_workflow.input_parser import parse_dam_input
    result = parse_dam_input("滑坡事件分析", ["img.jpg"])
    assert result["event_type"] == "滑坡"
    assert result["images"] == ["img.jpg"]
    assert result["videos"] == []
    assert result["media_objects"] == []
    print("PASS: input parser")


def test_actor_inference():
    """角色推断"""
    from src.dam_workflow.model_selector import infer_actor_name
    assert infer_actor_name("滑坡", {"event_name": "滑坡事件"}) == "自然灾害分析专家"
    assert infer_actor_name("人员入侵", {"event_category": "behavior"}) == "人员行为分析专家"
    assert infer_actor_name("暴雨", {"event_name": "暴雨预警"}) == "极端天气分析专家"
    assert infer_actor_name("滑坡", {"actor_name": "人员行为分析专家"}) == "人员行为分析专家"
    print("PASS: actor inference")


def test_rule_io_matcher():
    """规则 IO 匹配"""
    from src.dam_workflow.tools.rule_io_matcher import rule_based_io_match, START_OUTPUTS, LLM_ACTION_IO
    mapping = rule_based_io_match({"outputs": START_OUTPUTS}, LLM_ACTION_IO)
    assert "inputs" in mapping
    print("PASS: rule IO matcher")


if __name__ == "__main__":
    test_config_loads()
    test_keyword_extractor()
    test_event_templates()
    test_dag_generation_template_path()
    test_input_parser()
    test_actor_inference()
    test_rule_io_matcher()
    print("\nAll smoke tests passed!")
