"""Tunnel backend — single container with WireGuard VPN."""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from isolated_agent.core.backend import Backend
from isolated_agent.core.models import ExecutionResult, Sandbox

from tunnel_agent.core.models import TunnelConfig
from tunnel_agent.container.renderer import render_templates

if TYPE_CHECKING:
    from isolated_agent.core.agent import Agent

logger = logging.getLogger(__name__)


class DockerNotFoundError(Exception):
    """Raised when Docker or Docker Compose is not available."""


class TunnelBackend(Backend):
    """Backend that runs an agent in a single container with a WireGuard
    VPN tunnel to an external VPS for unrestricted internet access.
    """

    def __init__(self, config: TunnelConfig | None = None):
        # Intentionally skip super().__init__() — we use TunnelConfig, not BackendConfig
        self.config = config or TunnelConfig()
        self._check_docker()

    # ------------------------------------------------------------------
    # Public API (Backend ABC)
    # ------------------------------------------------------------------

    def setup(self, agent: Agent, workspace_path: Path | str) -> Sandbox:
        """Build and start the tunnel container."""
        workspace_path = Path(workspace_path).resolve()
        workspace_path.mkdir(parents=True, exist_ok=True)

        project_name = f"tunnel-{uuid.uuid4().hex[:8]}"
        build_dir = Path(tempfile.mkdtemp(prefix="tunnel-agent-"))

        try:
            # Validate WireGuard config exists before rendering
            wg_path = self.config.wireguard.config_path.expanduser()
            if not wg_path.exists():
                raise FileNotFoundError(
                    f"WireGuard config not found at {wg_path}. "
                    "Run the WireGuard setup script on your VPS first."
                )

            # Find .env file
            env_file = self._find_env_file(workspace_path)

            render_templates(
                build_dir=build_dir,
                agent=agent,
                config=self.config,
                workspace_path=workspace_path,
                env_file=env_file,
            )

            self._docker_compose(build_dir, "build", project_name)
            self._docker_compose(build_dir, "up", project_name, "-d", "--wait")
        except Exception:
            try:
                self._docker_compose(
                    build_dir, "down", project_name, "-v", "--remove-orphans"
                )
            except Exception:
                pass
            shutil.rmtree(build_dir, ignore_errors=True)
            raise

        return Sandbox(
            project_name=project_name,
            build_dir=build_dir,
            workspace_path=workspace_path,
        )

    def teardown(self, sandbox: Sandbox) -> None:
        """Stop the tunnel container and clean up build artefacts."""
        try:
            self._docker_compose(
                sandbox.build_dir,
                "down",
                sandbox.project_name,
                "-v",
                "--remove-orphans",
                "--timeout",
                "10",
            )
        finally:
            shutil.rmtree(sandbox.build_dir, ignore_errors=True)

    def healthcheck(self, sandbox: Sandbox) -> bool:
        """Verify the WireGuard tunnel is working by curling an AI API endpoint."""
        try:
            result = self._docker_compose_exec(
                sandbox,
                ["curl", "-s", "--max-time", "10", "https://api.anthropic.com"],
            )
            return result.exit_code == 0
        except Exception as exc:
            logger.warning("Healthcheck failed: %s", exc)
            return False

    def run_agent(self, sandbox: Sandbox, agent: Agent, task: str) -> ExecutionResult:
        """Launch the agent inside the tunnel container.

        For interactive mode (no task), allocates a TTY so the agent
        can accept user input. For task mode, streams output directly
        to the host terminal.
        """
        cmd = agent.launch_command(task)
        interactive = not task

        compose_cmd = [
            "docker",
            "compose",
            "-p",
            sandbox.project_name,
            "-f",
            str(sandbox.build_dir / "docker-compose.yml"),
            "exec",
        ]

        if interactive and sys.stdin.isatty():
            compose_cmd.extend(["-it"])
        else:
            compose_cmd.append("-T")

        compose_cmd.append("tunnel")
        compose_cmd.extend(cmd)

        logger.info("Running: %s", " ".join(cmd))

        proc = subprocess.run(
            compose_cmd,
            cwd=str(sandbox.build_dir),
            timeout=None,
        )

        return ExecutionResult(
            exit_code=proc.returncode,
            stdout="",
            stderr="",
        )

    def execute(self, sandbox: Sandbox, command: str) -> ExecutionResult:
        """Execute an arbitrary command inside the tunnel container."""
        return self._docker_compose_exec(
            sandbox, ["bash", "-c", command]
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_docker() -> None:
        """Verify docker and docker compose are available."""
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError:
            raise DockerNotFoundError(
                "Docker is not installed. Install Docker Desktop or the docker CLI."
            )
        except subprocess.CalledProcessError:
            raise DockerNotFoundError(
                "Docker Compose is not available. "
                "Install Docker Desktop or the docker-compose-plugin."
            )

    @staticmethod
    def _find_env_file(workspace_path: Path) -> Path | None:
        """Look for a .env file in the workspace or current directory."""
        candidates = [workspace_path / ".env", Path.cwd() / ".env"]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _docker_compose(
        self,
        build_dir: Path,
        command: str,
        project_name: str,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run a docker compose command."""
        cmd = [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(build_dir / "docker-compose.yml"),
            command,
        ] + list(args)

        logger.debug("Running: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error(
                "docker compose %s failed:\n%s", command, result.stderr
            )
            raise RuntimeError(
                f"docker compose {command} failed "
                f"(exit {result.returncode}): {result.stderr[:500]}"
            )

        return result

    def _docker_compose_exec(
        self,
        sandbox: Sandbox,
        cmd: list[str],
    ) -> ExecutionResult:
        """Run a command in the running tunnel container."""
        compose_cmd = [
            "docker",
            "compose",
            "-p",
            sandbox.project_name,
            "-f",
            str(sandbox.build_dir / "docker-compose.yml"),
            "exec",
            "-T",
            "tunnel",
        ] + cmd

        result = subprocess.run(
            compose_cmd,
            cwd=str(sandbox.build_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
