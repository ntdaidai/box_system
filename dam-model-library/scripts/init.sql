-- ============================================================
-- 轻量级模型库 - 建表脚本
-- 项目：dam-model-library
-- 创建日期：2026-07-10
-- ============================================================

-- 使用数据库
USE dam_system;

-- 模型注册表
CREATE TABLE IF NOT EXISTS `model_registry` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name`            VARCHAR(128)  NOT NULL COMMENT '模型名称',
  `description`     VARCHAR(512)  DEFAULT NULL COMMENT '模型描述',
  `framework`       VARCHAR(64)   DEFAULT NULL COMMENT '框架（PyTorch/TensorFlow/ONNX等）',
  `architecture`    VARCHAR(64)   DEFAULT NULL COMMENT '架构（CNN/Transformer等）',
  `model_type`      VARCHAR(64)   DEFAULT NULL COMMENT '模型类型（目标检测/图像分类/LLM等）',
  `model_size`      VARCHAR(32)   DEFAULT NULL COMMENT '模型大小（如 7B、1.2GB）',
  `runtime_status`  VARCHAR(16)   NOT NULL DEFAULT 'stopped' COMMENT '运行状态：stopped/starting/running/stopping/error',
  `owner_id`        BIGINT        DEFAULT NULL COMMENT '所有者用户 ID',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_owner_id` (`owner_id`),
  KEY `idx_runtime_status` (`runtime_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型注册表';

-- 部署绑定表
CREATE TABLE IF NOT EXISTS `model_deploy_binding` (
  `id`                BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`          BIGINT        NOT NULL COMMENT '关联模型 ID（model_registry.id）',
  `bind_type`         VARCHAR(16)   NOT NULL COMMENT '绑定类型：container / image / both',
  `container_id`      VARCHAR(64)   DEFAULT NULL COMMENT 'Docker 容器 ID',
  `container_name`    VARCHAR(128)  DEFAULT NULL COMMENT 'Docker 容器名称',
  `image_name`        VARCHAR(256)  DEFAULT NULL COMMENT 'Docker 镜像全名（含 tag）',
  `host_ip`           VARCHAR(64)   NOT NULL DEFAULT '127.0.0.1' COMMENT '宿主机 IP',
  `host_port`         INT           DEFAULT NULL COMMENT '宿主机映射端口',
  `container_port`    INT           DEFAULT NULL COMMENT '容器内部端口',
  `inference_path`    VARCHAR(256)  DEFAULT NULL COMMENT '推理接口路径（如 /predict）',
  `health_check_url`  VARCHAR(512)  DEFAULT NULL COMMENT '健康检查路径（如 /health）',
  `gpu_device`        VARCHAR(64)   DEFAULT NULL COMMENT 'GPU 设备映射（已废弃，请使用 container_config.gpus）',
  `extra_mounts`      JSON          DEFAULT NULL COMMENT '挂载卷 [{"host":"...","container":"..."}]',
  `extra_env`         JSON          DEFAULT NULL COMMENT '环境变量 {"KEY":"VALUE"}',
  `container_config`  JSON          DEFAULT NULL COMMENT 'Docker 容器运行时配置',
  `remark`            VARCHAR(256)  DEFAULT NULL COMMENT '备注',
  `create_time`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  KEY `idx_container_id` (`container_id`),
  CONSTRAINT `fk_binding_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型部署绑定表';

-- IO Schema 表
CREATE TABLE IF NOT EXISTS `model_io_schema` (
  `id`          BIGINT    NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`    BIGINT    NOT NULL COMMENT '关联模型 ID',
  `inputs`      JSON      DEFAULT NULL COMMENT '输入 Schema',
  `outputs`     JSON      DEFAULT NULL COMMENT '输出 Schema',
  `create_time` DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  CONSTRAINT `fk_schema_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型 IO Schema';

-- 操作日志表
CREATE TABLE IF NOT EXISTS `model_operation_log` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`     BIGINT       NOT NULL COMMENT '关联模型 ID',
  `operator_id`  BIGINT       DEFAULT NULL COMMENT '操作者用户 ID',
  `operation`    VARCHAR(32)  NOT NULL COMMENT '操作类型：start/stop/restart/rebuild/bind/unbind/delete',
  `detail`       JSON         DEFAULT NULL COMMENT '操作详情',
  `result`       VARCHAR(16)  NOT NULL COMMENT '结果：success/failed',
  `error_msg`    VARCHAR(512) DEFAULT NULL COMMENT '失败原因',
  `create_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_model_id` (`model_id`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型操作日志';
