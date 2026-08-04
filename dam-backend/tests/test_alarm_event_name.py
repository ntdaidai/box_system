from types import SimpleNamespace

from app.api.alarm import _infer_alarm_event_name


def alarm(content, alarm_type="threshold"):
    return SimpleNamespace(alarm_content=content, alarm_type=alarm_type)


def test_explicit_event_name_has_priority():
    assert _infer_alarm_event_name(
        alarm("模板标题：告警内容"),
        explicit_name="人员涉水",
        legacy_candidates=("大风告警",),
    ) == "人员涉水"


def test_legacy_event_name_matches_flow_candidate_in_content():
    assert _infer_alarm_event_name(
        alarm("大风告警：当前风速 4.2m/s"),
        legacy_candidates=("大风告警", "强风告警"),
    ) == "大风告警"


def test_legacy_event_name_uses_short_template_title():
    assert _infer_alarm_event_name(alarm("测试告警：风速超过阈值")) == "测试告警"


def test_event_name_has_readable_type_fallback():
    assert _infer_alarm_event_name(alarm("未提供标题的告警正文", "ai")) == "AI检测告警"
