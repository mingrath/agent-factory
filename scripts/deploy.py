#!/usr/bin/env python3
"""Agent Factory — deploys a complete expert AI agent from config JSON.

Usage:
    python3 deploy.py --config /tmp/agent-factory-config.json

Output: progress to stderr, final JSON result to stdout.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = Path.home()
OPENCLAW_DIR = HOME / ".openclaw"
OPENCLAW_JSON = OPENCLAW_DIR / "openclaw.json"
WORKSPACE_DIR = OPENCLAW_DIR / "workspace"
SKILLS_DIR = WORKSPACE_DIR / "skills"
TEMPLATES_DIR = SKILLS_DIR / "agent-factory" / "templates"
SYSTEMD_DIR = HOME / ".config" / "systemd" / "user"
CLOUDFLARED_CONFIG = HOME / ".cloudflared" / "config.yml"
RAG_TOOL = SKILLS_DIR / "rag" / "rag_tool.py"

TUNNEL_DOMAIN = "ohmmingrath.com"
TUNNEL_NAME = "openclaw-gateway"
PORT_RANGE = range(8080, 8100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """Print progress to stderr."""
    print(f"  {msg}", file=sys.stderr)


def heading(step: int, title: str) -> None:
    print(f"\n[{step}/10] {title}", file=sys.stderr)


def render(template_text: str, params: dict[str, str]) -> str:
    """Replace all {{PLACEHOLDER}} tokens in *template_text*."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        if key in params:
            return params[key]
        return m.group(0)  # leave unknown placeholders as-is
    return re.sub(r"\{\{(\w+)\}\}", _replace, template_text)


def render_file(src: Path, dst: Path, params: dict[str, str]) -> None:
    """Read *src* template, render placeholders, write to *dst*."""
    text = src.read_text(encoding="utf-8")
    dst.write_text(render(text, params), encoding="utf-8")
    log(f"  rendered {dst.name}")


def copy_file(src: Path, dst: Path) -> None:
    """Copy a non-template file as-is."""
    shutil.copy2(src, dst)
    log(f"  copied   {dst.name}")


def find_free_port() -> int:
    """Return the first unused TCP port in PORT_RANGE."""
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in {PORT_RANGE.start}-{PORT_RANGE.stop - 1}")


def read_gateway_token() -> str:
    """Read the gateway auth token from openclaw.json."""
    data = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    return data["gateway"]["auth"]["token"]


def lang_code(language: str) -> str:
    """Map a language name to an HTML lang code."""
    mapping = {
        "thai": "th",
        "english": "en",
        "japanese": "ja",
        "chinese": "zh",
        "korean": "ko",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "portuguese": "pt",
        "vietnamese": "vi",
        "indonesian": "id",
        "malay": "ms",
        "hindi": "hi",
        "arabic": "ar",
        "russian": "ru",
    }
    return mapping.get(language.lower(), "en")


# ---------------------------------------------------------------------------
# Localized UI text
# ---------------------------------------------------------------------------
def localized_ui(language: str, agent_name: str, domain: str) -> dict[str, str]:
    """Return localized header/UI strings based on language."""
    lang = language.lower()

    if lang == "thai":
        return {
            "SOUL_TAGLINE": f"ผู้เชี่ยวชาญด้าน{domain}ของคุณ",
            "HEADER_TITLE": agent_name,
            "HEADER_SUBTITLE": f"ผู้ช่วย AI ด้าน{domain}",
            "WELCOME_MESSAGE": f"สวัสดีค่ะ! ยินดีต้อนรับสู่ {agent_name} - ผู้ช่วย AI ด้าน{domain} ถามคำถามได้เลยค่ะ",
            "INPUT_PLACEHOLDER": "พิมพ์คำถามของคุณที่นี่...",
        }
    elif lang == "japanese":
        return {
            "SOUL_TAGLINE": f"あなたの{domain}エキスパート",
            "HEADER_TITLE": agent_name,
            "HEADER_SUBTITLE": f"{domain} AIアシスタント",
            "WELCOME_MESSAGE": f"こんにちは！{agent_name}へようこそ。{domain}について何でもお聞きください。",
            "INPUT_PLACEHOLDER": "ここに質問を入力してください...",
        }
    elif lang == "chinese":
        return {
            "SOUL_TAGLINE": f"您的{domain}专家",
            "HEADER_TITLE": agent_name,
            "HEADER_SUBTITLE": f"{domain} AI助手",
            "WELCOME_MESSAGE": f"您好！欢迎使用{agent_name}。请随时提出关于{domain}的问题。",
            "INPUT_PLACEHOLDER": "在这里输入您的问题...",
        }
    elif lang == "korean":
        return {
            "SOUL_TAGLINE": f"당신의 {domain} 전문가",
            "HEADER_TITLE": agent_name,
            "HEADER_SUBTITLE": f"{domain} AI 어시스턴트",
            "WELCOME_MESSAGE": f"안녕하세요! {agent_name}에 오신 것을 환영합니다. {domain}에 대해 무엇이든 물어보세요.",
            "INPUT_PLACEHOLDER": "여기에 질문을 입력하세요...",
        }
    else:
        # Default: English
        return {
            "SOUL_TAGLINE": f"Your {domain} expert",
            "HEADER_TITLE": agent_name,
            "HEADER_SUBTITLE": f"AI assistant for {domain}",
            "WELCOME_MESSAGE": f"Hello! Welcome to {agent_name}. Ask me anything about {domain}.",
            "INPUT_PLACEHOLDER": "Type your question here...",
        }


# ---------------------------------------------------------------------------
# build_params()
# ---------------------------------------------------------------------------
def build_params(config: dict) -> dict[str, str]:
    """Build the full parameter dict for template rendering."""
    agent_id = config["agent_id"]
    agent_name = config["agent_name"]
    language = config["language"]
    domain = config["domain"]
    disclaimer = config.get("disclaimer", "")
    self_expand = config.get("self_expand", False)
    local_name = config.get("agent_name_local", "")

    # Reuse existing port if agent was previously deployed
    existing_env = HOME / f"{agent_id}-app" / ".env"
    port = None
    if existing_env.exists():
        for line in existing_env.read_text().splitlines():
            if line.startswith("PORT="):
                try:
                    port = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass
                break
    if port is None:
        port = find_free_port()

    hostname = f"{agent_id}.{TUNNEL_DOMAIN}"

    # Disclaimer sections
    if disclaimer:
        disclaimer_section = (
            f"\n## Disclaimer\n\n"
            f"> **Important:** {disclaimer}\n\n"
            f"Always include this disclaimer when giving advice.\n\n"
        )
        disclaimer_skill_section = (
            f"\n## Disclaimer\n\n"
            f"> {disclaimer}\n\n"
        )
    else:
        disclaimer_section = ""
        disclaimer_skill_section = ""

    # Self-expand section
    if self_expand:
        self_expand_section = (
            "\n## Self-Expansion Protocol\n\n"
            "When you encounter topics not well-covered in the knowledge base:\n"
            "1. Note the gap in `knowledge/gaps.md`\n"
            "2. Use web search to find authoritative sources\n"
            "3. Summarize findings and save to `knowledge/` for future reference\n"
            "4. Still cite when information comes from general knowledge vs. the knowledge base\n\n"
        )
    else:
        self_expand_section = ""

    # Local name
    identity_local_name = f" ({local_name})" if local_name else ""

    # Skill triggers
    skill_triggers = (
        f'Trigger keywords: "{agent_id}", "{domain}", '
        f'"{agent_name}"'
    )
    if local_name:
        skill_triggers += f', "{local_name}"'

    # Localized UI
    ui = localized_ui(language, agent_name, domain)

    return {
        "AGENT_ID": agent_id,
        "AGENT_NAME": agent_name,
        "AGENT_NAME_LOCAL": local_name,
        "EMOJI": config.get("emoji", ""),
        "DOMAIN": domain,
        "LANGUAGE": language,
        "LANGUAGE_SECONDARY": config.get("language_secondary", "English"),
        "VIBE": config.get("vibe", "Professional"),
        "AUDIENCE": config.get("audience", "General users"),
        "RAG_COLLECTION": agent_id,
        "PORT": str(port),
        "HOSTNAME": hostname,
        "GATEWAY_TOKEN": read_gateway_token(),
        "HOME": str(HOME),
        "DISCLAIMER_SECTION": disclaimer_section,
        "DISCLAIMER_SKILL_SECTION": disclaimer_skill_section,
        "SELF_EXPAND_SECTION": self_expand_section,
        "IDENTITY_LOCAL_NAME": identity_local_name,
        "SOUL_TAGLINE": ui["SOUL_TAGLINE"],
        "HTML_LANG": lang_code(language),
        "HEADER_TITLE": ui["HEADER_TITLE"],
        "HEADER_SUBTITLE": ui["HEADER_SUBTITLE"],
        "WELCOME_MESSAGE": ui["WELCOME_MESSAGE"],
        "INPUT_PLACEHOLDER": ui["INPUT_PLACEHOLDER"],
        "SKILL_TRIGGERS": skill_triggers,
    }


# ---------------------------------------------------------------------------
# Deployment steps
# ---------------------------------------------------------------------------

def step_workspace(params: dict[str, str]) -> Path:
    """Step 1 — Create agent workspace at ~/.openclaw/workspace-{agent_id}/."""
    heading(1, "Create agent workspace")
    agent_id = params["AGENT_ID"]
    ws = OPENCLAW_DIR / f"workspace-{agent_id}"

    if ws.exists():
        log(f"workspace already exists at {ws}, skipping creation")
        return ws

    ws.mkdir(parents=True)
    (ws / "memory").mkdir()
    (ws / "skills").mkdir()
    (ws / "knowledge").mkdir()

    # Render workspace templates
    tmpl_dir = TEMPLATES_DIR / "workspace"
    for tmpl_file in tmpl_dir.iterdir():
        if tmpl_file.suffix == ".tmpl":
            out_name = tmpl_file.stem  # e.g. SOUL.md.tmpl -> SOUL.md
            render_file(tmpl_file, ws / out_name, params)

    # Symlink RAG skill
    rag_link = ws / "skills" / "rag"
    if not rag_link.exists():
        rag_link.symlink_to(SKILLS_DIR / "rag")
        log("  symlinked skills/rag")

    log(f"workspace created at {ws}")
    return ws


def step_skill(params: dict[str, str]) -> Path:
    """Step 2 — Create domain skill at ~/.openclaw/workspace/skills/{agent_id}/."""
    heading(2, "Create domain skill")
    agent_id = params["AGENT_ID"]
    skill_dir = SKILLS_DIR / agent_id

    if skill_dir.exists():
        log(f"skill dir already exists at {skill_dir}, skipping creation")
        return skill_dir

    skill_dir.mkdir(parents=True)
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "knowledge").mkdir(exist_ok=True)

    # Render skill template
    tmpl_file = TEMPLATES_DIR / "skill" / "SKILL.md.tmpl"
    render_file(tmpl_file, skill_dir / "SKILL.md", params)

    log(f"skill created at {skill_dir}")
    return skill_dir


def step_skill_symlink(params: dict[str, str], workspace: Path) -> None:
    """Step 2b — Symlink domain skill into agent workspace (after step_skill)."""
    agent_id = params["AGENT_ID"]
    link = workspace / "skills" / agent_id
    target = SKILLS_DIR / agent_id
    if not link.exists():
        link.symlink_to(target)
        log(f"  symlinked skills/{agent_id} in workspace")


def step_register(params: dict[str, str]) -> None:
    """Step 3 — Register agent + webchat binding in openclaw.json."""
    heading(3, "Register agent in openclaw.json")
    agent_id = params["AGENT_ID"]
    agent_name = params["AGENT_NAME"]

    data = json.loads(OPENCLAW_JSON.read_text())

    # Check if agent already registered
    existing_ids = {a["id"] for a in data["agents"]["list"]}
    if agent_id in existing_ids:
        log(f"agent '{agent_id}' already registered, skipping")
    else:
        agent_entry = {
            "id": agent_id,
            "name": agent_name,
            "workspace": str(OPENCLAW_DIR / f"workspace-{agent_id}"),
        }
        data["agents"]["list"].append(agent_entry)
        log(f"added agent '{agent_id}' to agents.list")

    # Check if binding already exists
    has_binding = any(
        b.get("agentId") == agent_id
        and b.get("match", {}).get("channel") == "webchat"
        for b in data.get("bindings", [])
    )
    if has_binding:
        log(f"webchat binding for '{agent_id}' already exists, skipping")
    else:
        binding = {
            "agentId": agent_id,
            "match": {
                "channel": "webchat",
                "accountId": agent_id,
            },
        }
        data.setdefault("bindings", []).append(binding)
        log(f"added webchat binding for '{agent_id}'")

    OPENCLAW_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    log("openclaw.json updated")


def step_restart_gateway() -> None:
    """Step 4 — Restart OpenClaw gateway so it picks up the new agent."""
    heading(4, "Restart OpenClaw gateway")
    subprocess.run(
        ["systemctl", "--user", "restart", "openclaw-gateway.service"],
        check=True,
        capture_output=True,
    )
    log("gateway restarting...")
    # Give it a moment to come up
    time.sleep(3)
    log("gateway restarted")


def step_webapp(params: dict[str, str]) -> Path:
    """Step 5 — Create web app at ~/{agent_id}-app/."""
    heading(5, "Create web app")
    agent_id = params["AGENT_ID"]
    app_dir = HOME / f"{agent_id}-app"

    if app_dir.exists():
        log(f"app dir already exists at {app_dir}, wiping and recreating")
        shutil.rmtree(app_dir)

    app_dir.mkdir(parents=True)
    (app_dir / "server").mkdir()
    (app_dir / "frontend").mkdir()

    # -- Render env.tmpl -> .env (in app root) --
    env_tmpl = TEMPLATES_DIR / "webapp" / "env.tmpl"
    render_file(env_tmpl, app_dir / ".env", params)

    # -- Process server/ directory --
    server_tmpl_dir = TEMPLATES_DIR / "webapp" / "server"
    for src_file in server_tmpl_dir.iterdir():
        if src_file.name.endswith(".tmpl"):
            # Render template, strip .tmpl suffix
            out_name = src_file.name[: -len(".tmpl")]
            render_file(src_file, app_dir / "server" / out_name, params)
        else:
            # Copy as-is (e.g. __init__.py, requirements.txt)
            copy_file(src_file, app_dir / "server" / src_file.name)

    # -- Process frontend/ directory --
    frontend_tmpl_dir = TEMPLATES_DIR / "webapp" / "frontend"
    for src_file in frontend_tmpl_dir.iterdir():
        if src_file.name.endswith(".tmpl"):
            out_name = src_file.name[: -len(".tmpl")]
            render_file(src_file, app_dir / "frontend" / out_name, params)
        else:
            copy_file(src_file, app_dir / "frontend" / src_file.name)

    log(f"web app created at {app_dir}")
    return app_dir


def step_venv(app_dir: Path) -> None:
    """Step 6 — Create venv and install dependencies."""
    heading(6, "Create venv + install deps")
    venv_dir = app_dir / "venv"

    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    log("venv created")

    pip = venv_dir / "bin" / "pip"
    requirements = app_dir / "server" / "requirements.txt"
    subprocess.run(
        [str(pip), "install", "-r", str(requirements)],
        check=True,
        capture_output=True,
    )
    log("dependencies installed")


def step_systemd(params: dict[str, str]) -> None:
    """Step 7 — Create systemd user service, enable, and start."""
    heading(7, "Create systemd service")
    agent_id = params["AGENT_ID"]
    service_name = f"{agent_id}-app.service"
    service_path = SYSTEMD_DIR / service_name

    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)

    # Render service template
    tmpl_file = TEMPLATES_DIR / "systemd" / "service.tmpl"
    render_file(tmpl_file, service_path, params)

    # Reload + enable + start
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["systemctl", "--user", "enable", service_name],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["systemctl", "--user", "start", service_name],
        check=True,
        capture_output=True,
    )
    log(f"{service_name} enabled and started")


def step_tunnel(params: dict[str, str]) -> None:
    """Step 8 — Add cloudflared tunnel route + DNS + restart."""
    heading(8, "Configure cloudflared tunnel")
    agent_id = params["AGENT_ID"]
    hostname = params["HOSTNAME"]
    port = params["PORT"]

    # --- Read current config ---
    config_text = CLOUDFLARED_CONFIG.read_text()

    # Check if hostname already in config
    if hostname in config_text:
        log(f"hostname {hostname} already in cloudflared config, skipping")
    else:
        # Insert new ingress rule before the catch-all rule (last line: - service: http_status:404)
        new_rule = f"  - hostname: {hostname}\n    service: http://127.0.0.1:{port}"

        # Split into lines, find the catch-all, insert before it
        lines = config_text.rstrip("\n").split("\n")
        # Find the catch-all rule (the line with "service: http_status:404")
        insert_idx = None
        for i, line in enumerate(lines):
            if "http_status:404" in line:
                # The catch-all is "  - service: http_status:404" — find the "- service" line
                insert_idx = i
                break

        if insert_idx is not None:
            lines.insert(insert_idx, new_rule)
        else:
            # No catch-all found; append before end
            lines.append(new_rule)

        CLOUDFLARED_CONFIG.write_text("\n".join(lines) + "\n")
        log(f"added ingress rule for {hostname} -> port {port}")

    # --- Add DNS route ---
    # Read tunnel ID from config
    tunnel_id = None
    for line in CLOUDFLARED_CONFIG.read_text().split("\n"):
        if line.startswith("tunnel:"):
            tunnel_id = line.split(":", 1)[1].strip()
            break

    if tunnel_id:
        result = subprocess.run(
            ["cloudflared", "tunnel", "route", "dns", tunnel_id, hostname],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log(f"DNS route added for {hostname}")
        else:
            # Already exists is not an error
            if "already exists" in result.stderr.lower():
                log(f"DNS route for {hostname} already exists")
            else:
                log(f"DNS route warning: {result.stderr.strip()}")
    else:
        log("WARNING: could not determine tunnel ID, skipping DNS route")

    # --- Restart cloudflared ---
    subprocess.run(
        ["systemctl", "--user", "restart", "cloudflared.service"],
        check=True,
        capture_output=True,
    )
    log("cloudflared restarted")


def step_rag(config: dict, params: dict[str, str]) -> None:
    """Step 9 — Ingest RAG data files if provided."""
    heading(9, "Ingest RAG data")
    rag_files = config.get("rag_files", [])

    if not rag_files:
        log("no RAG files specified, skipping")
        return

    collection = params["RAG_COLLECTION"]

    for filepath in rag_files:
        filepath = os.path.expanduser(filepath)
        if not os.path.exists(filepath):
            log(f"WARNING: file not found, skipping: {filepath}")
            continue

        log(f"ingesting {filepath} into collection '{collection}'...")
        result = subprocess.run(
            [
                sys.executable,
                str(RAG_TOOL),
                "ingest",
                filepath,
                "--collection",
                collection,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log(f"  ingested {os.path.basename(filepath)}")
        else:
            log(f"  WARNING: ingest failed for {filepath}: {result.stderr.strip()}")


def step_health(params: dict[str, str]) -> dict:
    """Step 10 — Health check."""
    heading(10, "Health check")
    agent_id = params["AGENT_ID"]
    port = params["PORT"]
    hostname = params["HOSTNAME"]

    # Wait a moment for the service to be ready
    time.sleep(2)

    # Check local health endpoint
    local_url = f"http://127.0.0.1:{port}/health"
    healthy = False
    for attempt in range(5):
        try:
            import urllib.request
            with urllib.request.urlopen(local_url, timeout=5) as resp:
                if resp.status == 200:
                    healthy = True
                    break
        except Exception:
            if attempt < 4:
                time.sleep(2)

    if healthy:
        log(f"local health check PASSED ({local_url})")
    else:
        log(f"WARNING: local health check failed ({local_url})")

    public_url = f"https://{hostname}"

    return {
        "status": "ok" if healthy else "degraded",
        "agent_id": agent_id,
        "agent_name": params["AGENT_NAME"],
        "workspace": str(OPENCLAW_DIR / f"workspace-{agent_id}"),
        "skill_dir": str(SKILLS_DIR / agent_id),
        "app_dir": str(HOME / f"{agent_id}-app"),
        "port": int(port),
        "local_url": f"http://127.0.0.1:{port}",
        "public_url": public_url,
        "health_url": f"{public_url}/health",
        "service": f"{agent_id}-app.service",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy an expert AI agent")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to agent config JSON file",
    )
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    agent_id = config.get("agent_id")
    if not agent_id:
        print("ERROR: config missing 'agent_id'", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  Agent Factory — deploying '{agent_id}'", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    # Build params
    params = build_params(config)
    log(f"port assigned: {params['PORT']}")
    log(f"hostname: {params['HOSTNAME']}")

    # Execute pipeline
    workspace = step_workspace(params)         # 1. Create workspace
    step_skill(params)                          # 2. Create domain skill
    step_skill_symlink(params, workspace)       # 2b. Symlink skill into workspace
    step_register(params)                       # 3. Register in openclaw.json
    step_restart_gateway()                      # 4. Restart gateway
    app_dir = step_webapp(params)               # 5. Create web app
    step_venv(app_dir)                          # 6. Create venv + deps
    step_systemd(params)                        # 7. Systemd service
    step_tunnel(params)                         # 8. Cloudflared tunnel
    step_rag(config, params)                    # 9. RAG ingestion
    result = step_health(params)                # 10. Health check

    print(f"\n{'='*60}", file=sys.stderr)
    if result["status"] == "ok":
        print(f"  DONE  {params['EMOJI']} {params['AGENT_NAME']} is live!", file=sys.stderr)
    else:
        print(f"  DONE (degraded) — check service logs", file=sys.stderr)
    print(f"  URL: {result['public_url']}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Final JSON to stdout
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
