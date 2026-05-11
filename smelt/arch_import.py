"""arch-import and arch-build CLI command implementations."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from smelt.arch.extractor import extract_principles
from smelt.arch.spec_generator import generate_all_specs

log = logging.getLogger(__name__)
console = Console()


def arch_import_command(
    doc: Path = typer.Option(..., "--doc", help="Path to architecture document (Markdown or plain text)."),
    specs_dir: Path = typer.Option(Path("specs"), "--specs-dir", help="Output directory for Crasis YAML specs."),
    model: str = typer.Option("claude-sonnet-4-5", "--model", help="LLM model for principle extraction."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Re-extract even if a cached result exists."),
) -> None:
    """Extract architectural principles from a SAD and generate Crasis YAML specs.

    Reads the architecture document, calls Claude to extract enforceable principles,
    writes one YAML spec per principle to --specs-dir, and prints a review table.

    Human review of the generated specs is required before running arch-build.
    """
    if not doc.exists():
        console.print(f"[bold red]Error:[/] document not found: {doc}")
        raise typer.Exit(1)

    doc_text = doc.read_text(encoding="utf-8")
    console.print(f"Extracting principles from [bold]{doc.name}[/]...")

    principles = extract_principles(doc_text, model=model, no_cache=no_cache)

    if not principles:
        console.print("[bold yellow]Warning:[/] no enforceable principles found in the document.")
        raise typer.Exit(0)

    spec_paths = generate_all_specs(principles, specs_dir)

    console.print(f"\nExtracted [bold]{len(principles)}[/] principles from {doc.name}\n")

    table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("name", min_width=28)
    table.add_column("weight", width=6, justify="right")
    table.add_column("chunk", width=8)
    table.add_column("trigger (truncated)", min_width=48)

    for i, p in enumerate(principles, start=1):
        trigger_preview = p.trigger[:60].replace("\n", " ")
        if len(p.trigger) > 60:
            trigger_preview += "..."
        weight_str = f"{p.weight:.1f}"
        if p.mandatory:
            weight_str = f"[bold]{weight_str}[/]"
        table.add_row(str(i), p.name, weight_str, p.chunk_level, trigger_preview)

    console.print(table)
    console.print(f"\nSpecs written to [bold]{specs_dir}/[/]")
    console.print("\nReview specs before running:")
    console.print(f"  [dim]smelt arch-build --specs-dir {specs_dir}/ --confirm[/]")


def arch_build_command(
    specs_dir: Path = typer.Option(Path("specs"), "--specs-dir", help="Directory containing Crasis YAML specs."),
    models_dir: Path = typer.Option(Path("specialists"), "--models-dir", help="Output directory for trained ONNX specialists."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="OpenRouter API key (or set OPENROUTER_API_KEY)."),
    confirm: bool = typer.Option(False, "--confirm", help="Required to prevent accidental budget spend."),
) -> None:
    """Build ONNX specialists from Crasis YAML specs.

    Runs crasis build for each spec in --specs-dir. This generates synthetic
    training data (via OpenRouter API) and trains ONNX specialists locally.

    Requires --confirm to prevent accidental training budget spend.
    Requires OPENROUTER_API_KEY env var or --api-key.
    """
    if not confirm:
        console.print(
            "[bold yellow]Safety gate:[/] arch-build spends training budget "
            "(synthetic data generation via OpenRouter + local fine-tuning).\n"
            "Review specs in [bold]{specs_dir}/[/] first, then run with [bold]--confirm[/]."
        )
        raise typer.Exit(0)

    if not specs_dir.exists():
        console.print(f"[bold red]Error:[/] specs directory not found: {specs_dir}")
        raise typer.Exit(1)

    spec_files = sorted(specs_dir.glob("*.yaml"))
    if not spec_files:
        console.print(f"[bold red]Error:[/] no .yaml files found in {specs_dir}")
        raise typer.Exit(1)

    import os
    resolved_api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not resolved_api_key:
        console.print(
            "[bold red]Error:[/] OpenRouter API key required. "
            "Set OPENROUTER_API_KEY or pass --api-key."
        )
        raise typer.Exit(1)

    console.print(f"Building [bold]{len(spec_files)}[/] specialists from {specs_dir}/\n")

    failed: list[str] = []
    for spec_path in spec_files:
        # Load spec to get the principle name for the output directory
        try:
            spec_data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            console.print(f"  [red]SKIP[/] {spec_path.name}: cannot read spec — {exc}")
            failed.append(spec_path.stem)
            continue

        name = spec_data.get("name", spec_path.stem)
        specialist_dir = models_dir / f"{name}-onnx"

        console.print(f"  Building [bold]{name}[/]...")

        cmd = [
            "crasis", "build",
            "--spec", str(spec_path),
            "--api-key", resolved_api_key,
            "--model-dir", str(specialist_dir),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"    [red]FAILED[/]: crasis build exited {result.returncode}")
            output = (result.stderr or result.stdout or "").strip()
            if output:
                console.print(f"    {output[:400]}")
            failed.append(name)
            continue

        # Write Smelt metadata sidecar so CrasisScorer knows chunk_level and weight
        smelt_meta = spec_data.get("_smelt_meta", {})
        _write_smelt_sidecar(specialist_dir, name, smelt_meta)

        console.print(f"    [green]OK[/] → {specialist_dir}/")

    if failed:
        console.print(f"\n[bold yellow]{len(failed)} specialist(s) failed:[/] {', '.join(failed)}")
        raise typer.Exit(1)

    console.print(f"\n[bold green]All specialists built.[/] Models in {models_dir}/")
    console.print("\nRun Smelt with the crasis_python profile:")
    console.print("  [dim]smelt run --spec <spec.md> --goals <goals.md> --profile crasis_python[/]")


def _write_smelt_sidecar(specialist_dir: Path, name: str, smelt_meta: dict) -> None:
    """Write crasis_meta.json with Smelt-specific fields alongside the ONNX package.

    CrasisScorer reads the "smelt" key from crasis_meta.json to get chunk_level
    and weight for each specialist, since the Specialist object only exposes name
    and label_names.
    """
    meta_path = specialist_dir / "crasis_meta.json"

    existing: dict = {}
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing["smelt"] = {
        "chunk_level": smelt_meta.get("chunk_level", "function"),
        "weight": smelt_meta.get("weight", 1.0),
        "mandatory": smelt_meta.get("mandatory", False),
        "source_section": smelt_meta.get("source_section", ""),
    }
    existing.setdefault("name", name)

    specialist_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
