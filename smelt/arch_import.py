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

from smelt.arch.extractor import ArchitecturalPrinciple, extract_principles
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

    local_principles = [p for p in principles if p.chunk_level != "cross-file"]
    cross_file_principles = [p for p in principles if p.chunk_level == "cross-file"]

    spec_paths = generate_all_specs(local_principles, specs_dir)

    for p in cross_file_principles:
        _write_layer_toml(p, specs_dir)

    console.print(f"\nExtracted [bold]{len(principles)}[/] principles from {doc.name}\n")

    table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("name", min_width=28)
    table.add_column("weight", width=6, justify="right")
    table.add_column("chunk", width=10)
    table.add_column("enforcer", width=12)
    table.add_column("trigger (truncated)", min_width=40)

    for i, p in enumerate(principles, start=1):
        trigger_preview = p.trigger[:50].replace("\n", " ")
        if len(p.trigger) > 50:
            trigger_preview += "..."
        weight_str = f"{p.weight:.1f}"
        if p.mandatory:
            weight_str = f"[bold]{weight_str}[/]"
        if p.chunk_level == "cross-file":
            enforcer = "[yellow]layer_scorer[/]"
            chunk_display = "[yellow]cross-file[/]"
        else:
            enforcer = "crasis"
            chunk_display = p.chunk_level
        table.add_row(str(i), p.name, weight_str, chunk_display, enforcer, trigger_preview)

    console.print(table)

    if cross_file_principles:
        console.print(
            f"\n[bold yellow]Routing notice:[/] {len(cross_file_principles)} principle(s) "
            "require cross-file dependency analysis and cannot be trained as Crasis ONNX specialists.\n"
            "These have been written as [bold].layer.toml[/] config snippets for the LayerScorer.\n"
        )
        for p in cross_file_principles:
            snippet_path = specs_dir / f"{p.name}.layer.toml"
            console.print(f"  [yellow]→[/] {snippet_path}  (merge into your profile's [scorers.layer] section)")
        console.print()

    if local_principles:
        console.print(f"Crasis specs written to [bold]{specs_dir}/[/]")
        console.print("\nReview specs before running:")
        console.print(f"  [dim]smelt arch-build --specs-dir {specs_dir}/ --confirm[/]")


def arch_build_command(
    specs_dir: Path = typer.Option(Path("specs"), "--specs-dir", help="Directory containing Crasis YAML specs."),
    models_dir: Path = typer.Option(Path("specialists"), "--models-dir", help="Output directory for trained ONNX specialists."),
    profile: Optional[Path] = typer.Option(None, "--profile", help="Profile TOML to read active_specialists from. Only specs listed there will be built."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="OpenRouter API key (or set OPENROUTER_API_KEY)."),
    confirm: bool = typer.Option(False, "--confirm", help="Required to prevent accidental budget spend."),
) -> None:
    """Build ONNX specialists from Crasis YAML specs.

    Runs crasis build for each spec in --specs-dir. This generates synthetic
    training data (via OpenRouter API) and trains ONNX specialists locally.

    When --profile is given, only the specialists listed under
    [scorers.crasis] active_specialists in that profile are built. Any spec
    file not in that list is skipped. This prevents accidentally retraining
    specialists from other projects when a specs/ directory is shared.

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

    # Filter spec files to only those declared in the profile's active_specialists.
    allowed: set[str] | None = _active_specialists_from_profile(profile)
    if allowed is not None:
        before = len(spec_files)
        spec_files = [f for f in spec_files if f.stem in allowed]
        skipped = before - len(spec_files)
        console.print(
            f"Profile filter: [bold]{len(spec_files)}[/] of {before} specs match "
            f"active_specialists ({skipped} skipped).\n"
        )
        if not spec_files:
            console.print("[bold red]Error:[/] no specs match the profile's active_specialists list.")
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


def _write_layer_toml(principle: ArchitecturalPrinciple, specs_dir: Path) -> None:
    """Write a .layer.toml config snippet for a cross-file principle.

    The snippet is a ready-to-merge fragment for the [scorers.layer] section of a
    profile TOML. The human must review it, fill in the actual layer names and allowed
    edges for the target system, and merge it into the profile manually.
    """

    specs_dir.mkdir(parents=True, exist_ok=True)
    snippet_path = specs_dir / f"{principle.name}.layer.toml"

    weight_str = f"{principle.weight:.1f}"
    mandatory_str = "true" if principle.mandatory else "false"

    content = f"""\
# LayerScorer config snippet — generated by smelt arch-import
# Source: {principle.source_section}
# Principle: {principle.title}
#
# This principle requires cross-file dependency analysis. Crasis ONNX classifiers
# cannot detect it because no single file contains the full violation evidence.
# The LayerScorer enforces it by inspecting #include directives across all source
# files and checking them against the declared allowed dependency edges below.
#
# ACTION REQUIRED: Fill in the layers and allowed edges for your project,
# then merge this block into your profile TOML under [scorers.layer].

[scorers.layer]
# List directory names that define architectural layers, in bottom-to-top order.
# Each source file's layer is determined by its top-level directory prefix.
layers   = ["hal", "processing", "application"]  # EDIT: replace with your layer names

# Permitted dependency edges. Any include not in this list is a violation.
# Format: {{ from = "caller_layer", to = "callee_layer" }}
allowed  = [
  {{ from = "processing",   to = "hal" }},          # EDIT: set your allowed edges
  {{ from = "application",  to = "processing" }},
]

mandatory = {mandatory_str}   # blocks CONVERGED exit if any violation present
weight    = {weight_str}       # principle weight in composite compliance score

# Original principle description:
# {principle.description[:200].replace(chr(10), chr(10) + "# ")}
"""
    snippet_path.write_text(content, encoding="utf-8")
    log.info("Wrote layer config snippet: %s", snippet_path)


def _active_specialists_from_profile(profile_path: Optional[Path]) -> set[str] | None:
    """Return the active_specialists set from a profile TOML, or None if no profile given.

    Returns None (no filtering) when profile_path is None.
    Returns an empty set if the profile exists but declares no active_specialists,
    which will cause arch-build to error out rather than build everything.
    """
    if profile_path is None:
        return None
    if not profile_path.exists():
        console.print(f"[bold red]Error:[/] profile not found: {profile_path}")
        raise typer.Exit(1)
    try:
        import tomllib
        with open(profile_path, "rb") as f:
            raw = tomllib.load(f)
    except Exception as exc:
        console.print(f"[bold red]Error:[/] cannot read profile {profile_path}: {exc}")
        raise typer.Exit(1)
    specialists = raw.get("scorers", {}).get("crasis", {}).get("active_specialists", [])
    return set(specialists)


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
