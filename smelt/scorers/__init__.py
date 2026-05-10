"""Scorer registry — maps profile scorer names to scorer classes."""

from smelt.scorers.mypy_scorer import MypyScorer
from smelt.scorers.ruff_scorer import RuffScorer

SCORER_REGISTRY: dict[str, type] = {
    "ruff": RuffScorer,
    "mypy": MypyScorer,
}
