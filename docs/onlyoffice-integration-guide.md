# OnlyOffice 集成指南

本指南将帮助您在 box_system 项目中集成 OnlyOffice 文档编辑功能。

## 📋 目录

- [功能概述](#功能概述)
- [系统要求](#系统要求)
- [快速部署](#快速部署)
- [配置说明](#配置说明)
- [前端集成](#前端集成)
- [后端集成](#后端集成)
- [API 文档](#api-文档)
- [常见问题](#常见问题)
- [高级配置](#高级配置)

## 功能概述

OnlyOffice 集成提供以下功能：

- ✅ **在线文档编辑** - 支持 Word、Excel、PPT、PDF 等格式
- ✅ **协同编辑** - 多人实时协作编辑同一文档
- ✅ **版本控制** - 自动保存和历史版本管理
- ✅ **文档预览** - 在线预览各种文档格式
- ✅ **文件管理** - 上传、下载、删除文档
- ✅ **权限控制** - 编辑、只读、填写表单等权限

## 系统要求

### 硬件要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 2 核 | 4 核 |
| 内存 | 2 GB | 4 GB |
| 磁盘 | 10 GB | 50 GB |

### 软件要求

- Docker 20.10+
- Docker Compose 2.0+
- 现代浏览器（Chrome 80+、Firefox 75+、Safari 14+、Edge 80+）

## 快速部署

### 1. 启动 OnlyOffice Document Server

```bash
cd /home/jetson/box_system

# 启动所有服务（包括 OnlyOffice）
docker compose up -d

# 查看服务状态
docker compose ps
```

### 2. 验证 OnlyOffice 服务

```bash
# 检查 OnlyOffice 健康状态
curl http://localhost:8080/healthcheck

# 预期返回：{"status":"ok"}
```

### 3. 访问 OnlyOffice 管理界面

打开浏览器访问：`http://localhost:8080`

## 配置说明

### 环境变量配置

在项目根目录创建 `.env.onlyoffice` 文件：

```bash
# OnlyOffice Document Server 地址
ONLYOFFICE_SERVER_URL=http://localhost:8080

# JWT 密钥（用于文档安全，生产环境必须修改）
ONLYOFFICE_JWT_SECRET=your-secret-key-here

# 文档存储路径
DOCUMENT_STORAGE_PATH=/var/www/onlyoffice/Data

# 前端 OnlyOffice 地址（用于加载 API 脚本）
VITE_ONLYOFFICE_URL=http://localhost:8080
```

### Docker Compose 配置

在 `docker-compose.yml` 中添加 OnlyOffice 服务：

```yaml
# ========== OnlyOffice 文档编辑服务 ==========
onlyoffice-documentserver:
  image: onlyoffice/documentserver:latest
  container_name: dam-onlyoffice
  restart: unless-stopped
  ports:
    - "8080:80"
  volumes:
    - onlyoffice_data:/var/www/onlyoffice/Data
    - onlyoffice_logs:/var/log/onlyoffice
  environment:
    JWT_SECRET: ${ONLYOFFICE_JWT_SECRET:-mysecretkey}
    JWT_HEADER: Authorization
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost/healthcheck"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s

volumes:
  onlyoffice_data:
  onlyoffice_logs:
```

## 前端集成

### 1. 引入组件

```vue
<template>
  <OnlyOfficeEditor
    :document-url="documentUrl"
    :document-title="documentTitle"
    document-type="word"
    mode="edit"
    :user="currentUser"
    @ready="onEditorReady"
    @save="onDocumentSave"
  />
</template>

<script setup>
import { ref } from 'vue'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'

const documentUrl = ref('http://localhost:8090/api/onlyoffice/document/doc_001')
const documentTitle = ref('示例文档.docx')
const currentUser = ref({
  id: 'user_001',
  name: '张三'
})

const onEditorReady = () => {
  console.log('编辑器已准备就绪')
}

const onDocumentSave = () => {
  console.log('文档已保存')
}
</script>
```

### 2. 组件属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `documentUrl` | String | 必填 | 文档访问 URL |
| `documentTitle` | String | '未命名文档' | 文档标题 |
| `documentType` | String | 'word' | 文档类型：word/cell/slide |
| `mode` | String | 'edit' | 编辑模式：edit/view/fillForms |
| `editorHeight` | String | '600px' | 编辑器高度 |
| `documentKey` | String | '' | 文档 key（协同编辑） |
| `user` | Object | {id, name} | 用户信息 |
| `callbackUrl` | String | '' | 回调 URL |
| `lang` | String | 'zh-CN' | 界面语言 |

### 3. 组件事件

| 事件 | 参数 | 说明 |
|------|------|------|
| `ready` | - | 编辑器准备就绪 |
| `documentStateChange` | event | 文档状态变化 |
| `error` | errorMsg | 错误发生 |
| `save` | - | 文档保存 |
| `close` | - | 编辑器关闭 |

### 4. 组件方法

```javascript
const editorRef = ref(null)

// 获取编辑器实例
editorRef.value.getEditor()

// 强制保存
editorRef.value.save()

// 重新加载文档
editorRef.value.reload()

// 销毁编辑器
editorRef.value.destroy()
```

## 后端集成

### 1. 注册 API 路由

在 FastAPI 应用中注册 OnlyOffice 路由：

```python
# main.py 或 app.py
from fastapi import FastAPI
from app.api.onlyoffice import router as onlyoffice_router

app = FastAPI()

# 注册 OnlyOffice 路由
app.include_router(onlyoffice_router)
```

### 2. API 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/onlyoffice/upload` | POST | 上传文档 |
| `/api/onlyoffice/document/{id}` | GET | 获取文档文件 |
| `/api/onlyoffice/callback` | POST | 文档编辑回调 |
| `/api/onlyoffice/editor-config/{id}` | GET | 获取编辑器配置 |
| `/api/onlyoffice/document/{id}` | DELETE | 删除文档 |
| `/api/onlyoffice/documents` | GET | 获取文档列表 |
| `/api/onlyoffice/health` | GET | 健康检查 |

### 3. 使用示例

```python
import httpx

async def upload_document(file_path: str, user_id: str):
    """上传文档示例"""
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f)}
            data = {
                "user_id": user_id,
                "user_name": "测试用户"
            }
            response = await client.post(
                "http://localhost:8090/api/onlyoffice/upload",
                files=files,
                data=data
            )
            return response.json()

async def get_editor_config(document_id: str, user_id: str):
    """获取编辑器配置示例"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8090/api/onlyoffice/editor-config/{document_id}",
            params={
                "user_id": user_id,
                "user_name": "测试用户",
                "mode": "edit"
            }
        )
        return response.json()
```

## API 文档

### 上传文档

**请求：**
```http
POST /api/onlyoffice/upload
Content-Type: multipart/form-data

file: (二进制文件)
user_id: user_001
user_name: 张三
```

**响应：**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_user_001_1690000000000",
    "document_key": "abc123def456",
    "title": "示例文档.docx",
    "url": "http://localhost:8090/api/onlyoffice/document/doc_user_001_1690000000000",
    "file_type": "docx",
    "file_size": 102400,
    "document_type": "word",
    "created_at": "2024-07-21T10:00:00",
    "owner_id": "user_001",
    "owner_name": "张三"
  }
}
```

### 获取编辑器配置

**请求：**
```http
GET /api/onlyoffice/editor-config/{document_id}?user_id=user_001&user_name=张三&mode=edit
```

**响应：**
```json
{
  "success": true,
  "data": {
    "document": {
      "fileType": "docx",
      "key": "abc123def456",
      "title": "示例文档.docx",
      "url": "http://localhost:8090/api/onlyoffice/document/doc_001",
      "permissions": {
        "comment": true,
        "download": true,
        "edit": true,
        "fillForms": true,
        "print": true,
        "review": true
      }
    },
    "documentType": "word",
    "editorConfig": {
      "callbackUrl": "http://localhost:8090/api/onlyoffice/callback",
      "lang": "zh-CN",
      "mode": "edit",
      "user": {
        "id": "user_001",
        "name": "张三"
      },
      "customization": {
        "forcesave": true
      }
    },
    "onlyoffice_server_url": "http://localhost:8080"
  }
}
```

### 文档编辑回调

**请求：**
```http
POST /api/onlyoffice/callback
Content-Type: application/json

{
  "key": "abc123def456",
  "status": 1,
  "url": "http://onlyoffice-server/cache/files/...",
  "users": ["user_001", "user_002"]
}
```

**状态码说明：**

| 状态码 | 说明 |
|--------|------|
| 0 | 正在编辑 |
| 1 | 文档已保存 |
| 2 | 文档保存错误 |
| 3 | 文档关闭 |
| 4 | 正在协同编辑 |
| 6 | 正在编辑（强制保存后） |
| 7 | 文档已保存（强制保存后） |

**响应：**
```json
{
  "error": 0
}
```

## 常见问题

### Q1: OnlyOffice 无法启动怎么办？

**A:** 检查以下几点：
1. 确保 Docker 有足够内存（至少 2GB）
2. 检查端口 8080 是否被占用
3. 查看容器日志：`docker logs dam-onlyoffice`

### Q2: 文档无法保存怎么办？

**A:** 检查以下几点：
1. 确认回调 URL 配置正确
2. 检查后端服务是否正常运行
3. 查看浏览器控制台是否有错误
4. 检查 OnlyOffice 容器日志

### Q3: 如何配置 HTTPS？

**A:** 参考 OnlyOffice 官方文档配置 SSL 证书，或使用 Nginx 反向代理：

```nginx
server {
    listen 443 ssl;
    server_name document.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Q4: 如何支持更多文件格式？

**A:** OnlyOffice 默认支持以下格式：
- Word: docx, doc, odt, rtf, txt, html
- Excel: xlsx, xls, ods, csv
- PowerPoint: pptx, ppt, odp
- PDF: pdf

如需支持更多格式，参考 OnlyOffice 官方文档进行配置。

### Q5: 如何优化性能？

**A:** 可以通过以下方式优化：
1. 增加 OnlyOffice 容器内存限制
2. 配置文档缓存
3. 使用 CDN 加速静态资源
4. 启用文档压缩

## 高级配置

### 1. 自定义主题

```javascript
const config = {
  // ... 其他配置
  editorConfig: {
    customization: {
      // 自定义 logo
      logo: {
        image: 'https://example.com/logo.png',
        imageEmbedded: 'https://example.com/logo-embedded.png',
        url: 'https://example.com'
      },
      // 自定义颜色
      colors: {
        toolbarBackground: '#f5f5f5',
        toolbarActive: '#4caf50',
        headerBackground: '#ffffff',
        headerText: '#333333'
      }
    }
  }
}
```

### 2. 插件开发

OnlyOffice 支持插件扩展，参考官方插件开发文档：
- 插件开发指南：https://api.onlyoffice.com/docs/plugin-and-macros/

### 3. 集成第三方存储

如需集成 MinIO、OSS 等第三方存储，需要修改后端文档存储逻辑：

```python
from minio import Minio

class MinioDocumentStorage:
    def __init__(self):
        self.client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
    
    async def upload(self, file_data: bytes, object_name: str):
        self.client.put_object(
            "documents",
            object_name,
            io.BytesIO(file_data),
            len(file_data)
        )
    
    async def download(self, object_name: str) -> bytes:
        response = self.client.get_object("documents", object_name)
        return response.read()
```

## 技术支持

如有问题，请参考以下资源：

- OnlyOffice 官方文档：https://api.onlyoffice.com/
- OnlyOffice GitHub：https://github.com/ONLYOFFICE
- 社区论坛：https://forum.onlyoffice.com/

## 许可证

OnlyOffice Document Server 社区版采用 AGPL v3 许可证。
商业使用请购买商业许可证：https://www.onlyoffice.com/
