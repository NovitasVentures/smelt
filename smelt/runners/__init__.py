"""Runner registry — maps profile runner names to runner classes."""

from smelt.runners.gtest_runner import GTestRunner
from smelt.runners.pytest_runner import PytestRunner

RUNNER_REGISTRY: dict[str, type] = {
    "pytest": PytestRunner,
    "gtest": GTestRunner,
}
