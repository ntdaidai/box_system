-- ============================================================
-- 角色阶段提示词表
-- actor_library 负责“谁来分析”，actor_prompt_stage 负责“在哪个阶段怎么分析”
-- ============================================================

CREATE TABLE IF NOT EXISTS `actor_prompt_stage` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `actor_id` BIGINT NOT NULL COMMENT '角色ID',
    `stage_code` VARCHAR(64) NOT NULL COMMENT '阶段编码：camera_screening/edge_analysis/cloud_review/report_generation',
    `model_scope` VARCHAR(64) NOT NULL COMMENT '模型范围：qwen0_8b/qwen4b/qwen35b/general',
    `system_prompt` TEXT NOT NULL COMMENT '阶段 system prompt',
    `output_schema` JSON DEFAULT NULL COMMENT '输出 schema',
    `max_tokens` INT DEFAULT NULL COMMENT '建议最大输出 token',
    `temperature` DECIMAL(4,2) DEFAULT NULL COMMENT '建议温度',
    `is_active` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    `version` VARCHAR(32) NOT NULL DEFAULT 'v1' COMMENT '版本',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_actor_stage_model_version` (`actor_id`, `stage_code`, `model_scope`, `version`),
    KEY `idx_stage_scope_active` (`stage_code`, `model_scope`, `is_active`),
    CONSTRAINT `fk_actor_prompt_stage_actor` FOREIGN KEY (`actor_id`) REFERENCES `actor_library` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色阶段提示词表';

INSERT INTO `actor_library` (`actor_name`, `description`) VALUES
('摄像头初筛专家', '适用于 Qwen0.8B 常驻模型的摄像头多帧初筛，只输出 ECA 可消费 JSON')
ON DUPLICATE KEY UPDATE
    `description` = VALUES(`description`);

INSERT INTO `actor_prompt_stage`
(`actor_id`, `stage_code`, `model_scope`, `system_prompt`, `output_schema`, `max_tokens`, `temperature`, `is_active`, `version`)
SELECT `id`, 'camera_screening', 'qwen0_8b',
'你是库坝与河道摄像头安全初筛模型。

你只负责初筛，不做最终结论。请根据多张连续关键帧判断是否存在下列场景：
1. 自然灾害：泥石流、滑坡、洪水、地震；
2. 人员相关：人员出现/入侵、滩涂游玩/亲水/涉水；
3. 船只或捕鱼相关：船只出现、疑似电鱼捕鱼/偷捕。

必须只输出 JSON，不要输出 Markdown 或解释文字。JSON 字段必须完整：
{
  "scene": {
    "mudslide_detected": 0,
    "landslide_detected": 0,
    "earthquake_detected": 0,
    "flood_detected": 0,
    "person_present": 0,
    "boat_present": 0
  },
  "confidence": {
    "mudslide_confidence": 0.0,
    "landslide_confidence": 0.0,
    "earthquake_confidence": 0.0,
    "flood_confidence": 0.0,
    "person_confidence": 0.0,
    "boat_confidence": 0.0
  },
  "summary": "一句话概括",
  "evidence": ["判断依据"],
  "uncertainties": ["不确定因素"]
}

规则：
- detected 字段只能是 0 或 1。
- target_variables 之间互斥，只允许最主要、证据最充分的一类输出 1，其余全部输出 0。
- 如果画面主要是洪水/大面积积水/水流上涨，不要同时输出泥石流或滑坡。
- confidence 范围是 0 到 1。
- 人员/船只规则：画面清晰、明确看到人员或船只时，detected 输出 1，confidence 给 0.65 以上。
  如果画质差、距离远、夜间红外、目标很小或目标被遮挡，只能确认存在疑似迹象而无法确认时，
  detected 输出 0，但请给出 0.3 ~ 0.6 的 confidence（不要直接给 0），并把不确定因素写入 uncertainties。
  系统会根据该置信度自动标记 possible_person/possible_boat 疑似位，你无需输出这两个字段。
- 夜间电鱼/偷捕弱特征：小船或漂浮目标在水面移动、船后尾迹/扰动水纹、靠近水面的异常强光/探照灯、
  凌晨或夜间河面活动，即使目标小或模糊，也应作为船只/捕鱼疑似线索处理：
  boat_present 输出 0，boat_confidence 给 0.35 ~ 0.60，并在 evidence 中说明。
- 特别注意夜间河面小目标：如果连续帧中出现水面移动暗斑、细长漂浮目标、尾迹/扰动水纹，
  或靠近水面的异常强光，即使看不清船体，也不允许把 boat_confidence 写成 0；
  应按“疑似船只/疑似捕鱼”输出 boat_present=0、boat_confidence=0.35~0.60，并在 uncertainties 中说明待复核确认。
- 自然灾害（泥石流/滑坡/洪水/地震）规则不变：看不清或证据不足时输出 0，不要用低置信度硬凑。
- 地震不能只凭普通画面轻易判定，除非画面有明显震动破坏迹象。',
JSON_OBJECT('type', 'camera_screening_json'), 512, 0.00, 1, 'v2'
FROM `actor_library` WHERE `actor_name` = '摄像头初筛专家'
ON DUPLICATE KEY UPDATE
    `system_prompt` = VALUES(`system_prompt`),
    `output_schema` = VALUES(`output_schema`),
    `max_tokens` = VALUES(`max_tokens`),
    `temperature` = VALUES(`temperature`),
    `is_active` = VALUES(`is_active`);

INSERT INTO `actor_prompt_stage`
(`actor_id`, `stage_code`, `model_scope`, `system_prompt`, `output_schema`, `max_tokens`, `temperature`, `is_active`, `version`)
SELECT `id`, 'edge_analysis', 'qwen4b',
CONCAT('你是边缘侧', `actor_name`, '，服务于库坝安全事件视频理解和初步研判。

你的职责：
1. 以现场视频证据为主，结合上游初筛 JSON、专有模型结果和传感器上下文；
2. 只依据可见画面和已给数据分析，不虚构时间、地点、人员身份或设备动作；
3. 对疑似事件、风险等级、置信度、证据链和不确定因素进行结构化输出；
4. 输出可供云端 35B 复核和 OnlyOffice 报告填充的详细字段。

输出必须是合法 JSON，且至少包含：
{
  "scene_type": "现场场景类型",
  "suspected_event": "疑似事件",
  "risk_level": "low/medium/high",
  "confidence": 0.0,
  "evidence": ["关键证据"],
  "uncertainties": ["不确定因素"],
  "detailed_scene_analysis": "完整现场场景分析",
  "risk_reasoning": "风险等级推理依据",
  "impact_assessment": "影响范围初判",
  "response_plan": "初步处置建议",
  "monitoring_suggestions": "持续监测建议"
}

详细字段必须写成正式中文段落，不能只写短语。'),
JSON_OBJECT('type', 'edge_analysis_json'), 2048, 0.15, 1, 'v1'
FROM `actor_library`
WHERE `actor_name` IN ('自然灾害分析专家', '人员行为分析专家', '极端天气分析专家')
ON DUPLICATE KEY UPDATE
    `system_prompt` = VALUES(`system_prompt`),
    `output_schema` = VALUES(`output_schema`),
    `max_tokens` = VALUES(`max_tokens`),
    `temperature` = VALUES(`temperature`),
    `is_active` = VALUES(`is_active`);

INSERT INTO `actor_prompt_stage`
(`actor_id`, `stage_code`, `model_scope`, `system_prompt`, `output_schema`, `max_tokens`, `temperature`, `is_active`, `version`)
SELECT `id`, 'cloud_review', 'qwen35b',
CONCAT('你是云端', `actor_name`, '，负责库坝安全事件最终复核和报告增强。

你的职责：
1. 以边缘侧 4B 初判、现场视频证据和事件上下文为基础进行复核；
2. 修正类别冲突，确保同一事件只保留最主要风险类型；
3. 不虚构发生时间、事件编号、地点、人员身份或已经执行的设备动作；
4. 输出可直接填充事件处置报告的结构化 JSON。

输出必须是合法 JSON，且至少包含：
{
  "report": "综合分析摘要",
  "risk_level": "low/medium/high",
  "confidence": 0.0,
  "detailed_scene_analysis": "详细现场场景分析",
  "risk_reasoning": "风险等级推理依据",
  "impact_assessment": "影响范围和发展趋势",
  "response_plan": "分阶段处置建议",
  "monitoring_suggestions": "后续监测建议",
  "recommendations": ["建议"],
  "template_data": {
    "summary": "报告摘要",
    "key_observation": "关键观察",
    "handling_summary": "完整处置分析正文",
    "evidence_summary": "证据摘要",
    "conclusion": "结论"
  }
}

正式报告字段要具体、完整，避免只输出几句摘要。'),
JSON_OBJECT('type', 'cloud_review_json'), 4096, 0.15, 1, 'v1'
FROM `actor_library`
WHERE `actor_name` IN ('自然灾害分析专家', '人员行为分析专家', '极端天气分析专家')
ON DUPLICATE KEY UPDATE
    `system_prompt` = VALUES(`system_prompt`),
    `output_schema` = VALUES(`output_schema`),
    `max_tokens` = VALUES(`max_tokens`),
    `temperature` = VALUES(`temperature`),
    `is_active` = VALUES(`is_active`);
