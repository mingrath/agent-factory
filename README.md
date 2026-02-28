# Agent Factory

Spin up a fully-deployed expert AI agent for **any domain** in under 2 minutes.

Built on [OpenClaw](https://github.com/nicepkg/openclaw) — an open-source AI agent framework with persistent identity, memory, and multi-channel support.

## What It Does

One command creates everything needed for a public-facing AI expert:

| Component | What Gets Created |
|---|---|
| **Workspace** | Agent identity (SOUL.md, IDENTITY.md, USER.md, MEMORY.md) |
| **Domain Skill** | RAG-powered knowledge skill with references |
| **Web App** | FastAPI backend + streaming chat UI |
| **Systemd Service** | Auto-start on boot |
| **Cloudflare Tunnel** | Public HTTPS URL via cloudflared |
| **RAG Collection** | ChromaDB vector store for domain knowledge |

## How It Works

```
You: "Create a new expert agent for Thai cooking"

Agent Factory asks 10 questions:
  1. Domain → Thai cooking and recipes
  2. Name → Chef AI
  3. ID → chef-ai
  4. Emoji → 👨‍🍳
  5. Personality → Friendly
  6. Languages → Thai + English
  7. Audience → Home cooks
  8. RAG data → /path/to/recipes.csv
  9. Self-expand? → No
  10. Disclaimer → No

Then deploys everything automatically.
→ https://chef-ai.yourdomain.com is live!
```

## Architecture

```
User → cloudflared tunnel → FastAPI (port 808x) → OpenClaw Gateway → Claude API
                                                        ↓
                                                   Agent Workspace
                                                   (SOUL + RAG + Skills)
```

The web app proxies chat requests through the OpenClaw Gateway's OpenAI-compatible API (`/v1/chat/completions`), keeping the gateway token server-side. The frontend uses Server-Sent Events (SSE) for streaming responses.

## Prerequisites

- [OpenClaw](https://github.com/nicepkg/openclaw) installed and running
- Python 3.10+
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) tunnel configured
- systemd (Linux user services)
- A Cloudflare-managed domain

## Installation

### As a Claude Code Skill

Copy the `SKILL.md` to your Claude Code skills directory:

```bash
mkdir -p ~/.claude/skills/agent-factory
cp SKILL.md ~/.claude/skills/agent-factory/SKILL.md
```

Then copy the full skill to your OpenClaw workspace:

```bash
cp -r . ~/.openclaw/workspace/skills/agent-factory/
```

Now you can use `/agent-factory` in Claude Code or just say "create a new agent".

### As an OpenClaw Skill

Copy the entire directory to your OpenClaw workspace skills:

```bash
cp -r . ~/.openclaw/workspace/skills/agent-factory/
```

The skill triggers on keywords like "create agent", "new bot", "deploy agent", etc.

## Manual Usage

You can also run the deploy script directly:

```bash
# 1. Create a config file
cat > /tmp/my-agent-config.json << 'EOF'
{
  "agent_id": "cooking-expert",
  "agent_name": "Cooking Expert AI",
  "agent_name_local": "",
  "emoji": "👨‍🍳",
  "domain": "Thai cooking and recipes",
  "language": "Thai",
  "language_secondary": "English",
  "vibe": "Friendly",
  "audience": "Home cooks wanting authentic Thai recipes",
  "disclaimer": "",
  "self_expand": false,
  "rag_files": ["/path/to/recipes.csv"]
}
EOF

# 2. Run the deploy script
python3 scripts/deploy.py --config /tmp/my-agent-config.json
```

The script runs 10 steps automatically:

1. Create agent workspace (`~/.openclaw/workspace-{id}/`)
2. Create domain skill (`~/.openclaw/workspace/skills/{id}/`)
3. Register in `openclaw.json`
4. Restart OpenClaw gateway
5. Create web app (`~/{id}-app/`)
6. Create venv + install dependencies
7. Create + enable systemd service
8. Configure cloudflared tunnel + DNS
9. Ingest RAG data (if provided)
10. Health check

## Config JSON Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | URL-safe slug (e.g., `cooking-expert`) |
| `agent_name` | string | Yes | Display name (e.g., `Cooking Expert AI`) |
| `agent_name_local` | string | No | Name in local language |
| `emoji` | string | No | Agent emoji |
| `domain` | string | Yes | Domain of expertise |
| `language` | string | Yes | Primary language |
| `language_secondary` | string | No | Secondary language (default: English) |
| `vibe` | string | No | Personality style (default: Professional) |
| `audience` | string | No | Target audience description |
| `disclaimer` | string | No | Disclaimer text to include in responses |
| `self_expand` | boolean | No | Auto-expand knowledge via web search (default: false) |
| `rag_files` | string[] | No | Paths to files for RAG ingestion |

## Supported Languages

Thai, English, Japanese, Chinese, Korean, Spanish, French, German, Portuguese, Vietnamese, Indonesian, Malay, Hindi, Arabic, Russian.

The web UI (headers, placeholders, welcome message) is automatically localized.

## Managing Deployed Agents

```bash
# Check status
systemctl --user status {agent-id}-app

# View logs
journalctl --user -u {agent-id}-app -f

# Restart
systemctl --user restart {agent-id}-app

# Stop
systemctl --user stop {agent-id}-app

# Add more RAG data
python3 ~/.openclaw/workspace/skills/rag/rag_tool.py ingest /path/to/file \
  --collection {agent-id}
```

## Project Structure

```
agent-factory/
├── SKILL.md                          # Skill definition (Q&A workflow)
├── scripts/
│   └── deploy.py                     # Deployment pipeline (10 steps)
├── templates/
│   ├── workspace/                    # Agent identity templates
│   │   ├── SOUL.md.tmpl
│   │   ├── AGENTS.md.tmpl
│   │   ├── IDENTITY.md.tmpl
│   │   ├── USER.md.tmpl
│   │   └── MEMORY.md.tmpl
│   ├── skill/
│   │   └── SKILL.md.tmpl            # Domain skill template
│   ├── webapp/
│   │   ├── env.tmpl                  # Environment variables
│   │   ├── server/
│   │   │   ├── app.py.tmpl           # FastAPI app with SSE streaming
│   │   │   ├── chat.py.tmpl          # OpenClaw gateway proxy
│   │   │   ├── requirements.txt
│   │   │   └── __init__.py
│   │   └── frontend/
│   │       ├── index.html.tmpl       # Chat UI
│   │       ├── app.js                # SSE stream handler
│   │       └── style.css             # Responsive styles
│   └── systemd/
│       └── service.tmpl              # Systemd user service
└── references/
    └── usage-guide.md                # Quick reference
```

## Customization

### Templates

All templates use `{{PLACEHOLDER}}` syntax. The deploy script replaces them with values from the config JSON. You can customize any template to change the agent's behavior, UI, or infrastructure.

### Port Range

By default, agents are assigned ports from 8080-8099. Change `PORT_RANGE` in `deploy.py` to adjust.

### Tunnel Domain

Change `TUNNEL_DOMAIN` in `deploy.py` to use your own domain.

## Troubleshooting

| Problem | Solution |
|---|---|
| Web app returns 404 | Check if systemd service is running: `systemctl --user status {id}-app` |
| Chat returns empty | Check OpenClaw gateway: `systemctl --user status openclaw-gateway` |
| Tunnel not working | Check `~/.cloudflared/config.yml` and restart: `systemctl --user restart cloudflared` |
| Port conflict | The script auto-assigns the first free port in range. Check with `ss -tlnp` |

## License

MIT
