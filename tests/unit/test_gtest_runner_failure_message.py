"""Tests for GTestRunner._extract_failure_message.

A raw tail slice of cmake/compiler stderr frequently keeps only trailing
notes and warnings while the actual `error:` line scrolls out of the slice,
especially with multi-file builds. This reprompts the generator with the
wrong failure detail, producing oscillation instead of convergence. These
tests pin the fix: filter for lines containing 'error:' with one line of
surrounding context, regardless of where in the log they appear.
"""

from smelt.runners.gtest_runner import _FAILURE_MESSAGE_CHARS, _extract_failure_message


def test_extracts_error_buried_before_trailing_warnings():
    stderr = (
        "hal/cell_sensor.cpp: In constructor 'CellSensor::CellSensor()':\n"
        "hal/cell_sensor.cpp:5:10: error: 'size_t' was not declared in this scope\n"
        "    5 |     for (size_t i = 0; i < cells_.size(); ++i) {\n"
        "      |          ^~~~~~\n"
        + ("padding line noise\n" * 200)
        + "test_implementation.cpp:616:32: warning: ignoring return value, "
        "declared with attribute 'nodiscard' [-Wunused-result]\n"
        "battery_supervisor.h:15:29: note: declared here\n"
        "gmake: *** [Makefile:136: all] Error 2\n"
    )

    message = _extract_failure_message(stderr)

    assert "error: 'size_t' was not declared" in message


def test_no_error_line_falls_back_to_tail():
    stderr = "linker output with no explicit 'error:' token\n" * 5 + "undefined reference to `foo'"

    message = _extract_failure_message(stderr)

    assert message == stderr[-_FAILURE_MESSAGE_CHARS:]
    assert "undefined reference to `foo'" in message


def test_multiple_errors_all_kept_up_to_budget():
    stderr = (
        "file_a.cpp:1:1: error: first problem\n"
        "file_b.cpp:2:2: error: second problem\n"
    )

    message = _extract_failure_message(stderr)

    assert "first problem" in message
    assert "second problem" in message


def test_very_long_error_context_is_capped():
    stderr = "\n".join(f"line {i}: error: repeated" for i in range(2000))

    message = _extract_failure_message(stderr)

    assert len(message) <= _FAILURE_MESSAGE_CHARS + len("\n... (truncated)")
    assert message.endswith("... (truncated)")
