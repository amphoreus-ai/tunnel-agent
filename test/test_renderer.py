"""Tests for tunnel_agent.container.renderer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

import pytest

from tunnel_agent.container.renderer import render_templates
from tunnel_agent.core.models import WireGuardConfig, TunnelConfig
from isolated_agent.agents.claude import ClaudeCodeAgent


@pytest.fixture()
def wg_conf(tmp_path):
    """Write a minimal WireGuard client config and return its path."""
    conf = tmp_path / "wg0.conf"
    conf.write_text(
        "[Interface]\n"
        "PrivateKey = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=\n"
        "Address = 10.0.0.2/32\n"
        "DNS = 1.1.1.1\n"
        "\n"
        "[Peer]\n"
        "PublicKey = bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=\n"
        "Endpoint = 192.0.2.1:51820\n"
        "AllowedIPs = 0.0.0.0/0\n"
    )
    return conf


@pytest.fixture()
def rendered(tmp_path, wg_conf):
    """Render all templates into a build dir and return the build dir."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    config = TunnelConfig(wireguard=WireGuardConfig(config_path=wg_conf))
    render_templates(
        build_dir=build_dir,
        agent=ClaudeCodeAgent(),
        config=config,
        workspace_path=workspace,
    )
    return build_dir


class TestRenderTemplates:
    def test_renders_all_files(self, rendered):
        assert (rendered / "Dockerfile").exists()
        assert (rendered / "docker-compose.yml").exists()
        assert (rendered / "entrypoint.sh").exists()
        assert (rendered / "wg0.conf").exists()

    def test_wg_conf_rendered_into_build(self, rendered):
        wg = (rendered / "wg0.conf").read_text()
        assert "[Interface]" in wg
        assert "[Peer]" in wg

    def test_dockerfile_has_wireguard_tools(self, rendered):
        content = (rendered / "Dockerfile").read_text()
        assert "wireguard-tools" in content

    def test_dockerfile_has_agent_packages(self, rendered):
        content = (rendered / "Dockerfile").read_text()
        assert "claude" in content.lower()

    def test_entrypoint_has_wg_quick(self, rendered):
        content = (rendered / "entrypoint.sh").read_text()
        assert "wg-quick" in content

    def test_entrypoint_is_executable(self, rendered):
        entrypoint = rendered / "entrypoint.sh"
        assert entrypoint.stat().st_mode & 0o111

    def test_no_ssh_mount_when_disabled(self, tmp_path, wg_conf):
        build_dir = tmp_path / "build2"
        build_dir.mkdir()
        workspace = tmp_path / "workspace2"
        workspace.mkdir()

        config = TunnelConfig(
            wireguard=WireGuardConfig(config_path=wg_conf),
            mount_ssh=False,
        )
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
        )

        content = (build_dir / "docker-compose.yml").read_text()
        assert ".ssh-mount" not in content

    def test_ssh_mount_when_enabled(self, tmp_path, wg_conf):
        build_dir = tmp_path / "build3"
        build_dir.mkdir()
        workspace = tmp_path / "workspace3"
        workspace.mkdir()

        config = TunnelConfig(
            wireguard=WireGuardConfig(config_path=wg_conf),
            mount_ssh=True,
        )
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
        )

        content = (build_dir / "docker-compose.yml").read_text()
        assert ".ssh-mount" in content

    def test_creates_empty_env_if_none_found(self, rendered):
        assert (rendered / ".env").exists()

    def test_uses_existing_env_file(self, tmp_path, wg_conf):
        build_dir = tmp_path / "build4"
        build_dir.mkdir()
        workspace = tmp_path / "workspace4"
        workspace.mkdir()
        env_file = workspace / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=test-key")

        config = TunnelConfig(wireguard=WireGuardConfig(config_path=wg_conf))
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
            env_file=env_file,
        )

        compose = (build_dir / "docker-compose.yml").read_text()
        assert str(env_file) in compose

    def test_entrypoint_sources_env(self, rendered):
        content = (rendered / "entrypoint.sh").read_text()
        assert ". /app/.env" in content

    def test_entrypoint_no_unsubstituted_template_vars(self, rendered):
        import re
        for filename in ["entrypoint.sh", "Dockerfile"]:
            content = (rendered / filename).read_text()
            unmatched = re.findall(r'\$\{(?![\d!#@*?])[a-z_]+\}', content)
            assert unmatched == [], f"Unsubstituted template vars in {filename}: {unmatched}"
