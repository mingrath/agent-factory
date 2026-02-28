---
name: agent-factory
description: >
  Creates fully-deployed expert AI agents for any domain.
  Use when "create agent", "new bot", "deploy agent", "สร้างบอท",
  "agent factory", "new expert", "spin up agent", "make a bot".
metadata:
  author: mingrath
  version: "1.0"
  category: devops
  tags: [agent, factory, deploy, template, bot]
---

# Agent Factory

Creates a complete expert AI agent: OpenClaw workspace, domain skill, RAG collection, public web app, cloudflared tunnel, and systemd service.

## Workflow

### Phase 1: Collect Parameters (Interactive Q&A)

Ask these questions one at a time:

1. **Domain:** "What domain is this expert agent for?" (open-ended)
2. **Agent name:** "What should the agent be called?" (suggest based on domain)
3. **Agent ID:** Derive slug from name (e.g., "Cooking Expert AI" → `cooking-expert`)
4. **Emoji:** "What emoji represents this agent?" (suggest based on domain)
5. **Vibe:** "What personality?" (Professional / Friendly / Casual / Authoritative)
6. **Language:** "Primary language?" + "Secondary language?"
7. **Audience:** "Who is the audience?" (open-ended)
8. **RAG data:** "Do you have data files to ingest?" (paths, or skip)
9. **Self-expand:** "Should the agent auto-expand its knowledge?" (Yes/No, default No)
10. **Disclaimer:** "Include a disclaimer in responses?" (Yes/No, if yes ask for text)

### Phase 2: Deploy

After collecting all answers, write config to `/tmp/agent-factory-config.json` and run:

```bash
python3 ~/.openclaw/workspace/skills/agent-factory/scripts/deploy.py \
  --config /tmp/agent-factory-config.json
```

The script handles everything: workspace creation, skill setup, openclaw.json registration, gateway restart, web app deployment, venv creation, systemd service, cloudflared tunnel, RAG ingestion, and health check.

### Phase 3: Verify

1. Check health: `curl https://{{AGENT_ID}}.ohmmingrath.com/health`
2. Report the shareable URL to the user

## Config JSON Format

```json
{
  "agent_id": "cooking-expert",
  "agent_name": "Cooking Expert AI",
  "agent_name_local": "เชฟ AI",
  "emoji": "👨‍🍳",
  "domain": "Thai cooking and recipes",
  "language": "Thai",
  "language_secondary": "English",
  "vibe": "Friendly, enthusiastic",
  "audience": "Home cooks wanting authentic Thai recipes",
  "disclaimer": "",
  "self_expand": false,
  "rag_files": ["/path/to/recipes.csv"]
}
```

## Reference

See `references/usage-guide.md` for examples and troubleshooting.
