"""MISRA C:2012 compliance scorer using cppcheck --addon=misra."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from smelt.scorers.base import BaseScorer, ScoreResult, Violation

log = logging.getLogger(__name__)

# cppcheck integrated output: file:line:col: severity: message [misra-c2012-X.Y]
_LINE_RE_CPPCHECK = re.compile(
    r"^(.+?):(\d+):(\d+):\s+\w+:\s+(.+?)\s+\[misra-c2012-(\d+)\.(\d+)\]"
)
# misra.py direct output: [file:line] (severity) message [misra-c2012-X.Y]
_LINE_RE_MISRAPY = re.compile(
    r"^\[(.+?):(\d+)\]\s+\([^)]+\)\s+(.+?)\s+\[misra-c2012-(\d+)\.(\d+)\]"
)

# MISRA C:2012 severity classification.
# Source: MISRA C:2012 Guidelines (mandatory/required/advisory categories).
# Unlisted rules default to advisory.
_MANDATORY: frozenset[tuple[int, int]] = frozenset(
    [
        (1, 3),   # Undefined behavior shall not occur
        (2, 1),   # Unreachable code shall not occur
        (8, 1),   # Types shall be explicitly specified
        (13, 2),  # Full expression operand order shall not have side effects
        (13, 6),  # sizeof operand shall not have side effects
        (15, 3),  # goto target shall be in scope
        (17, 3),  # Implicit function declaration shall not occur
        (17, 6),  # Array declarator shall not have VLA notation
        (21, 17), # String functions: memory overlap undefined
        (21, 18), # strncpy size shall not be 0
        (21, 19), # Return value of localeconv shall not be used
        (21, 20), # Return value of setlocale shall not be used
    ]
)

_REQUIRED: frozenset[tuple[int, int]] = frozenset(
    [
        (1, 1),   # Source encoding
        (1, 2),   # Language extensions
        (2, 2),   # Dead code
        (2, 3),   # Unused type declaration
        (2, 4),   # Unused tag
        (2, 5),   # Unused macro
        (2, 6),   # Unused label
        (2, 7),   # Unused variable
        (3, 1),   # Nested C++ comments
        (3, 2),   # Line-splicing in // comments
        (4, 1),   # Trigraph usage
        (4, 2),   # Digraph usage
        (5, 1),   # External identifier uniqueness
        (5, 2),   # Inner scope identifier uniqueness
        (5, 3),   # Inner scope typedef uniqueness
        (5, 4),   # Macro identifier uniqueness
        (5, 5),   # Identifier uniqueness vs macro
        (5, 6),   # Typedef uniqueness
        (5, 7),   # Tag uniqueness
        (5, 8),   # External linkage identifier uniqueness
        (5, 9),   # Internal linkage identifier uniqueness
        (6, 1),   # Bit field type
        (6, 2),   # Single-bit named bit fields
        (7, 1),   # Octal constant
        (7, 2),   # Suffix on numeric literals
        (7, 3),   # Lowercase l suffix
        (7, 4),   # String literal modifiable
        (8, 2),   # Function type declaration in scope
        (8, 3),   # Parameter names match
        (8, 4),   # External object/function declaration
        (8, 5),   # External object/function single definition
        (8, 6),   # Identifier with external linkage one definition
        (8, 7),   # Identifier used in single file
        (8, 8),   # Static storage class specifier
        (8, 9),   # Object defined at block scope
        (8, 10),  # Inline function internal linkage
        (8, 11),  # Extern array size
        (8, 12),  # Implicit enum value
        (8, 14),  # restrict pointer qualifier
        (9, 1),   # Uninitialized value use
        (9, 2),   # Initializer braces
        (9, 3),   # Array initializer
        (9, 4),   # Initializer element
        (9, 5),   # Designated initializer
        (10, 1),  # Essential type operation
        (10, 2),  # Essential type expression
        (10, 3),  # Essential type assignment
        (10, 4),  # Essential type arithmetic
        (10, 5),  # Essential type cast
        (10, 6),  # Composite expression assigned to wider type
        (10, 7),  # Composite expression narrowing
        (10, 8),  # Composite expression cast
        (11, 1),  # Function pointer conversion
        (11, 2),  # Pointer conversion to incompatible type
        (11, 3),  # Cast from pointer to non-integer
        (11, 4),  # Conversion from pointer to integer
        (11, 5),  # void pointer conversion
        (11, 6),  # Cast from integer to pointer
        (11, 7),  # Pointer to non-arithmetic conversion
        (11, 8),  # Cast discards const/volatile
        (11, 9),  # NULL not zero integer constant
        (12, 1),  # Precedence of operators
        (12, 2),  # Shift operand value
        (12, 3),  # Comma operator
        (12, 4),  # Constant expression evaluation
        (13, 1),  # Initializer list side effects
        (13, 3),  # Full expression with increment/decrement
        (13, 4),  # Assignment result used
        (13, 5),  # Right-hand operand of &&/|| with persistent side effects
        (14, 1),  # Loop counter float
        (14, 2),  # for loop compliance
        (14, 3),  # Controlling expression invariant
        (14, 4),  # Controlling expression bool
        (15, 1),  # goto usage
        (15, 2),  # goto backward
        (15, 4),  # Single break per loop
        (15, 5),  # Single exit point per function
        (15, 6),  # Single statement per if/else/loop body
        (15, 7),  # if-else termination
        (16, 1),  # switch-case compliance
        (16, 2),  # switch expression
        (16, 3),  # switch case unconditional break
        (16, 4),  # switch default clause
        (16, 5),  # switch with no case
        (16, 6),  # switch single clause
        (16, 7),  # switch expression bool
        (17, 1),  # stdarg.h functions
        (17, 2),  # Recursive functions
        (17, 4),  # Function pointer address
        (17, 5),  # Function parameter count
        (17, 7),  # Return value of non-void function
        (17, 8),  # Function parameter modification
        (18, 1),  # Pointer arithmetic
        (18, 2),  # Pointer subtraction
        (18, 3),  # Pointer comparison
        (18, 5),  # Nested pointer declaration depth
        (18, 6),  # Address of automatic storage object
        (18, 7),  # Flexible array member
        (18, 8),  # Variable-length array type
        (19, 1),  # Object overlap
        (20, 1),  # #include first
        (20, 2),  # Header file name
        (20, 3),  # #include followed by comment
        (20, 4),  # Macro naming conflict
        (20, 5),  # #undef
        (20, 6),  # Token pasting
        (20, 7),  # Macro parameter parentheses
        (20, 8),  # #if controlling expression
        (20, 9),  # Predefined macro not defined
        (20, 10), # Stringize operator
        (20, 11), # Macro parameter stringize
        (20, 12), # Macro parameter token pasting
        (20, 13), # Terminating # in #define
        (20, 14), # #elif/#else/#endif pairing
        (21, 1),  # Macro definition reserved
        (21, 2),  # Reserved identifier definition
        (21, 3),  # Dynamic memory allocation
        (21, 4),  # setjmp/longjmp
        (21, 5),  # signal.h
        (21, 6),  # Standard I/O
        (21, 7),  # atoi/atof/atol/atoll
        (21, 8),  # Library termination functions
        (21, 9),  # bsearch/qsort
        (21, 10), # Time/date functions
        (21, 11), # tgmath.h
        (21, 12), # fenv exception functions
        (21, 13), # isalpha etc. with non-uchar
        (21, 14), # memcmp with non-char types
        (21, 15), # memcpy/memmove/memcmp pointer types
        (21, 16), # memcmp compared value
        (22, 1),  # Resource acquire/release
        (22, 2),  # Heap memory free
        (22, 3),  # Same file multiple open
        (22, 4),  # Write to read-only file
        (22, 5),  # FILE object dereference
        (22, 6),  # fclose'd file use
        (22, 7),  # errno comparison
        (22, 8),  # errno setting before call
        (22, 9),  # errno checking after call
        (22, 10), # strtol/strtod errno checking
    ]
)


def _severity(major: int, minor: int) -> str:
    key = (major, minor)
    if key in _MANDATORY:
        return "mandatory"
    if key in _REQUIRED:
        return "required"
    return "advisory"


class MisraScorer(BaseScorer):
    """MISRA C:2012 compliance scorer using cppcheck --addon=misra."""

    name = "misra"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        if not shutil.which("cppcheck"):
            log.warning("MisraScorer: cppcheck not found on PATH — returning score=1.0")
            return ScoreResult(score=1.0, violations=[])

        violations = self._run_cppcheck(code_path, config)
        return ScoreResult(score=self._calculate(violations, config), violations=violations)

    def _run_cppcheck(self, code_path: Path, config: dict) -> list[Violation]:
        std = config.get("std", "c99")

        # Step 1: cppcheck --dump to generate .dump files for each .c file
        c_files = [str(f) for f in code_path.rglob("*.c") if "_build" not in f.parts]
        if not c_files:
            return []

        dump_result = subprocess.run(
            ["cppcheck", "--dump", "--quiet", "--error-exitcode=0", f"--std={std}"] + c_files,
            capture_output=True, text=True,
        )

        # Step 2: run misra.py on the generated .dump files
        dump_files = [f + ".dump" for f in c_files if Path(f + ".dump").exists()]
        if not dump_files:
            log.warning("MisraScorer: no .dump files generated — running cppcheck --enable=all as fallback")
            fallback = subprocess.run(
                ["cppcheck", "--enable=all", "--error-exitcode=0", "--quiet", str(code_path)],
                capture_output=True, text=True,
            )
            return self._parse_general(fallback.stderr + fallback.stdout)

        misra_py = self._find_misra_py()
        rule_texts_args = self._rule_texts_args(config)

        misra_result = subprocess.run(
            ["python3", misra_py] + rule_texts_args + dump_files,
            capture_output=True, text=True,
        )
        output = misra_result.stderr + misra_result.stdout

        # Clean up dump files
        for df in dump_files:
            try:
                Path(df).unlink()
            except OSError:
                pass

        violations = self._parse(output)
        return violations

    @staticmethod
    def _find_misra_py() -> str:
        """Return path to misra.py addon."""
        candidates = [
            "/usr/lib/x86_64-linux-gnu/cppcheck/addons/misra.py",
            "/usr/share/cppcheck/addons/misra.py",
            "/usr/lib/cppcheck/addons/misra.py",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        # Last resort: search
        result = subprocess.run(["find", "/usr", "-name", "misra.py", "-path", "*/cppcheck/*"],
                                capture_output=True, text=True)
        found = result.stdout.strip().splitlines()
        if found:
            return found[0]
        raise RuntimeError("misra.py not found; install cppcheck with addon support")

    @staticmethod
    def _rule_texts_args(config: dict) -> list[str]:
        """Return misra.py args for rule texts and suppressed rules."""
        args: list[str] = []

        # --rule-texts
        explicit = config.get("rule_texts")
        if explicit and Path(explicit).exists():
            args.append(f"--rule-texts={explicit}")
        else:
            for candidate in (
                Path.cwd() / "misra_rules.txt",
                Path(__file__).parent.parent.parent / "misra_rules.txt",
            ):
                if candidate.exists():
                    args.append(f"--rule-texts={candidate}")
                    break
        # Violations are still tagged with [misra-c2012-X.Y] even without rule texts

        # --suppress-rules
        suppress = config.get("suppress_rules")
        if suppress:
            args.append(f"--suppress-rules={suppress}")

        return args

    def _parse(self, output: str) -> list[Violation]:
        violations: list[Violation] = []
        for line in output.splitlines():
            # Try cppcheck integrated format first, then misra.py direct format
            m = _LINE_RE_CPPCHECK.match(line)
            if m:
                file_, lineno, _col, message, major_s, minor_s = m.groups()
            else:
                m = _LINE_RE_MISRAPY.match(line)
                if m:
                    file_, lineno, message, major_s, minor_s = m.groups()
                else:
                    continue
            major, minor = int(major_s), int(minor_s)
            sev = _severity(major, minor)
            rule_id = f"MISRA-C2012-{major}.{minor} [{sev}]"
            violations.append(
                Violation(
                    file=file_,
                    line=int(lineno),
                    rule=rule_id,
                    message=message.strip(),
                )
            )
        return violations

    def _parse_general(self, output: str) -> list[Violation]:
        """Parse plain cppcheck output as advisory violations."""
        pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+\w+:\s+(.+?)(?:\s+\[(.+)\])?$")
        violations: list[Violation] = []
        for line in output.splitlines():
            m = pattern.match(line)
            if not m:
                continue
            file_, lineno, _col, message, rule = m.groups()
            violations.append(
                Violation(
                    file=file_,
                    line=int(lineno),
                    rule=rule or "cppcheck [advisory]",
                    message=message.strip(),
                )
            )
        return violations

    def _calculate(self, violations: list[Violation], config: dict) -> float:
        non_advisory = [v for v in violations if "[advisory]" not in v.rule]
        return max(0.0, 1.0 - len(non_advisory) / 5.0)
