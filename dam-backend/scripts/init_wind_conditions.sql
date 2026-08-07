-- =====================================================
-- 风灾条件初始化脚本
-- 基于《风力等级》国家标准 (GB/T 28591-2012)
-- =====================================================

-- 1. 确保风速数据源存在
INSERT INTO data_source (id, source_name, source_type, description, is_activate)
VALUES (2, '风速风向传感器', 'sensor', '小聚碳一体式风速风向传感器', 1)
ON DUPLICATE KEY UPDATE source_name = '风速风向传感器';

-- 2. 清理旧的风灾条件（可选，如果要重新配置）
-- DELETE FROM event_condition WHERE condition_id IN (SELECT id FROM condition_library WHERE source_id = 2);
-- DELETE FROM condition_library WHERE source_id = 2;

-- 3. 插入风力等级条件（使用区间表达式）
-- 风速变量名: wind_speed_ms (m/s)
-- 表达式语法: "变量 >= 下限 AND 变量 < 上限"

-- 6级强风 (10.8~13.8 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('6级强风', 2, 'wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9', 5, 0, '风速10.8~13.9m/s，大树枝摆动，电线呼呼有声', 1);

-- 7级疾风 (13.9~17.1 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('7级疾风', 2, 'wind_speed_ms >= 13.9 AND wind_speed_ms < 17.2', 5, 0, '风速13.9~17.2m/s，全树摇动，迎风步行感觉不便', 1);

-- 8级大风 (17.2~20.7 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('8级大风', 2, 'wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8', 5, 0, '风速17.2~20.8m/s，微枝折毁，人向前行感觉阻力甚大', 1);

-- 9级烈风 (20.8~24.4 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('9级烈风', 2, 'wind_speed_ms >= 20.8 AND wind_speed_ms < 24.5', 5, 3, '风速20.8~24.5m/s，建筑物有损坏，持续3秒触发', 1);

-- 10级狂风 (24.5~28.4 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('10级狂风', 2, 'wind_speed_ms >= 24.5 AND wind_speed_ms < 28.5', 5, 3, '风速24.5~28.5m/s，树木拔起，建筑物严重损坏，持续3秒触发', 1);

-- 11级暴风 (28.5~32.6 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('11级暴风', 2, 'wind_speed_ms >= 28.5 AND wind_speed_ms < 32.7', 5, 3, '风速28.5~32.7m/s，有则必有重大损毁，持续3秒触发', 1);

-- 12级飓风 (32.7~36.9 m/s)
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description, is_activate)
VALUES ('12级飓风', 2, 'wind_speed_ms >= 32.7', 5, 0, '风速≥32.7m/s，摧毁力极大，立即触发', 1);


-- 4. 插入风灾事件
INSERT INTO event_library (event_name, event_code, event_category, risk_level, trigger_mode, description, is_activate)
VALUES
('大风预警', 'WIND_LEVEL_6', 'environment', 1, 'single', '6级强风预警，需关注', 1),
('强风预警', 'WIND_LEVEL_7', 'environment', 1, 'single', '7级疾风预警，需注意', 1),
('大风警报', 'WIND_LEVEL_8', 'environment', 2, 'single', '8级大风警报，危险', 1),
('烈风警报', 'WIND_LEVEL_9', 'environment', 2, 'single', '9级烈风警报，建筑物可能损坏', 1),
('狂风警报', 'WIND_LEVEL_10', 'environment', 3, 'single', '10级狂风警报，树木拔起，立即避险', 1),
('暴风警报', 'WIND_LEVEL_11', 'environment', 3, 'single', '11级暴风警报，重大损毁风险', 1),
('飓风警报', 'WIND_LEVEL_12', 'environment', 3, 'single', '12级飓风警报，极端危险', 1);


-- 5. 关联事件和条件
-- 获取刚插入的事件和条件ID（使用子查询）

-- 6级强风 → 大风预警
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_6' AND c.condition_name = '6级强风';

-- 7级疾风 → 强风预警
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_7' AND c.condition_name = '7级疾风';

-- 8级大风 → 大风警报
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_8' AND c.condition_name = '8级大风';

-- 9级烈风 → 烈风警报
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_9' AND c.condition_name = '9级烈风';

-- 10级狂风 → 狂风警报
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_10' AND c.condition_name = '10级狂风';

-- 11级暴风 → 暴风警报
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_11' AND c.condition_name = '11级暴风';

-- 12级飓风 → 飓风警报
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
SELECT e.id, c.id, 'AND', 0, 1
FROM event_library e, condition_library c
WHERE e.event_code = 'WIND_LEVEL_12' AND c.condition_name = '12级飓风';


-- 6. 插入事件动作配置
-- 当前动作表为 event_action，一行表示一个事件的一个动作步骤。

-- 6-7级：只记录日志
INSERT INTO event_action (
    event_id, step_order, action_type, action_name, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 1, 'script', '记录风速日志',
       '{"priority": 1, "action": "log", "message": "风速预警: {wind_speed_ms}m/s"}',
       120, 'continue', 1
FROM event_library e
WHERE e.event_code IN ('WIND_LEVEL_6', 'WIND_LEVEL_7')
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

-- 8-9级：YOLO检测 + 告警
INSERT INTO event_action (
    event_id, step_order, action_type, action_name, model_id, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 1, 'llm', 'YOLO检测风灾损害', m.id,
       '{"priority": 1, "prompt": "检测大风导致的树木倒塌、建筑损坏等异常"}',
       180, 'continue', 1
FROM event_library e, model_library m
WHERE e.event_code IN ('WIND_LEVEL_8', 'WIND_LEVEL_9') AND m.model_name = 'YOLOv8'
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    model_id = VALUES(model_id),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

INSERT INTO event_action (
    event_id, step_order, action_type, action_name, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 2, 'alert', '发送风灾警报',
       '{"priority": 1, "level": 2, "channels": ["app", "sms"], "template": "风灾警报：当前风速{wind_speed_ms}m/s，请注意安全"}',
       180, 'continue', 1
FROM event_library e
WHERE e.event_code IN ('WIND_LEVEL_8', 'WIND_LEVEL_9')
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

-- 10-12级：YOLO + SAM + Qwen + 紧急告警
INSERT INTO event_action (
    event_id, step_order, action_type, action_name, model_id, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 1, 'llm', 'YOLO检测风灾损害', m.id,
       '{"priority": 1, "prompt": "检测大风导致的严重损害：树木拔起、建筑倒塌、道路阻断"}',
       300, 'continue', 1
FROM event_library e, model_library m
WHERE e.event_code IN ('WIND_LEVEL_10', 'WIND_LEVEL_11', 'WIND_LEVEL_12') AND m.model_name = 'YOLOv8'
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    model_id = VALUES(model_id),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

INSERT INTO event_action (
    event_id, step_order, action_type, action_name, model_id, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 2, 'llm', 'SAM分割受损区域', m.id,
       '{"priority": 2, "prompt": "分割受损区域，评估影响范围"}',
       300, 'continue', 1
FROM event_library e, model_library m
WHERE e.event_code IN ('WIND_LEVEL_10', 'WIND_LEVEL_11', 'WIND_LEVEL_12') AND m.model_name = 'SAM'
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    model_id = VALUES(model_id),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

INSERT INTO event_action (
    event_id, step_order, action_type, action_name, model_id, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 3, 'llm', 'Qwen综合分析', m.id,
       '{"priority": 3, "prompt": "综合分析风灾影响，评估大坝安全风险，生成应急建议"}',
       300, 'continue', 1
FROM event_library e, model_library m
WHERE e.event_code IN ('WIND_LEVEL_10', 'WIND_LEVEL_11', 'WIND_LEVEL_12') AND m.model_name = 'Qwen3-VL-8B'
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    model_id = VALUES(model_id),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);

INSERT INTO event_action (
    event_id, step_order, action_type, action_name, parameter,
    timeout_seconds, failure_strategy, is_activate
)
SELECT e.id, 4, 'alert', '发送紧急风灾警报',
       '{"priority": 1, "level": 3, "channels": ["app", "sms", "phone"], "template": "紧急风灾警报：当前风速{wind_speed_ms}m/s，已达{wind_level}级，立即撤离危险区域！"}',
       300, 'continue', 1
FROM event_library e
WHERE e.event_code IN ('WIND_LEVEL_10', 'WIND_LEVEL_11', 'WIND_LEVEL_12')
ON DUPLICATE KEY UPDATE
    action_type = VALUES(action_type),
    action_name = VALUES(action_name),
    parameter = VALUES(parameter),
    timeout_seconds = VALUES(timeout_seconds),
    failure_strategy = VALUES(failure_strategy),
    is_activate = VALUES(is_activate);


-- 完成
SELECT '风灾条件初始化完成' AS result;
