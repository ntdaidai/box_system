ALTER TABLE safety_event
    ADD COLUMN IF NOT EXISTS max_risk_level VARCHAR(16) NOT NULL DEFAULT 'NONE' COMMENT '最高风险等级' AFTER risk_level,
    ADD COLUMN IF NOT EXISTS handling_mode VARCHAR(32) NOT NULL DEFAULT 'AUTO' COMMENT '处置责任模式: AUTO/AUTO_DEVICE/MANUAL' AFTER max_risk_level,
    ADD COLUMN IF NOT EXISTS disposal_status VARCHAR(32) NOT NULL DEFAULT 'MONITORING' COMMENT '处置状态' AFTER handling_mode,
    ADD COLUMN IF NOT EXISTS target_status VARCHAR(32) NOT NULL DEFAULT 'IN_DANGER' COMMENT '目标状态' AFTER disposal_status,
    ADD COLUMN IF NOT EXISTS medium_entered_at DATETIME NULL COMMENT '进入中风险时间' AFTER low_entered_at;

ALTER TABLE safety_event_task
    ADD COLUMN IF NOT EXISTS accepted_at DATETIME NULL COMMENT '接单时间' AFTER dispatched_at;

ALTER TABLE event_action
    MODIFY COLUMN action_type VARCHAR(64) NULL COMMENT 'Action type, e.g. AUTO_BROADCAST',
    ADD COLUMN IF NOT EXISTS risk_level VARCHAR(16) NULL COMMENT 'Safety event risk level' AFTER camera_id,
    ADD COLUMN IF NOT EXISTS drone_id VARCHAR(64) NULL COMMENT 'Drone id' AFTER device_id,
    ADD COLUMN IF NOT EXISTS strategy_id VARCHAR(64) NULL COMMENT 'Drone strategy id' AFTER drone_id,
    ADD COLUMN IF NOT EXISTS dispatch_time DATETIME NULL COMMENT 'Drone dispatch time' AFTER start_time;
