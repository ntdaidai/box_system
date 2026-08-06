-- ============================================================
-- 统一模型库 ORM 与实际库结构
-- 日期：2026-08-06
-- 说明：
-- 1. model_registry.tags 已在实际库存在，初始化脚本与 ORM 补齐该字段。
-- 2. model_event_mapping 的模型类别统一为 specialized/local_llm/cloud_llm。
-- 3. model_evaluation_template 补齐 template_type，便于区分场景推理与最终报告模板。
-- ============================================================

USE dam_system;

SET @has_registry_tags := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'model_registry'
    AND COLUMN_NAME = 'tags'
);
SET @sql := IF(
  @has_registry_tags = 0,
  'ALTER TABLE model_registry ADD COLUMN tags JSON DEFAULT NULL COMMENT ''模型标签'' AFTER description',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE model_event_mapping
  MODIFY COLUMN model_category ENUM('specialized','local_llm','cloud_llm') NOT NULL
  COMMENT '模型类别：specialized=专用小模型，local_llm=本地大模型，cloud_llm=云端大模型';

SET @has_template_type := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'model_evaluation_template'
    AND COLUMN_NAME = 'template_type'
);
SET @sql := IF(
  @has_template_type = 0,
  'ALTER TABLE model_evaluation_template ADD COLUMN template_type VARCHAR(32) DEFAULT NULL COMMENT ''模板类型：reasoning=场景推理，report=最终报告'' AFTER event_type',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_template_type_idx := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'model_evaluation_template'
    AND INDEX_NAME = 'idx_template_type'
);
SET @sql := IF(
  @has_template_type_idx = 0,
  'ALTER TABLE model_evaluation_template ADD KEY idx_template_type (template_type)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
