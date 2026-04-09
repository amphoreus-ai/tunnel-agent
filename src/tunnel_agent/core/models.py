from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WireGuardConfig:
    """Configuration for WireGuard VPN tunnel."""

    config_path: Path = field(default_factory=lambda: Path.home() / ".tunnel-agent" / "wg0.conf")


@dataclass
class TunnelConfig:
    """Top-level configuration for tunnel-agent."""

    wireguard: WireGuardConfig = field(default_factory=WireGuardConfig)
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
