-- 补齐模型库中文描述与标签
-- 仅更新展示元信息，不修改运行状态、部署绑定和 IO Schema。

USE dam_system;

UPDATE model_registry
SET
  name = 'Qwen3.5-0.8B 轻量语言模型',
  description = '常驻本地的轻量语言模型，适合快速文本理解、结构化提取和规则编排辅助。',
  framework = 'vLLM',
  architecture = 'Transformer',
  model_type = '大语言模型',
  tags = JSON_ARRAY('文本理解', '结构化提取', '本地部署', '轻量模型', '常驻服务')
WHERE id = 9;

UPDATE model_registry
SET
  name = 'Qwen3-VL-4B-Instruct 视觉语言模型',
  description = '本地视觉语言模型，支持图像与文本联合理解，可用于巡查画面解读、风险线索提取和多模态问答。',
  framework = 'vLLM',
  architecture = 'Transformer',
  model_type = '视觉语言模型',
  tags = JSON_ARRAY('视觉语言模型', '图像理解', '文本理解', '多模态分析', '本地部署')
WHERE id = 10;

UPDATE model_registry
SET
  name = 'YOLO26 灾害分类模型',
  description = '面向地震、洪水、滑坡、泥石流场景训练的高精度图像分类模型，适合作为灾害图像识别主模型。',
  framework = 'Ultralytics',
  architecture = 'YOLO26x',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('灾害分类', '地震', '洪水', '滑坡', '泥石流', '专用模型')
WHERE id = 12;

UPDATE model_registry
SET
  name = 'Qwen3.5-35B 云端增强推理模型',
  description = '云端大语言模型服务，适合复杂灾情研判、长文本分析和评估报告生成。',
  framework = 'vLLM',
  architecture = 'Transformer',
  model_type = '大语言模型',
  tags = JSON_ARRAY('文本推理', '报告生成', '灾情研判', '云端部署', '增强推理')
WHERE id = 13;

UPDATE model_registry
SET
  name = 'Qwen-VL-4B 本地视觉语言模型',
  description = '边缘侧视觉语言模型，支持巡查图像、问题文本和知识库检索结果的联合分析。',
  framework = 'vLLM',
  architecture = 'Transformer',
  model_type = '视觉语言模型',
  tags = JSON_ARRAY('视觉语言模型', '巡查分析', '图像理解', '知识库增强', '本地部署')
WHERE id = 14;

UPDATE model_registry
SET
  name = 'MobileNetV4 灾害分类模型',
  description = '面向地震、洪水、滑坡、泥石流场景微调的轻量图像分类模型，适合资源受限环境快速推理。',
  framework = 'TIMM',
  architecture = 'MobileNetV4',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('灾害分类', '轻量模型', '快速推理', '地震', '洪水', '专用模型')
WHERE id = 15;

UPDATE model_registry
SET
  name = 'MobileNetV4 ImageNet 基线模型',
  description = 'MobileNetV4 的 ImageNet 预训练基线模型，用于灾害分类微调前后的效果对照。',
  framework = 'TIMM',
  architecture = 'MobileNetV4',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('通用分类', 'ImageNet', '轻量模型', '基线模型', '对照评估')
WHERE id = 16;

UPDATE model_registry
SET
  name = 'RepViT 灾害分类模型',
  description = '面向地震、洪水、滑坡、泥石流场景微调的图像分类模型，兼顾识别精度与推理开销。',
  framework = 'TIMM',
  architecture = 'RepViT',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('灾害分类', '轻量模型', '地震', '洪水', '滑坡', '专用模型')
WHERE id = 17;

UPDATE model_registry
SET
  name = 'RepViT ImageNet 基线模型',
  description = 'RepViT 的 ImageNet 预训练基线模型，用于灾害分类训练和模型效果对照。',
  framework = 'TIMM',
  architecture = 'RepViT',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('通用分类', 'ImageNet', '轻量模型', '基线模型', '对照评估')
WHERE id = 18;

UPDATE model_registry
SET
  name = 'YOLO26x ImageNet 基线模型',
  description = 'YOLO26x 分类架构的 ImageNet 预训练基线模型，用于灾害分类模型的训练对照。',
  framework = 'Ultralytics',
  architecture = 'YOLO26x',
  model_type = '图像分类模型',
  tags = JSON_ARRAY('通用分类', 'ImageNet', '分类基线', '基线模型', '对照评估')
WHERE id = 19;

UPDATE model_registry
SET
  name = 'YOLO26x 人员目标检测模型',
  description = '面向库区人员和船只相关事件训练的目标检测模型，输出船只、涉水人员、人员、人群等目标。',
  framework = 'Ultralytics',
  architecture = 'YOLO26x',
  model_type = '目标检测模型',
  tags = JSON_ARRAY('人员检测', '船只检测', '涉水人员', '人群检测', '事件识别', '专用模型')
WHERE id = 20;

UPDATE model_registry
SET
  name = 'YOLO26x COCO 目标检测基线模型',
  description = '基于 COCO 预训练权重的通用目标检测模型，可作为人员和船只检测的兜底与对照模型。',
  framework = 'Ultralytics',
  architecture = 'YOLO26x',
  model_type = '目标检测模型',
  tags = JSON_ARRAY('通用检测', 'COCO', '人员检测', '船只检测', '基线模型', '兜底模型')
WHERE id = 21;
