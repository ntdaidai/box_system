ALTER TABLE safety_event
    ADD COLUMN IF NOT EXISTS video_status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '留证视频状态' AFTER video_url,
    ADD COLUMN IF NOT EXISTS video_error VARCHAR(500) NULL COMMENT '留证视频失败原因' AFTER video_status,
    ADD COLUMN IF NOT EXISTS video_created_at DATETIME NULL COMMENT '留证视频生成完成时间' AFTER video_error,
    ADD COLUMN IF NOT EXISTS video_expires_at DATETIME NULL COMMENT '留证视频留档到期时间' AFTER video_created_at;
