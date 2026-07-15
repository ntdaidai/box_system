# -*- coding: utf-8 -*-
"""冒烟测试：验证基本模块导入和模板匹配"""
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_loads():
    """配置模块能正常加载"""
    from src.core.config import settings
    assert settings.host == "0.0.0.0"
    assert settings.port == 5002
    assert settings.model_registry_db_host == "192.168.31.52"
    print("PASS: config loads")


def test_keyword_extractor():
    """关键词提取能正常工作"""
    from src.dam_workflow.tools.keyword_extractor import extract_event_type
    assert extract_event_type("发生了滑坡事件") == "滑坡"
    assert extract_event_type("检测到裂缝") == "裂缝"
    assert extract_event_type("渗漏严重") == "渗漏"
    assert extract_event_type("无关文本") is None
    print("PASS: keyword extractor")


def test_event_templates():
    """6 种事件模板都存在"""
    from src.dam_workflow.tools.event_templates import get_template, get_supported_event_types
    types = get_supported_event_types()
    assert len(types) == 6
    for t in types:
        tpl = get_template(t)
        assert tpl is not None, f"模板缺失: {t}"
        assert "nodes" in tpl
        assert "edges" in tpl
        classes = {n["node_class"] for n in tpl["nodes"]}
        assert "START" in classes, f"{t} 缺少 START"
        assert "END" in classes, f"{t} 缺少 END"
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
    assert "EVALUATION" in classes
    assert "START" in classes
    assert "END" in classes
    print("PASS: DAG generation (template path)")


def test_input_parser():
    """输入解析"""
    from src.dam_workflow.input_parser import parse_dam_input
    result = parse_dam_input("滑坡事件分析", ["img.jpg"])
    assert result["event_type"] == "滑坡"
    assert result["images"] == ["img.jpg"]
    print("PASS: input parser")


def test_rule_io_matcher():
    """规则 IO 匹配"""
    from src.dam_workflow.tools.rule_io_matcher import rule_based_io_match, START_OUTPUTS, EVALUATION_IO
    mapping = rule_based_io_match({"outputs": START_OUTPUTS}, EVALUATION_IO)
    assert "inputs" in mapping
    print("PASS: rule IO matcher")


if __name__ == "__main__":
    test_config_loads()
    test_keyword_extractor()
    test_event_templates()
    test_dag_generation_template_path()
    test_input_parser()
    test_rule_io_matcher()
    print("\nAll smoke tests passed!")
