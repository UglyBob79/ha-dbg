#!/usr/bin/env python3
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN")

if not HA_TOKEN:
    import sys
    sys.stderr.write("HA_TOKEN environment variable is required\n")
    sys.exit(1)

server = Server("ha-dbg")

def headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

async def ha_get(path: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{HA_URL}{path}", headers=headers(), timeout=30)
        res.raise_for_status()
        return res

async def ha_post(path: str, body: dict = {}) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{HA_URL}{path}", headers=headers(), json=body, timeout=30)
        res.raise_for_status()
        return res

def text(s: str) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=s)]

TOOLS = [
    types.Tool(
        name="get_error_log",
        description="Get the Home Assistant error/warning log",
        inputSchema={
            "type": "object",
            "properties": {
                "lines": {"type": "number", "description": "Lines from end (default 100)"},
                "filter": {"type": "string", "description": "Only return lines containing this string"},
            },
        },
    ),
    types.Tool(
        name="get_host_logs",
        description="Get host/system journal logs from Home Assistant OS",
        inputSchema={
            "type": "object",
            "properties": {
                "lines": {"type": "number", "description": "Lines from end (default 100)"},
                "filter": {"type": "string", "description": "Filter string"},
            },
        },
    ),
    types.Tool(
        name="get_logbook",
        description="Get Home Assistant logbook entries",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Filter by entity ID"},
                "hours": {"type": "number", "description": "How many hours back (default 1)"},
                "filter": {"type": "string", "description": "Filter by entity_id or name containing this string"},
                "domain": {"type": "string", "description": "Filter by domain, e.g. 'alexa', 'automation', 'light'"},
            },
        },
    ),
    types.Tool(
        name="get_entities",
        description="List entities, optionally filtered by domain, area, or search string",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Filter by domain, e.g. 'light', 'switch', 'sensor'"},
                "search": {"type": "string", "description": "Filter entity_id or friendly_name containing this string"},
                "include_attributes": {"type": "boolean", "description": "Include full attributes (default false)"},
            },
        },
    ),
    types.Tool(
        name="get_entity",
        description="Get full state and attributes for a single entity",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID, e.g. 'light.bedroom'"},
            },
            "required": ["entity_id"],
        },
    ),
    types.Tool(
        name="get_history",
        description="Get state history for an entity",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID"},
                "hours": {"type": "number", "description": "How many hours back (default 3)"},
            },
            "required": ["entity_id"],
        },
    ),
    types.Tool(
        name="call_service",
        description="Call any Home Assistant service",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Service domain, e.g. 'light', 'switch'"},
                "service": {"type": "string", "description": "Service name, e.g. 'turn_on', 'reload'"},
                "data": {"type": "object", "description": "Service data payload (optional)"},
            },
            "required": ["domain", "service"],
        },
    ),
    types.Tool(
        name="reload",
        description="Reload a Home Assistant config domain (automations, scripts, input_datetime, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain to reload: automations, scripts, scenes, input_boolean, input_datetime, input_number, input_select, input_text, timer, counter, template"},
            },
            "required": ["domain"],
        },
    ),
]

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:

    if name == "get_error_log":
        lines = int(arguments.get("lines", 100))
        filter_str = arguments.get("filter")
        raw = None
        async with httpx.AsyncClient() as client:
            for path in ["/api/hassio/core/logs", "/api/error_log"]:
                res = await client.get(f"{HA_URL}{path}", headers=headers(), timeout=30)
                if res.is_success:
                    raw = res.text
                    break
        if not raw:
            raise RuntimeError("Could not fetch error log")
        import re
        raw = re.sub(r"\x1b\[[0-9;]*m", "", raw)
        rows = raw.split("\n")
        if filter_str:
            rows = [l for l in rows if filter_str.lower() in l.lower()]
        return text("\n".join(rows[-lines:]))

    if name == "get_host_logs":
        lines = int(arguments.get("lines", 100))
        filter_str = arguments.get("filter")
        res = await ha_get("/api/hassio/host/logs")
        import re
        raw = re.sub(r"\x1b\[[0-9;]*m", "", res.text)
        rows = raw.split("\n")
        if filter_str:
            rows = [l for l in rows if filter_str.lower() in l.lower()]
        return text("\n".join(rows[-lines:]))

    if name == "get_logbook":
        hours = float(arguments.get("hours", 1))
        filter_str = arguments.get("filter")
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        url = f"/api/logbook/{start}"
        if "entity_id" in arguments:
            url += f"?entity={arguments['entity_id']}"
        res = await ha_get(url)
        data = res.json()
        if filter_str:
            f = filter_str.lower()
            data = [e for e in data if f in (e.get("entity_id") or "").lower() or f in (e.get("name") or "").lower()]
        if "domain" in arguments:
            d = arguments["domain"].lower()
            data = [e for e in data if (e.get("domain") or "").lower() == d]
        return text(json.dumps(data, indent=2))

    if name == "get_entities":
        res = await ha_get("/api/states")
        states = res.json()
        if "domain" in arguments:
            states = [s for s in states if s["entity_id"].startswith(arguments["domain"] + ".")]
        if "search" in arguments:
            q = arguments["search"].lower()
        else:
            q = None
        if q:
            states = [s for s in states if q in s["entity_id"].lower() or q in (s.get("attributes", {}).get("friendly_name") or "").lower()]
        if arguments.get("include_attributes"):
            return text(json.dumps(states, indent=2))
        summary = [{"entity_id": s["entity_id"], "state": s["state"], "name": s.get("attributes", {}).get("friendly_name"), "last_changed": s["last_changed"]} for s in states]
        return text(json.dumps(summary, indent=2))

    if name == "get_entity":
        res = await ha_get(f"/api/states/{arguments['entity_id']}")
        return text(json.dumps(res.json(), indent=2))

    if name == "get_history":
        hours = float(arguments.get("hours", 3))
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        res = await ha_get(f"/api/history/period/{start}?filter_entity_id={arguments['entity_id']}&end_time={end}&minimal_response=true")
        data = res.json()
        return text(json.dumps(data[0] if data else [], indent=2))

    if name == "call_service":
        res = await ha_post(f"/api/services/{arguments['domain']}/{arguments['service']}", arguments.get("data") or {})
        return text(res.text or "OK")

    if name == "reload":
        domain = "automation" if arguments["domain"] == "automations" else arguments["domain"]
        await ha_post(f"/api/services/{domain}/reload")
        return text(f"Reloaded {arguments['domain']}")

    raise RuntimeError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
