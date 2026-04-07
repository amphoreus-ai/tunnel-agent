"""Tests for tunnel_agent.core.models."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

from tunnel_agent.core.models import ProxyConfig, TunnelConfig, TunnelSandbox


class TestProxyConfig:
    def test_defaults(self):
        config = ProxyConfig()
        assert config.host == "host.docker.internal"
        assert config.port == 1080
        assert "api.anthropic.com" in config.domains
        assert "api.openai.com" in config.domains
        assert "generativelanguage.googleapis.com" in config.domains
        assert config.proxy_ips == {}

    def test_custom_values(self):
        config = ProxyConfig(host="localhost", port=8080, domains=["example.com"])
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.domains == ["example.com"]

    def test_proxy_ips_override(self):
        config = ProxyConfig(proxy_ips={"api.anthropic.com": ["1.2.3.4"]})
        assert config.proxy_ips["api.anthropic.com"] == ["1.2.3.4"]

    def test_domains_are_independent_instances(self):
        c1 = ProxyConfig()
        c2 = ProxyConfig()
        c1.domains.append("extra.com")
        assert "extra.com" not in c2.domains


class TestTunnelConfig:
    def test_defaults(self):
        config = TunnelConfig()
        assert config.default_agent == "claude"
        assert config.mount_ssh is True
        assert config.mount_claude is True
        assert config.extra_mounts == {}
        assert isinstance(config.proxy, ProxyConfig)

    def test_custom_proxy(self):
        proxy = ProxyConfig(port=9090)
        config = TunnelConfig(proxy=proxy)
        assert config.proxy.port == 9090

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
