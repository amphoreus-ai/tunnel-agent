"""Tests for tunnel_agent.core.models."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

from tunnel_agent.core.models import WireGuardConfig, TunnelConfig, TunnelSandbox


class TestWireGuardConfig:
    def test_default_path(self):
        config = WireGuardConfig()
        assert config.config_path == Path.home() / ".tunnel-agent" / "wg0.conf"

    def test_custom_path(self):
        config = WireGuardConfig(config_path=Path("/etc/wireguard/custom.conf"))
        assert config.config_path == Path("/etc/wireguard/custom.conf")


class TestTunnelConfig:
    def test_defaults(self):
        config = TunnelConfig()
        assert config.default_agent == "claude"
        assert config.mount_ssh is True
        assert config.mount_claude is True
        assert config.extra_mounts == {}
        assert isinstance(config.wireguard, WireGuardConfig)

    def test_custom_wireguard(self):
        wg = WireGuardConfig(config_path=Path("/tmp/wg0.conf"))
        config = TunnelConfig(wireguard=wg)
        assert config.wireguard.config_path == Path("/tmp/wg0.conf")

    def test_disable_mounts(self):
        config = TunnelConfig(mount_ssh=False, mount_claude=False)
        assert config.mount_ssh is False
        assert config.mount_claude is False


class TestTunnelSandbox:
    def test_construction(self, tmp_path):
        sandbox = TunnelSandbox(
            project_name="test-project",
            build_dir=tmp_path,
            workspace_path=tmp_path / "workspace",
            config=TunnelConfig(),
        )
        assert sandbox.project_name == "test-project"
        assert sandbox.build_dir == tmp_path
        assert sandbox.config.default_agent == "claude"
