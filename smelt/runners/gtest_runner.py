"""GTest runner: cmake build + XML result parsing."""

import logging
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from smelt.runners.base import BaseRunner, Failure, RunResult

log = logging.getLogger(__name__)

_FAILURE_MESSAGE_CHARS = 4000


def _extract_failure_message(stderr: str) -> str:
    """Pull the actionable part of a cmake/compiler stderr blob.

    A raw tail slice of build output frequently keeps only trailing notes and
    warnings (e.g. a `[[nodiscard]]` note pointing at an unrelated frozen
    test) while the actual `error:` line that failed the build scrolled out
    of the slice — especially with parallel builds, where multiple
    translation units interleave their output. Reprompting the generator
    with that tail is reprompting with the wrong failure, which produces
    exactly the kind of oscillation (fix one thing, break another, forever)
    this scorer exists to prevent. Filtering for lines containing 'error:'
    (plus one line of context before/after, for a hint like the offending
    declaration) keeps the message on the actual defect regardless of where
    in a large log it appears.
    """
    lines = stderr.splitlines()
    error_line_indices = [i for i, line in enumerate(lines) if "error:" in line]
    if not error_line_indices:
        return stderr[-_FAILURE_MESSAGE_CHARS:]

    kept_indices: set[int] = set()
    for i in error_line_indices:
        kept_indices.update(range(max(0, i - 1), min(len(lines), i + 2)))

    message = "\n".join(lines[i] for i in sorted(kept_indices))
    if len(message) > _FAILURE_MESSAGE_CHARS:
        message = message[:_FAILURE_MESSAGE_CHARS] + "\n... (truncated)"
    return message

_CMAKE_TEMPLATE_C = """\
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

_CMAKE_TEMPLATE_CPP = """\
cmake_minimum_required(VERSION 3.14)
project({module_name}_tests CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/v1.14.0.zip
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# Collect implementation sources from named layer directories only.
# Never glob from the build directory root to avoid picking up CMake-generated files.
set(SRC_DIRS {src_dirs})
set(CPP_SOURCES "")
foreach(dir IN LISTS SRC_DIRS)
  if(EXISTS "${{CMAKE_CURRENT_SOURCE_DIR}}/${{dir}}")
    file(GLOB_RECURSE dir_sources "${{CMAKE_CURRENT_SOURCE_DIR}}/${{dir}}/*.cpp")
    list(APPEND CPP_SOURCES ${{dir_sources}})
  endif()
endforeach()
file(GLOB CPP_TESTS "${{CMAKE_CURRENT_SOURCE_DIR}}/test_*.cpp")

add_executable({module_name}_test ${{CPP_SOURCES}} ${{CPP_TESTS}})

target_link_libraries({module_name}_test PRIVATE GTest::gtest_main)
target_include_directories({module_name}_test PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})

include(GoogleTest)
gtest_discover_tests({module_name}_test)
"""


_DEFAULT_SRC_DIRS = ["hal", "processing", "application", "common"]


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

        has_cpp = any(code_path.rglob("*.cpp")) or any(code_path.rglob("*.h"))
        cmake_template = _CMAKE_TEMPLATE_CPP if has_cpp else _CMAKE_TEMPLATE_C
        if cmake_template is _CMAKE_TEMPLATE_CPP:
            src_dirs = config.get("src_dirs") or _DEFAULT_SRC_DIRS
            cmake_content = cmake_template.format(
                module_name=module_name, src_dirs=" ".join(src_dirs)
            )
        else:
            cmake_content = cmake_template.format(module_name=module_name)
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
                failures=[Failure("build_failure", _extract_failure_message(configure.stderr), "")],
            )

        # No --parallel: interleaved output from concurrent translation units
        # makes it unreliable to locate the failing one in the combined
        # stderr stream. A single-threaded build keeps each file's errors
        # contiguous, which _extract_failure_message relies on for the
        # one-line-of-context window around each `error:`.
        build = subprocess.run(
            ["cmake", "--build", str(build_dir)],
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            log.debug("cmake build failed:\n%s", build.stderr[-1000:])
            return RunResult(
                passed=0,
                failed=1,
                failures=[Failure("build_failure", _extract_failure_message(build.stderr), "")],
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
