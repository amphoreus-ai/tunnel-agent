from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from tunnel_agent.core.models import WireGuardConfig, TunnelConfig


CONFIG_DIR = Path.home() / ".tunnel-agent"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _merge_wireguard(defaults: WireGuardConfig, data: dict[str, Any]) -> WireGuardConfig:
    config_path = data.get("config_path", defaults.config_path)
    return WireGuardConfig(
        config_path=Path(config_path),
    )


def _merge_config(defaults: TunnelConfig, data: dict[str, Any]) -> TunnelConfig:
    if "proxy" in data:
        print(
            "WARNING: 'proxy:' key in config is deprecated and has no effect. "
            "Use 'wireguard:' instead.",
            file=sys.stderr,
        )

    wireguard = defaults.wireguard
    if "wireguard" in data and isinstance(data["wireguard"], dict):
        wireguard = _merge_wireguard(defaults.wireguard, data["wireguard"])

    return TunnelConfig(
        wireguard=wireguard,
        default_agent=data.get("default_agent", defaults.default_agent),
        mount_ssh=data.get("mount_ssh", defaults.mount_ssh),
        mount_claude=data.get("mount_claude", defaults.mount_claude),
        extra_mounts=data.get("extra_mounts", defaults.extra_mounts),
    )


def load_config(path: Path | None = None) -> TunnelConfig:
    """Load config from YAML, merging over defaults. Returns defaults if no file."""
    target = path or CONFIG_FILE
    defaults = TunnelConfig()

    if not target.exists():
        return defaults

    with target.open() as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return defaults

    return _merge_config(defaults, data)


def save_config(config: TunnelConfig, path: Path | None = None) -> None:
    """Save config to YAML."""
    target = path or CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "wireguard": {
            "config_path": str(config.wireguard.config_path),
        },
        "default_agent": config.default_agent,
        "mount_ssh": config.mount_ssh,
        "mount_claude": config.mount_claude,
        "extra_mounts": config.extra_mounts,
    }

    with target.open("w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
