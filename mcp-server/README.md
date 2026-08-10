# Dam Knowledge MCP Server

把库坝系统知识库暴露给支持 MCP 的模型/Agent。该目录已经纳入 `/home/jetson/box_system/docker-compose.yml`，可作为 Docker 服务运行。

## 启动

```bash
cd /home/jetson/box_system
docker compose up -d dam-knowledge-mcp
```

## Tools

- `list_knowledge_bases`：列出已启用知识库
- `search_knowledge`：按问题检索知识片段，返回内容、分数和来源

## MCP 客户端配置示例

如果模型客户端支持连接本机 Docker 中的 stdio MCP 服务，可使用：

```json
{
  "mcpServers": {
    "dam-knowledge": {
      "command": "docker",
      "args": ["exec", "-i", "dam-knowledge-mcp", "python", "/app/main.py"]
    }
  }
}
```
