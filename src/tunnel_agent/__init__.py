"""tunnel-agent: Run AI coding agents with selective network routing through SOCKS5 proxy."""
from tunnel_agent.core.models import ProxyConfig, TunnelConfig, TunnelSandbox
from tunnel_agent.core.config import load_config, save_config
from tunnel_agent.container.backend import TunnelBackend

__version__ = "0.1.0"

__all__ = [
    "TunnelBackend",
    "ProxyConfig",
    "TunnelConfig",
    "TunnelSandbox",
    "load_config",
    "save_config",
]
