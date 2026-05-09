"""Base classes for compliance scorers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Violation:
    """A single compliance violation."""

    file: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        """Return human-readable violation string."""
        return f"{self.rule}  line {self.line}  {self.message}"


@dataclass
class ScoreResult:
    """Result from a compliance scorer."""

    score: float
    violations: list[Violation] = field(default_factory=list)


class BaseScorer(ABC):
    """Interface all compliance scorers must implement."""

    name: str

    @abstractmethod
    def score(self, code_path: Path, config: dict) -> ScoreResult:
        """Score the code at code_path for compliance.

        Args:
            code_path: Directory containing generated source files.
            config: Profile config dict for this scorer.

        Returns:
            ScoreResult with normalized score [0.0, 1.0] and violation list.
        """
