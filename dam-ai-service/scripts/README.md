# 风灾条件初始化脚本

## 脚本说明

### `init_wind_conditions.py`

初始化风灾相关的 ECA 规则，包括：

1. **数据源配置** - 风速风向传感器
2. **条件库** - 风力等级 6-12 级的触发条件
3. **事件库** - 对应的风灾预警/警报事件
4. **行为流程** - 三级响应流程（预警/警报/紧急）
5. **流程步骤** - 带资源感知优先级的模型调用链
6. **事件-条件关联** - 事件触发条件
7. **事件-流程关联** - 事件触发的响应流程

## 风力等级标准

基于《风力等级》国家标准 (GB/T 28591-2012)：

| 等级 | 名称 | 风速 (m/s) | 条件表达式 | 风险等级 | 响应流程 |
|------|------|-----------|-----------|----------|----------|
| 6 | 强风 | 10.8~13.8 | `wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9` | 1级（低） | 预警响应 |
| 7 | 疾风 | 13.9~17.1 | `wind_speed_ms >= 13.9 AND wind_speed_ms < 17.2` | 1级（低） | 预警响应 |
| 8 | 大风 | 17.2~20.7 | `wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8` | 2级（中） | 警报响应 |
| 9 | 烈风 | 20.8~24.4 | `wind_speed_ms >= 20.8 AND wind_speed_ms < 24.5` | 2级（中） | 警报响应 |
| 10 | 狂风 | 24.5~28.4 | `wind_speed_ms >= 24.5 AND wind_speed_ms < 28.5` | 3级（高） | 紧急响应 |
| 11 | 暴风 | 28.5~32.6 | `wind_speed_ms >= 28.5 AND wind_speed_ms < 32.7` | 3级（高） | 紧急响应 |
| 12 | 飓风 | ≥32.7 | `wind_speed_ms >= 32.7` | 3级（高） | 紧急响应 |

### 条件表达式语法

区间表达式使用 `AND` 连接两个条件：
```sql
-- 左闭右开区间 [下限, 上限)
wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9

-- 最高级别无上限
wind_speed_ms >= 32.7
```

## 响应流程说明

### 预警响应（6-7级）
- 只记录日志
- 不触发模型推理
- 不发送告警

### 警报响应（8-9级）
- YOLO 检测风灾损害（优先级 1）
- 发送告警通知（优先级 1）
- GPU 高负载时只执行告警

### 紧急响应（10-12级）
- YOLO 检测风灾损害（优先级 1）
- SAM 分割受损区域（优先级 2）
- Qwen 综合分析风险（优先级 3）
- 发送紧急告警（优先级 1）
- GPU 高负载时跳过 Qwen，中负载时跳过 SAM+Qwen

## 使用方法

### 方式一：Python 脚本

```bash
cd /home/jetson/box_system/dam-ai-service
python scripts/init_wind_conditions.py
```

### 方式二：SQL 脚本

```bash
mysql -u root -p dam_system < scripts/init_wind_conditions.sql
```

### 方式三：API 接口

```bash
# 手动触发事件检查
curl -X POST http://localhost:8090/api/v1/eca/check \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 验证

初始化完成后，可以通过以下方式验证：

```bash
# 查看条件库
curl http://localhost:8090/api/v1/eca/conditions?source_id=2 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 查看事件库
curl http://localhost:8090/api/v1/eca/events?event_category=environment \
  -H "Authorization: Bearer YOUR_TOKEN"

# 查看调度器状态
curl http://localhost:8090/api/v1/eca/scheduler/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 注意事项

1. **持续时间设置**
   - 6-8级、12级：`duration=0`，立即触发
   - 9-11级：`duration=3`，持续 3 分钟才触发

2. **资源感知优先级**
   - `priority=1`：critical，必须执行（告警、YOLO 检测）
   - `priority=2`：important，重要步骤（SAM 分割）
   - `priority=3`：optional，可选步骤（Qwen 分析）

3. **幂等性**
   - 脚本可重复执行，已存在的记录会更新而非重复创建
