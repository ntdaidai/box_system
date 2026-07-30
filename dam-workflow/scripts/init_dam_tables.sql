-- ============================================================
-- DAM 工作流系统 - 专属表建表脚本
-- 项目：dam-workflow
-- 创建日期：2026-07-28
-- 说明：这些表需要在模型库数据库（dam_system）中创建
-- ============================================================

USE dam_system;

-- 事件→模型映射表
CREATE TABLE IF NOT EXISTS `model_event_mapping` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `event_type`      VARCHAR(64)   NOT NULL COMMENT '事件类型（滑坡/裂缝/渗漏/变形/沉降/管涌/降雨/水位）',
  `task_type`       VARCHAR(128)  NOT NULL COMMENT '任务类型（检测/分割/变化检测/场景推理/最终报告）',
  `model_category`  ENUM('specialized', 'local_llm', 'cloud_llm') NOT NULL COMMENT '模型类别：specialized=专用小模型，local_llm=本地大模型，cloud_llm=云端大模型',
  `model_id`        BIGINT        DEFAULT NULL COMMENT '模型 ID（关联 model_registry.id）',
  `priority`        INT           NOT NULL DEFAULT 0 COMMENT '优先级（数值越大越优先）',
  `remark`          VARCHAR(256)  DEFAULT NULL COMMENT '备注说明',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_task` (`event_type`, `task_type`),
  KEY `idx_model_id` (`model_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件→模型映射表';

-- 评价 prompt 模板表
CREATE TABLE IF NOT EXISTS `model_evaluation_template` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name`   VARCHAR(128)  NOT NULL COMMENT '模板名称',
  `event_type`      VARCHAR(64)   DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用模板）',
  `template_type`   VARCHAR(32)   DEFAULT NULL COMMENT '模板类型：reasoning=场景推理，report=最终报告',
  `prompt_template` TEXT          NOT NULL COMMENT 'prompt 模板（含占位符：{{user_prompt}}, {{detection_results}}, {{sensor_data}}）',
  `input_schema`    JSON          NOT NULL COMMENT '输入 schema 定义',
  `output_schema`   JSON          NOT NULL COMMENT '输出 schema 定义',
  `is_active`       TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否启用：0=禁用，1=启用',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_type` (`event_type`),
  KEY `idx_template_type` (`template_type`),
  UNIQUE KEY `uk_template_name` (`template_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价 prompt 模板表';

-- IO 配对模板表
CREATE TABLE IF NOT EXISTS `model_io_template` (
  `id`                    BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name`         VARCHAR(128)  NOT NULL COMMENT '模板名称',
  `event_type`            VARCHAR(64)   DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用）',
  `source_model_category` VARCHAR(64)   NOT NULL COMMENT '上游模型类别（specialized/local_llm/cloud_llm）',
  `target_model_category` VARCHAR(64)   NOT NULL COMMENT '下游模型类别（specialized/local_llm/cloud_llm）',
  `source_task_type`      VARCHAR(128)  DEFAULT NULL COMMENT '上游任务类型（可选，用于精确匹配）',
  `target_task_type`      VARCHAR(128)  DEFAULT NULL COMMENT '下游任务类型（可选，用于精确匹配）',
  `field_mapping`         JSON          NOT NULL COMMENT '字段映射规则',
  `create_time`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_source_target` (`event_type`, `source_model_category`, `target_model_category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IO 配对模板表';
