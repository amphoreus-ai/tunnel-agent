from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProxyConfig:
    """Configuration for the SOCKS5 proxy used to route AI API traffic."""

    host: str = "host.docker.internal"
    port: int = 1080
    domains: list[str] = field(default_factory=lambda: [
        "api.anthropic.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
    ])
    proxy_ips: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class TunnelConfig:
    """Top-level configuration for tunnel-agent."""

    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    default_agent: str = "claude"
    mount_ssh: bool = True
    mount_claude: bool = True
    extra_mounts: dict[str, str] = field(default_factory=dict)


@dataclass
class TunnelSandbox:
    """Represents a running tunnel sandbox environment."""

    project_name: str
    build_dir: Path
    workspace_path: Path
    config: TunnelConfig
