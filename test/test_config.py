"""Tests for tunnel_agent.core.config."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

import yaml

from tunnel_agent.core.config import load_config, save_config
from tunnel_agent.core.models import WireGuardConfig, TunnelConfig


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.default_agent == "claude"
        assert config.wireguard.config_path == Path.home() / ".tunnel-agent" / "wg0.conf"

    def test_returns_defaults_for_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.default_agent == "claude"

    def test_partial_merge_with_config_path(self, tmp_path):
        custom_path = "/tmp/custom.conf"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump({"wireguard": {"config_path": custom_path}}))
        config = load_config(config_file)
        assert config.wireguard.config_path == Path(custom_path)
        assert config.default_agent == "claude"

    def test_old_proxy_key_does_not_crash(self, tmp_path, capsys):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump({"proxy": {"host": "oldhost", "port": 1080}}))
        config = load_config(config_file)
        assert config.default_agent == "claude"
        captured = capsys.readouterr()
        assert "deprecated" in captured.err

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

    def test_roundtrip_with_wireguard_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        custom_path = tmp_path / "wg0.conf"
        original = TunnelConfig(
            wireguard=WireGuardConfig(config_path=custom_path),
            default_agent="aider",
            mount_ssh=False,
        )
        save_config(original, config_file)
        loaded = load_config(config_file)
        assert loaded.wireguard.config_path == custom_path
        assert loaded.default_agent == "aider"
        assert loaded.mount_ssh is False
