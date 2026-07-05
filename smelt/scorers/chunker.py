"""Code chunker for Crasis architectural scoring."""

import ast
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_TOKENS = 512
_TOKENS_PER_CHAR = 4  # characters per token (approximation)
_MAX_CHARS = _MAX_TOKENS * _TOKENS_PER_CHAR


class ChunkLevel(Enum):
    FUNCTION = "function"
    CLASS = "class"
    FILE = "file"
    MODULE = "module"


@dataclass
class CodeChunk:
    text: str
    location: str    # "filepath:start_line-end_line"
    signature: str   # "ClassName.method_name" or "function_name" or filename
    level: ChunkLevel
    start_line: int  # for Violation.line mapping
    mutates_self: bool = True  # False only when AST confirms no self.* mutation


def chunk_code(
    source: str,
    level: ChunkLevel,
    filepath: str = "<unknown>",
    is_cpp: bool = False,
) -> list[CodeChunk]:
    """Chunk source into CodeChunk objects at the requested granularity.

    For MODULE level, filepath is treated as a directory path and source is ignored.
    is_cpp=True enables C++ regex-based function chunking instead of Python AST.
    """
    if level == ChunkLevel.MODULE:
        return _chunk_module(filepath)
    if level == ChunkLevel.FILE:
        return _chunk_file(source, filepath)
    if is_cpp:
        return _chunk_cpp_functions(source, filepath)
    if level == ChunkLevel.CLASS:
        return _chunk_classes(source, filepath)
    return _chunk_functions(source, filepath)


def _chunk_cpp_functions(source: str, filepath: str) -> list[CodeChunk]:
    """Chunk C++ source into one CodeChunk per function definition.

    Uses brace-matching to extract function bodies. Falls back to FILE chunk
    if no functions are found (e.g., header-only files with no bodies).
    """
    lines = source.splitlines(keepends=True)
    chunks: list[CodeChunk] = []

    # Matches: [ReturnType] [ClassName::]FunctionName(...) [const/noexcept] [-> TrailingType] {
    # Handles both traditional (ErrorCode foo()) and trailing-return (auto foo() -> ErrorCode).
    # Anchored at start of line to skip forward declarations.
    func_header = re.compile(
        r"^(?![ \t]*//)(?P<decl>[^\n{};#]+(?:\w+\s*::\s*)?\w+\s*\([^)]*\)"
        r"(?:\s*(?:const|override|noexcept|final))*"
        r"(?:\s*->\s*[^\n{};]+)?)\s*\{",
        re.MULTILINE,
    )

    for match in func_header.finditer(source):
        brace_start = match.end() - 1  # position of '{'
        depth = 0
        pos = brace_start
        while pos < len(source):
            if source[pos] == "{":
                depth += 1
            elif source[pos] == "}":
                depth -= 1
                if depth == 0:
                    break
            pos += 1

        func_text = source[match.start():pos + 1]
        start_line = source[:match.start()].count("\n") + 1
        end_line = source[:pos + 1].count("\n") + 1

        # Extract a readable signature: everything up to the opening brace
        signature = match.group("decl").strip().replace("\n", " ")
        signature = re.sub(r"\s+", " ", signature)

        # Skip control-flow statements that the regex may mis-match as function headers:
        # for(...), while(...), if(...), switch(...), catch(...), else if(...).
        # These never have a return type before them.
        _CONTROL_FLOW = re.compile(
            r"^(for|while|if|else\s+if|switch|catch|do)\s*\("
        )
        if _CONTROL_FLOW.match(signature):
            continue

        # Skip member initializer lists: lines starting with ":" like ": member_(val)"
        if signature.startswith(":"):
            continue

        # Skip constructors and destructors — they have no return type or error codes.
        # A constructor/destructor signature has the form "ClassName::ClassName(" or
        # "ClassName::~ClassName(" — no return type token before the class name.
        # Detect by checking if the token before "::" is a single word with no preceding type.
        ctor_match = re.match(r"^(\w+)\s*::\s*~?\1\s*\(", signature)
        if ctor_match:
            continue

        location = f"{filepath}:{start_line}-{end_line}"

        if len(func_text) > _MAX_CHARS:
            sub = _split_large_chunk(func_text, location, signature, filepath, start_line, level=ChunkLevel.FUNCTION)
            chunks.extend(sub)
        else:
            chunks.append(CodeChunk(
                text=func_text,
                location=location,
                signature=signature,
                level=ChunkLevel.FUNCTION,
                start_line=start_line,
            ))

    if not chunks:
        return _chunk_file(source, filepath)

    return chunks


def _chunk_functions(source: str, filepath: str) -> list[CodeChunk]:
    """One chunk per top-level function or method. Includes enclosing class signature."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        log.warning("Syntax error in %s — falling back to FILE chunk", filepath)
        return _chunk_file(source, filepath)

    lines = source.splitlines(keepends=True)
    chunks: list[CodeChunk] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        start = node.lineno - 1  # 0-indexed
        end = node.end_lineno    # exclusive (1-indexed end = exclusive 0-indexed)
        func_lines = lines[start:end]
        func_text = "".join(func_lines)

        # Find enclosing class if any
        class_name = _enclosing_class(tree, node)
        if class_name:
            signature = f"{class_name}.{node.name}"
            # Prepend the class declaration line for context
            class_node = _find_class_node(tree, class_name)
            if class_node:
                class_decl = lines[class_node.lineno - 1].rstrip()
                func_text = f"{class_decl}\n    ...\n{func_text}"
        else:
            signature = node.name

        chunk_text = func_text
        location = f"{filepath}:{node.lineno}-{node.end_lineno}"
        does_mutate = _mutates_self(node)

        if len(chunk_text) > _MAX_CHARS:
            sub = _split_large_chunk(chunk_text, location, signature, filepath, node.lineno, level=ChunkLevel.FUNCTION)
            for s in sub:
                s.mutates_self = does_mutate
            chunks.extend(sub)
        else:
            chunks.append(CodeChunk(
                text=chunk_text,
                location=location,
                signature=signature,
                level=ChunkLevel.FUNCTION,
                start_line=node.lineno,
                mutates_self=does_mutate,
            ))

    if not chunks:
        return _chunk_file(source, filepath)

    return chunks


def _chunk_classes(source: str, filepath: str) -> list[CodeChunk]:
    """One chunk per class, including all method bodies."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        log.warning("Syntax error in %s — falling back to FILE chunk", filepath)
        return _chunk_file(source, filepath)

    lines = source.splitlines(keepends=True)
    chunks: list[CodeChunk] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        start = node.lineno - 1
        end = node.end_lineno
        class_text = "".join(lines[start:end])
        location = f"{filepath}:{node.lineno}-{node.end_lineno}"

        if len(class_text) > _MAX_CHARS:
            sub = _split_large_chunk(class_text, location, node.name, filepath, node.lineno, level=ChunkLevel.CLASS)
            chunks.extend(sub)
        else:
            chunks.append(CodeChunk(
                text=class_text,
                location=location,
                signature=node.name,
                level=ChunkLevel.CLASS,
                start_line=node.lineno,
            ))

    if not chunks:
        return _chunk_file(source, filepath)

    return chunks


def _chunk_file(source: str, filepath: str) -> list[CodeChunk]:
    """Whole file as a single chunk."""
    line_count = source.count("\n") + 1

    if len(source) > _MAX_CHARS:
        return _split_large_chunk(source, f"{filepath}:1-{line_count}", Path(filepath).name, filepath, 1, level=ChunkLevel.FILE)

    return [CodeChunk(
        text=source,
        location=f"{filepath}:1-{line_count}",
        signature=Path(filepath).name,
        level=ChunkLevel.FILE,
        start_line=1,
    )]


def _chunk_module(directory: str) -> list[CodeChunk]:
    """Concatenate all .py files in a directory into one chunk per file, with separators."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        log.warning("MODULE chunk: %s is not a directory", directory)
        return []

    py_files = sorted(dir_path.glob("*.py"))
    if not py_files:
        log.warning("MODULE chunk: no .py files found in %s", directory)
        return []

    parts: list[str] = []
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Cannot read %s: %s", py_file, exc)
            continue
        parts.append(f"# --- {py_file} ---\n{content}")

    combined = "\n".join(parts)
    line_count = combined.count("\n") + 1
    location = f"{directory}:1-{line_count}"

    if len(combined) > _MAX_CHARS:
        return _split_large_chunk(combined, location, Path(directory).name, directory, 1, level=ChunkLevel.MODULE)

    return [CodeChunk(
        text=combined,
        location=location,
        signature=Path(directory).name,
        level=ChunkLevel.MODULE,
        start_line=1,
    )]


def _split_large_chunk(
    text: str,
    location: str,
    signature: str,
    filepath: str,
    base_line: int,
    level: ChunkLevel,
) -> list[CodeChunk]:
    """Split oversized text into ~512-token sub-chunks at line boundaries."""
    lines = text.splitlines(keepends=True)
    chunks: list[CodeChunk] = []
    current_lines: list[str] = []
    current_chars = 0
    chunk_start = base_line

    for i, line in enumerate(lines):
        if current_chars + len(line) > _MAX_CHARS and current_lines:
            chunk_text = "".join(current_lines)
            chunk_end = chunk_start + len(current_lines) - 1
            chunks.append(CodeChunk(
                text=chunk_text,
                location=f"{filepath}:{chunk_start}-{chunk_end}",
                signature=f"{signature}[part{len(chunks)+1}]",
                level=level,
                start_line=chunk_start,
            ))
            chunk_start = base_line + i
            current_lines = []
            current_chars = 0

        current_lines.append(line)
        current_chars += len(line)

    if current_lines:
        chunk_text = "".join(current_lines)
        chunk_end = chunk_start + len(current_lines) - 1
        chunks.append(CodeChunk(
            text=chunk_text,
            location=f"{filepath}:{chunk_start}-{chunk_end}",
            signature=f"{signature}[part{len(chunks)+1}]" if chunks else signature,
            level=level,
            start_line=chunk_start,
        ))

    return chunks


_CPP_KEYWORDS_AND_TYPES = frozenset({
    "if", "else", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "goto", "sizeof", "static_cast", "dynamic_cast",
    "const_cast", "reinterpret_cast", "new", "delete", "this", "nullptr",
    "true", "false", "void", "bool", "char", "int", "float", "double",
    "long", "short", "unsigned", "signed", "auto", "const", "static",
    "volatile", "constexpr", "struct", "class", "enum", "namespace",
    "using", "typedef", "template", "typename", "public", "private",
    "protected", "virtual", "override", "final", "explicit", "friend",
    "inline", "extern", "noexcept", "throw", "try", "catch",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t", "size_t",
})


def redact_identifiers(text: str) -> str:
    """Replace class names, function names, and member identifiers with generic
    placeholders, stable within a single chunk but uninformative across chunks.

    Intended for training/inference of specialists that must reason about
    control-flow and data-flow shape without learning a shortcut keyed to a
    specific function or member name (e.g. "any chunk containing the literal
    token 'update_cell' is clean"). Preserves C++ keywords, built-in types,
    literals, operators, and enum-qualified values (FaultType::NONE stays
    intact — only the bare identifier immediately before '::' in a
    Class::method(...) declaration and trailing-underscore member names are
    replaced).

    Replacement is deterministic per-chunk: the same source identifier always
    maps to the same placeholder within one call, so structural relationships
    (the same member appearing twice) are preserved for the classifier.
    """
    class_map: dict[str, str] = {}
    func_map: dict[str, str] = {}
    member_map: dict[str, str] = {}

    # ClassName::methodName( — redact both sides of the qualifier.
    def _redact_decl(match: re.Match) -> str:
        cls, func = match.group(1), match.group(2)
        if cls not in class_map:
            class_map[cls] = f"CLASS_{len(class_map)}"
        if func not in func_map:
            func_map[func] = f"FUNC_{len(func_map)}"
        return f"{class_map[cls]}::{func_map[func]}("

    text = re.sub(r"\b(\w+)\s*::\s*(\w+)\s*\(", _redact_decl, text)

    # Bare function name (no ClassName::) immediately followed by '(' at the
    # start of a declaration — only rewrite if not already a known keyword,
    # not a call to a previously-redacted function/class, and not immediately
    # preceded by '::' (already handled above).
    def _redact_bare_func(match: re.Match) -> str:
        name = match.group(1)
        if name in _CPP_KEYWORDS_AND_TYPES or name in class_map or name in member_map:
            return match.group(0)
        if name not in func_map:
            func_map[name] = f"FUNC_{len(func_map)}"
        return f"{func_map[name]}("

    text = re.sub(r"(?<!::)\b(\w+)\s*\(", _redact_bare_func, text)

    # Trailing-underscore member identifiers (faults_, last_mv_, valid_, ...),
    # excluding ALL_CAPS constants (CELL_COUNT) which are not member state.
    def _redact_member(match: re.Match) -> str:
        name = match.group(0)
        if name.isupper():
            return name
        if name not in member_map:
            member_map[name] = f"MEMBER_{len(member_map)}"
        return member_map[name]

    text = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*_\b", _redact_member, text)

    return text


def _mutates_self(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function body contains any self.* mutation.

    Detects: self.attr = ..., self.collection.append/extend/add/insert/update/
    remove/discard/pop/popleft/clear/setdefault(...), del self.attr[...].
    Does NOT fire on reads: self.attr access without assignment is not mutation.
    """
    _MUTATING_CALLS = frozenset({
        "append", "extend", "add", "insert", "update", "remove",
        "discard", "pop", "popleft", "clear", "setdefault", "setitem",
    })

    for node in ast.walk(func_node):
        # self.x = value  or  self.x += value  etc.
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_self_attr(target):
                    return True
        if isinstance(node, ast.AugAssign) and _is_self_attr(node.target):
            return True
        if isinstance(node, ast.AnnAssign) and node.value is not None and _is_self_attr(node.target):
            return True
        # del self.x  or  del self.x[i]
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if _is_self_attr(target) or (isinstance(target, ast.Subscript) and _is_self_attr(target.value)):
                    return True
        # self.collection.mutating_method(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MUTATING_CALLS
            and _is_self_attr(node.func.value)
        ):
            return True
    return False


def _is_self_attr(node: ast.expr) -> bool:
    """True if node is self.something (one level of attribute access on 'self')."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _enclosing_class(tree: ast.Module, func_node: ast.AST) -> str | None:
    """Return the name of the class that directly contains func_node, or None."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in ast.walk(node):
            if child is func_node:
                return node.name
    return None


def _find_class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find the ClassDef node with the given name."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None
