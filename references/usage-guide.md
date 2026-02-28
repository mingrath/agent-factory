# Agent Factory — Usage Guide

## Quick Start

Tell Claude: "Create a new expert agent for [domain]"

Claude will ask you questions about:
1. Domain and identity (name, emoji, personality)
2. Language and audience
3. Knowledge data and options

Then it deploys everything automatically.

## What Gets Created

| Component | Location |
|---|---|
| Workspace | `~/.openclaw/workspace-{agent-id}/` |
| Domain skill | `~/.openclaw/workspace/skills/{agent-id}/` |
| Web app | `~/{agent-id}-app/` |
| Systemd service | `~/.config/systemd/user/{agent-id}-app.service` |
| Tunnel route | `{agent-id}.ohmmingrath.com` |
| RAG collection | `{agent-id}` (in ChromaDB) |

## Managing Agents

```bash
# Check web app status
systemctl --user status {agent-id}-app

# View logs
journalctl --user -u {agent-id}-app -f

# Restart web app
systemctl --user restart {agent-id}-app

# Stop web app
systemctl --user stop {agent-id}-app

# Add more data to RAG
python3 ~/.openclaw/workspace/skills/rag/rag_tool.py ingest /path/to/file --collection {agent-id}

# Check RAG stats
python3 ~/.openclaw/workspace/skills/rag/rag_tool.py stats --collection {agent-id}
```

## Troubleshooting

**Web app returns 404:** Check if the systemd service is running.
**Chat returns empty:** Check if the OpenClaw gateway is running and the agent is registered in openclaw.json.
**Tunnel not working:** Check `~/.cloudflared/config.yml` has the ingress rule and restart cloudflared.
