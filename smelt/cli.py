"""Smelt CLI entrypoint."""

import logging
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

from smelt.arch_import import arch_build_command, arch_import_command
from smelt.config import settings
from smelt.core import loop

app = typer.Typer(help="Spec-driven autonomous code generation with convergence guarantees.")
console = Console()

app.command("arch-import")(arch_import_command)
app.command("arch-build")(arch_build_command)


@app.command()
def run(
    spec: Path = typer.Option(..., "--spec", help="Path to the natural language spec file."),
    goals: Path = typer.Option(..., "--goals", help="Path to the test goals file."),
    profile: Optional[Path] = typer.Option(
        None, "--profile", help="Path to a profile .toml (overrides smelt.toml profile field)."
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", help="Path to smelt.toml (default: ./smelt.toml)."
    ),
    module_name: str = typer.Option(
        "implementation", "--module", help="Python module name to generate."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Run Smelt: synthesize tests, freeze them, then loop code generation to convergence."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    if not spec.exists():
        console.print(f"[bold red]Error:[/] spec file not found: {spec}")
        raise typer.Exit(1)
    if not goals.exists():
        console.print(f"[bold red]Error:[/] goals file not found: {goals}")
        raise typer.Exit(1)

    cfg = settings.load(config_path, profile_path=profile)

    loop.run(
        spec_path=spec,
        goals_path=goals,
        config=cfg,
        console=console,
        module_name=module_name,
    )
