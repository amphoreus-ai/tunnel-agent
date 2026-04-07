"""Tests for tunnel_agent.container.renderer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "isolated-agent" / "src"))

from tunnel_agent.container.renderer import render_templates
from tunnel_agent.core.models import ProxyConfig, TunnelConfig
from isolated_agent.agents.claude import ClaudeCodeAgent


class TestRenderTemplates:
    def test_renders_all_files(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        agent = ClaudeCodeAgent()
        config = TunnelConfig()

        render_templates(
            build_dir=build_dir,
            agent=agent,
            config=config,
            workspace_path=workspace,
        )

        assert (build_dir / "Dockerfile").exists()
        assert (build_dir / "docker-compose.yml").exists()
        assert (build_dir / "entrypoint.sh").exists()
        assert (build_dir / "redsocks.conf").exists()

    def test_entrypoint_is_executable(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        entrypoint = build_dir / "entrypoint.sh"
        assert entrypoint.stat().st_mode & 0o111

    def test_redsocks_conf_has_proxy_settings(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = TunnelConfig(proxy=ProxyConfig(host="myproxy", port=2080))
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
        )

        content = (build_dir / "redsocks.conf").read_text()
        assert "myproxy" in content
        assert "2080" in content

    def test_entrypoint_has_proxy_domains(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        content = (build_dir / "entrypoint.sh").read_text()
        assert "api.anthropic.com" in content
        assert "api.openai.com" in content

    def test_no_ssh_mount_when_disabled(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = TunnelConfig(mount_ssh=False)
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
        )

        content = (build_dir / "docker-compose.yml").read_text()
        assert ".ssh-mount" not in content

    def test_ssh_mount_when_enabled(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = TunnelConfig(mount_ssh=True)
        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=config,
            workspace_path=workspace,
        )

        content = (build_dir / "docker-compose.yml").read_text()
        assert ".ssh-mount" in content

    def test_creates_empty_env_if_none_found(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        assert (build_dir / ".env").exists()

    def test_uses_existing_env_file(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        env_file = workspace / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=test-key")

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
            env_file=env_file,
        )

        compose = (build_dir / "docker-compose.yml").read_text()
        assert str(env_file) in compose

    def test_dockerfile_has_agent_packages(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        content = (build_dir / "Dockerfile").read_text()
        assert "redsocks" in content
        assert "iptables" in content
        assert "claude-code" in content

    def test_entrypoint_sources_env(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        content = (build_dir / "entrypoint.sh").read_text()
        assert ". /app/.env" in content

    def test_entrypoint_no_unsubstituted_template_vars(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        render_templates(
            build_dir=build_dir,
            agent=ClaudeCodeAgent(),
            config=TunnelConfig(),
            workspace_path=workspace,
        )

        for filename in ["entrypoint.sh", "redsocks.conf", "Dockerfile"]:
            content = (build_dir / filename).read_text()
            # After rendering, there should be no ${...} template vars left
            # (shell $VAR and ${VAR} are fine — they start with $$ in the template)
            import re
            # Look for template-style vars that weren't substituted
            # safe_substitute leaves unmatched ${var} as-is
            unmatched = re.findall(r'\$\{(?![\d!#@*?])[a-z_]+\}', content)
            assert unmatched == [], f"Unsubstituted template vars in {filename}: {unmatched}"
