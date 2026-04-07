from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tunnel_agent.core.models import ProxyConfig, TunnelConfig


CONFIG_DIR = Path.home() / ".tunnel-agent"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _merge_proxy(defaults: ProxyConfig, data: dict[str, Any]) -> ProxyConfig:
    return ProxyConfig(
        host=data.get("host", defaults.host),
        port=data.get("port", defaults.port),
        domains=data.get("domains", defaults.domains),
        proxy_ips=data.get("proxy_ips", defaults.proxy_ips),
    )


def _merge_config(defaults: TunnelConfig, data: dict[str, Any]) -> TunnelConfig:
    proxy = defaults.proxy
    if "proxy" in data and isinstance(data["proxy"], dict):
        proxy = _merge_proxy(defaults.proxy, data["proxy"])

    return TunnelConfig(
        proxy=proxy,
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
        "proxy": {
            "host": config.proxy.host,
            "port": config.proxy.port,
            "domains": config.proxy.domains,
            "proxy_ips": config.proxy.proxy_ips,
        },
        "default_agent": config.default_agent,
        "mount_ssh": config.mount_ssh,
        "mount_claude": config.mount_claude,
        "extra_mounts": config.extra_mounts,
    }

    with target.open("w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
