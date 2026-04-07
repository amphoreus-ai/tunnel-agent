# tunnel-agent

Run any AI coding agent with selective network routing through your Astrill SOCKS5 proxy. AI API traffic goes through the VPN; SSH, git, and everything else goes direct.

Supports **8 agents** out of the box: Claude Code, Codex, Aider, Goose, Cline, Gemini CLI, Amp, OpenCode.

---

## The Problem

In China, AI APIs (Anthropic, OpenAI, Google) are blocked without a VPN. But enabling a full-system VPN breaks direct access to China-hosted servers you rely on — SSH to your production boxes, git to your internal Gitea, monitoring dashboards. Turning the VPN on and off mid-session is not a workflow.

## The Solution

tunnel-agent runs the agent inside a single Docker container where only traffic to AI API endpoints is routed through Astrill's SOCKS5 proxy. All other traffic — SSH, git to China, internal tooling — bypasses the proxy and goes direct over your normal connection. The agent doesn't know any of this is happening.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  macOS Host                                                       │
│                                                                   │
│  Astrill VPN → SOCKS5 proxy listening on 0.0.0.0:1080           │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Docker container (Debian)                                  │  │
│  │                                                             │  │
│  │  redsocks (127.0.0.1:12345)                                 │  │
│  │       ↑ redirected by iptables NAT OUTPUT rule              │  │
│  │                                                             │  │
│  │  iptables: only AI API IPs → redsocks → host SOCKS5        │  │
│  │                                                             │  │
│  │  Agent process                                              │  │
│  │    ├── curl api.anthropic.com  →→→ proxy →→→ internet      │  │
│  │    ├── curl api.openai.com     →→→ proxy →→→ internet      │  │
│  │    ├── ssh user@cn-server      ─── direct ─── China         │  │
│  │    └── git push origin main    ─── direct ─── China         │  │
│  │                                                             │  │
│  │  ~/.ssh and ~/.claude are mounted in from host              │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

Traffic is split at the iptables level: only the resolved IPs for the configured domains are redirected through redsocks. Everything else exits the container as normal.

---

## Prerequisites

- **Docker Desktop** (macOS) with Compose v2
- **Astrill VPN** with SOCKS5 proxy enabled (see setup below)
- **Python 3.11+**
- **Auth** for your chosen agent — Claude Code subscription (via `~/.claude/`), API key, or both

---

## Astrill SOCKS5 Setup

This step is critical. The Docker container reaches your host's SOCKS5 proxy via `host.docker.internal`. For that to work, Astrill must bind the proxy to `0.0.0.0` — not `127.0.0.1`.

1. Open the Astrill app
2. Go to **Settings** → **Proxy**
3. Enable **SOCKS5 proxy**
4. Set the **bind address** to `0.0.0.0` (the default `127.0.0.1` will not be reachable from Docker)
5. Note the port — the default is **1080**

If Astrill is only listening on `127.0.0.1`, the container cannot reach it and the proxy will silently not work (agent can't reach AI APIs).

---

## Installation

```bash
cd amphoreus-ai
pip install -e ./isolated-agent
pip install -e ./tunnel-agent
```

---

## Quick Start

### Option A: Use your Claude Code subscription (recommended)

If you have a Claude Code subscription, your auth tokens are in `~/.claude/` on your Mac. tunnel-agent mounts this directory into the container automatically — no API key needed.

```bash
# First time only: log in on your Mac (turn VPN on briefly)
claude login
# Turn VPN off, enable Astrill SOCKS5 proxy instead

# Run Claude Code — uses your subscription via mounted ~/.claude/
tunnel-agent run --agent claude "fix the auth bug in server.py"

# Interactive mode — opens a full TTY session
tunnel-agent run --agent claude
```

If your auth tokens are stored in macOS Keychain only (not `~/.claude/`), you can log in inside the container on first run — the proxy routes the OAuth flow through Astrill:

```bash
# Start interactive, then run `claude login` inside
tunnel-agent run --agent claude
# Claude will print a URL → open it in your Mac's browser → authorize
# Token saves to the mounted ~/.claude/ and persists across restarts
```

### Option B: Use an API key

```bash
# Set your API key in .env
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Or export it
export ANTHROPIC_API_KEY=sk-ant-...

tunnel-agent run --agent claude "fix the auth bug in server.py"
```

### Other agents

```bash
tunnel-agent run --agent codex "add unit tests for the API module"
tunnel-agent run --agent aider "refactor the database layer"
```

---

## CLI Reference

### `tunnel-agent run`

```
tunnel-agent run [OPTIONS] [TASK]
```

Launch an agent in a tunnel container. If `TASK` is omitted, starts in interactive mode.

| Flag | Default | Description |
|------|---------|-------------|
| `--agent NAME` | `claude` | Agent to run. See `tunnel-agent agents` for valid names. |
| `--workspace PATH` | `.` (current dir) | Directory to mount as `/workspace` in the container. |
| `--proxy-port PORT` | `1080` | Override the SOCKS5 proxy port for this run. |
| `--proxy-host HOST` | `host.docker.internal` | Override the SOCKS5 proxy host. |
| `--domains LIST` | — | Additional domains to proxy (comma-separated). |
| `--verbose` | — | Enable debug logging. |

### `tunnel-agent agents`

```
tunnel-agent agents
```

List all supported agents with their CLI name and install method.

### `tunnel-agent config`

```
tunnel-agent config [OPTIONS]
```

View or update the config file at `~/.tunnel-agent/config.yaml`.

| Flag | Description |
|------|-------------|
| `--proxy-host HOST` | Set the SOCKS5 proxy host |
| `--proxy-port PORT` | Set the SOCKS5 proxy port |
| `--default-agent NAME` | Set the default agent |
| *(no flags)* | Print the current config |

---

## Configuration

tunnel-agent reads `~/.tunnel-agent/config.yaml` on startup. If the file does not exist, defaults are used. You can create and edit it by hand or use `tunnel-agent config`.

```yaml
proxy:
  host: host.docker.internal   # SOCKS5 proxy host (Docker's name for your Mac)
  port: 1080                   # Astrill's SOCKS5 port
  domains:
    - api.anthropic.com
    - api.openai.com
    - generativelanguage.googleapis.com
  proxy_ips: {}                # Optional: override resolved IPs per domain
                               # e.g. api.anthropic.com: ["1.2.3.4", "5.6.7.8"]

default_agent: claude          # Used when --agent is not specified
mount_ssh: true                # Mount ~/.ssh into the container
mount_claude: true             # Mount ~/.claude into the container
```

All fields are optional — the file can be partial and missing fields fall back to defaults.

### Manual IP overrides

If DNS resolution inside the container is unreliable, you can pin IPs:

```yaml
proxy:
  proxy_ips:
    api.anthropic.com:
      - 18.196.81.10
      - 18.197.93.22
```

When `proxy_ips` is set for a domain, those IPs are used instead of resolving in the container.

---

## Supported Agents

| Agent | Name flag | Auth | Install method |
|-------|-----------|------|----------------|
| Claude Code | `claude` | Subscription (`~/.claude/`) or `ANTHROPIC_API_KEY` | npm |
| Codex | `codex` | `OPENAI_API_KEY` | npm |
| Aider | `aider` | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | pip |
| Goose | `goose` | `OPENAI_API_KEY` | binary |
| Cline | `cline` | `ANTHROPIC_API_KEY` | npm |
| Gemini CLI | `gemini` | `GEMINI_API_KEY` | npm |
| Amp | `amp` | `AMP_API_KEY` | npm |
| OpenCode | `opencode` | `ANTHROPIC_API_KEY` | npm |

For Claude Code, your subscription tokens in `~/.claude/` are mounted automatically. For other agents, set the API key in `.env` or as an environment variable.

---

## Python API

```python
from tunnel_agent import TunnelBackend, TunnelConfig, ProxyConfig
from isolated_agent import ClaudeCodeAgent, Session

# Use defaults (proxy at host.docker.internal:1080)
backend = TunnelBackend(config=TunnelConfig())

# Or customize
backend = TunnelBackend(config=TunnelConfig(
    proxy=ProxyConfig(port=1081),
    mount_ssh=True,
    mount_claude=True,
))

session = Session(
    agent=ClaudeCodeAgent(),
    backend=backend,
    workspace="./my-project",
)
result = session.run(task="fix the auth bug")
print(f"Exit code: {result.exit_code}, Duration: {result.duration_seconds}s")
```

---

## How It Works

### Container startup sequence

When `tunnel-agent run` is invoked, the backend:

1. Renders a Dockerfile, `docker-compose.yml`, `entrypoint.sh`, and `redsocks.conf` into a temp build directory
2. Builds the Docker image (Debian base with redsocks, iptables, dnsutils, su-exec, openssh-client, and the agent CLI)
3. Starts the container and waits for it to be healthy

Inside the container, `entrypoint.sh` runs as root and performs five steps before handing off to the agent:

1. **Start redsocks** — binds `127.0.0.1:12345`, configured to forward to `host.docker.internal:${PROXY_PORT}`
2. **Resolve proxy domains** — runs `dig +short` inside the container to get the current IPs for each configured domain (e.g. `api.anthropic.com`). If `proxy_ips` overrides are set, those are used instead.
3. **Install iptables rules** — for each resolved IP: `iptables -t nat -A OUTPUT -d <ip> -p tcp -j REDIRECT --to-port 12345`. Only those IPs are redirected; all other traffic exits normally.
4. **Fix SSH key permissions** — the `~/.ssh` directory is mounted read-only at `.ssh-mount` to avoid host permission conflicts, then copied and `chmod 600` applied.
5. **Drop to non-root and launch agent** — `exec gosu <user> <agent-cli> [task]`

### Network split

iptables rules operate at the kernel level before packets leave the container. There is no per-process proxy setting — the agent subprocess and all its children are affected uniformly. Traffic to unlisted IPs goes through the container's default gateway (your router), not the VPN.

---

## Limitations (v1)

**Claude subscription auth depends on `~/.claude/` contents.** If your OAuth tokens are stored only in macOS Keychain (not in `~/.claude/`), you'll need to run `claude login` inside the container once. The container's proxy routing makes this possible — Claude prints a URL you open in your browser.

**No DNS refresh during sessions.** AI API IPs are resolved once when the container starts. If an IP changes during a long-running session, proxy routing for that endpoint will stop working. Restart the container to re-resolve. (A cron-based refresh is planned for v2.)

**Astrill must bind SOCKS5 to 0.0.0.0.** If Astrill is configured to bind on `127.0.0.1` (the default in some versions), the container at `host.docker.internal` cannot reach it. See the setup instructions above.

---

## Adding Custom Agents

tunnel-agent uses the same `Agent` base class as isolated-agent. Write a class that implements `launch_command()`, `get_shim_config()`, and the other required methods, then pass it directly:

```python
from tunnel_agent import TunnelBackend, TunnelConfig
from isolated_agent import Session
from my_package import MyCustomAgent

session = Session(
    agent=MyCustomAgent(),
    backend=TunnelBackend(config=TunnelConfig()),
    workspace="./my-project",
)
result = session.run(task="do the thing")
```

See the [isolated-agent README](../isolated-agent/README.md) for the full `Agent` interface and a worked example.

---

## Requirements

- Python 3.11+
- Docker Desktop (macOS) with Compose v2
- Astrill VPN with SOCKS5 enabled and bound to `0.0.0.0`
- Claude Code subscription (tokens in `~/.claude/`) or API key for your chosen agent
