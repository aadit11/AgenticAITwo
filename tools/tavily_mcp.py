"""One Tavily Remote MCP server, shared by Research and Summary.

The API key is passed as a query parameter. It is never placed in the request body.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SERVER_NAME = "tavily"
SEARCH_TOOL = "tavily_search"
EXTRACT_TOOL = "tavily_extract"


def server_url() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return "https://mcp.tavily.com/mcp/?tavilyApiKey=" + quote(key, safe="")


def _client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            SERVER_NAME: {
                "transport": "streamable_http",
                "url": server_url(),
            }
        }
    )


async def _invoke(tool_name: str, arguments: dict):
    client = _client()
    tools = await client.get_tools(server_name=SERVER_NAME)
    match = next(
        (tool for tool in tools if tool.name == tool_name or tool.name.endswith(tool_name)),
        None,
    )
    if match is None:
        names = ", ".join(tool.name for tool in tools)
        raise RuntimeError(f"{tool_name} is not on the Tavily server (tools: {names})")
    return await match.ainvoke(arguments)


def _text(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts = []
        for block in payload:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or block))
            else:
                text = getattr(block, "text", None)
                parts.append(text if isinstance(text, str) else str(block))
        return "\n".join(parts)
    return str(payload)


def _json_objects(payload) -> list:
    text = _text(payload).strip()
    found = []
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            found.append(parsed)
        except json.JSONDecodeError:
            pass
    for match in re.finditer(r"\{.*?\}", text, re.DOTALL):
        try:
            found.append(json.loads(match.group(0)))
        except json.JSONDecodeError:
            continue
    return found


def _search_results(payload) -> list[dict]:
    results = []
    for obj in _json_objects(payload):
        rows = obj.get("results") if isinstance(obj, dict) else None
        if isinstance(rows, list):
            results.extend(row for row in rows if isinstance(row, dict))
    if results:
        return results
    urls = re.findall(r"https://[^\s)\]>\"']+", _text(payload))
    return [{"url": url, "title": url, "content": ""} for url in urls]


def tavily_search(
    query: str,
    *,
    start_date: str | None = None,
    include_domains: list[str] | None = None,
    max_results: int = 5,
) -> dict:
    """Research and Summary both call this tool. Their queries differ."""
    arguments = {
        "query": query,
        "search_depth": "basic",
        "topic": "general",
        "max_results": max_results,
    }
    if start_date:
        arguments["start_date"] = start_date
    if include_domains:
        arguments["include_domains"] = include_domains
    payload = asyncio.run(_invoke(SEARCH_TOOL, arguments))
    results = []
    for row in _search_results(payload)[:max_results]:
        url = str(row.get("url") or "")
        if not url.startswith("http"):
            continue
        results.append(
            {
                "url": url,
                "title": str(row.get("title") or url),
                "content": str(row.get("content") or "")[:500],
            }
        )
    return {"tool": SEARCH_TOOL, "arguments": arguments, "results": results}


def tavily_extract(urls: list[str]) -> dict:
    """Summary uses this, and only for URLs Research already returned."""
    arguments = {"urls": urls, "extract_depth": "basic", "format": "markdown"}
    payload = asyncio.run(_invoke(EXTRACT_TOOL, arguments))
    return {
        "tool": EXTRACT_TOOL,
        "arguments": arguments,
        "content": _text(payload)[:2000],
    }
