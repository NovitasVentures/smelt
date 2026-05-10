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
    scorer_weights: dict[str, float] = field(default_factory=dict)
    scorer_config: dict[str, dict] = field(default_factory=dict)
    runner: str = "pytest"
    language: str = "python"
    mutation_engine: str = "mutmut"


_PROFILES_DIR = Path(__file__).parent / "profiles"


def _load_profile(profile: str | Path) -> dict:
    """Resolve a profile name or path and return its raw TOML dict.

    If profile is an absolute path or a relative path containing separators,
    resolve it from cwd. Otherwise treat it as a bare name and look it up in
    the bundled profiles directory.
    """
    path = Path(profile)
    if path.is_absolute() or path.parent != Path("."):
        # Explicit path — resolve relative to cwd
        path = path.resolve()
    else:
        # Bare name like "python_default" → bundled profiles dir
        path = _PROFILES_DIR / f"{path.stem}.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _apply_profile(cfg: SmeltConfig, raw: dict) -> None:
    """Apply a profile TOML dict to cfg in-place."""
    meta = raw.get("meta", {})
    if "language" in meta:
        cfg.language = meta["language"]

    mutator = raw.get("mutator", {})
    if "engine" in mutator:
        cfg.mutation_engine = mutator["engine"]

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
    if "weights" in scorers:
        cfg.scorer_weights = {k: float(v) for k, v in scorers["weights"].items()}
    for key, val in scorers.items():
        if key not in ("active", "weights") and isinstance(val, dict):
            cfg.scorer_config[key] = val

    runners = raw.get("runners", {})
    if "framework" in runners:
        cfg.runner = runners["framework"]


def load(config_path: Path | None = None, profile_path: Path | None = None) -> SmeltConfig:
    """Load SmeltConfig from a profile TOML and smelt.toml, applying defaults for missing fields.

    When profile_path is given explicitly (e.g. via --profile), it takes full precedence
    over smelt.toml for all profile-specific fields (scorers, runner, language, thresholds).
    smelt.toml still provides LLM settings and output directory overrides.

    Args:
        config_path: Explicit path to smelt.toml. Defaults to cwd/smelt.toml.
        profile_path: Explicit path to a profile TOML. Overrides [smelt] profile from smelt.toml.

    Returns:
        Populated SmeltConfig.
    """
    cfg = SmeltConfig()

    path = config_path or Path("smelt.toml")
    raw: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    smelt_section = raw.get("smelt", {})

    if profile_path is not None:
        # Explicit --profile wins: apply it, then only overlay LLM/output settings from smelt.toml
        profile_raw = _load_profile(profile_path)
        _apply_profile(cfg, profile_raw)

        if "output_dir" in smelt_section:
            cfg.output_dir = Path(smelt_section["output_dir"])
        if "log_level" in smelt_section:
            cfg.log_level = smelt_section["log_level"]
    else:
        # No explicit profile: apply profile named in smelt.toml, then let smelt.toml override
        effective_profile = smelt_section.get("profile", cfg.profile)
        profile_raw = _load_profile(effective_profile)
        _apply_profile(cfg, profile_raw)

        if "profile" in smelt_section:
            cfg.profile = smelt_section["profile"]
        if "output_dir" in smelt_section:
            cfg.output_dir = Path(smelt_section["output_dir"])
        if "log_level" in smelt_section:
            cfg.log_level = smelt_section["log_level"]

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
        if "weights" in scorers:
            cfg.scorer_weights = {k: float(v) for k, v in scorers["weights"].items()}
        for key, val in scorers.items():
            if key not in ("active", "weights") and isinstance(val, dict):
                cfg.scorer_config[key] = val

        runners = raw.get("runners", {})
        if "framework" in runners:
            cfg.runner = runners["framework"]

    # LLM settings always come from smelt.toml (not profile-specific)
    llm = raw.get("llm", {})
    if "provider" in llm:
        cfg.provider = llm["provider"]
    if "model" in llm:
        cfg.model = llm["model"]
    if "max_tokens" in llm:
        cfg.max_tokens = llm["max_tokens"]

    return cfg
