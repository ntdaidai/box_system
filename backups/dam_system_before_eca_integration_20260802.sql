-- MySQL dump 10.13  Distrib 8.0.46, for Linux (aarch64)
--
-- Host: 192.168.31.52    Database: dam_system
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `action_flow`
--

DROP TABLE IF EXISTS `action_flow`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_flow` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '流程ID',
  `flow_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '流程名称，如滑坡分析流程',
  `flow_code` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '流程编码',
  `timeout_seconds` int DEFAULT '300' COMMENT '超时时间（秒）',
  `failure_strategy` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'retry' COMMENT '失败策略: retry-重试/abort-终止/skip-跳过',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '流程描述',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `flow_code` (`flow_code`),
  KEY `idx_flow_code` (`flow_code`),
  KEY `idx_is_activate` (`is_activate`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行为流程库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_flow`
--

LOCK TABLES `action_flow` WRITE;
/*!40000 ALTER TABLE `action_flow` DISABLE KEYS */;
INSERT INTO `action_flow` VALUES (5,'一般预警处理流程','GENERAL_ALERT',120,'skip','一般预警事件的处理流程',1,'2026-07-04 16:25:01','2026-07-04 16:25:01'),(6,'紧急告警处理流程','EMERGENCY_ALERT',60,'abort','紧急告警事件的处理流程',1,'2026-07-04 16:25:01','2026-07-04 16:25:01'),(9,'风灾预警响应流程','WIND_WARNING',120,'continue','6-7级风预警，只做监测记录',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(10,'风灾警报响应流程','WIND_ALERT',180,'continue','8-9级风警报，YOLO检测+告警',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(11,'风灾紧急响应流程','WIND_EMERGENCY',300,'continue','10级以上风灾，全模型分析+紧急告警',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(12,'风灾裂缝响应流程','WIND_CRACK_RESPONSE',300,'continue','风灾导致裂缝的应急响应',1,'2026-07-07 10:47:26','2026-07-07 10:47:26'),(13,'风灾渗水响应流程','WIND_SEEPAGE_RESPONSE',300,'continue','风灾导致渗水的应急响应',1,'2026-07-07 10:47:26','2026-07-07 10:47:26'),(14,'风灾护坡损坏响应流程','WIND_SLOPE_RESPONSE',300,'continue','风灾导致护坡损坏的应急响应',1,'2026-07-07 10:47:26','2026-07-07 10:47:26'),(15,'风灾闸门变形响应流程','WIND_GATE_RESPONSE',300,'continue','风灾导致闸门变形的应急响应',1,'2026-07-07 10:47:26','2026-07-07 10:47:26'),(16,'温度告警响应流程','TEMP_ALERT',120,'continue','温度异常告警响应',1,'2026-07-08 15:51:14','2026-07-08 15:51:14'),(17,'湿度告警流程','HUMIDITY_ALERT',120,'continue','湿度异常告警',1,'2026-07-08 16:51:18','2026-07-08 16:51:18'),(18,'测试Qwen流程','TEST_QWEN_FLOW',300,'continue','测试Qwen模型调用',1,'2026-07-09 10:05:31','2026-07-09 10:05:31');
/*!40000 ALTER TABLE `action_flow` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_step`
--

DROP TABLE IF EXISTS `action_step`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_step` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '步骤ID',
  `flow_id` bigint NOT NULL COMMENT '所属流程ID',
  `step_order` int NOT NULL DEFAULT '1' COMMENT '步骤顺序',
  `step_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '步骤名称',
  `action_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '动作类型: llm-大模型推理/alert-告警/script-脚本/http-接口',
  `model_id` bigint DEFAULT NULL COMMENT '关联模型ID（action_type为llm时使用）',
  `parameter` json DEFAULT NULL COMMENT '步骤参数（JSON格式）',
  `retry_count` int DEFAULT '0' COMMENT '重试次数',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '步骤描述',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `model_id` (`model_id`),
  KEY `idx_flow_id` (`flow_id`),
  KEY `idx_action_type` (`action_type`),
  CONSTRAINT `action_step_ibfk_1` FOREIGN KEY (`flow_id`) REFERENCES `action_flow` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `action_step_ibfk_2` FOREIGN KEY (`model_id`) REFERENCES `model_library` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行为步骤库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_step`
--

LOCK TABLES `action_step` WRITE;
/*!40000 ALTER TABLE `action_step` DISABLE KEYS */;
INSERT INTO `action_step` VALUES (13,5,1,'发送通知','alert',NULL,'{\"level\": 1, \"channels\": [\"app\"], \"template\": \"预警通知：{event_name}，详情：{details}\"}',0,'发送APP通知','2026-07-04 16:25:25','2026-07-04 16:25:25'),(14,6,1,'发送告警','alert',NULL,'{\"level\": 3, \"channels\": [\"sms\", \"app\", \"siren\"], \"template\": \"紧急告警：{event_name}，{details}\"}',0,'发送紧急告警','2026-07-04 16:25:25','2026-07-04 16:25:25'),(15,6,2,'摄像头抓拍','script',NULL,'{\"action\": \"snapshot\", \"camera_id\": 5, \"save_path\": \"/data/camera/alerts/emergency/\"}',1,'触发摄像头抓拍','2026-07-04 16:25:25','2026-07-04 16:25:25'),(19,9,1,NULL,'script',NULL,'{\"action\": \"log\", \"message\": \"风速预警: {wind_speed_ms}m/s\", \"priority\": 1}',0,'记录风速日志','2026-07-07 10:23:37','2026-07-07 10:23:37'),(20,10,1,NULL,'llm',2,'{\"prompt\": \"检测大坝表面裂缝、渗水、结构位移等风灾导致的异常\", \"priority\": 1}',0,'YOLO检测风灾损害','2026-07-07 10:23:37','2026-07-07 10:43:01'),(21,10,2,NULL,'alert',NULL,'{\"level\": 2, \"channels\": [\"app\", \"sms\"], \"priority\": 1, \"template\": \"风灾警报：当前风速{wind_speed_ms}m/s，请注意安全\"}',0,'发送风灾警报','2026-07-07 10:23:37','2026-07-07 10:23:37'),(22,11,1,NULL,'llm',2,'{\"prompt\": \"检测大坝表面裂缝、渗水、护坡损坏、闸门变形等严重风灾损害\", \"priority\": 1}',0,'YOLO检测风灾损害','2026-07-07 10:23:37','2026-07-07 10:43:01'),(23,11,3,NULL,'llm',1,'{\"prompt\": \"综合分析风灾对大坝安全的影响，评估风险等级，生成应急处置建议\", \"priority\": 3}',0,'Qwen综合分析','2026-07-07 10:23:37','2026-07-07 10:43:01'),(24,11,4,NULL,'alert',NULL,'{\"level\": 3, \"channels\": [\"app\", \"sms\", \"phone\"], \"priority\": 1, \"template\": \"紧急风灾警报：当前风速{wind_speed_ms}m/s，已达{wind_level}级，立即撤离危险区域！\"}',0,'发送紧急风灾警报','2026-07-07 10:23:37','2026-07-07 10:23:37'),(25,11,2,NULL,'llm',7,'{\"prompt\": \"分割受损区域，计算裂缝长度、渗水面积等量化指标\", \"priority\": 2}',0,'SAM分割受损区域','2026-07-07 10:26:08','2026-07-07 10:43:01'),(26,12,1,NULL,'llm',5,'{\"prompt\": \"精确检测裂缝位置、长度、宽度，评估裂缝严重程度\", \"priority\": 1}',0,'YOLO检测裂缝','2026-07-07 10:47:26','2026-07-07 10:47:26'),(27,12,2,NULL,'llm',7,'{\"prompt\": \"分割裂缝区域，精确计算裂缝长度和面积\", \"priority\": 2}',0,'SAM分割裂缝区域','2026-07-07 10:47:26','2026-07-07 10:47:26'),(28,12,3,NULL,'llm',1,'{\"prompt\": \"分析裂缝成因（风灾导致），评估对大坝结构安全的影响，建议处置措施\", \"priority\": 3}',0,'Qwen分析裂缝风险','2026-07-07 10:47:26','2026-07-07 10:47:26'),(29,12,4,NULL,'alert',NULL,'{\"level\": 3, \"channels\": [\"app\", \"sms\", \"phone\"], \"priority\": 1, \"template\": \"风灾裂缝警报：风速{wind_speed_ms}m/s条件下检测到大坝裂缝，长度约{crack_length}m，请立即排查！\"}',0,'发送风灾裂缝警报','2026-07-07 10:47:26','2026-07-07 10:47:26'),(30,13,1,NULL,'llm',6,'{\"prompt\": \"检测渗水点位置、渗水量，评估渗水严重程度\", \"priority\": 1}',0,'YOLO检测渗水','2026-07-07 10:47:26','2026-07-07 10:47:26'),(31,13,2,NULL,'llm',7,'{\"prompt\": \"分割渗水区域，计算渗水面积\", \"priority\": 2}',0,'SAM分割渗水区域','2026-07-07 10:47:26','2026-07-07 10:47:26'),(32,13,3,NULL,'llm',1,'{\"prompt\": \"分析渗水成因（风灾导致），评估渗透稳定性风险，建议处置措施\", \"priority\": 3}',0,'Qwen分析渗水风险','2026-07-07 10:47:26','2026-07-07 10:47:26'),(33,13,4,NULL,'alert',NULL,'{\"level\": 3, \"channels\": [\"app\", \"sms\", \"phone\"], \"priority\": 1, \"template\": \"风灾渗水警报：风速{wind_speed_ms}m/s条件下检测到大坝渗水，面积约{seepage_area}m²，请立即排查！\"}',0,'发送风灾渗水警报','2026-07-07 10:47:26','2026-07-07 10:47:26'),(34,9,2,NULL,'alert',NULL,'{\"level\": 1, \"channels\": [\"app\"], \"priority\": 1, \"template\": \"大风告警：当前风速{wind_speed_ms}m/s，请注意防范\"}',0,'发送预警通知','2026-07-07 13:10:00','2026-07-07 15:24:46'),(35,16,1,NULL,'alert',NULL,'{\"level\": 1, \"channels\": [\"app\"], \"priority\": 1, \"template\": \"温度告警：当前温度{temperature}℃，请注意设备运行状态\"}',0,'发送温度告警','2026-07-08 15:51:14','2026-07-08 15:51:14'),(37,17,1,NULL,'llm',1,'{\"prompt\": \"分析当前湿度环境对大坝安全的影响，评估风险等级，给出防护建议\", \"priority\": 1}',0,'Qwen分析湿度风险','2026-07-09 10:03:15','2026-07-09 10:03:15'),(38,17,2,NULL,'alert',NULL,'{\"level\": 2, \"priority\": 1, \"template\": \"湿度告警：当前相对湿度{humidity}%，Qwen分析结果已生成\"}',0,'发送湿度告警','2026-07-09 10:03:15','2026-07-09 10:03:15'),(39,18,1,NULL,'llm',1,'{\"prompt\": \"请你作为大坝安全监测专家，分析当前传感器数据和图像，评估大坝安全状况。\", \"priority\": 1, \"image_url\": \"http://localhost:9000/dam/2026-07-09/test.png\", \"max_tokens\": 2048, \"temperature\": 0.15}',0,'Qwen分析','2026-07-09 10:05:31','2026-07-09 12:41:32'),(40,18,2,NULL,'alert',NULL,'{\"level\": 2, \"priority\": 1, \"template\": \"测试告警：风速{wind_speed_ms}m/s\\n\\nQwen分析结果：\\n{step_1_response}\"}',0,'发送告警','2026-07-09 10:05:31','2026-07-09 12:44:43');
/*!40000 ALTER TABLE `action_step` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `actor_library`
--

DROP TABLE IF EXISTS `actor_library`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `actor_library` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `actor_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '角色名称',
  `description` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '角色描述',
  `local_system_prompt` text COLLATE utf8mb4_unicode_ci COMMENT '边缘模型系统提示词（Qwen-VL-4B）',
  `cloud_system_prompt` text COLLATE utf8mb4_unicode_ci COMMENT '云端模型系统提示词（A100 大模型）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_actor_name` (`actor_name`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `actor_library`
--

LOCK TABLES `actor_library` WRITE;
/*!40000 ALTER TABLE `actor_library` DISABLE KEYS */;
INSERT INTO `actor_library` VALUES (1,'灾害分析专家','负责灾害场景识别与风险评估的专业角色','你是边缘侧灾害巡查智能分析模型。\n\n你的任务：\n1. 根据现场图像理解场景；\n2. 结合专有模型检测结果；\n3. 结合环境传感器数据；\n4. 判断是否存在灾害风险；\n5. 输出结构化分析结果。\n\n注意：\n你的输出作为云端大模型增强推理的参考依据，不是最终结论。\n\n请严格按照以下 JSON 格式输出，不要输出其他内容：\n{\n    \"scene_description\": \"场景描述\",\n    \"risk_level\": \"low/medium/high\",\n    \"confidence\": 0.0-1.0,\n    \"evidence\": [\"判断依据1\", \"判断依据2\"],\n    \"uncertainties\": [\"不确定因素1\", \"不确定因素2\"]\n}','你是云端灾害分析增强模型。\n\n你的任务：\n1. 接收边缘侧初步分析结果；\n2. 结合上传的关键图像和视频；\n3. 进行深度分析和长上下文推理；\n4. 生成详细的灾害评估报告。\n\n输出要求：\n- 场景详细描述\n- 灾害类型判定\n- 风险等级评估\n- 影响范围分析\n- 应急处置建议\n- 后续监测方案');
/*!40000 ALTER TABLE `actor_library` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `alarm`
--

DROP TABLE IF EXISTS `alarm`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarm` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '告警ID',
  `alarm_code` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '告警编码',
  `device_id` int DEFAULT NULL COMMENT '关联设备ID',
  `alarm_type` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '告警类型: threshold-阈值告警/manual-人工告警/ai-AI告警',
  `alarm_level` int DEFAULT NULL COMMENT '告警级别: 1-低 2-中 3-高',
  `alarm_content` text COLLATE utf8mb4_unicode_ci COMMENT '告警内容',
  `alarm_time` datetime DEFAULT NULL COMMENT '告警触发时间',
  `handle_status` int DEFAULT '0' COMMENT '处理状态: 0-未处理 1-已处理',
  `handle_user` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '处理人用户名',
  `handle_time` datetime DEFAULT NULL COMMENT '处理时间',
  `handle_remark` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '处理备注',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_device_id` (`device_id`),
  KEY `idx_alarm_type` (`alarm_type`),
  KEY `idx_alarm_level` (`alarm_level`),
  KEY `idx_handle_status` (`handle_status`),
  KEY `idx_alarm_time` (`alarm_time`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alarm`
--

LOCK TABLES `alarm` WRITE;
/*!40000 ALTER TABLE `alarm` DISABLE KEYS */;
INSERT INTO `alarm` VALUES (13,'ECA_34_1783484813',2,'threshold',1,'大风告警：当前风速4.9m/s，请注意防范','2026-07-08 12:26:54',0,NULL,NULL,NULL,'2026-07-08 12:26:53'),(14,'ECA_34_1783564943',2,'threshold',1,'大风告警：当前风速1.6m/s，请注意防范','2026-07-09 10:42:23',0,NULL,NULL,NULL,'2026-07-09 10:42:23'),(15,'ECA_40_1783565018',2,'threshold',2,'测试告警：风速1.6m/s，Qwen分析已完成','2026-07-09 10:43:38',0,NULL,NULL,NULL,'2026-07-09 10:43:38'),(16,'ECA_34_1783572413',2,'threshold',1,'大风告警：当前风速3.7m/s，请注意防范','2026-07-09 12:46:54',0,NULL,NULL,NULL,'2026-07-09 12:46:53'),(17,'ECA_40_1783572495',2,'threshold',2,'测试告警：风速3.7m/s\n\nQwen分析结果：\n**大坝安全监测评估报告**\n\n**评估时间**：当前数据采集时刻  \n**评估人**：大坝安全监测专家\n\n---\n\n### 一、环境气象条件分析\n\n- **温度**：当前温度为 26.3°C（传感器读数），历史温度 27.87°C，处于正常范围，无异常升温或骤降，对大坝结构无热应力风险。\n- **湿度**：44.9%，属中等偏干，有利于减少渗流风险，无潮湿诱发裂缝或侵蚀的迹象。\n- **风速**...','2026-07-09 12:48:16',0,NULL,NULL,NULL,'2026-07-09 12:48:15'),(18,'ECA_40_1783581523',2,'threshold',2,'测试告警：风速4.2m/s\n\nQwen分析结果：\n作为大坝安全监测专家，我已对当前传感器数据和图像（虽未提供图像，但基于数据可进行综合评估）进行分析，现将安全状况评估如下：\n\n---\n\n✅ **一、环境气象条件评估**\n\n- **温度**：当前温度为24.5°C（传感器数据）和26.65°C（温度字段，可能为不同传感器或重复），均处于正常范围，无异常热应力风险。\n- **湿度**：42.4%，属干燥至中等湿度，对混凝土结构无明显不利影响。\n- **风速**：4.2 m/s（约15.14 km/h），风力等级3级（轻风），对大坝结构无显著影响。\n- **降雨**：今日、昨日、小时、24小时最大降雨均为0.0mm，累计降雨7.1mm（可能为历史或前日数据），当前无降水影响，无渗流风险。\n- **风向**：东风（93°），对大坝迎风面无特殊冲击，结构受力正常。\n\n→ **结论**：当前气象条件稳定，无极端天气影响，环境因素对大坝安全无威胁。\n\n---\n\n✅ **二、结构动态监测数据评估**\n\n- **加速度**（X/Y/Z）及**幅值**：全部为0.0，表明无振动或冲击荷载作用，结构处于静止稳定状态。\n- **速度**（X/Y/Z）：全部为0.0，无结构运动迹象。\n- **位移**（X/Y/Z）：全部为0.0，结构无明显变形或沉降。\n- **频率**（X/Y/Z）：全部为0.0，无共振或异常振动频率。\n\n→ **结论**：结构动态响应正常，无异常振动或位移，表明大坝结构当前处于静态稳定状态。\n\n---\n\n✅ **三、安全预警系统评估**\n\n- **裂缝检测**：0（无裂缝）\n- **渗流检测**：0（无渗漏）\n- **边坡损伤检测**：0（无滑坡或边坡破坏迹象）\n- **闸门变形检测**：0（无闸门异常变形）\n\n→ **结论**：所有关键安全预警指标均为“0”，表明当前无结构损伤或功能异常，安全系统未触发任何警报。\n\n---\n\n✅ **四、综合安全评估**\n\n当前所有传感器数据均显示：\n\n- 环境条件稳定，无极端气象影响；\n- 结构动态参数正常，无振动、位移或变形；\n- 安全监测系统未检测到任何异常（裂缝、渗流、边坡、闸门变形）；\n- 数据连续性良好，无突变或异常值。\n\n---\n\n🟢 **最终安全评估结论：**\n\n> **大坝当前安全状况良好，处于正常稳定运行状态。无任何安全隐患或异常征兆。建议继续保持常规监测，但无需采取紧急措施或调整运行策略。**\n\n如后续出现降雨、温度骤变、风力增强或传感器数据突变，应立即启动预警机制并进行复核。\n\n---\n\n如需进一步分析历史趋势、传感器校准或图像辅助诊断，请提供更详细数据或图像资料。\n\n—— 大坝安全监测专家  \n2025年4月5日','2026-07-09 15:18:44',0,NULL,NULL,NULL,'2026-07-09 15:18:43'),(19,'ECA_40_1784526738',2,'threshold',2,'测试告警：风速1.5m/s\n\nQwen分析结果：\n作为大坝安全监测专家，我已接收并分析了您提供的传感器数据。基于这些数据，我为您生成了一份**大坝安全状况评估报告**。\n\n### 📊 数据概览与异常检测\n\n首先，我们观察数据中的关键异常指标：\n\n1.  **温度异常**：\n    *   当前实测温度：**25.39°C**（显著高于 23.2°C 的基准值）。\n    *   分析：大坝运行温度通常控制在 20-25°C 之间。25.39°C 表明大坝内部或周围存在**过热风险**。这可能源于：\n        *   大坝内部冷却系统失效。\n        *   大坝表面存在大量未排出的热辐射（如混凝土裂缝或破损）。\n        *   大坝周边植被或水体温度异常升高。\n    *   **结论**：**存在潜在过热隐患，需立即关注并排查散热问题。**\n\n2.  **降雨数据**：\n    *   近期降雨量：**7.1 mm**（0.0 小时降雨，0.0 分钟降雨）。\n    *   分析：降雨量极低，且无连续降雨记录。\n    *   **结论**：当前降雨风险**极低**。大坝处于相对干燥状态，无需担心因降雨导致的渗流或冲刷问题。\n\n3.  **风环境**：\n    *   风速：**5.6 km/h**（1.5 m/s），风向为**东**。\n    *   分析：风速在安全范围内（通常大坝设计风速为 2-4 m/s 或更高，具体取决于坝体类型）。\n    *   **结论**：风荷载安全，无风蚀风险。\n\n4.  **位移与加速度**：\n    *   位移：0.0 m（无宏观位移）。\n    *   加速度：0.0 m/s²（无明显振动）。\n    *   **结论**：大坝结构稳定，无明显的机械振动或位移异常。\n\n5.  **裂缝与渗流**：\n    *   裂缝检测：**0**\n    *   渗流检测：**0**\n    *   **结论**：无结构性裂缝或渗流通道，结构完整性良好。\n\n---\n\n### 🏗️ 综合安全评估结论\n\n#### ✅ 总体安全评级：**安全（S）**\n**判定依据**：\n*   **结构完整性**：无裂缝、无渗流、无位移。\n*   **运行状态**：无过热迹象，无风蚀风险。\n*   **环境因素**：降雨量极低，风荷载安全。\n\n#### ⚠️ 重点关注项（需立即行动）\n尽管整体安全，但**温度异常**是当前的首要关注点。\n*   **风险等级**：中等偏高（需立即核实）。\n*   **潜在原因**：\n    1.  **内部散热失效**：大坝内部冷却系统（如风冷、水冷或自然对流）可能堵塞、损坏或效率低下。\n    2.  **表面热辐射**：大坝表面可能存在大面积的混凝土裂缝、破损或老化，导致大量热量散发。\n    3.  **外部热源**：大坝周边温度异常升高（如周边水体温度过高或植被生长旺盛）。\n\n#### 🚨 建议采取的措施\n1.  **立即核查**：联系大坝运维团队，检查大坝内部冷却系统的运行状态，确认是否存在堵塞或故障。\n2.  **表面检查**：对大坝表面进行红外热成像或目视检查，寻找裂缝、破损或热辐射源。\n3.  **监测预警**：\n    *   密切监控温度曲线，设定报警阈值（建议设定在 28°C 以上）。\n    *   若温度持续上升，需启动应急预案（如增加冷却、封闭区域或暂停部分坝体作业）。\n4.  **气象预警**：鉴于降雨量极低，建议关注未来 24 小时的气象预报，确保无突发暴雨。\n\n---\n\n**专家总结**：\n当前大坝运行环境**整体安全**，但**温度异常**是必须立即排查的隐患。请优先关注大坝内部散热系统的运行状况，一旦确认散热正常，即可恢复正常监测。','2026-07-20 05:52:18',1,'系统','2026-07-20 09:04:53','已确认并处理','2026-07-20 13:52:18'),(20,'ECA_40_1785160649',2,'threshold',2,'测试告警：风速1.7m/s\n\nQwen分析结果：\n[错误] 模型调用失败: HTTP 404','2026-07-27 13:57:30',0,NULL,NULL,NULL,'2026-07-27 21:57:29'),(21,'ECA_40_1785246845',2,'threshold',2,'测试告警：风速3.8m/s\n\nQwen分析结果：\n[错误] 模型调用失败: HTTP 404','2026-07-28 13:54:06',1,'系统','2026-07-30 14:46:09','已确认并处理','2026-07-28 21:54:05');
/*!40000 ALTER TABLE `alarm` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `analysis_report`
--

DROP TABLE IF EXISTS `analysis_report`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `analysis_report` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '报告ID',
  `report_title` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '报告标题',
  `report_type` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '报告类型: vision-视觉分析/manual-人工分析/daily-日报',
  `risk_level` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '风险等级: low-低/medium-中/high-高/critical-危急',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '报告内容（Markdown格式）',
  `ai_model` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '使用的AI模型',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_report_type` (`report_type`),
  KEY `idx_risk_level` (`risk_level`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分析报告表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `analysis_report`
--

LOCK TABLES `analysis_report` WRITE;
/*!40000 ALTER TABLE `analysis_report` DISABLE KEYS */;
INSERT INTO `analysis_report` VALUES (1,'2026-07-27 今日巡逻报告','daily','low','# 2026-07-27 今日巡逻报告\n\n- 摄像头: dahua_001\n- 安全事件总数: 0\n- 低风险: 0\n- 中风险: 0\n- 高风险: 0\n- 已闭环: 0\n- 未闭环: 0\n\n## 联动动作\n- 今日无联动动作','safety_event_engine','2026-07-27 14:18:11');
/*!40000 ALTER TABLE `analysis_report` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `broadcast_device`
--

DROP TABLE IF EXISTS `broadcast_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `broadcast_device` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `vendor_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `device_code` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `port` int DEFAULT NULL,
  `username` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `location` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL,
  `config_json` json DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `device_code` (`device_code`),
  KEY `ix_broadcast_device_vendor_type` (`vendor_type`),
  KEY `ix_broadcast_device_enabled` (`enabled`),
  KEY `ix_broadcast_device_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `broadcast_device`
--

LOCK TABLES `broadcast_device` WRITE;
/*!40000 ALTER TABLE `broadcast_device` DISABLE KEYS */;
INSERT INTO `broadcast_device` VALUES (1,'本机耳机/音响测试','LOCAL_AUDIO','local_audio_default',NULL,NULL,NULL,NULL,'OFFLINE','浏览器本机',0,NULL,'2026-07-25 11:25:26','2026-07-31 06:27:42'),(2,'Jetson USB外放','USB_AUDIO','jetson_usb_speaker',NULL,NULL,NULL,NULL,'ONLINE','Jetson USB音频输出',1,'{\"alsa_device\": \"plughw:2,0\"}','2026-07-30 06:26:14','2026-07-31 06:18:28');
/*!40000 ALTER TABLE `broadcast_device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `broadcast_template`
--

DROP TABLE IF EXISTS `broadcast_template`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `broadcast_template` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `risk_level` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `scene_type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_broadcast_template_risk_level` (`risk_level`),
  KEY `ix_broadcast_template_scene_type` (`scene_type`),
  KEY `ix_broadcast_template_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `broadcast_template`
--

LOCK TABLES `broadcast_template` WRITE;
/*!40000 ALTER TABLE `broadcast_template` DISABLE KEYS */;
INSERT INTO `broadcast_template` VALUES ('FISHING','非法捕鱼提醒',NULL,'FISHING','当前水域禁止非法捕鱼，请立即驶离。',1,'2026-07-25 11:25:26','2026-07-25 11:25:26'),('PERSON_HIGH','人员高风险紧急警告','HIGH','PERSON','紧急警告，当前区域存在重大安全风险，请立即撤离。',1,'2026-07-25 11:25:26','2026-07-25 11:25:26'),('PERSON_LOW','人员低风险提醒','LOW','PERSON','您已进入安全警戒区域，请立即远离水边危险区域。',1,'2026-07-25 11:25:26','2026-07-25 11:25:26'),('PERSON_MEDIUM','人员中风险警告','MEDIUM','PERSON','警告，请立即停止亲水活动并离开危险区域。',1,'2026-07-25 11:25:26','2026-07-25 11:25:26');
/*!40000 ALTER TABLE `broadcast_template` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `camera_broadcast_device`
--

DROP TABLE IF EXISTS `camera_broadcast_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `camera_broadcast_device` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `camera_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `broadcast_device_id` bigint NOT NULL,
  `create_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_camera_broadcast_device_broadcast_device_id` (`broadcast_device_id`),
  KEY `ix_camera_broadcast_device_camera_id` (`camera_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `camera_broadcast_device`
--

LOCK TABLES `camera_broadcast_device` WRITE;
/*!40000 ALTER TABLE `camera_broadcast_device` DISABLE KEYS */;
INSERT INTO `camera_broadcast_device` VALUES (1,'dahua_001',1,'2026-07-25 11:25:26'),(2,'dahua_001',2,'2026-07-30 06:26:14');
/*!40000 ALTER TABLE `camera_broadcast_device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `camera_detection_zone`
--

DROP TABLE IF EXISTS `camera_detection_zone`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `camera_detection_zone` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '区域ID',
  `camera_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '摄像头ID',
  `zone_name` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '区域名称',
  `zone_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '区域类型: warning_zone-警戒区/waterside_zone-亲水区/wading_zone-涉水区',
  `rect_x` decimal(8,6) NOT NULL COMMENT '左上角X坐标，0-1归一化',
  `rect_y` decimal(8,6) NOT NULL COMMENT '左上角Y坐标，0-1归一化',
  `rect_width` decimal(8,6) NOT NULL COMMENT '区域宽度，0-1归一化',
  `rect_height` decimal(8,6) NOT NULL COMMENT '区域高度，0-1归一化',
  `enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `zone_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '前端绘制区域唯一编号',
  `polygon_points` json DEFAULT NULL COMMENT '多边形顶点坐标，0-1归一化',
  `risk_level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'LOW' COMMENT '风险等级: LOW/MEDIUM/HIGH',
  `trigger_seconds` decimal(8,3) NOT NULL DEFAULT '10.000' COMMENT '触发持续时间秒数',
  PRIMARY KEY (`id`),
  KEY `idx_camera_detection_zone_camera_id` (`camera_id`),
  KEY `idx_camera_detection_zone_zone_type` (`zone_type`),
  KEY `idx_camera_detection_zone_enabled` (`enabled`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='摄像头虚拟检测区域表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `camera_detection_zone`
--

LOCK TABLES `camera_detection_zone` WRITE;
/*!40000 ALTER TABLE `camera_detection_zone` DISABLE KEYS */;
INSERT INTO `camera_detection_zone` VALUES (8,'dahua_001','警戒区 1','WARNING_ZONE',0.133618,0.333929,0.230277,0.283928,1,'2026-07-29 13:36:13','2026-07-29 13:36:13','WARNING_ZONE_1785159705817','[{\"x\": 0.133618, \"y\": 0.333929}, {\"x\": 0.363895, \"y\": 0.421429}, {\"x\": 0.146411, \"y\": 0.617857}, {\"x\": 0.146411, \"y\": 0.617857}]','MEDIUM',10.000),(9,'camera_zone','入口禁入区','WARNING_ZONE',0.100000,0.200000,0.300000,0.400000,1,'2026-07-30 13:35:16','2026-07-30 13:35:16','entry_area','[{\"x\": 0.1, \"y\": 0.2}, {\"x\": 0.4, \"y\": 0.2}, {\"x\": 0.4, \"y\": 0.6}, {\"x\": 0.1, \"y\": 0.6}]','LOW',10.000);
/*!40000 ALTER TABLE `camera_detection_zone` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `camera_device`
--

DROP TABLE IF EXISTS `camera_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `camera_device` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `camera_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设备ID',
  `camera_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设备名称',
  `brand` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '品牌: dahua/hikvision',
  `ip_address` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '摄像头IP地址',
  `rtsp_port` int NOT NULL COMMENT 'RTSP端口',
  `web_port` int NOT NULL COMMENT 'Web控制台端口',
  `web_proxy_port` int DEFAULT NULL COMMENT 'Web控制台本机监听端口',
  `username` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '登录账号',
  `password` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '登录密码',
  `rtsp_path` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RTSP通道路径',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '描述',
  `enabled` tinyint(1) NOT NULL COMMENT '是否启用',
  `last_online_at` datetime DEFAULT NULL COMMENT '最后在线时间',
  `last_error` text COLLATE utf8mb4_unicode_ci COMMENT '最后连接错误',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
  `install_address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '安装地址',
  `latitude` double DEFAULT NULL COMMENT '纬度',
  `longitude` double DEFAULT NULL COMMENT '经度',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_camera_device_camera_id` (`camera_id`),
  UNIQUE KEY `web_proxy_port` (`web_proxy_port`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `camera_device`
--

LOCK TABLES `camera_device` WRITE;
/*!40000 ALTER TABLE `camera_device` DISABLE KEYS */;
INSERT INTO `camera_device` VALUES (1,'dahua_001','一号点摄像头','dahua','10.1.1.65',554,80,12346,'admin','hhu@4208','cam/realmonitor?channel=1&subtype=0','监测一号点位',1,'2026-07-30 13:27:29','无法连接视频源','2026-07-29 16:18:55','2026-07-30 21:42:26','河海大学西康路校区图书馆',32.055156,118.75809);
/*!40000 ALTER TABLE `camera_device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `condition_library`
--

DROP TABLE IF EXISTS `condition_library`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `condition_library` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '条件ID',
  `condition_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '条件名称，如雨量>80mm/振动频率异常',
  `source_id` bigint NOT NULL COMMENT '数据源ID',
  `expression` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '条件表达式，如 rainfall > 80',
  `time_window` int DEFAULT '5' COMMENT '时间窗口（分钟）',
  `duration` int DEFAULT '0' COMMENT '持续时间（分钟），达到此时间才算触发',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '条件说明',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_source_id` (`source_id`),
  KEY `idx_condition_name` (`condition_name`),
  KEY `idx_is_activate` (`is_activate`),
  CONSTRAINT `condition_library_ibfk_1` FOREIGN KEY (`source_id`) REFERENCES `data_source` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='条件库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `condition_library`
--

LOCK TABLES `condition_library` WRITE;
/*!40000 ALTER TABLE `condition_library` DISABLE KEYS */;
INSERT INTO `condition_library` VALUES (8,'6级强风',2,'wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9',5,0,'风速10.8~13.9m/s',1,'2026-07-07 10:23:36','2026-07-09 14:35:14'),(9,'7级疾风',2,'wind_speed_ms >= 13.9 AND wind_speed_ms < 17.2',5,0,'风速13.9~17.2m/s',1,'2026-07-07 10:23:36','2026-07-07 16:31:59'),(10,'8级大风',2,'wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8',5,0,'风速17.2~20.8m/s',1,'2026-07-07 10:23:36','2026-07-07 16:32:01'),(11,'9级烈风',2,'wind_speed_ms >= 20.8 AND wind_speed_ms < 24.5',5,3,'风速20.8~24.5m/s',1,'2026-07-07 10:23:36','2026-07-07 16:32:02'),(12,'10级狂风',2,'wind_speed_ms >= 24.5 AND wind_speed_ms < 28.5',5,3,'风速24.5~28.5m/s',1,'2026-07-07 10:23:36','2026-07-07 16:32:04'),(13,'11级暴风',2,'wind_speed_ms >= 28.5 AND wind_speed_ms < 32.7',5,3,'风速28.5~32.7m/s',1,'2026-07-07 10:23:36','2026-07-07 16:32:06'),(14,'12级飓风',2,'wind_speed_ms >= 32.7',5,0,'风速≥32.7m/s',1,'2026-07-07 10:23:36','2026-07-07 16:32:11'),(23,'极低温',1,'temperature < -10',10,5,'温度<-10℃，高风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(24,'低温',1,'temperature >= -10 AND temperature < 0',10,5,'温度-10~0℃，中风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(25,'高温',1,'temperature >= 35 AND temperature < 40',10,5,'温度35~40℃，中风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(26,'极高温',1,'temperature >= 40',10,3,'温度≥40℃，高风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(28,'湿度极高',1,'humidity >= 90',5,0,'相对湿度≥90%，空气接近饱和',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(29,'湿度高',1,'humidity >= 80 AND humidity < 90',5,0,'相对湿度80%-90%，易凝露',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(30,'湿度低',1,'humidity >= 20 AND humidity < 30',5,0,'相对湿度20%-30%，偏干燥',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(31,'湿度极低',1,'humidity < 20',5,0,'相对湿度<20%，极度干燥',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(33,'检测到泥石流灾害',6,'mudslide_detected == 1',1,0,'AI检测到泥石流灾害',1,'2026-07-30 17:24:03','2026-07-30 17:25:29'),(34,'检测到滑坡灾害',6,'landslide_detected == 1',1,0,'AI检测到滑坡灾害',1,'2026-07-30 17:24:03','2026-07-30 17:25:35'),(35,'检测到地震灾害',6,'earthquake_detected == 1',1,0,'AI检测到地震灾害',1,'2026-07-30 17:24:03','2026-07-30 17:25:37'),(36,'检测到洪水灾害',6,'flood_detected == 1',1,0,'AI检测到洪水灾害',1,'2026-07-30 17:24:03','2026-07-30 19:26:56');
/*!40000 ALTER TABLE `condition_library` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_source`
--

DROP TABLE IF EXISTS `data_source`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_source` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '数据源ID',
  `source_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '数据源名称',
  `source_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '数据源类型: sensor-传感器/camera-摄像头/api-接口/file-文件',
  `device_id` int DEFAULT NULL COMMENT '关联设备ID（对应device表）',
  `data_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '数据路径或接口地址',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '描述',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_source_type` (`source_type`),
  KEY `idx_device_id` (`device_id`),
  KEY `idx_is_activate` (`is_activate`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_source`
--

LOCK TABLES `data_source` WRITE;
/*!40000 ALTER TABLE `data_source` DISABLE KEYS */;
INSERT INTO `data_source` VALUES (1,'温湿度传感器','sensor',NULL,NULL,'WS3000-485 温湿度传感器',1,'2026-07-08 15:50:38','2026-07-08 15:50:38'),(2,'风速风向传感器','sensor',2,'root.dam.sensor.wind','小聚碳一体式风速风向传感器',1,'2026-07-04 13:36:22','2026-07-04 13:36:22'),(4,'振动传感器','sensor',NULL,NULL,'WTVB05-485 振动传感器',1,'2026-07-08 15:50:38','2026-07-08 15:50:38'),(6,'大华摄像头','camera',NULL,'rtsp://admin:hhu%404208@10.1.1.65:554/cam/realmonitor?channel=1&subtype=0','海康威视H8系列摄像头 + AI视觉分析',1,'2026-07-07 10:47:26','2026-07-29 14:35:48');
/*!40000 ALTER TABLE `data_source` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event_action`
--

DROP TABLE IF EXISTS `event_action`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_action` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `event_id` bigint DEFAULT NULL,
  `flow_id` bigint DEFAULT NULL,
  `priority` int DEFAULT '0' COMMENT '执行优先级，数值越小优先级越高',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `action_type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `broadcast_event_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `camera_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `device_id` bigint DEFAULT NULL,
  `template_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `trigger_type` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content` text COLLATE utf8mb4_unicode_ci,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `result` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `operator` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `risk_level` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `drone_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `strategy_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dispatch_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_event_id` (`event_id`),
  KEY `idx_flow_id` (`flow_id`),
  KEY `idx_priority` (`priority`),
  CONSTRAINT `event_action_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `event_library` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `event_action_ibfk_2` FOREIGN KEY (`flow_id`) REFERENCES `action_flow` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=115 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件-行为关系表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_action`
--

LOCK TABLES `event_action` WRITE;
/*!40000 ALTER TABLE `event_action` DISABLE KEYS */;
INSERT INTO `event_action` VALUES (54,22,9,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(55,23,9,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(57,24,10,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(58,25,10,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(60,26,11,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(61,27,11,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(62,28,11,1,1,'2026-07-07 10:23:37',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(66,38,16,1,1,'2026-07-08 15:51:14',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(67,36,16,1,1,'2026-07-08 15:51:14',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(68,33,16,1,1,'2026-07-08 15:51:14',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(69,35,16,1,1,'2026-07-08 15:51:14',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(70,34,16,1,1,'2026-07-08 15:51:14',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(72,40,17,1,1,'2026-07-08 16:51:39',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(73,41,17,1,1,'2026-07-08 16:51:39',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(74,39,17,1,1,'2026-07-08 16:51:39',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(75,42,17,1,1,'2026-07-08 16:51:39',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(80,NULL,NULL,0,1,'2026-07-25 22:22:26','BROADCAST',NULL,'dahua_001',1,'FISHING','MANUAL','当前水域禁止非法捕鱼，请立即驶离。','2026-07-25 14:22:27','2026-07-25 14:22:27','SUCCESS',NULL,'admin',NULL,NULL,NULL,NULL),(81,NULL,NULL,0,1,'2026-07-25 22:22:32','BROADCAST',NULL,'dahua_001',1,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-25 14:22:32','2026-07-25 14:22:32','SUCCESS',NULL,'admin',NULL,NULL,NULL,NULL),(82,NULL,NULL,0,1,'2026-07-30 16:14:59','AUTO_BROADCAST','mp_demo_low_001','dahua_001',NULL,'demo_broadcast','AUTO','您已进入危险区域，请立即离开。','2026-07-30 08:12:20','2026-07-30 08:12:25','success',NULL,'SYSTEM','LOW',NULL,NULL,NULL),(83,NULL,NULL,0,1,'2026-07-30 16:14:59','AUTO_BROADCAST','mp_demo_medium_001','dahua_001',NULL,'demo_broadcast','AUTO','您已进入危险区域，请立即离开。','2026-07-30 08:11:00','2026-07-30 08:11:05','success',NULL,'SYSTEM','MEDIUM',NULL,NULL,NULL),(84,NULL,NULL,0,1,'2026-07-30 16:14:59','DRONE_DISPATCH','mp_demo_medium_001','dahua_001',NULL,NULL,'AUTO',NULL,NULL,NULL,'success',NULL,'SYSTEM','MEDIUM','demo_drone_001','demo_strategy','2026-07-30 08:11:35'),(85,NULL,NULL,0,1,'2026-07-30 16:14:59','AUTO_BROADCAST','mp_demo_high_001','dahua_001',NULL,'demo_broadcast','AUTO','您已进入危险区域，请立即离开。','2026-07-30 08:08:20','2026-07-30 08:08:25','success',NULL,'SYSTEM','LOW',NULL,NULL,NULL),(86,NULL,NULL,0,1,'2026-07-30 16:14:59','DRONE_DISPATCH','mp_demo_high_001','dahua_001',NULL,NULL,'AUTO',NULL,NULL,NULL,'success',NULL,'SYSTEM','MEDIUM','demo_drone_001','demo_strategy','2026-07-30 08:08:55'),(87,NULL,NULL,0,1,'2026-07-30 16:14:59','AUTO_BROADCAST','mp_demo_high_processing_001','dahua_001',NULL,'demo_broadcast','AUTO','您已进入危险区域，请立即离开。','2026-07-30 08:05:00','2026-07-30 08:05:05','success',NULL,'SYSTEM','LOW',NULL,NULL,NULL),(88,NULL,NULL,0,1,'2026-07-30 16:14:59','DRONE_DISPATCH','mp_demo_high_processing_001','dahua_001',NULL,NULL,'AUTO',NULL,NULL,NULL,'success',NULL,'SYSTEM','MEDIUM','demo_drone_001','demo_strategy','2026-07-30 08:05:35'),(89,NULL,NULL,0,1,'2026-07-30 16:23:52','MANUAL_BROADCAST','mp_demo_high_001','dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-30 08:23:53','2026-07-30 08:23:53','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(90,NULL,NULL,0,1,'2026-07-30 16:23:52','MANUAL_BROADCAST','mp_demo_high_001','dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-30 08:23:53','2026-07-30 08:23:53','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(91,NULL,NULL,0,1,'2026-07-30 22:05:35','MANUAL_BROADCAST','mp_demo_low_001','dahua_001',1,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-30 14:05:35','2026-07-30 14:05:35','SUCCESS',NULL,'微信小程序工作人员','LOW',NULL,NULL,NULL),(92,NULL,NULL,0,1,'2026-07-30 22:05:35','MANUAL_BROADCAST','mp_demo_low_001','dahua_001',2,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-30 14:05:36','2026-07-30 14:05:36','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','LOW',NULL,NULL,NULL),(93,NULL,NULL,0,1,'2026-07-31 13:52:09','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 05:52:09','2026-07-31 05:52:09','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(94,NULL,NULL,0,1,'2026-07-31 13:52:09','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 05:52:09','2026-07-31 05:52:09','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(95,NULL,NULL,0,1,'2026-07-31 14:02:04','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:04','2026-07-31 06:02:04','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(96,NULL,NULL,0,1,'2026-07-31 14:02:04','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:04','2026-07-31 06:02:04','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(97,NULL,NULL,0,1,'2026-07-31 14:02:05','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:05','2026-07-31 06:02:05','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(98,NULL,NULL,0,1,'2026-07-31 14:02:05','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:05','2026-07-31 06:02:05','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(99,NULL,NULL,0,1,'2026-07-31 14:02:05','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:06','2026-07-31 06:02:06','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(100,NULL,NULL,0,1,'2026-07-31 14:02:06','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:06','2026-07-31 06:02:06','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(101,NULL,NULL,0,1,'2026-07-31 14:02:06','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:06','2026-07-31 06:02:06','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(102,NULL,NULL,0,1,'2026-07-31 14:02:06','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:06','2026-07-31 06:02:06','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(103,NULL,NULL,0,1,'2026-07-31 14:02:06','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:07','2026-07-31 06:02:07','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(104,NULL,NULL,0,1,'2026-07-31 14:02:07','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:07','2026-07-31 06:02:07','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(105,NULL,NULL,0,1,'2026-07-31 14:02:15','MANUAL_BROADCAST',NULL,'dahua_001',1,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:15','2026-07-31 06:02:16','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(106,NULL,NULL,0,1,'2026-07-31 14:02:15','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 06:02:16','2026-07-31 06:02:16','FAILED','USB_AUDIO only supports recorded audio playback','微信小程序工作人员','HIGH',NULL,NULL,NULL),(107,NULL,NULL,0,1,'2026-07-31 14:19:56','MANUAL_BROADCAST',NULL,'dahua_001',2,NULL,'MANUAL','测试喊话，USB外放模板语音测试。','2026-07-31 06:19:57','2026-07-31 06:20:02','SUCCESS',NULL,'Codex测试','HIGH',NULL,NULL,NULL),(108,NULL,NULL,0,1,'2026-07-31 15:08:39','MANUAL_BROADCAST','mp_demo_high_processing_002','dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 07:08:40','2026-07-31 07:08:48','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(109,NULL,NULL,0,1,'2026-07-31 15:08:52','MANUAL_BROADCAST','mp_demo_low_001','dahua_001',2,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-31 07:08:53','2026-07-31 07:09:00','SUCCESS',NULL,'微信小程序工作人员','LOW',NULL,NULL,NULL),(110,NULL,NULL,0,1,'2026-07-31 16:54:24','MANUAL_BROADCAST',NULL,'dahua_001',2,'FISHING','MANUAL','当前水域禁止非法捕鱼，请立即驶离。','2026-07-31 08:54:24','2026-07-31 08:54:30','SUCCESS',NULL,'admin',NULL,NULL,NULL,NULL),(111,NULL,NULL,0,1,'2026-07-31 16:55:02','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-31 08:55:03','2026-07-31 08:55:10','SUCCESS',NULL,'admin',NULL,NULL,NULL,NULL),(112,NULL,NULL,0,1,'2026-07-31 16:55:20','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_LOW','MANUAL','您已进入安全警戒区域，请立即远离水边危险区域。','2026-07-31 08:55:20','2026-07-31 08:55:28','SUCCESS',NULL,'admin',NULL,NULL,NULL,NULL),(113,NULL,NULL,0,1,'2026-07-31 16:56:03','MANUAL_BROADCAST',NULL,'dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 08:56:04','2026-07-31 08:56:12','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL),(114,NULL,NULL,0,1,'2026-07-31 16:56:18','MANUAL_BROADCAST','mp_demo_high_processing_002','dahua_001',2,'PERSON_HIGH','MANUAL','紧急警告，当前区域存在重大安全风险，请立即撤离。','2026-07-31 08:56:18','2026-07-31 08:56:26','SUCCESS',NULL,'微信小程序工作人员','HIGH',NULL,NULL,NULL);
/*!40000 ALTER TABLE `event_action` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event_condition`
--

DROP TABLE IF EXISTS `event_condition`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_condition` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `event_id` bigint NOT NULL COMMENT '事件ID',
  `condition_id` bigint NOT NULL COMMENT '条件ID',
  `logic_type` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT 'AND' COMMENT '逻辑类型: AND-与/OR-或',
  `group_id` int DEFAULT '0' COMMENT '条件分组ID（同组内AND/OR，组间AND）',
  `sort_order` int DEFAULT '0' COMMENT '判断顺序',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_id` (`event_id`),
  KEY `idx_condition_id` (`condition_id`),
  KEY `idx_group_id` (`group_id`),
  CONSTRAINT `event_condition_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `event_library` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `event_condition_ibfk_2` FOREIGN KEY (`condition_id`) REFERENCES `condition_library` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件-条件关系表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_condition`
--

LOCK TABLES `event_condition` WRITE;
/*!40000 ALTER TABLE `event_condition` DISABLE KEYS */;
INSERT INTO `event_condition` VALUES (10,22,8,'AND',0,1,'2026-07-07 10:23:37'),(11,23,9,'AND',0,1,'2026-07-07 10:23:37'),(12,24,10,'AND',0,1,'2026-07-07 10:23:37'),(13,25,11,'AND',0,1,'2026-07-07 10:23:37'),(14,26,12,'AND',0,1,'2026-07-07 10:23:37'),(15,27,13,'AND',0,1,'2026-07-07 10:23:37'),(16,28,14,'AND',0,1,'2026-07-07 10:23:37'),(25,33,23,'AND',0,1,'2026-07-08 15:51:13'),(26,34,24,'AND',0,1,'2026-07-08 15:51:13'),(27,35,25,'AND',0,1,'2026-07-08 15:51:13'),(28,36,26,'AND',0,1,'2026-07-08 15:51:13'),(31,38,24,'AND',0,1,'2026-07-08 15:51:14'),(32,39,28,'AND',0,1,'2026-07-08 16:51:03'),(33,40,29,'AND',0,1,'2026-07-08 16:51:03'),(34,41,30,'AND',0,1,'2026-07-08 16:51:03'),(35,42,31,'AND',0,1,'2026-07-08 16:51:03'),(37,44,33,'AND',0,1,'2026-07-30 17:24:03'),(38,45,34,'AND',0,1,'2026-07-30 17:24:03'),(39,46,35,'AND',0,1,'2026-07-30 17:24:03'),(40,47,36,'AND',0,1,'2026-07-30 17:24:03');
/*!40000 ALTER TABLE `event_condition` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event_library`
--

DROP TABLE IF EXISTS `event_library`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_library` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '事件ID',
  `event_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '事件名称，如滑坡预警/裂缝扩展',
  `event_code` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件编码，如LANDSLIDE/CRACK',
  `event_category` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件分类: environment-环境/structure-结构/equipment-设备',
  `risk_level` tinyint DEFAULT '1' COMMENT '风险等级: 1-低 2-中 3-高',
  `trigger_mode` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'single' COMMENT '触发模式: single-单源/multi-多源',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件描述',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `event_code` (`event_code`),
  KEY `idx_event_code` (`event_code`),
  KEY `idx_event_category` (`event_category`),
  KEY `idx_risk_level` (`risk_level`)
) ENGINE=InnoDB AUTO_INCREMENT=48 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_library`
--

LOCK TABLES `event_library` WRITE;
/*!40000 ALTER TABLE `event_library` DISABLE KEYS */;
INSERT INTO `event_library` VALUES (22,'大风告警','WIND_LEVEL_6','environment',1,'single','6级强风预警，需关注',1,'2026-07-07 10:23:37','2026-07-07 15:23:14'),(23,'强风告警','WIND_LEVEL_7','environment',1,'single','7级疾风预警，需注意',1,'2026-07-07 10:23:37','2026-07-07 15:23:14'),(24,'大风警报','WIND_LEVEL_8','environment',2,'single','8级大风警报，危险',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(25,'烈风警报','WIND_LEVEL_9','environment',2,'single','9级烈风警报，建筑物可能损坏',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(26,'狂风警报','WIND_LEVEL_10','environment',3,'single','10级狂风警报，树木拔起，立即避险',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(27,'暴风警报','WIND_LEVEL_11','environment',3,'single','11级暴风警报，重大损毁风险',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(28,'飓风警报','WIND_LEVEL_12','environment',3,'single','12级飓风警报，极端危险',1,'2026-07-07 10:23:37','2026-07-07 10:23:37'),(33,'极低温告警','TEMP_EXTREME_LOW','environment',3,'single','温度<-10℃，高风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(34,'低温告警','TEMP_LOW','environment',2,'single','温度-10~0℃，中风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(35,'高温告警','TEMP_HIGH','environment',2,'single','温度35~40℃，中风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(36,'极高温告警','TEMP_EXTREME_HIGH','environment',3,'single','温度≥40℃，高风险',1,'2026-07-08 15:51:13','2026-07-08 15:51:13'),(38,'冰冻风险告警','FREEZE_RISK','environment',3,'single','低温触发冰冻风险告警',1,'2026-07-08 15:51:13','2026-07-30 16:21:01'),(39,'极高湿事件','HUMIDITY_VERY_HIGH','environment',1,'single','相对湿度≥90%，空气接近饱和',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(40,'高湿事件','HUMIDITY_HIGH','environment',2,'single','相对湿度80%-90%，易凝露结霜',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(41,'低湿事件','HUMIDITY_LOW','environment',2,'single','相对湿度20%-30%，偏干燥',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(42,'极低湿事件','HUMIDITY_VERY_LOW','environment',1,'single','相对湿度<20%，极度干燥',1,'2026-07-08 16:50:39','2026-07-08 16:50:39'),(44,'泥石流灾害告警','AI_MUDSLIDE','environment',3,'single','摄像头AI检测到泥石流灾害，触发告警',1,'2026-07-30 17:24:03','2026-07-30 17:34:00'),(45,'滑坡灾害告警','AI_LANDSLIDE','environment',3,'single','摄像头AI检测到滑坡灾害，触发告警',1,'2026-07-30 17:24:03','2026-07-30 17:26:31'),(46,'地震灾害告警','AI_EARTHQUAKE','environment',3,'single','摄像头AI检测到地震灾害，触发告警',1,'2026-07-30 17:24:03','2026-07-30 17:26:29'),(47,'洪水灾害告警','AI_FLOOD','environment',3,'single','摄像头AI检测到洪水灾害，触发告警',1,'2026-07-30 17:24:03','2026-07-30 17:26:27');
/*!40000 ALTER TABLE `event_library` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event_log`
--

DROP TABLE IF EXISTS `event_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '记录ID',
  `event_id` bigint NOT NULL COMMENT '事件ID',
  `trigger_time` datetime NOT NULL COMMENT '触发时间',
  `trigger_data` json DEFAULT NULL COMMENT '触发时的数据快照',
  `conditions_met` json DEFAULT NULL COMMENT '满足的条件详情',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'triggered' COMMENT '状态: triggered-已触发/processing-处理中/completed-已完成/failed-失败',
  `result` text COLLATE utf8mb4_unicode_ci COMMENT '处理结果',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_id` (`event_id`),
  KEY `idx_trigger_time` (`trigger_time`),
  KEY `idx_status` (`status`),
  CONSTRAINT `event_log_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `event_library` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件触发记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_log`
--

LOCK TABLES `event_log` WRITE;
/*!40000 ALTER TABLE `event_log` DISABLE KEYS */;
INSERT INTO `event_log` VALUES (4,22,'2026-07-08 04:26:52','{\"wind_speed_ms\": 4.9}','{\"event_id\": 22, \"event_name\": \"大风告警\"}','processing',NULL,'2026-07-08 12:26:52'),(5,22,'2026-07-09 02:42:22','{\"wind_speed_ms\": 1.6}','{\"event_id\": 22, \"event_name\": \"大风告警\"}','processing',NULL,'2026-07-09 10:42:22'),(7,22,'2026-07-09 04:46:53','{\"wind_speed_ms\": 3.7}','{\"event_id\": 22, \"event_name\": \"大风告警\"}','processing',NULL,'2026-07-09 12:46:52');
/*!40000 ALTER TABLE `event_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mini_program_subscription`
--

DROP TABLE IF EXISTS `mini_program_subscription`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mini_program_subscription` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '订阅记录ID',
  `openid` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '微信用户OpenID',
  `template_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '订阅消息模板ID',
  `subscription_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '订阅类型: once/permanent',
  `scope` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '订阅范围',
  `event_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '指定事件ID，为空表示全部风险',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '订阅状态',
  `remaining_quota` int NOT NULL COMMENT '剩余可发送次数',
  `last_sent_event_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最近发送事件ID',
  `last_sent_action_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最近发送动作ID',
  `last_error` text COLLATE utf8mb4_unicode_ci COMMENT '最近发送错误',
  `subscribed_at` datetime DEFAULT NULL COMMENT '最近订阅时间',
  `last_sent_at` datetime DEFAULT NULL COMMENT '最近发送时间',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_mini_program_subscription_status` (`status`),
  KEY `ix_mini_program_subscription_subscribed_at` (`subscribed_at`),
  KEY `ix_mini_program_subscription_subscription_type` (`subscription_type`),
  KEY `ix_mini_program_subscription_scope` (`scope`),
  KEY `ix_mini_program_subscription_openid` (`openid`),
  KEY `ix_mini_program_subscription_template_id` (`template_id`),
  KEY `ix_mini_program_subscription_event_id` (`event_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mini_program_subscription`
--

LOCK TABLES `mini_program_subscription` WRITE;
/*!40000 ALTER TABLE `mini_program_subscription` DISABLE KEYS */;
INSERT INTO `mini_program_subscription` VALUES (1,'ogKFq3Rac1K0oiIN_PoOAybsRMAU','5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA','once','event','mp_demo_high_processing_002','ACTIVE',3,NULL,NULL,NULL,'2026-07-31 13:28:34',NULL,'2026-07-31 07:08:50','2026-07-31 13:28:34'),(2,'ogKFq3Rac1K0oiIN_PoOAybsRMAU','5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA','once','risk_alerts',NULL,'ACTIVE',1,NULL,NULL,NULL,'2026-07-31 13:28:38',NULL,'2026-07-31 13:28:38','2026-07-31 13:28:38');
/*!40000 ALTER TABLE `mini_program_subscription` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_deploy_binding`
--

DROP TABLE IF EXISTS `model_deploy_binding`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_deploy_binding` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id` bigint NOT NULL COMMENT '关联模型 ID（model_registry.id）',
  `bind_type` varchar(16) NOT NULL COMMENT '绑定类型：container / image / both',
  `container_id` varchar(64) DEFAULT NULL COMMENT 'Docker 容器 ID',
  `container_name` varchar(128) DEFAULT NULL COMMENT 'Docker 容器名称',
  `image_name` varchar(256) DEFAULT NULL COMMENT 'Docker 镜像全名（含 tag）',
  `host_ip` varchar(64) NOT NULL DEFAULT '127.0.0.1' COMMENT '宿主机 IP',
  `host_port` int DEFAULT NULL COMMENT '宿主机映射端口',
  `container_port` int DEFAULT NULL COMMENT '容器内部端口',
  `inference_path` varchar(256) DEFAULT NULL COMMENT '推理接口路径（如 /predict）',
  `health_check_url` varchar(512) DEFAULT NULL COMMENT '健康检查路径（如 /health）',
  `gpu_device` varchar(64) DEFAULT NULL COMMENT 'GPU 设备映射（已废弃，请使用 container_config.gpus）',
  `extra_mounts` json DEFAULT NULL COMMENT '挂载卷 [{"host":"...","container":"..."}]',
  `extra_env` json DEFAULT NULL COMMENT '环境变量 {"KEY":"VALUE"}',
  `container_config` json DEFAULT NULL COMMENT 'Docker 容器运行时配置',
  `remark` varchar(256) DEFAULT NULL COMMENT '备注',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  KEY `idx_container_id` (`container_id`),
  CONSTRAINT `fk_binding_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型部署绑定表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_deploy_binding`
--

LOCK TABLES `model_deploy_binding` WRITE;
/*!40000 ALTER TABLE `model_deploy_binding` DISABLE KEYS */;
INSERT INTO `model_deploy_binding` VALUES (11,9,'both','b5d3e6d1d743230b4b089d8d31151946bd0704036d068f18d25754e52b5e2ab5','dam-qwen3-5-0-8b-9','vllm-qwen-0.8b:latest','127.0.0.1',8003,8000,'/v1/chat/completions','/health',NULL,'[{\"host\": \"/home/jetson/.cache/modelscope/hub/models/Qwen/Qwen3.5-0.8B\", \"container\": \"/models\"}, {\"host\": \"/home/jetson/vllm_cache\", \"container\": \"/root/.cache/vllm\"}]','null','{\"gpus\": \"all\", \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": \"host\", \"shm_size\": \"2g\", \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-28 08:17:56','2026-07-28 08:18:21'),(12,10,'both','369b440d7703916c30606e98ea9a268d586d3bc9267aea48a078956f0807d587','dam-qwen3-vl-4b-instruct-10','vllm-qwen-4b:latest','127.0.0.1',8001,8000,'/v1/chat/completions','/health',NULL,'[{\"host\": \"/home/jetson/.cache/modelscope/hub/models/Qwen/Qwen3-VL-4B-Instruct\", \"container\": \"/models\"}, {\"host\": \"/home/jetson/vllm_cache\", \"container\": \"/root/.cache/vllm\"}]','null','{\"gpus\": \"all\", \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": \"host\", \"shm_size\": \"8g\", \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-28 08:18:03','2026-07-28 08:24:35'),(14,12,'both','7369c61325b15ff0843066903c63dd5f580060d0962437aca6e3f84eae5d107f','dam-yolo26-12','yolo-cls:latest','127.0.0.1',8004,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/yolo-cls/yolo26x_cls_acc_96.pt\", \"container\": \"/app/models/yolo26x_cls_acc_96.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"256\", \"MODEL_WEIGHTS\": \"/app/models/yolo26x_cls_acc_96.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": \"all\", \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-29 11:32:57','2026-07-31 09:33:19'),(17,13,'both','486f68a2004d5638d1e7e7525174000dfbabb25a4141abd5156a56dea9863252','dam-qwen3-5-35b-13','qwen35b-service-qwen35b-proxy:latest','127.0.0.1',9900,9457,'/api/v1/cloud-inference','/health',NULL,'null','null','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-30 06:52:12','2026-07-30 06:53:21'),(19,14,'both','2c81363de7bff294b24629949cb1349f7cd4e127bc71116e50a0120306f6f834','dam-qwen-vl-4b-14','qwen4b-service-qwen4b-local:latest','127.0.0.1',9901,9901,'/api/v1/local-inference',NULL,NULL,'null','null','null',NULL,'2026-07-31 05:55:13','2026-07-31 05:56:34'),(20,15,'both','3fb54b3b54efb52403ae473f11c939e276d7c70ad2fd8919d4049035f281d1ff','dam-mobilenetv4-15','mobilenetv4-cls-mobilenetv4-cls-api:latest','127.0.0.1',8006,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/mobilenetv4-cls/mobilenetv4_conv_medium_cls_acc_92_25.pt\", \"container\": \"/app/models/mobilenetv4_conv_medium_cls_acc_92_25.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"256\", \"MODEL_NAME\": \"mobilenetv4_conv_medium.e500_r256_in1k\", \"CLASS_NAMES\": \"earthquake,flood,landslide,mudslide\", \"MODEL_BACKEND\": \"timm\", \"MODEL_WEIGHTS\": \"/app/models/mobilenetv4_conv_medium_cls_acc_92_25.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-31 09:26:03','2026-07-31 09:26:52'),(21,16,'both','07f665dffba995f71387b92bd3145113f1771d881abb7c90d0de681ead0f2491','dam-mobilenetv4-16','mobilenetv4-cls-default:latest','127.0.0.1',8007,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/mobilenetv4-cls_default/mobilenetv4_conv_medium_cls_default.pt\", \"container\": \"/app/models/mobilenetv4_conv_medium_cls_default.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"256\", \"MODEL_NAME\": \"mobilenetv4_conv_medium.e500_r256_in1k\", \"MODEL_BACKEND\": \"timm\", \"MODEL_WEIGHTS\": \"/app/models/mobilenetv4_conv_medium_cls_default.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-31 09:26:15','2026-07-31 09:27:01'),(22,17,'both','48c2a9c12fa356cbcf22824727a7a955875fa2954f1af5c680085b6e2057f916','dam-repvit-17','repvit-cls:latest','127.0.0.1',8008,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/repvit-cls/repvit_m1_1_cls_acc_94_25.pt\", \"container\": \"/app/models/repvit_m1_1_cls_acc_94_25.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"224\", \"MODEL_NAME\": \"repvit_m1_1.dist_450e_in1k\", \"CLASS_NAMES\": \"earthquake,flood,landslide,mudslide\", \"MODEL_BACKEND\": \"timm\", \"MODEL_WEIGHTS\": \"/app/models/repvit_m1_1_cls_acc_94_25.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-31 09:26:21','2026-07-31 09:27:10'),(23,18,'both','5c92a29af492b2df4b88a7f3617c99cedbdaeb92b9b6663ba374947b78a03631','dam-repvit-18','repvit-cls-default:latest','127.0.0.1',8009,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/repvit-cls_default/repvit_m1_1_cls_default.pt\", \"container\": \"/app/models/repvit_m1_1_cls_default.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"224\", \"MODEL_NAME\": \"repvit_m1_1.dist_450e_in1k\", \"MODEL_BACKEND\": \"timm\", \"MODEL_WEIGHTS\": \"/app/models/repvit_m1_1_cls_default.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-31 09:26:27','2026-07-31 09:27:20'),(24,19,'both','55f5e304fafb01b241d12ec56698d6b71643d8f02502301996fcfea45b01dca4','dam-yolo26x-19','yolo-cls-default:latest','127.0.0.1',8005,8000,'/classify/image','/health',NULL,'[{\"host\": \"/home/jetson/box_system/models/yolo-cls_default/yolo26x_cls_default.pt\", \"container\": \"/app/models/yolo26x_cls_default.pt\"}]','{\"TOP_K\": \"3\", \"DEVICE\": \"0\", \"IMG_SIZE\": \"256\", \"MODEL_BACKEND\": \"yolo\", \"MODEL_WEIGHTS\": \"/app/models/yolo26x_cls_default.pt\", \"MINIO_ENDPOINT\": \"minio:9000\", \"MINIO_ACCESS_KEY\": \"minioadmin\", \"MINIO_SECRET_KEY\": \"minioadmin\"}','{\"gpus\": null, \"labels\": null, \"cap_add\": null, \"devices\": null, \"runtime\": null, \"ulimits\": null, \"ipc_mode\": null, \"shm_size\": null, \"privileged\": false, \"network_mode\": \"bridge\", \"restart_policy\": null}',NULL,'2026-07-31 09:26:33','2026-07-31 09:27:29');
/*!40000 ALTER TABLE `model_deploy_binding` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_evaluation_template`
--

DROP TABLE IF EXISTS `model_evaluation_template`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_evaluation_template` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name` varchar(128) NOT NULL COMMENT '模板名称',
  `event_type` varchar(64) DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用模板）',
  `prompt_template` text NOT NULL COMMENT 'prompt 模板（含占位符：{{user_prompt}}, {{detection_results}}, {{sensor_data}}）',
  `input_schema` json NOT NULL COMMENT '输入 schema 定义',
  `output_schema` json NOT NULL COMMENT '输出 schema 定义',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用：0=禁用，1=启用',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_template_name` (`template_name`),
  KEY `idx_event_type` (`event_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='评价 prompt 模板表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_evaluation_template`
--

LOCK TABLES `model_evaluation_template` WRITE;
/*!40000 ALTER TABLE `model_evaluation_template` DISABLE KEYS */;
/*!40000 ALTER TABLE `model_evaluation_template` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_event_mapping`
--

DROP TABLE IF EXISTS `model_event_mapping`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_event_mapping` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `event_type` varchar(64) NOT NULL COMMENT '事件类型（滑坡/裂缝/渗漏/变形/沉降/管涌）',
  `task_type` varchar(128) NOT NULL COMMENT '任务类型（检测/分割/变化检测/推理）',
  `model_category` enum('specialized','llm') NOT NULL COMMENT '模型类别：specialized=专有模型，llm=大模型',
  `model_id` bigint DEFAULT NULL COMMENT '模型 ID（关联 model_registry.id）',
  `priority` int NOT NULL DEFAULT '0' COMMENT '优先级（数值越大越优先）',
  `remark` varchar(256) DEFAULT NULL COMMENT '备注说明',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_task` (`event_type`,`task_type`),
  KEY `idx_model_id` (`model_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='事件→模型映射表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_event_mapping`
--

LOCK TABLES `model_event_mapping` WRITE;
/*!40000 ALTER TABLE `model_event_mapping` DISABLE KEYS */;
/*!40000 ALTER TABLE `model_event_mapping` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_io_schema`
--

DROP TABLE IF EXISTS `model_io_schema`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_io_schema` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id` bigint NOT NULL COMMENT '关联模型 ID',
  `inputs` json DEFAULT NULL COMMENT '输入 Schema',
  `outputs` json DEFAULT NULL COMMENT '输出 Schema',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  CONSTRAINT `fk_schema_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型 IO Schema';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_io_schema`
--

LOCK TABLES `model_io_schema` WRITE;
/*!40000 ALTER TABLE `model_io_schema` DISABLE KEYS */;
/*!40000 ALTER TABLE `model_io_schema` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_io_template`
--

DROP TABLE IF EXISTS `model_io_template`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_io_template` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name` varchar(128) NOT NULL COMMENT '模板名称',
  `event_type` varchar(64) DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用）',
  `source_model_category` varchar(64) NOT NULL COMMENT '上游模型类别（specialized/llm）',
  `target_model_category` varchar(64) NOT NULL COMMENT '下游模型类别（specialized/llm）',
  `source_task_type` varchar(128) DEFAULT NULL COMMENT '上游任务类型（可选，用于精确匹配）',
  `target_task_type` varchar(128) DEFAULT NULL COMMENT '下游任务类型（可选，用于精确匹配）',
  `field_mapping` json NOT NULL COMMENT '字段映射规则',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_source_target` (`event_type`,`source_model_category`,`target_model_category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='IO 配对模板表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_io_template`
--

LOCK TABLES `model_io_template` WRITE;
/*!40000 ALTER TABLE `model_io_template` DISABLE KEYS */;
/*!40000 ALTER TABLE `model_io_template` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_library`
--

DROP TABLE IF EXISTS `model_library`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_library` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '模型ID',
  `model_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型名称，如YOLOv8/RT-DETR/Qwen-VL/SegFormer',
  `model_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型类型: detection-目标检测/segmentation-分割/vlm-视觉语言',
  `api_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型API地址',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型描述',
  `is_activate` tinyint(1) DEFAULT '1' COMMENT '是否启用: 0-禁用 1-启用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_model_name` (`model_name`),
  KEY `idx_model_type` (`model_type`),
  KEY `idx_is_activate` (`is_activate`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI模型库';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_library`
--

LOCK TABLES `model_library` WRITE;
/*!40000 ALTER TABLE `model_library` DISABLE KEYS */;
INSERT INTO `model_library` VALUES (1,'Qwen3-VL-8B','vlm','http://localhost:8000/v1/chat/completions','通义千问视觉语言大模型，用于场景分析和风险推理',1,'2026-07-04 13:36:04','2026-07-09 10:20:59'),(2,'YOLOv8','detection','http://localhost:8001/v1/completions','YOLOv8目标检测模型，用于裂缝、渗水等目标识别',1,'2026-07-04 13:36:04','2026-07-09 10:20:59'),(3,'RT-DETR','detection','/models/rtdetr-l.pt','RT-DETR实时检测模型',0,'2026-07-04 13:36:04','2026-07-04 13:36:04'),(4,'SegFormer','segmentation','/models/segformer-b2.pth','SegFormer语义分割模型',0,'2026-07-04 13:36:04','2026-07-04 13:36:04'),(5,'CrackDetection-v1','detection','/models/crack_detection_v1.pt','裂缝检测专用模型',1,'2026-07-04 13:36:04','2026-07-04 13:36:04'),(6,'SeepageDetection-v1','detection','/models/seepage_detection_v1.pt','渗水检测专用模型',1,'2026-07-04 13:36:04','2026-07-04 13:36:04'),(7,'SAM','segmentation','http://localhost:8002/v1/completions','Segment Anything Model 图像分割',1,'2026-07-07 10:26:08','2026-07-09 10:20:59');
/*!40000 ALTER TABLE `model_library` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_operation_log`
--

DROP TABLE IF EXISTS `model_operation_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_operation_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id` bigint NOT NULL COMMENT '关联模型 ID',
  `operator_id` bigint DEFAULT NULL COMMENT '操作者用户 ID',
  `operation` varchar(32) NOT NULL COMMENT '操作类型：start/stop/restart/rebuild/bind/unbind/delete',
  `detail` json DEFAULT NULL COMMENT '操作详情',
  `result` varchar(16) NOT NULL COMMENT '结果：success/failed',
  `error_msg` varchar(512) DEFAULT NULL COMMENT '失败原因',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_model_id` (`model_id`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB AUTO_INCREMENT=104 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型操作日志';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_operation_log`
--

LOCK TABLES `model_operation_log` WRITE;
/*!40000 ALTER TABLE `model_operation_log` DISABLE KEYS */;
INSERT INTO `model_operation_log` VALUES (53,9,NULL,'create',NULL,'success',NULL,'2026-07-28 08:17:35'),(54,10,NULL,'create',NULL,'success',NULL,'2026-07-28 08:17:40'),(55,9,NULL,'bind_image',NULL,'success',NULL,'2026-07-28 08:17:57'),(56,10,NULL,'bind_image',NULL,'success',NULL,'2026-07-28 08:18:03'),(57,9,NULL,'start',NULL,'failed','健康检查超时: http://127.0.0.1:8003/health','2026-07-28 08:20:23'),(58,10,NULL,'start',NULL,'failed','健康检查超时: http://127.0.0.1:8001/health','2026-07-28 08:26:36'),(61,12,NULL,'create',NULL,'success',NULL,'2026-07-29 11:28:20'),(62,12,NULL,'bind_image',NULL,'success',NULL,'2026-07-29 11:32:57'),(63,13,NULL,'create',NULL,'success',NULL,'2026-07-30 06:30:18'),(64,13,NULL,'bind_image',NULL,'success',NULL,'2026-07-30 06:30:35'),(65,13,NULL,'unbind',NULL,'success',NULL,'2026-07-30 06:32:56'),(66,13,NULL,'bind_image',NULL,'success',NULL,'2026-07-30 06:32:56'),(67,13,NULL,'unbind',NULL,'success',NULL,'2026-07-30 06:52:12'),(68,13,NULL,'bind_image',NULL,'success',NULL,'2026-07-30 06:52:12'),(69,13,NULL,'start',NULL,'failed','创建容器失败: 400 Client Error for http+docker://localhost/v1.54/containers/create?name=dam-qwen3-5-35b-%E4%BA%91%E7%AB%AF%E5%A2%9E%E5%BC%BA%E6%8E%A8%E7%90%86-13: Bad Request (\"Invalid container name (dam-qwen3-5-35b-云端增强推理-13), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed\")','2026-07-30 06:52:40'),(70,13,NULL,'start',NULL,'success',NULL,'2026-07-30 06:53:23'),(71,13,NULL,'stop',NULL,'success',NULL,'2026-07-30 07:17:19'),(72,14,NULL,'create',NULL,'success',NULL,'2026-07-30 07:59:14'),(73,14,NULL,'bind_image',NULL,'success',NULL,'2026-07-30 07:59:48'),(74,14,NULL,'unbind',NULL,'success',NULL,'2026-07-31 05:55:13'),(75,14,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 05:55:13'),(76,12,NULL,'start',NULL,'success',NULL,'2026-07-31 05:56:19'),(77,14,NULL,'start',NULL,'success',NULL,'2026-07-31 05:56:34'),(78,12,NULL,'stop',NULL,'success',NULL,'2026-07-31 05:57:34'),(79,14,NULL,'stop',NULL,'success',NULL,'2026-07-31 05:57:42'),(80,15,NULL,'create',NULL,'success',NULL,'2026-07-31 09:25:21'),(81,16,NULL,'create',NULL,'success',NULL,'2026-07-31 09:25:26'),(82,17,NULL,'create',NULL,'success',NULL,'2026-07-31 09:25:32'),(83,18,NULL,'create',NULL,'success',NULL,'2026-07-31 09:25:37'),(84,19,NULL,'create',NULL,'success',NULL,'2026-07-31 09:25:41'),(85,15,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 09:26:03'),(86,16,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 09:26:15'),(87,17,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 09:26:21'),(88,18,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 09:26:27'),(89,19,NULL,'bind_image',NULL,'success',NULL,'2026-07-31 09:26:33'),(90,15,NULL,'start',NULL,'success',NULL,'2026-07-31 09:27:00'),(91,16,NULL,'start',NULL,'success',NULL,'2026-07-31 09:27:09'),(92,17,NULL,'start',NULL,'success',NULL,'2026-07-31 09:27:19'),(93,18,NULL,'start',NULL,'success',NULL,'2026-07-31 09:27:28'),(94,19,NULL,'start',NULL,'success',NULL,'2026-07-31 09:27:37'),(95,15,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:27:48'),(96,16,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:27:50'),(97,17,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:27:52'),(98,18,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:27:54'),(99,19,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:27:56'),(100,12,NULL,'start',NULL,'failed','容器不存在: b3f87f3834b744ef9657640f954288cc7cba8d1e2de8edeb698ea87e7c29f5d2','2026-07-31 09:32:51'),(101,12,NULL,'start',NULL,'failed','容器不存在: b3f87f3834b744ef9657640f954288cc7cba8d1e2de8edeb698ea87e7c29f5d2','2026-07-31 09:33:00'),(102,12,NULL,'start',NULL,'success',NULL,'2026-07-31 09:33:27'),(103,12,NULL,'stop',NULL,'success',NULL,'2026-07-31 09:33:39');
/*!40000 ALTER TABLE `model_operation_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `model_registry`
--

DROP TABLE IF EXISTS `model_registry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_registry` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name` varchar(128) NOT NULL COMMENT '模型名称',
  `description` varchar(512) DEFAULT NULL COMMENT '模型描述',
  `tags` json DEFAULT NULL COMMENT '标签列表',
  `framework` varchar(64) DEFAULT NULL COMMENT '框架（PyTorch/TensorFlow/ONNX等）',
  `architecture` varchar(64) DEFAULT NULL COMMENT '架构（CNN/Transformer等）',
  `model_type` varchar(64) DEFAULT NULL COMMENT '模型类型（目标检测/图像分类/LLM等）',
  `model_size` varchar(32) DEFAULT NULL COMMENT '模型大小（如 7B、1.2GB）',
  `runtime_status` varchar(16) NOT NULL DEFAULT 'stopped' COMMENT '运行状态：stopped/starting/running/stopping/error',
  `owner_id` bigint DEFAULT NULL COMMENT '所有者用户 ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_owner_id` (`owner_id`),
  KEY `idx_runtime_status` (`runtime_status`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型注册表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `model_registry`
--

LOCK TABLES `model_registry` WRITE;
/*!40000 ALTER TABLE `model_registry` DISABLE KEYS */;
INSERT INTO `model_registry` VALUES (9,'Qwen3.5-0.8B','Qwen3.5 0.8B 轻量语言模型',NULL,'vLLM','Transformer','LLM','0.8B','running',NULL,'2026-07-28 08:17:35','2026-07-28 08:20:38'),(10,'Qwen3-VL-4B-Instruct','Qwen3-VL 4B 视觉语言模型',NULL,'vLLM','Transformer','VLM','4B','stopped',NULL,'2026-07-28 08:17:40','2026-07-30 07:05:34'),(12,'YOLO26 灾害分类','基于 YOLO26x 的灾害类型分类模型，支持图片和视频分类（地震/洪水/滑坡/泥石流）',NULL,'Ultralytics','YOLO26x','Classification','57MB','stopped',NULL,'2026-07-29 11:28:20','2026-07-31 09:36:43'),(13,'Qwen3.5-35B 云端增强推理','云端服务 10.196.85.11:9457，支持灾害评估报告生成',NULL,'vLLM','Transformer','LLM','35B','stopped',NULL,'2026-07-30 06:30:18','2026-07-30 07:17:19'),(14,'Qwen-VL-4B 本地推理','边缘侧灾害巡查智能分析模型，支持多模态输入（图像+文本）',NULL,'vLLM','Transformer','VLM','4B','stopped',NULL,'2026-07-30 07:59:14','2026-07-31 05:57:42'),(15,'MobileNetV4 灾害分类','MobileNetV4 灾害类型分类模型（自定义类别）',NULL,'TIMM','MobileNetV4','分类','34MB','stopped',NULL,'2026-07-31 09:25:21','2026-07-31 09:27:48'),(16,'MobileNetV4 默认分类','MobileNetV4 默认 ImageNet 类别分类模型',NULL,'TIMM','MobileNetV4','分类','39MB','stopped',NULL,'2026-07-31 09:25:26','2026-07-31 09:27:50'),(17,'RepViT 灾害分类','RepViT 灾害类型分类模型（自定义类别）',NULL,'TIMM','RepViT','分类','31MB','stopped',NULL,'2026-07-31 09:25:32','2026-07-31 09:27:52'),(18,'RepViT 默认分类','RepViT 默认 ImageNet 类别分类模型',NULL,'TIMM','RepViT','分类','35MB','stopped',NULL,'2026-07-31 09:25:37','2026-07-31 09:27:54'),(19,'YOLO26x 默认分类','YOLO26x 默认 ImageNet 类别分类模型',NULL,'Ultralytics','YOLO26x','分类','59MB','stopped',NULL,'2026-07-31 09:25:41','2026-07-31 09:27:56');
/*!40000 ALTER TABLE `model_registry` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `safety_event`
--

DROP TABLE IF EXISTS `safety_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `safety_event` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '安全事件ID',
  `event_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '事件唯一编号',
  `camera_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '摄像头ID',
  `entity_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '目标类型: person/boat',
  `track_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '目标跟踪ID',
  `state` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '事件状态',
  `risk_level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '风险等级',
  `started_at` datetime NOT NULL COMMENT '事件开始时间',
  `first_seen_at` datetime NOT NULL COMMENT '首次跟踪到目标时间',
  `danger_started_at` datetime NOT NULL COMMENT '目标进入危险区域时间',
  `last_seen_at` datetime NOT NULL COMMENT '最近一次看到目标时间',
  `low_entered_at` datetime DEFAULT NULL COMMENT '进入低风险时间',
  `missing_since` datetime DEFAULT NULL COMMENT '目标丢失开始时间',
  `clear_since` datetime DEFAULT NULL COMMENT '目标离开危险区域开始时间',
  `resolved_at` datetime DEFAULT NULL COMMENT '事件关闭时间',
  `resolve_reason` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件关闭原因',
  `snapshot_url` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '首张告警快照MinIO地址或本地路径',
  `zone_type` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前触发区域类型',
  `zone_name` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前触发区域名称',
  `zone_ids` json DEFAULT NULL COMMENT '触发区域ID列表',
  `latest_bbox` json DEFAULT NULL COMMENT '最近一次目标框',
  `latest_observation` json DEFAULT NULL COMMENT '最近一次观测数据',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING' COMMENT '处置闭环状态',
  `event_type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件类型',
  `camera_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '摄像头名称',
  `video_url` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '事件录像地址',
  `duration_seconds` int NOT NULL DEFAULT '0' COMMENT '事件持续秒数',
  `ack_operator` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '确认人员',
  `ack_at` datetime DEFAULT NULL COMMENT '确认时间',
  `resolved_operator` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '解除人员',
  `false_alarm_operator` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '误报确认人员',
  `false_alarm_reason` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '误报原因',
  `version` int NOT NULL DEFAULT '0' COMMENT '乐观锁版本号',
  `max_risk_level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NONE' COMMENT '最高风险等级',
  `handling_mode` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'AUTO' COMMENT '处置责任模式',
  `disposal_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'MONITORING' COMMENT '处置状态',
  `target_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'IN_DANGER' COMMENT '目标状态',
  `medium_entered_at` datetime DEFAULT NULL COMMENT '进入中风险时间',
  `video_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING' COMMENT '留证视频状态',
  `video_error` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '留证视频失败原因',
  `video_created_at` datetime DEFAULT NULL COMMENT '留证视频生成完成时间',
  `video_expires_at` datetime DEFAULT NULL COMMENT '留证视频留档到期时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_safety_event_event_id` (`event_id`),
  KEY `idx_safety_event_camera_id` (`camera_id`),
  KEY `idx_safety_event_track_id` (`track_id`),
  KEY `idx_safety_event_state` (`state`),
  KEY `idx_safety_event_risk_level` (`risk_level`),
  KEY `idx_safety_event_started_at` (`started_at`),
  KEY `idx_safety_event_resolved_at` (`resolved_at`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI视频安全事件表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `safety_event`
--

LOCK TABLES `safety_event` WRITE;
/*!40000 ALTER TABLE `safety_event` DISABLE KEYS */;
INSERT INTO `safety_event` VALUES (1,'mp_demo_low_001','dahua_001','person','track_mp_demo_low_001','ACTIVE','LOW','2026-07-30 08:12:00','2026-07-30 08:12:00','2026-07-30 08:12:05','2026-07-30 08:15:00','2026-07-30 08:12:10',NULL,NULL,NULL,NULL,NULL,'WARNING_ZONE','警戒区','[\"demo_zone\"]','{\"x\": 0.42, \"y\": 0.36, \"width\": 0.16, \"height\": 0.32}','{\"source\": \"miniprogram_demo\", \"confidence\": 0.91}','2026-07-30 08:15:00','2026-07-31 07:08:53','PROCESSING','警戒区人员停留','一号点摄像头',NULL,82612,NULL,NULL,NULL,NULL,NULL,3,'LOW','AUTO','AUTO_HANDLING','IN_DANGER',NULL,'PENDING',NULL,NULL,NULL),(2,'mp_demo_medium_001','dahua_001','person','track_mp_demo_medium_001','ACTIVE','MEDIUM','2026-07-30 08:10:40','2026-07-30 08:10:40','2026-07-30 08:10:45','2026-07-30 08:15:00','2026-07-30 08:10:50',NULL,NULL,NULL,NULL,NULL,'WATERFRONT_ZONE','亲水区','[\"demo_zone\"]','{\"x\": 0.42, \"y\": 0.36, \"width\": 0.16, \"height\": 0.32}','{\"source\": \"miniprogram_demo\", \"confidence\": 0.91}','2026-07-30 08:15:00','2026-07-30 08:15:00','PROCESSING','亲水区人员进入','一号点摄像头',NULL,260,NULL,NULL,NULL,NULL,NULL,1,'MEDIUM','AUTO','AUTO_HANDLING','IN_DANGER','2026-07-30 08:11:30','PENDING',NULL,NULL,NULL),(3,'mp_demo_high_001','dahua_001','person','track_mp_demo_high_001','RESOLVED','HIGH','2026-07-30 08:08:00','2026-07-30 08:08:00','2026-07-30 08:08:05','2026-07-30 08:15:00','2026-07-30 08:08:10',NULL,NULL,'2026-07-30 14:24:24','manual_close',NULL,'WATER_ZONE','涉水区','[\"demo_zone\"]','{\"x\": 0.42, \"y\": 0.36, \"width\": 0.16, \"height\": 0.32}','{\"source\": \"miniprogram_demo\", \"confidence\": 0.91}','2026-07-30 08:15:00','2026-07-30 14:24:24','RESOLVED','涉水区人员进入','一号点摄像头',NULL,22583,'微信小程序工作人员','2026-07-30 08:24:48','微信小程序工作人员',NULL,NULL,4,'HIGH','MANUAL','RESOLVED','LEFT','2026-07-30 08:08:50','PENDING',NULL,NULL,NULL),(4,'mp_demo_high_processing_001','dahua_001','person','track_mp_demo_high_processing_001','RESOLVED','HIGH','2026-07-30 08:04:40','2026-07-30 08:04:40','2026-07-30 08:04:45','2026-07-30 08:15:00','2026-07-30 08:04:50',NULL,NULL,'2026-08-02 07:46:23','manual_close',NULL,'WATER_ZONE','涉水区','[\"demo_zone\"]','{\"x\": 0.42, \"y\": 0.36, \"width\": 0.16, \"height\": 0.32}','{\"source\": \"miniprogram_demo\", \"confidence\": 0.91}','2026-07-30 08:15:00','2026-08-02 07:46:23','RESOLVED','涉水区人员进入','一号点摄像头',NULL,258102,NULL,NULL,'微信小程序工作人员',NULL,NULL,2,'HIGH','MANUAL','RESOLVED','LEFT','2026-07-30 08:05:30','PENDING',NULL,NULL,NULL),(5,'mp_demo_high_processing_002','dahua_001','person','track_mp_demo_high_processing_001','ACTIVE','HIGH','2026-07-30 08:04:40','2026-07-30 08:04:40','2026-07-30 08:04:45','2026-07-30 08:15:00','2026-07-30 08:04:50',NULL,NULL,NULL,NULL,NULL,'WATER_ZONE','涉水区','[\"demo_zone\"]','{\"x\": 0.42, \"y\": 0.36, \"width\": 0.16, \"height\": 0.32}','{\"source\": \"miniprogram_demo\", \"confidence\": 0.91}','2026-07-30 08:15:00','2026-07-31 08:56:18','PROCESSING','涉水区人员进入','一号点摄像头',NULL,89498,NULL,NULL,NULL,NULL,NULL,2,'NONE','AUTO','MONITORING','IN_DANGER',NULL,'PENDING',NULL,NULL,NULL);
/*!40000 ALTER TABLE `safety_event` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `safety_event_log`
--

DROP TABLE IF EXISTS `safety_event_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `safety_event_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `action_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '动作唯一编号',
  `event_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '事件唯一编号',
  `action_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '动作类型',
  `risk_level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '当前风险等级',
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '执行状态',
  `message` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '动作说明或失败原因',
  `payload` json DEFAULT NULL COMMENT '动作上下文',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `from_status` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作前处置状态',
  `to_status` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作后处置状态',
  `operator` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作人员',
  `operator_role` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作人员角色',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_safety_event_log_action_id` (`action_id`),
  KEY `idx_safety_event_log_event_id` (`event_id`),
  KEY `idx_safety_event_log_action_type` (`action_type`),
  KEY `idx_safety_event_log_risk_level` (`risk_level`),
  KEY `idx_safety_event_log_status` (`status`),
  KEY `idx_safety_event_log_create_time` (`create_time`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI视频安全事件动作日志表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `safety_event_log`
--

LOCK TABLES `safety_event_log` WRITE;
/*!40000 ALTER TABLE `safety_event_log` DISABLE KEYS */;
INSERT INTO `safety_event_log` VALUES (1,'02a9b184cb6a46ca9de23ee2c1e3ffd4','mp_demo_low_001','AI_DETECTED','LOW','success','检测到人员','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:12:00','2026-07-30 08:15:00',NULL,'AUTO_HANDLING','SYSTEM','system'),(2,'4f78748ae6ae40eab79eb73716460f52','mp_demo_low_001','RISK_LOW','LOW','success','低风险，自动喊话','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:12:10','2026-07-30 08:15:00',NULL,'AUTO_HANDLING','SYSTEM','system'),(3,'25cbc5218ac4448589b88ee0fb7219d4','mp_demo_medium_001','AI_DETECTED','MEDIUM','success','检测到人员','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:10:40','2026-07-30 08:15:00',NULL,'AUTO_HANDLING','SYSTEM','system'),(4,'c206bdf1f41f4fe980f2b23cdb19f1a6','mp_demo_medium_001','RISK_LOW','LOW','success','低风险，自动喊话','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:10:50','2026-07-30 08:15:00',NULL,'AUTO_HANDLING','SYSTEM','system'),(5,'0c5e50756c5045a4a4101ccda947af13','mp_demo_medium_001','RISK_MEDIUM','MEDIUM','success','中风险，再次自动喊话，无人机自动派飞','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:11:30','2026-07-30 08:15:00',NULL,'AUTO_HANDLING','SYSTEM','system'),(6,'aac3c16244df4a1e9a6b85bf72cb72fe','mp_demo_high_001','AI_DETECTED','HIGH','success','检测到人员','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:08:00','2026-07-30 08:15:00',NULL,'WAITING_MANUAL','SYSTEM','system'),(7,'0f3a61c2306a400b8e277c7cf95ae0e5','mp_demo_high_001','RISK_LOW','LOW','success','低风险，自动喊话','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:08:10','2026-07-30 08:15:00',NULL,'WAITING_MANUAL','SYSTEM','system'),(8,'ae6cf75622af4b0a82d760cb97fd4b73','mp_demo_high_001','RISK_MEDIUM','MEDIUM','success','中风险，再次自动喊话，无人机自动派飞','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:08:50','2026-07-30 08:15:00',NULL,'WAITING_MANUAL','SYSTEM','system'),(9,'174a99cc8bd147ef89c8144ee57abced','mp_demo_high_001','RISK_HIGH','HIGH','success','高风险，等待人工处理','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:10:00','2026-07-30 08:15:00',NULL,'WAITING_MANUAL','SYSTEM','system'),(10,'76c043b406e1418293201c7111419c76','mp_demo_high_processing_001','AI_DETECTED','HIGH','success','检测到人员','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:04:40','2026-07-30 08:15:00',NULL,'MANUAL_HANDLING','SYSTEM','system'),(11,'f1a6893676dd458ea03f65266ac12c37','mp_demo_high_processing_001','RISK_LOW','LOW','success','低风险，自动喊话','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:04:50','2026-07-30 08:15:00',NULL,'MANUAL_HANDLING','SYSTEM','system'),(12,'f5dc7bd58daf45bd959059bcb8c56a72','mp_demo_high_processing_001','RISK_MEDIUM','MEDIUM','success','中风险，再次自动喊话，无人机自动派飞','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:05:30','2026-07-30 08:15:00',NULL,'MANUAL_HANDLING','SYSTEM','system'),(13,'d080d607adc44a259ef3d423f0dd43d7','mp_demo_high_processing_001','RISK_HIGH','HIGH','success','高风险，等待人工处理','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:06:40','2026-07-30 08:15:00',NULL,'MANUAL_HANDLING','SYSTEM','system'),(14,'dcc92f4ece184573be0a1e893d9633ea','mp_demo_high_processing_001','staff_accepted','HIGH','success','工作人员开始处理','{\"source\": \"miniprogram_demo\"}','2026-07-30 08:07:40','2026-07-30 08:15:00',NULL,'MANUAL_HANDLING','演示人员','miniprogram'),(15,'c269849ab7ac437ea00c50e9346a157d','mp_demo_high_001','manual_broadcast','HIGH','success','PARTIAL_SUCCESS','{\"reason\": null, \"remark\": null, \"content\": null, \"assignee\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"PENDING\", \"device_ids\": [], \"from_status\": \"PENDING\", \"template_id\": \"PERSON_HIGH\", \"operator_role\": \"miniprogram\", \"assignee_phone\": null, \"broadcast_result\": {\"text\": \"紧急警告，当前区域存在重大安全风险，请立即撤离。\", \"items\": [{\"result\": \"SUCCESS\", \"message\": \"LOCAL_AUDIO accepted\", \"device_id\": 1, \"device_name\": \"本机耳机/音响测试\", \"vendor_type\": \"LOCAL_AUDIO\"}, {\"result\": \"FAILED\", \"message\": \"USB_AUDIO only supports recorded audio playback\", \"device_id\": 2, \"device_name\": \"Jetson USB外放\", \"vendor_type\": \"USB_AUDIO\"}], \"result\": \"PARTIAL_SUCCESS\", \"success\": true, \"browser_tts\": true}, \"canonical_action_type\": \"MANUAL_BROADCAST\"}','2026-07-30 08:23:53','2026-07-30 08:23:53','PENDING','PENDING','微信小程序工作人员','miniprogram'),(16,'0dccb68bfb4d45aba8c8e8dac97265bf','mp_demo_high_001','staff_accepted','HIGH','success','工作人员开始处理','{\"remark\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"MANUAL_PROCESSING\", \"from_status\": \"WAITING_MANUAL\", \"canonical_action_type\": \"STAFF_ACCEPTED\"}','2026-07-30 08:24:48','2026-07-30 08:24:48','WAITING_MANUAL','MANUAL_PROCESSING','微信小程序工作人员','miniprogram'),(17,'f2a29cba11874458a9ac5b5374ddcbb8','mp_demo_low_001','manual_broadcast','LOW','success','PARTIAL_SUCCESS','{\"reason\": null, \"remark\": null, \"content\": null, \"assignee\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"PROCESSING\", \"device_ids\": [], \"from_status\": \"PROCESSING\", \"template_id\": \"PERSON_LOW\", \"operator_role\": \"miniprogram\", \"assignee_phone\": null, \"broadcast_result\": {\"text\": \"您已进入安全警戒区域，请立即远离水边危险区域。\", \"items\": [{\"result\": \"SUCCESS\", \"message\": \"LOCAL_AUDIO accepted\", \"device_id\": 1, \"device_name\": \"本机耳机/音响测试\", \"vendor_type\": \"LOCAL_AUDIO\"}, {\"result\": \"FAILED\", \"message\": \"USB_AUDIO only supports recorded audio playback\", \"device_id\": 2, \"device_name\": \"Jetson USB外放\", \"vendor_type\": \"USB_AUDIO\"}], \"result\": \"PARTIAL_SUCCESS\", \"success\": true, \"browser_tts\": true}, \"canonical_action_type\": \"MANUAL_BROADCAST\"}','2026-07-30 14:05:35','2026-07-30 14:05:36','PROCESSING','PROCESSING','微信小程序工作人员','miniprogram'),(18,'a45b9a0646054bde93c1faa2f29709a6','mp_demo_high_001','staff_completed','HIGH','success','上传现场照片，完成处置','{\"remark\": \"\", \"result\": \"OTHER\", \"operator\": \"微信小程序工作人员\", \"photo_url\": \"http://localhost:9000/dam/safety-events/field-results/mp_demo_high_001/2026-07-30/784d1044804b4317bca11938ebcbb4cc.jpg\", \"result_label\": \"其他\", \"canonical_action_type\": \"STAFF_COMPLETED\"}','2026-07-30 14:24:24','2026-07-30 14:24:24','MANUAL_PROCESSING','RESOLVED','微信小程序工作人员','miniprogram'),(19,'2de160274cd74dc9b2ebdad5d3d749ba','mp_demo_high_001','event_manual_closed','HIGH','success','其他，事件闭环','{\"reason\": \"manual_close\", \"remark\": \"\", \"result\": \"OTHER\", \"operator\": \"微信小程序工作人员\", \"photo_url\": \"http://localhost:9000/dam/safety-events/field-results/mp_demo_high_001/2026-07-30/784d1044804b4317bca11938ebcbb4cc.jpg\", \"result_label\": \"其他\", \"canonical_action_type\": \"MANUAL_RESOLVED\"}','2026-07-30 14:24:24','2026-07-30 14:24:24','MANUAL_PROCESSING','RESOLVED','微信小程序工作人员','miniprogram'),(20,'29edcf90ddc045d984b2ccccd99c09bf','mp_demo_high_processing_002','manual_broadcast','HIGH','success','SUCCESS','{\"reason\": null, \"remark\": null, \"content\": null, \"assignee\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"PROCESSING\", \"device_ids\": [], \"from_status\": \"PROCESSING\", \"template_id\": \"PERSON_HIGH\", \"operator_role\": \"miniprogram\", \"assignee_phone\": null, \"broadcast_result\": {\"text\": \"紧急警告，当前区域存在重大安全风险，请立即撤离。\", \"items\": [{\"result\": \"SUCCESS\", \"message\": \"USB_AUDIO played via plughw:2,0\", \"device_id\": 2, \"device_name\": \"Jetson USB外放\", \"vendor_type\": \"USB_AUDIO\"}], \"result\": \"SUCCESS\", \"success\": true, \"browser_tts\": false}, \"canonical_action_type\": \"MANUAL_BROADCAST\"}','2026-07-31 07:08:40','2026-07-31 07:08:48','PROCESSING','PROCESSING','微信小程序工作人员','miniprogram'),(21,'ba2727a9d9e54f268e47e6d4e6e22c85','mp_demo_low_001','manual_broadcast','LOW','success','SUCCESS','{\"reason\": null, \"remark\": null, \"content\": null, \"assignee\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"PROCESSING\", \"device_ids\": [], \"from_status\": \"PROCESSING\", \"template_id\": \"PERSON_LOW\", \"operator_role\": \"miniprogram\", \"assignee_phone\": null, \"broadcast_result\": {\"text\": \"您已进入安全警戒区域，请立即远离水边危险区域。\", \"items\": [{\"result\": \"SUCCESS\", \"message\": \"USB_AUDIO played via plughw:2,0\", \"device_id\": 2, \"device_name\": \"Jetson USB外放\", \"vendor_type\": \"USB_AUDIO\"}], \"result\": \"SUCCESS\", \"success\": true, \"browser_tts\": false}, \"canonical_action_type\": \"MANUAL_BROADCAST\"}','2026-07-31 07:08:53','2026-07-31 07:09:00','PROCESSING','PROCESSING','微信小程序工作人员','miniprogram'),(22,'cf699e5e255948f9b161f9a1f340e242','mp_demo_high_processing_002','manual_broadcast','HIGH','success','SUCCESS','{\"reason\": null, \"remark\": null, \"content\": null, \"assignee\": null, \"operator\": \"微信小程序工作人员\", \"to_status\": \"PROCESSING\", \"device_ids\": [], \"from_status\": \"PROCESSING\", \"template_id\": \"PERSON_HIGH\", \"operator_role\": \"miniprogram\", \"assignee_phone\": null, \"broadcast_result\": {\"text\": \"紧急警告，当前区域存在重大安全风险，请立即撤离。\", \"items\": [{\"result\": \"SUCCESS\", \"message\": \"USB_AUDIO played via plughw:2,0\", \"device_id\": 2, \"device_name\": \"Jetson USB外放\", \"vendor_type\": \"USB_AUDIO\"}], \"result\": \"SUCCESS\", \"success\": true, \"browser_tts\": false}, \"canonical_action_type\": \"MANUAL_BROADCAST\"}','2026-07-31 08:56:18','2026-07-31 08:56:26','PROCESSING','PROCESSING','微信小程序工作人员','miniprogram'),(23,'661f8b7ed9084ab688f85feff1c1ecda','mp_demo_high_processing_001','staff_completed','HIGH','success','上传现场照片，完成处置','{\"remark\": \"\", \"result\": \"DRIVEN_AWAY\", \"operator\": \"微信小程序工作人员\", \"photo_url\": \"http://localhost:9000/dam/safety-events/field-results/mp_demo_high_processing_001/2026-08-02/160743aaf6bf4635975a41d430d7e043.jpg\", \"result_label\": \"已完成驱离\", \"canonical_action_type\": \"STAFF_COMPLETED\"}','2026-08-02 07:46:23','2026-08-02 07:46:23','MANUAL_PROCESSING','RESOLVED','微信小程序工作人员','miniprogram'),(24,'942e571de8f745deb374816f5881fc18','mp_demo_high_processing_001','event_manual_closed','HIGH','success','已完成驱离，事件闭环','{\"reason\": \"manual_close\", \"remark\": \"\", \"result\": \"DRIVEN_AWAY\", \"operator\": \"微信小程序工作人员\", \"photo_url\": \"http://localhost:9000/dam/safety-events/field-results/mp_demo_high_processing_001/2026-08-02/160743aaf6bf4635975a41d430d7e043.jpg\", \"result_label\": \"已完成驱离\", \"canonical_action_type\": \"MANUAL_RESOLVED\"}','2026-08-02 07:46:23','2026-08-02 07:46:23','MANUAL_PROCESSING','RESOLVED','微信小程序工作人员','miniprogram');
/*!40000 ALTER TABLE `safety_event_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `safety_event_task`
--

DROP TABLE IF EXISTS `safety_event_task`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `safety_event_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '派单任务ID',
  `event_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '事件唯一编号',
  `assignee` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '现场处置人员',
  `assignee_phone` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '联系电话',
  `dispatch_operator` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '派单人员',
  `task_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务状态',
  `task_note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '派单说明',
  `dispatched_at` datetime DEFAULT NULL COMMENT '派单时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  `accepted_at` datetime DEFAULT NULL COMMENT '接单时间',
  PRIMARY KEY (`id`),
  KEY `ix_safety_event_task_task_status` (`task_status`),
  KEY `ix_safety_event_task_event_id` (`event_id`),
  KEY `ix_safety_event_task_dispatched_at` (`dispatched_at`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `safety_event_task`
--

LOCK TABLES `safety_event_task` WRITE;
/*!40000 ALTER TABLE `safety_event_task` DISABLE KEYS */;
INSERT INTO `safety_event_task` VALUES (1,'mp_demo_high_processing_001','演示人员',NULL,'SYSTEM','COMPLETED','小程序演示：工作人员主动现场处理','2026-07-30 08:06:40','2026-08-02 07:46:23','2026-07-30 08:07:40'),(2,'mp_demo_high_001','微信小程序工作人员',NULL,'SYSTEM','COMPLETED','小程序工作人员主动现场处理','2026-07-30 08:24:48','2026-07-30 14:24:24','2026-07-30 08:24:48');
/*!40000 ALTER TABLE `safety_event_task` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sys_device`
--

DROP TABLE IF EXISTS `sys_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sys_device` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '设备ID',
  `device_code` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设备编号',
  `device_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '设备名称',
  `device_type` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '设备类型',
  `serial_port` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '串口地址',
  `modbus_addr` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Modbus 地址',
  `location` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '安装位置',
  `longitude` float DEFAULT NULL COMMENT '经度',
  `latitude` float DEFAULT NULL COMMENT '纬度',
  `status` int DEFAULT NULL COMMENT '状态: 0-离线 1-在线',
  `deleted` int DEFAULT NULL COMMENT '逻辑删除: 0-正常 1-已删除',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `device_code` (`device_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sys_device`
--

LOCK TABLES `sys_device` WRITE;
/*!40000 ALTER TABLE `sys_device` DISABLE KEYS */;
/*!40000 ALTER TABLE `sys_device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sys_trigger_rule`
--

DROP TABLE IF EXISTS `sys_trigger_rule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sys_trigger_rule` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '规则ID',
  `rule_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规则名称',
  `rule_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规则类型: threshold/variation',
  `sensor_type` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '传感器类型',
  `condition_expr` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '条件表达式',
  `alarm_level` int DEFAULT NULL COMMENT '告警级别: 1-一般 2-重要 3-紧急',
  `enable_status` int DEFAULT NULL COMMENT '启用状态: 0-禁用 1-启用',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sys_trigger_rule`
--

LOCK TABLES `sys_trigger_rule` WRITE;
/*!40000 ALTER TABLE `sys_trigger_rule` DISABLE KEYS */;
/*!40000 ALTER TABLE `sys_trigger_rule` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sys_user`
--

DROP TABLE IF EXISTS `sys_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sys_user` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户名',
  `password` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'bcrypt哈希密码',
  `real_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '真实姓名',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `email` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱',
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '角色: admin-管理员/user-普通用户',
  `status` int NOT NULL DEFAULT '1' COMMENT '状态: 1-启用 0-禁用',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `idx_username` (`username`),
  KEY `idx_role` (`role`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sys_user`
--

LOCK TABLES `sys_user` WRITE;
/*!40000 ALTER TABLE `sys_user` DISABLE KEYS */;
INSERT INTO `sys_user` VALUES (1,'admin','$2b$12$q6flNeYPtqjqNZpbitCvLOHhGAOZ2pEOLRP1Otkwv0LoTvxwP12AS','管理员',NULL,NULL,'admin',1,'2026-07-02 13:04:55','2026-07-06 10:52:01');
/*!40000 ALTER TABLE `sys_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'dam_system'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-02 11:32:36
