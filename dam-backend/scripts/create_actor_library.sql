-- ============================================================
-- 角色库表 (actor_library)
-- 只定义“谁来分析”；具体提示词由 actor_prompt_stage 分阶段管理。
-- ============================================================

CREATE TABLE IF NOT EXISTS `actor_library` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `actor_name` VARCHAR(128) NOT NULL COMMENT '角色名称',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '角色描述',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_actor_name` (`actor_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色库';

-- 兼容已存在的旧 actor_library 表：删除已迁移到 actor_prompt_stage 的粗粒度 prompt 列。
SET @has_local_prompt := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'actor_library'
      AND COLUMN_NAME = 'local_system_prompt'
);
SET @ddl := IF(
    @has_local_prompt > 0,
    'ALTER TABLE `actor_library` DROP COLUMN `local_system_prompt`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_cloud_prompt := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'actor_library'
      AND COLUMN_NAME = 'cloud_system_prompt'
);
SET @ddl := IF(
    @has_cloud_prompt > 0,
    'ALTER TABLE `actor_library` DROP COLUMN `cloud_system_prompt`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_create_time := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'actor_library'
      AND COLUMN_NAME = 'create_time'
);
SET @ddl := IF(
    @has_create_time = 0,
    'ALTER TABLE `actor_library` ADD COLUMN `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT ''创建时间''',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_update_time := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'actor_library'
      AND COLUMN_NAME = 'update_time'
);
SET @ddl := IF(
    @has_update_time = 0,
    'ALTER TABLE `actor_library` ADD COLUMN `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间''',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================
-- 初始化数据：按智能路由三类工作流预置角色
-- ============================================================

INSERT INTO `actor_library` (`actor_name`, `description`) VALUES
('自然灾害分析专家', '适用于泥石流、滑坡、洪水、地震等自然灾害事件分析工作流'),
('人员行为分析专家', '适用于人员入侵、滩涂游玩、夜间电鱼捕鱼等异常行为事件分析工作流'),
('极端天气分析专家', '适用于台风、暴雨、高温、低温等极端天气风险分析工作流'),
('摄像头初筛专家', '适用于 Qwen0.8B 常驻模型的摄像头多帧初筛，只输出 ECA 可消费 JSON')
ON DUPLICATE KEY UPDATE
    `description` = VALUES(`description`);
