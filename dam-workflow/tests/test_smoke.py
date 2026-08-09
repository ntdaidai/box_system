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
    assert extract_event_type("AI_FLOOD 洪水灾害告警") == "洪水"
    assert extract_event_type("PERSON_INTRUSION 人员闯入") == "人员入侵"
    assert extract_event_type("BOAT_ILLEGAL_FISHING 船只偷捕") == "夜间电鱼捕鱼"
    assert extract_event_type("暴雨来袭") == "暴雨"
    assert extract_event_type("检测到裂缝") is None
    assert extract_event_type("水位异常") is None
    assert extract_event_type("无关文本") is None
    print("PASS: keyword extractor")


def test_event_templates():
    """三类新工作流事件模板都存在"""
    from src.dam_workflow.tools.event_templates import get_template, get_supported_event_types
    types = get_supported_event_types()
    assert len(types) == 11
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
    assert result["event_group"] == "natural_disaster"
    assert result["images"] == ["img.jpg"]
    assert result["videos"] == []
    assert result["media_objects"] == []
    flood = parse_dam_input(
        "当前触发事件：洪水灾害告警",
        ["img.jpg"],
        sensor_data={"event_code": "AI_FLOOD"},
    )
    assert flood["event_type"] == "洪水"
    assert flood["event_group"] == "natural_disaster"
    print("PASS: input parser")


def test_actor_inference():
    """角色推断"""
    from src.dam_workflow.model_selector import infer_actor_name
    assert infer_actor_name("滑坡", {"event_name": "滑坡事件"}) == "自然灾害分析专家"
    assert infer_actor_name("人员入侵", {"event_category": "behavior"}) == "人员行为分析专家"
    assert infer_actor_name("暴雨", {"event_name": "暴雨预警"}) == "极端天气分析专家"
    assert infer_actor_name("滑坡", {"actor_name": "人员行为分析专家"}) == "人员行为分析专家"
    print("PASS: actor inference")


def test_actor_stage_prompt_preferred():
    """角色阶段 prompt 优先于旧 actor_library 字段。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.core.models import Base, ActorLibrary, ActorPromptStage
    from src.dam_workflow.model_selector import configure_action_node

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[ActorLibrary.__table__, ActorPromptStage.__table__])
    db = sessionmaker(bind=engine)()
    try:
        actor = ActorLibrary(
            actor_name="自然灾害分析专家",
            description="test",
            local_system_prompt="旧本地提示词",
            cloud_system_prompt="旧云端提示词",
        )
        db.add(actor)
        db.flush()
        db.add(
            ActorPromptStage(
                actor_id=actor.id,
                stage_code="edge_analysis",
                model_scope="qwen4b",
                system_prompt="阶段化 4B 提示词",
                is_active=1,
                version="v2",
            )
        )
        db.commit()

        node = {"node_class": "ACTION", "model_category": "local_llm", "node_type": "场景理解"}
        configure_action_node(node, "洪水", "洪水事件", db, sensor_data={"event_name": "洪水告警"})

        assert node["system_prompt"] == "阶段化 4B 提示词"
        assert node["system_prompt_source"] == "actor_prompt_stage.edge_analysis.qwen4b.v2"
        assert node["stage_code"] == "edge_analysis"
        assert node["prompt_version"] == "v2"
    finally:
        db.close()
        engine.dispose()
    print("PASS: actor stage prompt preferred")


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
    test_actor_stage_prompt_preferred()
    test_rule_io_matcher()
    print("\nAll smoke tests passed!")
