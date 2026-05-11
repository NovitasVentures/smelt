"""Generates Crasis YAML spec files from extracted architectural principles."""

import logging
from pathlib import Path

import yaml

from smelt.arch.extractor import ArchitecturalPrinciple

log = logging.getLogger(__name__)

CRASIS_SPEC_VERSION = "v1"
DEFAULT_TRAINING_VOLUME = 3000
DEFAULT_MIN_ACCURACY = 0.93
DEFAULT_MAX_MODEL_SIZE_MB = 20
DEFAULT_MAX_INFERENCE_MS = 10


def generate_spec(principle: ArchitecturalPrinciple, output_dir: Path) -> Path:
    """Write a Crasis YAML spec file for one architectural principle.

    Args:
        principle: Extracted architectural principle.
        output_dir: Directory to write the spec file into.

    Returns:
        Path to the written YAML file.
    """
    spec: dict = {
        "crasis_spec": CRASIS_SPEC_VERSION,
        "name": principle.name,
        "description": principle.description,
        "task": {
            "type": "binary_classification",
            "trigger": principle.trigger,
            "ignore": principle.ignore,
        },
        "constraints": {
            "max_model_size_mb": DEFAULT_MAX_MODEL_SIZE_MB,
            "max_inference_ms": DEFAULT_MAX_INFERENCE_MS,
            "connectivity": "none",
        },
        "quality": {
            "min_accuracy": DEFAULT_MIN_ACCURACY,
            "eval_on": principle.eval_cases,
        },
        "training": {
            "strategy": "synthetic",
            "volume": DEFAULT_TRAINING_VOLUME,
        },
        # _smelt_meta is a non-standard extension key. Crasis ignores unknown
        # top-level keys beginning with "_". This carries Smelt-specific metadata
        # (chunk level, weight, mandatory flag) through the spec file so that
        # smelt arch-build can write it into the specialist's crasis_meta.json sidecar,
        # and CrasisScorer can read it back at load time.
        "_smelt_meta": {
            "source_section": principle.source_section,
            "chunk_level": principle.chunk_level,
            "weight": principle.weight,
            "mandatory": principle.mandatory,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{principle.name}.yaml"
    output_path.write_text(
        yaml.dump(spec, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("Wrote spec: %s", output_path)
    return output_path


def generate_all_specs(
    principles: list[ArchitecturalPrinciple],
    output_dir: Path,
) -> list[Path]:
    """Write Crasis YAML specs for all principles.

    Args:
        principles: List of extracted architectural principles.
        output_dir: Directory to write spec files into. Created if absent.

    Returns:
        List of paths to written spec files, in the same order as principles.
    """
    return [generate_spec(p, output_dir) for p in principles]
