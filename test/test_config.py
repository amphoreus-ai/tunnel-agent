"""Tests for tunnel_agent.core.config."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

import yaml

from tunnel_agent.core.config import load_config, save_config
from tunnel_agent.core.models import ProxyConfig, TunnelConfig


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.default_agent == "claude"
        assert config.proxy.port == 1080
        assert len(config.proxy.domains) == 3

    def test_returns_defaults_for_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.default_agent == "claude"

    def test_partial_config_merges_over_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump({"proxy": {"port": 9090}}))
        config = load_config(config_file)
        assert config.proxy.port == 9090
        assert config.proxy.host == "host.docker.internal"
        assert len(config.proxy.domains) == 3

    def test_full_config_override(self, tmp_path):
        data = {
            "proxy": {
                "host": "myhost",
                "port": 2080,
                "domains": ["custom.api.com"],
                "proxy_ips": {"custom.api.com": ["10.0.0.1"]},
            },
            "default_agent": "codex",
            "mount_ssh": False,
            "mount_claude": False,
            "extra_mounts": {"/host/data": "/container/data"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump(data))
        config = load_config(config_file)
        assert config.proxy.host == "myhost"
        assert config.proxy.port == 2080
        assert config.proxy.domains == ["custom.api.com"]
        assert config.default_agent == "codex"
        assert config.mount_ssh is False
        assert config.extra_mounts == {"/host/data": "/container/data"}

    def test_invalid_yaml_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("just a string not a dict")
        config = load_config(config_file)
        assert config.default_agent == "claude"


class TestSaveConfig:
    def test_save_creates_file(self, tmp_path):
        config_file = tmp_path / "subdir" / "config.yaml"
        save_config(TunnelConfig(), config_file)
        assert config_file.exists()

    def test_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        original = TunnelConfig(
            proxy=ProxyConfig(port=9999, domains=["test.com"]),
            default_agent="aider",
            mount_ssh=False,
        )
        save_config(original, config_file)
        loaded = load_config(config_file)
        assert loaded.proxy.port == 9999
        assert loaded.proxy.domains == ["test.com"]
        assert loaded.default_agent == "aider"
        assert loaded.mount_ssh is False
