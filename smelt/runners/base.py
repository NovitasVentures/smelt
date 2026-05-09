"""Base classes for test runners."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Failure:
    """A single test failure."""

    test_name: str
    message: str
    traceback: str

    def __str__(self) -> str:
        """Return human-readable failure string."""
        return f"{self.test_name}\n  {self.message}"


@dataclass
class RunResult:
    """Result from a test runner."""

    passed: int
    failed: int
    failures: list[Failure] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of tests collected."""
        return self.passed + self.failed

    @property
    def goal_score(self) -> float:
        """Fraction of tests passing, 0.0 if no tests collected."""
        if self.total == 0:
            return 0.0
        return self.passed / self.total


class BaseRunner(ABC):
    """Interface all test runners must implement."""

    name: str

    @abstractmethod
    def run(self, test_path: Path, code_path: Path, config: dict) -> RunResult:
        """Execute the test suite.

        Args:
            test_path: Path to the frozen test file or directory.
            code_path: Directory containing generated implementation.
            config: Profile config dict for this runner.

        Returns:
            RunResult with pass/fail counts and failure detail.
        """
