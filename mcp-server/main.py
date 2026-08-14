"""MCP server exposing dam knowledge-base tools."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import anyio
import httpx
import mcp_types as types
from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server


KNOWLEDGE_API_BASE = os.getenv(
    "KNOWLEDGE_API_BASE",
    "http://127.0.0.1:8090/api/v1/knowledge",
).rstrip("/")


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{KNOWLEDGE_API_BASE}{path}", json=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("code") == 200 and "data" in data:
            return data["data"]
        return data


async def _get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{KNOWLEDGE_API_BASE}{path}")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("code") == 200 and "data" in data:
            return data["data"]
        return data


async def list_knowledge_bases() -> list[dict[str, Any]]:
    """List enabled knowledge bases available to the model."""
    bases = await _get("/bases")
    return [base for base in bases if base.get("enabled")]


async def search_knowledge(
    query: str,
    base_ids: Optional[list[int]] = None,
    category: str = "",
    source_type: str = "",
    event_type: str = "",
    risk_level: str = "",
    top_k: int = 8,
) -> dict[str, Any]:
    """Search dam inspection knowledge and return source-grounded snippets."""
    return await _post(
        "/mcp/search_knowledge",
        {
            "query": query,
            "base_ids": base_ids or [],
            "category": category,
            "source_type": source_type,
            "event_type": event_type,
            "risk_level": risk_level,
            "top_k": top_k,
        },
    )


async def get_knowledge_chunk(chunk_id: int) -> dict[str, Any]:
    """Return a complete source citation for one knowledge chunk."""
    return await _get(f"/chunks/{chunk_id}")


async def trace_report_claim(
    claim: str,
    candidate_chunk_ids: Optional[list[int]] = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Trace a report sentence back to the most relevant knowledge chunks."""
    return await _post(
        "/mcp/trace_report_claim",
        {
            "claim": claim,
            "candidate_chunk_ids": candidate_chunk_ids or [],
            "top_k": top_k,
        },
    )


TOOLS = [
    types.Tool(
        name="list_knowledge_bases",
        description="列出可供模型使用的库坝巡查知识库。",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="search_knowledge",
        description="检索库坝巡查知识库，返回带来源的知识片段。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题或关键词"},
                "base_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "可选知识库ID列表",
                },
                "category": {"type": "string", "description": "可选分类过滤"},
                "source_type": {"type": "string", "description": "可选来源类型过滤，如 natural_disaster/person_safety/risk_rule/device_linkage/emergency_response"},
                "event_type": {"type": "string", "description": "可选事件类型过滤，如 flood/landslide/illegal_fishing"},
                "risk_level": {"type": "string", "description": "可选风险等级过滤，如 low/medium/high/critical"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_knowledge_chunk",
        description="根据 chunk_id 获取知识片段的完整来源、条款、章节、原文和文档链接。",
        inputSchema={
            "type": "object",
            "properties": {
                "chunk_id": {"type": "integer", "description": "知识片段ID"},
            },
            "required": ["chunk_id"],
        },
    ),
    types.Tool(
        name="trace_report_claim",
        description="把报告中的一句话回溯到最可能支撑它的知识库 Word 片段。",
        inputSchema={
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "报告中的一句话或短段落"},
                "candidate_chunk_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "可选候选 chunk_id 列表",
                },
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["claim"],
        },
    ),
]


async def handle_list_tools(_ctx, _params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def handle_call_tool(_ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    args = params.arguments or {}
    if params.name == "list_knowledge_bases":
        result = await list_knowledge_bases()
    elif params.name == "search_knowledge":
        result = await search_knowledge(
            query=str(args.get("query") or ""),
            base_ids=args.get("base_ids") or None,
            category=str(args.get("category") or ""),
            source_type=str(args.get("source_type") or ""),
            event_type=str(args.get("event_type") or ""),
            risk_level=str(args.get("risk_level") or ""),
            top_k=int(args.get("top_k") or 8),
        )
    elif params.name == "get_knowledge_chunk":
        result = await get_knowledge_chunk(chunk_id=int(args.get("chunk_id") or 0))
    elif params.name == "trace_report_claim":
        result = await trace_report_claim(
            claim=str(args.get("claim") or ""),
            candidate_chunk_ids=args.get("candidate_chunk_ids") or None,
            top_k=int(args.get("top_k") or 5),
        )
    else:
        return types.CallToolResult(
            isError=True,
            content=[types.TextContent(text=f"未知工具: {params.name}")],
        )
    return types.CallToolResult(
        content=[types.TextContent(text=json.dumps(result, ensure_ascii=False, indent=2))],
        structuredContent=result,
    )


async def main() -> None:
    server: Server[dict[str, object]] = Server(
        "dam-knowledge",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
