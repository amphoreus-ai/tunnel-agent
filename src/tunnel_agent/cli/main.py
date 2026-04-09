"""CLI for tunnel-agent."""
from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from isolated_agent.core.agent import Agent
from isolated_agent.core.models import SessionState
from isolated_agent.core.session import Session

from tunnel_agent.container.backend import DockerNotFoundError, TunnelBackend
from tunnel_agent.core.config import CONFIG_FILE, load_config, save_config

console = Console()

AGENT_CLASSES: dict[str, tuple[str, str]] = {
    "amp": ("isolated_agent.agents.amp", "AmpAgent"),
    "aider": ("isolated_agent.agents.aider", "AiderAgent"),
    "claude": ("isolated_agent.agents.claude", "ClaudeCodeAgent"),
    "cline": ("isolated_agent.agents.cline", "ClineAgent"),
    "codex": ("isolated_agent.agents.codex", "CodexAgent"),
    "gemini": ("isolated_agent.agents.gemini", "GeminiAgent"),
    "goose": ("isolated_agent.agents.goose", "GooseAgent"),
    "opencode": ("isolated_agent.agents.opencode", "OpenCodeAgent"),
}

AGENT_DESCRIPTIONS: dict[str, str] = {
    "amp": "Sourcegraph Amp coding agent",
    "aider": "Aider AI pair programming (Python)",
    "claude": "Anthropic Claude Code CLI",
    "cline": "Cline CLI autonomous coding agent",
    "codex": "OpenAI Codex CLI",
    "gemini": "Google Gemini CLI coding agent",
    "goose": "Block Goose autonomous agent (Rust binary)",
    "opencode": "OpenCode terminal AI coding agent",
}


def _get_agent(name: str) -> Agent:
    if name not in AGENT_CLASSES:
        available = ", ".join(sorted(AGENT_CLASSES.keys()))
        raise click.BadParameter(f"Unknown agent '{name}'. Available: {available}")
    module_name, class_name = AGENT_CLASSES[name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


@click.group(invoke_without_command=True)
@click.version_option(version="0.2.0", prog_name="tunnel-agent")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Run AI coding agents through a WireGuard VPN tunnel."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("task", required=False, default=None)
@click.option("--agent", "-a", default=None, help="Agent to use (default: from config)")
@click.option("--workspace", "-w", default=".", help="Workspace directory (default: current dir)")
@click.option("--wg-config", default=None, type=click.Path(), help="Override WireGuard config file path")
@click.option("--agent-args", default=None, help="Extra args for agent CLI (e.g. '--dangerously-skip-permissions')")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def run(
    task: str | None,
    agent: str | None,
    workspace: str,
    wg_config: str | None,
    agent_args: str | None,
    verbose: bool,
) -> None:
    """Run an agent in a tunnel container.

    TASK is optional. Omit for interactive mode.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    config = load_config()

    agent_name = agent or config.default_agent

    if wg_config is not None:
        config.wireguard.config_path = Path(wg_config)

    try:
        agent_instance = _get_agent(agent_name)
    except click.BadParameter as exc:
        console.print(Panel(str(exc), title="[bold red]Error[/bold red]", border_style="red"))
        sys.exit(1)

    try:
        backend = TunnelBackend(config=config)
    except DockerNotFoundError as exc:
        console.print(Panel(str(exc), title="[bold red]Docker Error[/bold red]", border_style="red"))
        sys.exit(1)
    except Exception as exc:
        console.print(
            Panel(str(exc), title="[bold red]Backend Error[/bold red]", border_style="red")
        )
        sys.exit(1)

    mode = "interactive" if task is None else "task"
    info_lines = (
        f"[bold]Agent:[/bold] {agent_name}\n"
        f"[bold]Workspace:[/bold] {workspace}\n"
        f"[bold]WireGuard:[/bold] {config.wireguard.config_path}\n"
        f"[bold]Mode:[/bold] {mode}"
    )
    if task:
        info_lines += f"\n[bold]Task:[/bold] {task}"

    console.print(
        Panel(info_lines, title="[bold blue]tunnel-agent[/bold blue]", border_style="blue")
    )

    extra = agent_args.split() if agent_args else []
    agent_instance.extra_args = extra

    if task is not None:
        session = Session(agent=agent_instance, backend=backend, workspace=workspace)
        result = session.run(task=task)

        if result.state == SessionState.STOPPED and result.exit_code == 0:
            console.print(
                Panel(
                    f"[green]Agent completed successfully[/green]\n"
                    f"Duration: {result.duration_seconds:.1f}s",
                    title="[bold green]Done[/bold green]",
                    border_style="green",
                )
            )
        elif result.state == SessionState.STOPPED:
            console.print(
                Panel(
                    f"[yellow]Agent stopped[/yellow]\n"
                    f"Exit code: {result.exit_code}\n"
                    f"Duration: {result.duration_seconds:.1f}s"
                    + (f"\n{result.error}" if result.error else ""),
                    title="[bold yellow]Stopped[/bold yellow]",
                    border_style="yellow",
                )
            )
        else:
            console.print(
                Panel(
                    f"[red]Agent failed[/red]\n"
                    f"Exit code: {result.exit_code}\n"
                    f"Duration: {result.duration_seconds:.1f}s"
                    + (f"\nError: {result.error}" if result.error else ""),
                    title="[bold red]Failed[/bold red]",
                    border_style="red",
                )
            )
            sys.exit(1)
    else:
        _run_interactive(agent_instance, backend, workspace, extra)


def _run_interactive(agent: Agent, backend: TunnelBackend, workspace: str, extra_args: list[str] | None = None) -> None:
    """Run agent in interactive mode (no task string).

    Bypasses Session.run() since Session always passes a task to run_agent().
    Directly manages the lifecycle: setup -> healthcheck -> exec -it -> teardown.
    """
    sandbox = None
    exit_code = 0
    try:
        console.print("[dim]Setting up tunnel container...[/dim]")
        sandbox = backend.setup(agent, workspace)

        console.print("[dim]Running healthcheck...[/dim]")
        if not backend.healthcheck(sandbox):
            console.print(
                Panel(
                    "WireGuard healthcheck failed. Check that wg0.conf is valid "
                    "and the VPS endpoint is reachable.",
                    title="[bold red]Healthcheck Failed[/bold red]",
                    border_style="red",
                )
            )
            exit_code = 1
            return

        agent_binary = _resolve_agent_binary(agent)

        compose_cmd = [
            "docker",
            "compose",
            "-p",
            sandbox.project_name,
            "-f",
            str(sandbox.build_dir / "docker-compose.yml"),
            "exec",
        ]

        if sys.stdin.isatty():
            compose_cmd.extend(["-it"])
        else:
            compose_cmd.append("-T")

        compose_cmd.extend(["--user", "agent"])
        compose_cmd.append("tunnel")
        compose_cmd.append(agent_binary)
        if extra_args:
            compose_cmd.extend(extra_args)

        try:
            subprocess.run(compose_cmd, cwd=str(sandbox.build_dir))
        except KeyboardInterrupt:
            pass

    except Exception as exc:
        console.print(
            Panel(str(exc), title="[bold red]Error[/bold red]", border_style="red")
        )
        exit_code = 1

    finally:
        if sandbox is not None:
            console.print("[dim]Tearing down tunnel container...[/dim]")
            try:
                backend.teardown(sandbox)
            except Exception as teardown_exc:
                console.print(
                    f"[yellow]Warning: teardown error (non-fatal): {teardown_exc}[/yellow]"
                )

    if exit_code != 0:
        sys.exit(exit_code)


def _resolve_agent_binary(agent: Agent) -> str:
    """Derive the interactive binary name from the agent's launch_command.

    launch_command() always returns something like ['claude', '-p', task, ...].
    The binary is the first element of that list.
    """
    dummy_cmd = agent.launch_command("__dummy__")
    return dummy_cmd[0]


@cli.command("agents")
def list_agents() -> None:
    """List available agents."""
    table = Table(title="Available Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for name in sorted(AGENT_CLASSES.keys()):
        table.add_row(name, AGENT_DESCRIPTIONS.get(name, ""))

    console.print(table)


@cli.command("config")
@click.option("--wg-config", default=None, type=click.Path(), help="Set WireGuard config file path")
@click.option("--default-agent", default=None, help="Set default agent name")
def config_cmd(wg_config: str | None, default_agent: str | None) -> None:
    """Update the tunnel-agent config file."""
    if wg_config is None and default_agent is None:
        current = load_config()
        console.print(
            Panel(
                f"[bold]Config file:[/bold] {CONFIG_FILE}\n"
                f"[bold]WireGuard:[/bold] {current.wireguard.config_path}\n"
                f"[bold]Default agent:[/bold] {current.default_agent}\n"
                f"[bold]Mount SSH:[/bold] {current.mount_ssh}\n"
                f"[bold]Mount ~/.claude:[/bold] {current.mount_claude}",
                title="[bold blue]tunnel-agent config[/bold blue]",
                border_style="blue",
            )
        )
        return

    config = load_config()

    if default_agent is not None:
        if default_agent not in AGENT_CLASSES:
            available = ", ".join(sorted(AGENT_CLASSES.keys()))
            console.print(
                Panel(
                    f"Unknown agent '{default_agent}'. Available: {available}",
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                )
            )
            sys.exit(1)
        config.default_agent = default_agent

    if wg_config is not None:
        config.wireguard.config_path = Path(wg_config)

    save_config(config)

    changed: list[str] = []
    if wg_config is not None:
        changed.append(f"WireGuard config → {wg_config}")
    if default_agent is not None:
        changed.append(f"default agent → {default_agent}")

    console.print(
        Panel(
            "\n".join(f"[green]Updated[/green] {c}" for c in changed)
            + f"\n\n[bold]Config file:[/bold] {CONFIG_FILE}",
            title="[bold green]Config saved[/bold green]",
            border_style="green",
        )
    )


@cli.command("build")
@click.option("--agent", "-a", default=None, help="Agent to build for (default: from config)")
@click.option("--wg-config", default=None, type=click.Path(), help="Path to WireGuard .conf file")
def build_cmd(agent: str | None, wg_config: str | None) -> None:
    """Pre-build the Docker image (downloads packages, installs agent CLI).

    Run this once after setup to cache the image. Subsequent runs will be fast.
    """
    config = load_config()
    agent_name = agent or config.default_agent

    if wg_config is not None:
        config.wireguard.config_path = Path(wg_config)

    try:
        agent_instance = _get_agent(agent_name)
    except click.BadParameter as exc:
        console.print(Panel(str(exc), title="[bold red]Error[/bold red]", border_style="red"))
        sys.exit(1)

    try:
        backend = TunnelBackend(config=config)
    except DockerNotFoundError as exc:
        console.print(Panel(str(exc), title="[bold red]Docker Error[/bold red]", border_style="red"))
        sys.exit(1)

    console.print(f"[bold]Building image for agent:[/bold] {agent_name}")
    console.print(f"[bold]WireGuard config:[/bold] {config.wireguard.config_path}")
    console.print()

    import tempfile
    import shutil
    from tunnel_agent.container.renderer import render_templates

    build_dir = Path(tempfile.mkdtemp(prefix="tunnel-agent-build-"))
    try:
        render_templates(
            build_dir=build_dir,
            agent=agent_instance,
            config=config,
            workspace_path=Path.cwd(),
        )
        # Stream build output so user sees progress
        backend._docker_compose(build_dir, "build", "tunnel-build", stream=True)
        console.print(Panel(
            "[green]Image built successfully.[/green]\n"
            "Subsequent `tunnel-agent run` will start instantly.",
            title="[bold green]Build complete[/bold green]",
            border_style="green",
        ))
    except Exception as exc:
        console.print(Panel(str(exc), title="[bold red]Build failed[/bold red]", border_style="red"))
        sys.exit(1)
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
