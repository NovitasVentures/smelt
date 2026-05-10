"""Scorer registry — maps profile scorer names to scorer classes."""

from smelt.scorers.clang_tidy_scorer import ClangTidyScorer
from smelt.scorers.misra_scorer import MisraScorer
from smelt.scorers.mypy_scorer import MypyScorer
from smelt.scorers.ruff_scorer import RuffScorer

SCORER_REGISTRY: dict[str, type] = {
    "ruff": RuffScorer,
    "mypy": MypyScorer,
    "misra": MisraScorer,
    "clang_tidy": ClangTidyScorer,
}
