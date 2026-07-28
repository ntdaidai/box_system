# dam-model-library API 接口文档

## 概述

dam-model-library 是一个轻量级模型库服务，为其他系统提供模型注册和 Docker 容器部署管理能力。

- **服务地址**: `http://localhost:5001`
- **API 前缀**: `/api`
- **文档地址**:
  - Swagger UI: `http://localhost:5001/docs`
  - ReDoc: `http://localhost:5001/redoc`

## 接口服务列表

| 服务 | 文档 | 说明 |
|------|------|------|
| 健康检查 | [health.md](health.md) | 检查服务、MySQL、Docker 连通性 |
| 模型注册 | [registry.md](registry.md) | 模型 CRUD + 批量操作 |
| 部署绑定 | [binding.md](binding.md) | 容器/镜像绑定管理 |
| 容器生命周期 | [lifecycle.md](lifecycle.md) | 启动/停止/重启/重建容器 |
| 容器日志 | [logs.md](logs.md) | 获取容器日志 |
| IO Schema | [io-schema.md](io-schema.md) | 模型输入输出 Schema 管理 |
| 模型推理 | [infer.md](infer.md) | 模型推理接口 |
| Docker 测试 | [docker.md](docker.md) | Docker 容器查询测试接口 |

## 统一响应格式

### 成功响应 (Result)
```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### 分页响应 (PageResult)
```json
{
  "code": 200,
  "message": "success",
  "data": [...],
  "total": 100,
  "page_num": 1,
  "page_size": 10
}
```

### 错误响应
```json
{
  "code": 400,
  "message": "错误信息",
  "data": null
}
```

## 通用状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 状态冲突（如运行中禁止删除） |
| 500 | 服务器内部错误 |

## 模型运行状态

```
stopped (默认) --> starting --> running --> stopping --> stopped
                   \            \ error   /
```

| 状态 | 说明 |
|------|------|
| stopped | 已停止 |
| starting | 启动中 |
| running | 运行中 |
| stopping | 停止中 |
| error | 异常 |

## 数据库表结构

| 表名 | 说明 |
|------|------|
| model_registry | 模型注册表 |
| model_deploy_binding | 部署绑定表 |
| model_io_schema | IO Schema 表 |
| model_operation_log | 操作日志表 |

详细表结构请参考 `scripts/init.sql`。
