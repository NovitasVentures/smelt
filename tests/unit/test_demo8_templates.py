"""Template rendering tests for the Demo 8 layer-parameterization fixes (Fix 1, Fix 2).

Verifies:
- The GTest CMake template renders SRC_DIRS from an arbitrary layer list without KeyError.
- The Phase 1 C++ test-gen system prompt names the Demo 8 layers (hal, monitoring,
  supervision) and omits the Demo 7 layers (processing, application) when given the
  Demo 8 layer list.
- Both templates still render their Demo 7 defaults unchanged when no layer list is given.
"""

from smelt.core.phase1 import _DEFAULT_CPP_LAYERS, _render_test_gen_system_cpp
from smelt.runners.gtest_runner import _CMAKE_TEMPLATE_CPP, _DEFAULT_SRC_DIRS


def test_cmake_template_renders_demo8_layers() -> None:
    rendered = _CMAKE_TEMPLATE_CPP.format(
        module_name="bms",
        src_dirs=" ".join(["hal", "monitoring", "supervision", "common"]),
    )
    assert "set(SRC_DIRS hal monitoring supervision common)" in rendered


def test_cmake_template_renders_demo7_defaults() -> None:
    rendered = _CMAKE_TEMPLATE_CPP.format(
        module_name="sensor",
        src_dirs=" ".join(_DEFAULT_SRC_DIRS),
    )
    assert "set(SRC_DIRS hal processing application common)" in rendered


def test_phase1_cpp_prompt_names_demo8_layers() -> None:
    prompt = _render_test_gen_system_cpp("bms", layers=["hal", "monitoring", "supervision"])
    assert "monitoring/" in prompt
    assert "supervision/" in prompt
    assert "processing/" not in prompt
    assert "application/" not in prompt


def test_phase1_cpp_prompt_defaults_to_demo7_layers() -> None:
    prompt = _render_test_gen_system_cpp("sensor", layers=None)
    assert _DEFAULT_CPP_LAYERS == ["hal", "processing", "application"]
    assert "processing/" in prompt
    assert "application/" in prompt
    assert "monitoring/" not in prompt
    assert "supervision/" not in prompt
