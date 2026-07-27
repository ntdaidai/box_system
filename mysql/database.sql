-- ============================================================
-- 大坝监测系统 - 完整数据库建表脚本
-- 项目：box_system (dam-ai-service)
-- 创建日期：2026-07-02
-- 说明：包含基础业务表 + ECA（事件-条件-动作）模型表
-- 数据库：dam_system
-- ============================================================

-- 使用数据库
USE dam_system;

-- ============================================================
-- 第一部分：基础业务表
-- 说明：用户、设备、告警、规则、报告等核心业务
-- ============================================================

-- ------------------------------------------------------------
-- 1. 用户表
-- 说明：系统用户管理，支持登录认证和权限控制
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    username        VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password        VARCHAR(255) NOT NULL COMMENT 'bcrypt哈希密码',
    real_name       VARCHAR(50) COMMENT '真实姓名',
    phone           VARCHAR(20) COMMENT '手机号',
    email           VARCHAR(100) COMMENT '邮箱',
    role            VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色: admin-管理员/user-普通用户',
    status          INT NOT NULL DEFAULT 1 COMMENT '状态: 1-启用 0-禁用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_role (role),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ------------------------------------------------------------
-- 2. 告警表
-- 说明：告警记录存储和处理跟踪
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alarm (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '告警ID',
    alarm_code      VARCHAR(64) COMMENT '告警编码',
    device_id       INT COMMENT '关联设备ID',
    alarm_type      VARCHAR(32) COMMENT '告警类型: threshold-阈值告警/manual-人工告警/ai-AI告警',
    alarm_level     INT COMMENT '告警级别: 1-低 2-中 3-高',
    alarm_content   VARCHAR(500) COMMENT '告警内容',
    alarm_time      DATETIME COMMENT '告警触发时间',
    handle_status   INT DEFAULT 0 COMMENT '处理状态: 0-未处理 1-已处理',
    handle_user     VARCHAR(50) COMMENT '处理人用户名',
    handle_time     DATETIME COMMENT '处理时间',
    handle_remark   VARCHAR(500) COMMENT '处理备注',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    INDEX idx_device_id (device_id),
    INDEX idx_alarm_type (alarm_type),
    INDEX idx_alarm_level (alarm_level),
    INDEX idx_handle_status (handle_status),
    INDEX idx_alarm_time (alarm_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警表';

-- ------------------------------------------------------------
-- 3. 分析报告表
-- 说明：AI分析报告和人工报告存储
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_report (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '报告ID',
    report_title    VARCHAR(200) COMMENT '报告标题',
    report_type     VARCHAR(32) COMMENT '报告类型: vision-视觉分析/manual-人工分析/daily-日报',
    risk_level      VARCHAR(16) COMMENT '风险等级: low-低/medium-中/high-高/critical-危急',
    content         TEXT COMMENT '报告内容（Markdown格式）',
    ai_model        VARCHAR(64) COMMENT '使用的AI模型',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_report_type (report_type),
    INDEX idx_risk_level (risk_level),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分析报告表';


-- ============================================================
-- 第二部分：ECA模型表
-- 说明：事件-条件-动作架构，支持复杂的多源触发和智能响应
-- ============================================================

-- ------------------------------------------------------------
-- 4. AI模型库
-- 说明：管理AI推理模型，如YOLO、Qwen-VL等
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_library (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '模型ID',
    model_name      VARCHAR(100) NOT NULL COMMENT '模型名称，如YOLOv8/RT-DETR/Qwen-VL/SegFormer',
    model_type      VARCHAR(50) COMMENT '模型类型: detection-目标检测/segmentation-分割/vlm-视觉语言',
    model_path      VARCHAR(500) NOT NULL COMMENT '模型文件路径',
    description     VARCHAR(500) COMMENT '模型描述',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_model_name (model_name),
    INDEX idx_model_type (model_type),
    INDEX idx_is_activate (is_activate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI模型库';

-- ------------------------------------------------------------
-- 5. 数据源表
-- 说明：抽象数据源定义，关联设备或外部数据
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_source (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '数据源ID',
    source_name     VARCHAR(100) NOT NULL COMMENT '数据源名称',
    source_type     VARCHAR(50) NOT NULL COMMENT '数据源类型: sensor-传感器/camera-摄像头/api-接口/file-文件',
    device_id       INT COMMENT '关联设备ID（对应device表）',
    data_path       VARCHAR(500) COMMENT '数据路径或接口地址',
    description     VARCHAR(500) COMMENT '描述',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_source_type (source_type),
    INDEX idx_device_id (device_id),
    INDEX idx_is_activate (is_activate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源表';

-- ------------------------------------------------------------
-- 6. 条件库
-- 说明：定义监测条件，支持复杂表达式和时间窗口
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS condition_library (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '条件ID',
    condition_name  VARCHAR(200) NOT NULL COMMENT '条件名称，如雨量>80mm/振动频率异常',
    source_id       BIGINT NOT NULL COMMENT '数据源ID',
    expression      VARCHAR(500) NOT NULL COMMENT '条件表达式，如 rainfall > 80',
    time_window     INT DEFAULT 5 COMMENT '时间窗口（分钟）',
    duration        INT DEFAULT 0 COMMENT '持续时间（分钟），达到此时间才算触发',
    description     VARCHAR(500) COMMENT '条件说明',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (source_id) REFERENCES data_source(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_source_id (source_id),
    INDEX idx_condition_name (condition_name),
    INDEX idx_is_activate (is_activate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='条件库';

-- ------------------------------------------------------------
-- 7. 事件库
-- 说明：定义事件类型，如滑坡、裂缝、道路阻断等
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_library (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '事件ID',
    event_name      VARCHAR(100) NOT NULL COMMENT '事件名称，如滑坡预警/裂缝扩展',
    event_code      VARCHAR(50) UNIQUE COMMENT '事件编码，如LANDSLIDE/CRACK',
    event_category  VARCHAR(50) COMMENT '事件分类: environment-环境/structure-结构/equipment-设备',
    risk_level      TINYINT DEFAULT 1 COMMENT '风险等级: 1-低 2-中 3-高',
    trigger_mode    VARCHAR(20) DEFAULT 'single' COMMENT '触发模式: single-单源/multi-多源',
    description     VARCHAR(500) COMMENT '事件描述',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_event_code (event_code),
    INDEX idx_event_category (event_category),
    INDEX idx_risk_level (risk_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件库';

-- ------------------------------------------------------------
-- 8. 事件-条件关系表
-- 说明：定义事件与条件的多对多关系，支持AND/OR逻辑组合
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_condition (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '关系ID',
    event_id        BIGINT NOT NULL COMMENT '事件ID',
    condition_id    BIGINT NOT NULL COMMENT '条件ID',
    logic_type      VARCHAR(10) DEFAULT 'AND' COMMENT '逻辑类型: AND-与/OR-或',
    group_id        INT DEFAULT 0 COMMENT '条件分组ID（同组内AND/OR，组间AND）',
    sort_order      INT DEFAULT 0 COMMENT '判断顺序',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (event_id) REFERENCES event_library(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (condition_id) REFERENCES condition_library(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_event_id (event_id),
    INDEX idx_condition_id (condition_id),
    INDEX idx_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件-条件关系表';

-- ------------------------------------------------------------
-- 9. 行为流程库
-- 说明：定义事件触发后的响应流程
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_flow (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '流程ID',
    flow_name       VARCHAR(200) NOT NULL COMMENT '流程名称，如滑坡分析流程',
    flow_code       VARCHAR(50) UNIQUE COMMENT '流程编码',
    timeout_seconds INT DEFAULT 300 COMMENT '超时时间（秒）',
    failure_strategy VARCHAR(50) DEFAULT 'retry' COMMENT '失败策略: retry-重试/abort-终止/skip-跳过',
    description     VARCHAR(500) COMMENT '流程描述',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_flow_code (flow_code),
    INDEX idx_is_activate (is_activate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行为流程库';

-- ------------------------------------------------------------
-- 10. 行为步骤库
-- 说明：流程中的具体执行步骤
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_step (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '步骤ID',
    flow_id         BIGINT NOT NULL COMMENT '所属流程ID',
    step_order      INT NOT NULL DEFAULT 1 COMMENT '步骤顺序',
    step_name       VARCHAR(100) COMMENT '步骤名称',
    action_type     VARCHAR(50) NOT NULL COMMENT '动作类型: llm-大模型推理/alert-告警/script-脚本/http-接口',
    model_id        BIGINT COMMENT '关联模型ID（action_type为llm时使用）',
    parameter       JSON COMMENT '步骤参数（JSON格式）',
    retry_count     INT DEFAULT 0 COMMENT '重试次数',
    description     VARCHAR(500) COMMENT '步骤描述',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (flow_id) REFERENCES action_flow(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (model_id) REFERENCES model_library(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_flow_id (flow_id),
    INDEX idx_action_type (action_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行为步骤库';

-- ------------------------------------------------------------
-- 11. 事件-行为关系表
-- 说明：定义事件触发后执行哪些行为流程
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_action (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '关系ID',
    event_id        BIGINT NOT NULL COMMENT '事件ID',
    flow_id         BIGINT NOT NULL COMMENT '行为流程ID',
    priority        INT DEFAULT 0 COMMENT '执行优先级，数值越小优先级越高',
    is_activate     TINYINT(1) DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (event_id) REFERENCES event_library(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (flow_id) REFERENCES action_flow(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_event_id (event_id),
    INDEX idx_flow_id (flow_id),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件-行为关系表';

-- ------------------------------------------------------------
-- 12. 事件触发记录表
-- 说明：记录事件触发历史，用于追溯和统计
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_log (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '记录ID',
    event_id        BIGINT NOT NULL COMMENT '事件ID',
    trigger_time    DATETIME NOT NULL COMMENT '触发时间',
    trigger_data    JSON COMMENT '触发时的数据快照',
    conditions_met  JSON COMMENT '满足的条件详情',
    status          VARCHAR(20) DEFAULT 'triggered' COMMENT '状态: triggered-已触发/processing-处理中/completed-已完成/failed-失败',
    result          VARCHAR(500) COMMENT '处理结果',
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (event_id) REFERENCES event_library(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_event_id (event_id),
    INDEX idx_trigger_time (trigger_time),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件触发记录表';


-- ============================================================
-- 第三部分：初始化数据
-- ============================================================

-- ------------------------------------------------------------
-- 默认管理员账号（密码: admin123）
-- ------------------------------------------------------------
INSERT INTO sys_user (username, password, real_name, role, status) VALUES
('admin', '$2b$12$LJ3m4ys3Lk0TSwHjnF4oR.K3VJxqfVYqxSy3TqFG3YfP0z3bGHXBe', '管理员', 'admin', 1);

-- ------------------------------------------------------------
-- 示例AI模型
-- ------------------------------------------------------------
INSERT INTO model_library (model_name, model_type, model_path, description, is_activate) VALUES
('YOLOv8', 'detection', '/models/yolov8.pt', 'YOLOv8目标检测模型', 1),
('RT-DETR', 'detection', '/models/rt_detr.pt', 'RT-DETR实时检测模型', 1),
('Qwen-VL', 'vlm', '/models/qwen-vl', '通义千问视觉语言模型', 1),
('SegFormer', 'segmentation', '/models/segformer.pt', 'SegFormer语义分割模型', 0);

-- ------------------------------------------------------------
-- 示例数据源
-- ------------------------------------------------------------
INSERT INTO data_source (source_name, source_type, device_id, data_path, description) VALUES
('雨量数据', 'sensor', NULL, 'root.dam.sensor.rain', '雨量传感器数据源'),
('振动数据', 'sensor', NULL, 'root.dam.sensor.vibration', '振动传感器数据源'),
('边坡摄像头', 'camera', NULL, '/data/camera/snapshots/', '边坡监控摄像头'),
('位移数据', 'sensor', NULL, 'root.dam.sensor.displacement', '位移传感器数据源');

-- ------------------------------------------------------------
-- 示例条件
-- ------------------------------------------------------------
INSERT INTO condition_library (condition_name, source_id, expression, time_window, duration, description) VALUES
('雨量超过80mm', 1, 'rainfall > 80', 5, 3, '5分钟内平均雨量超过80mm，持续3分钟'),
('振动频率异常', 2, 'vibration_freq > 50', 10, 5, '10分钟内振动频率超过50Hz，持续5分钟'),
('位移量超阈值', 4, 'displacement > 10', 30, 10, '30分钟内位移超过10mm，持续10分钟'),
('AI识别滑坡迹象', 3, 'ai_detect == landslide', 5, 1, 'AI视觉识别检测到滑坡迹象');

-- ------------------------------------------------------------
-- 示例事件
-- ------------------------------------------------------------
INSERT INTO event_library (event_name, event_code, event_category, risk_level, trigger_mode, description) VALUES
('滑坡预警', 'LANDSLIDE', 'environment', 3, 'multi', '综合多源数据判断滑坡风险'),
('裂缝扩展', 'CRACK', 'structure', 2, 'single', '监测到结构裂缝扩展'),
('道路阻断', 'ROAD_BLOCK', 'environment', 3, 'multi', '道路可能被阻断'),
('设备故障', 'DEVICE_FAULT', 'equipment', 1, 'single', '监测设备异常');

-- ------------------------------------------------------------
-- 示例事件-条件关系
-- ------------------------------------------------------------
INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order) VALUES
(1, 1, 'AND', 1, 1),  -- 滑坡预警 = 雨量>80 AND 振动异常
(1, 2, 'AND', 1, 2),
(1, 4, 'OR', 2, 1),   -- 或者 AI识别到滑坡
(2, 3, 'AND', 1, 1),  -- 裂缝扩展 = 位移超阈值
(3, 1, 'AND', 1, 1),  -- 道路阻断 = 雨量>80 AND 位移超阈值
(3, 3, 'AND', 1, 2);

-- ------------------------------------------------------------
-- 示例行为流程
-- ------------------------------------------------------------
INSERT INTO action_flow (flow_name, flow_code, timeout_seconds, failure_strategy, description) VALUES
('滑坡分析流程', 'LANDSLIDE_ANALYSIS', 600, 'retry', '滑坡事件触发后的AI分析流程'),
('裂缝监测流程', 'CRACK_MONITOR', 300, 'abort', '裂缝扩展事件的监测分析流程'),
('道路阻断应急流程', 'ROAD_EMERGENCY', 120, 'skip', '道路阻断事件的应急响应流程');

-- ------------------------------------------------------------
-- 示例行为步骤
-- ------------------------------------------------------------
INSERT INTO action_step (flow_id, step_order, step_name, action_type, model_id, parameter, description) VALUES
(1, 1, '图像检测', 'llm', 1, '{"task": "image_detection", "confidence": 0.8}', '使用YOLOv8检测滑坡迹象'),
(1, 2, '区域分割', 'llm', 4, '{"task": "segmentation", "target": "landslide"}', '使用SegFormer分割滑坡区域'),
(1, 3, '发送告警', 'alert', NULL, '{"level": "high", "notify": ["sms", "email"]}', '发送高级别告警通知'),
(2, 1, '裂缝检测', 'llm', 1, '{"task": "crack_detection", "min_size": 5}', '检测裂缝大小'),
(2, 2, '发送告警', 'alert', NULL, '{"level": "medium", "notify": ["email"]}', '发送中级别告警');

-- ------------------------------------------------------------
-- 示例事件-行为关系
-- ------------------------------------------------------------
INSERT INTO event_action (event_id, flow_id, priority) VALUES
(1, 1, 1),  -- 滑坡预警 -> 滑坡分析流程
(2, 2, 2),  -- 裂缝扩展 -> 裂缝监测流程
(3, 3, 1);  -- 道路阻断 -> 道路阻断应急流程


-- ============================================================
-- 完成
-- ============================================================
