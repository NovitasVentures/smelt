"""GTest runner: cmake build + XML result parsing."""

import logging
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from smelt.runners.base import BaseRunner, Failure, RunResult

log = logging.getLogger(__name__)

_CMAKE_TEMPLATE = """\
cmake_minimum_required(VERSION 3.14)
project({module_name}_tests C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/v1.14.0.zip
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

file(GLOB C_SOURCES "*.c")
file(GLOB CPP_TESTS "test_*.cpp")

add_executable({module_name}_test ${{C_SOURCES}} ${{CPP_TESTS}})

target_link_libraries({module_name}_test PRIVATE GTest::gtest_main)
target_include_directories({module_name}_test PRIVATE .)

set_source_files_properties(${{C_SOURCES}} PROPERTIES
    COMPILE_FLAGS "-Wall -Wextra -Wpedantic"
)

include(GoogleTest)
gtest_discover_tests({module_name}_test)
"""


def _find_binary(build_dir: Path, name: str) -> Path | None:
    for candidate in build_dir.rglob(name):
        if candidate.is_file() and not candidate.suffix:
            return candidate
    return None


def _parse_xml(xml_path: Path) -> RunResult:
    if not xml_path.exists():
        return RunResult(
            passed=0,
            failed=1,
            failures=[Failure("xml_not_found", "GTest XML output was not generated", "")],
        )

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        return RunResult(
            passed=0,
            failed=1,
            failures=[Failure("xml_parse_error", str(exc), "")],
        )

    root = tree.getroot()
    passed = 0
    failed = 0
    failures: list[Failure] = []

    for testcase in root.iter("testcase"):
        failure_el = testcase.find("failure")
        suite = testcase.get("classname", "")
        name = testcase.get("name", "")
        test_name = f"{suite}.{name}" if suite else name
        if failure_el is not None:
            failed += 1
            message = (failure_el.get("message") or "")[:400]
            traceback = (failure_el.text or "")[:600]
            failures.append(Failure(test_name=test_name, message=message, traceback=traceback))
        else:
            passed += 1

    return RunResult(passed=passed, failed=failed, failures=failures)


class GTestRunner(BaseRunner):
    """Build with cmake, run GTest binary, parse XML results."""

    name = "gtest"

    def run(self, test_path: Path, code_path: Path, config: dict) -> RunResult:
        if not shutil.which("cmake"):
            raise RuntimeError(
                "GTestRunner requires cmake on PATH. "
                "Install cmake (e.g. apt install cmake) and retry."
            )

        module_name = config.get("module_name", "implementation")
        build_dir = code_path / "_build"
        xml_path = code_path / "test_results.xml"

        cmake_content = _CMAKE_TEMPLATE.format(module_name=module_name)
        (code_path / "CMakeLists.txt").write_text(cmake_content)

        # Copy frozen test into code dir so cmake finds it
        dest = code_path / test_path.name
        if not dest.exists() or dest.resolve() != test_path.resolve():
            shutil.copy(test_path, dest)

        configure = subprocess.run(
            ["cmake", "-S", str(code_path), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Debug"],
            capture_output=True,
            text=True,
        )
        if configure.returncode != 0:
            log.debug("cmake configure failed:\n%s", configure.stderr[-1000:])
            return RunResult(
                passed=0,
                failed=1,
                failures=[Failure("build_failure", configure.stderr[-500:], "")],
            )

        build = subprocess.run(
            ["cmake", "--build", str(build_dir), "--parallel"],
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            log.debug("cmake build failed:\n%s", build.stderr[-1000:])
            return RunResult(
                passed=0,
                failed=1,
                failures=[Failure("build_failure", build.stderr[-500:], "")],
            )

        binary = _find_binary(build_dir, f"{module_name}_test")
        if binary is None:
            return RunResult(
                passed=0,
                failed=1,
                failures=[Failure("binary_not_found", f"{module_name}_test binary not found in build dir", "")],
            )

        subprocess.run(
            [str(binary), f"--gtest_output=xml:{xml_path}"],
            capture_output=True,
            text=True,
        )

        return _parse_xml(xml_path)
