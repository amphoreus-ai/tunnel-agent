"""Renders Docker templates for the tunnel-agent container."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

from tunnel_agent.core.models import TunnelConfig

if TYPE_CHECKING:
    from isolated_agent.core.agent import Agent

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_template(template_name: str, context: dict[str, str]) -> str:
    """Render a single .tpl file with the given context dictionary."""
    template_path = TEMPLATES_DIR / template_name
    template = Template(template_path.read_text())
    return template.safe_substitute(context)


def render_templates(
    build_dir: Path,
    agent: Agent,
    config: TunnelConfig,
    workspace_path: Path,
    env_file: Path | None = None,
) -> None:
    """Render all template files into the build directory.

    Reads .tpl files from the templates/ directory, substitutes variables
    using string.Template, and writes the rendered output to build_dir.
    """
    shim = agent.get_shim_config()

    project_name = build_dir.name

    # --- Read WireGuard config ---
    wg_path = config.wireguard.config_path.expanduser()
    if not wg_path.exists():
        raise FileNotFoundError(
            f"WireGuard config not found at {wg_path}. "
            "Run the WireGuard setup script on your VPS first."
        )
    wg_config_content = wg_path.read_text()

    # --- Resolve env_file path ---
    if env_file is None:
        # Look in workspace first, then cwd, then create empty
        candidates = [workspace_path / ".env", Path.cwd() / ".env"]
        for candidate in candidates:
            if candidate.exists():
                env_file = candidate
                break
        if env_file is None:
            env_file = build_dir / ".env"
            env_file.touch()

    # --- Build mount strings for docker-compose ---
    user = shim.run_as_user or "root"
    home_dir = shim.home_dir or "/root"

    ssh_mount = ""
    if config.mount_ssh:
        ssh_mount = f"- ~/.ssh:{home_dir}/.ssh-mount:ro"

    claude_mount = ""
    if config.mount_claude:
        claude_mount = f"- ~/.claude:{home_dir}/.claude:rw"

    # --- Extra mounts ---
    extra_mount_lines = []
    for host_path, container_path in config.extra_mounts.items():
        extra_mount_lines.append(f"- {host_path}:{container_path}")
    extra_mounts = "\n      ".join(extra_mount_lines)

    # --- Environment block for Dockerfile ---
    env_str = ""
    if shim.env_vars:
        env_lines = [f"{k}={v}" for k, v in shim.env_vars.items()]
        env_str = "ENV " + " \\\n    ".join(env_lines)

    # --- GPU detection ---
    gpu_config = ""
    if shutil.which("nvidia-smi"):
        try:
            subprocess.run(["nvidia-smi"], capture_output=True, check=True, timeout=5)
            gpu_config = (
                "deploy:\n"
                "      resources:\n"
                "        reservations:\n"
                "          devices:\n"
                "            - driver: nvidia\n"
                "              count: all\n"
                "              capabilities: [gpu]"
            )
            logger.info("NVIDIA GPU detected — enabling GPU passthrough")
        except Exception:
            pass

    # --- Template context ---
    context: dict[str, str] = {
        # Project
        "project_name": project_name,
        "workspace_path": str(workspace_path),
        "env_file": str(env_file),
        # ShimConfig fields
        "system_packages": shim.system_packages,
        "cli_install_cmd": shim.cli_install_cmd,
        "env_vars": env_str,
        "home_dir": home_dir,
        "run_as_user": user,
        # WireGuard
        "wg_config_content": wg_config_content,
        # Mounts
        "ssh_mount": ssh_mount,
        "claude_mount": claude_mount,
        "extra_mounts": extra_mounts,
        # GPU
        "gpu_config": gpu_config,
    }

    logger.debug("Rendering templates with context keys: %s", list(context.keys()))

    # --- Render and write each template ---
    templates = {
        "Dockerfile.tpl": "Dockerfile",
        "docker-compose.yml.tpl": "docker-compose.yml",
        "entrypoint.sh.tpl": "entrypoint.sh",
        "wg0.conf.tpl": "wg0.conf",
    }

    for tpl_name, output_name in templates.items():
        rendered = render_template(tpl_name, context)
        output_path = build_dir / output_name
        output_path.write_text(rendered)
        logger.debug("Wrote %s", output_path)

    # Make entrypoint executable
    entrypoint = build_dir / "entrypoint.sh"
    entrypoint.chmod(0o755)
