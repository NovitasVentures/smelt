"""Configuration loading for Smelt."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SmeltConfig:
    """Runtime configuration assembled from smelt.toml and profile."""

    profile: str = "python_default"
    output_dir: Path = field(default_factory=lambda: Path("smelt_output"))
    log_level: str = "info"
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 8192
    compliance_threshold: float = 0.95
    goal_threshold: float = 1.00
    mutation_threshold: float = 0.70
    max_iterations: int = 20
    scorers: list[str] = field(default_factory=lambda: ["ruff"])
    runner: str = "pytest"


def load(config_path: Path | None = None) -> SmeltConfig:
    """Load SmeltConfig from smelt.toml, applying defaults for missing fields.

    Args:
        config_path: Explicit path to smelt.toml. Defaults to cwd/smelt.toml.

    Returns:
        Populated SmeltConfig.
    """
    cfg = SmeltConfig()

    path = config_path or Path("smelt.toml")
    if not path.exists():
        return cfg

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    smelt = raw.get("smelt", {})
    if "profile" in smelt:
        cfg.profile = smelt["profile"]
    if "output_dir" in smelt:
        cfg.output_dir = Path(smelt["output_dir"])
    if "log_level" in smelt:
        cfg.log_level = smelt["log_level"]

    llm = raw.get("llm", {})
    if "provider" in llm:
        cfg.provider = llm["provider"]
    if "model" in llm:
        cfg.model = llm["model"]
    if "max_tokens" in llm:
        cfg.max_tokens = llm["max_tokens"]

    thresholds = raw.get("thresholds", {})
    if "compliance" in thresholds:
        cfg.compliance_threshold = thresholds["compliance"]
    if "goal" in thresholds:
        cfg.goal_threshold = thresholds["goal"]
    if "mutation" in thresholds:
        cfg.mutation_threshold = thresholds["mutation"]

    iterations = raw.get("iterations", {})
    if "max" in iterations:
        cfg.max_iterations = iterations["max"]

    scorers = raw.get("scorers", {})
    if "active" in scorers:
        cfg.scorers = scorers["active"]

    runners = raw.get("runners", {})
    if "framework" in runners:
        cfg.runner = runners["framework"]

    return cfg
