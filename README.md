# ha-dbg

MCP server for inspecting and debugging [Home Assistant](https://www.home-assistant.io/). Exposes read and control tools useful when working with Claude Code on automations, scripts, or device issues.

## Tools

| Tool | Description |
|------|-------------|
| `get_error_log` | HA error/warning log, with optional line count and filter |
| `get_host_logs` | Host/system journal logs from HA OS |
| `get_logbook` | Logbook entries, filterable by entity or search string |
| `get_entities` | List entities filtered by domain, search string, or both |
| `get_entity` | Full state and attributes for a single entity |
| `get_history` | State history for an entity over the last N hours |
| `call_service` | Call any HA service with arbitrary data |
| `reload` | Reload a config domain (automations, scripts, input_boolean, etc.) |

## Requirements

- Python 3.11+
- `pip install -r requirements.txt`

## Setup

Create a [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile) in Home Assistant under your profile page.

Set the following environment variables:

| Variable | Required | Default |
|----------|----------|---------|
| `HA_TOKEN` | Yes | — |
| `HA_URL` | No | `http://homeassistant.local:8123` |

## Claude Code configuration

Add to your `~/.claude/claude_desktop_config.json` or Claude Code MCP settings:

```json
{
  "mcpServers": {
    "ha-dbg": {
      "command": "python",
      "args": ["/path/to/ha-dbg/server.py"],
      "env": {
        "HA_TOKEN": "your-long-lived-token",
        "HA_URL": "http://your-ha-instance:8123"
      }
    }
  }
}
```
