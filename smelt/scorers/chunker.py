"""Code chunker for Crasis architectural scoring."""

import ast
import logging
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


def chunk_code(
    source: str,
    level: ChunkLevel,
    filepath: str = "<unknown>",
) -> list[CodeChunk]:
    """Chunk Python source into CodeChunk objects at the requested granularity.

    For MODULE level, filepath is treated as a directory path and source is ignored.
    """
    if level == ChunkLevel.MODULE:
        return _chunk_module(filepath)
    if level == ChunkLevel.FILE:
        return _chunk_file(source, filepath)
    if level == ChunkLevel.CLASS:
        return _chunk_classes(source, filepath)
    return _chunk_functions(source, filepath)


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

        if len(chunk_text) > _MAX_CHARS:
            sub = _split_large_chunk(chunk_text, location, signature, filepath, node.lineno, level=ChunkLevel.FUNCTION)
            chunks.extend(sub)
        else:
            chunks.append(CodeChunk(
                text=chunk_text,
                location=location,
                signature=signature,
                level=ChunkLevel.FUNCTION,
                start_line=node.lineno,
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
