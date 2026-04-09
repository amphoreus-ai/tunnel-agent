"""tunnel-agent: Run AI coding agents through a WireGuard VPN tunnel."""
from tunnel_agent.core.models import WireGuardConfig, TunnelConfig, TunnelSandbox
from tunnel_agent.core.config import load_config, save_config
from tunnel_agent.container.backend import TunnelBackend

__version__ = "0.1.0"

__all__ = [
    "TunnelBackend",
    "WireGuardConfig",
    "TunnelConfig",
    "TunnelSandbox",
    "load_config",
    "save_config",
]
