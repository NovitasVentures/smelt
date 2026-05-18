"""Architectural principle extractor — reads a SAD and returns structured principles."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from smelt.llm import client as llm

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-5"
_DEFAULT_CACHE_DIR = Path(".smelt_cache") / "arch"

_EXTRACTION_SYSTEM = """\
You are an architectural compliance analyst. Your task is to extract enforceable \
architectural principles from a software architecture document.

An enforceable principle is one that can be determined TRUE or FALSE by examining a \
single code snippet. Discard aspirational statements unless they resolve to a concrete, \
observable check (e.g. "the system should be maintainable" is not enforceable; \
"no function has more than one return statement" is).

Output ONLY a JSON array. No prose, no markdown fences, no preamble. Nothing outside \
the JSON array.

Each element of the array must have exactly these fields:
{
  "name": string,
  "title": string,
  "description": string,
  "trigger": string,
  "ignore": string,
  "chunk_level": string,
  "weight": float,
  "eval_cases": [string],
  "source_section": string
}

Field definitions:

"name": kebab-case slug derived from the principle title. \
Example: "single-exit-path", "shared-core-dry".

"title": The human-readable title of the principle, taken directly from the document.

"description": The full text of the principle from the document, verbatim or paraphrased.

"trigger": Describes what a VIOLATION looks like — the positive class for the binary \
classifier. Written as plain English directed at a non-expert. Must describe the \
violation, not the rule.
  BAD trigger: "Code follows the layering architecture"
  GOOD trigger: "A function has more than one return statement, causing execution to \
exit at multiple points in the function body rather than at the final line."
The trigger is what the classifier fires on. Make it precise and unambiguous.

"ignore": Acceptable patterns that might superficially look like violations but are not. \
Prevents false positives. Examples: generator functions with yield, re-raising exceptions.

"chunk_level": The smallest granularity at which the violation is fully visible. \
Must be one of: "function", "class", "file", "module", "cross-file".
  "function"   — violation manifests in how a single function is written (call patterns, \
                 return structure, exception handling within the function body)
  "class"      — violation manifests in how a class is structured (inheritance, composition)
  "file"       — violation manifests in import/include statements or module-level definitions
  "module"     — violation manifests in cross-file dependency direction within a package
  "cross-file" — violation is ONLY detectable by examining dependency relationships \
                 across multiple files simultaneously (e.g. layer isolation: file A \
                 includes file B from a forbidden layer). No single file inspection \
                 can determine the violation. Use this when the principle concerns \
                 the direction of dependencies between architectural layers or modules.

"weight": Importance of this principle, 0.0 to 1.0.
  1.0 if the document uses language like "must", "shall", "required"
  0.7 if the document uses "should", "recommended"
  0.4 if the document uses "may", "can", "preferred"

"eval_cases": A list of 3 to 5 tricky edge cases that a weak classifier might get wrong. \
Include both false-positive traps (patterns that look wrong but are fine) and subtle \
violations (patterns that should fire but are easy to miss). Write each case as a brief \
description or short code snippet.

"source_section": The section number or title in the original document. \
Example: "6.1", "Section 3 — Development View".

Rules:
1. Only extract principles that are directly enforceable by inspecting a code snippet.
2. The "trigger" always describes the violation (positive class = bad pattern). \
   Never write the trigger as the correct behavior.
3. Set "chunk_level" to the smallest level that makes the violation detectable.
4. "eval_cases" must include at least one false-positive trap and one subtle violation.
5. Output valid JSON only. The response must start with "[" and end with "]".
6. ONE violation pattern per principle. If a section of the document describes multiple \
   distinct failure modes (e.g. "bare except OR swallowing exceptions OR missing re-wrap"), \
   split them into separate principles — one per failure mode. A compound trigger that \
   contains "or" almost always means the principle should be split. Each resulting \
   principle gets its own name, trigger, ignore, chunk_level, and eval_cases. \
   A classifier trained on a compound trigger will learn a blurry boundary; a classifier \
   trained on a single, atomic failure mode will be accurate and interpretable.
"""


@dataclass
class ArchitecturalPrinciple:
    """A single architectural principle extracted from a SAD."""

    name: str
    title: str
    description: str
    trigger: str
    ignore: str
    chunk_level: str
    weight: float
    mandatory: bool
    eval_cases: list[str]
    source_section: str


def extract_principles(
    doc_text: str,
    model: str = _DEFAULT_MODEL,
    cache_dir: Path = _DEFAULT_CACHE_DIR,
    no_cache: bool = False,
) -> list[ArchitecturalPrinciple]:
    """Extract architectural principles from an architecture document.

    Calls Claude with a structured prompt. Results are cached by content hash
    to avoid re-spending tokens on identical documents.

    Args:
        doc_text: Full text of the architecture document.
        model: Anthropic model ID to use for extraction.
        cache_dir: Directory for caching extraction results.
        no_cache: If True, skip cache read (still writes result).

    Returns:
        List of structured ArchitecturalPrinciple objects.
    """
    cache_path = _cache_path(doc_text, cache_dir)

    if not no_cache:
        cached = _load_cache(cache_path)
        if cached is not None:
            log.info("Loaded %d principles from cache: %s", len(cached), cache_path)
            return cached

    log.info("Extracting principles from architecture document (%d chars)", len(doc_text))
    user_message = (
        "Extract all enforceable architectural principles from this architecture document:\n\n"
        f"<document>\n{doc_text}\n</document>"
    )

    raw = llm.complete(system=_EXTRACTION_SYSTEM, user=user_message, model=model, max_tokens=4096)

    principles = _parse_response(raw)
    _save_cache(principles, cache_path)
    log.info("Extracted %d principles, cached to %s", len(principles), cache_path)
    return principles


def _cache_path(doc_text: str, cache_dir: Path) -> Path:
    doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{doc_hash}.json"


def _load_cache(cache_path: Path) -> list[ArchitecturalPrinciple] | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return [_principle_from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("Cache read failed (%s), re-extracting: %s", cache_path, exc)
        return None


def _save_cache(principles: list[ArchitecturalPrinciple], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(p) for p in principles]
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_response(raw_json: str) -> list[ArchitecturalPrinciple]:
    """Parse raw JSON string from LLM into ArchitecturalPrinciple objects."""
    # The LLM client already strips markdown fences, but trim whitespace to be safe
    cleaned = raw_json.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Extractor returned invalid JSON: {exc}\nRaw: {cleaned[:500]}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    principles: list[ArchitecturalPrinciple] = []
    for i, item in enumerate(data):
        try:
            principles.append(_principle_from_dict(item))
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Principle {i} has invalid structure: {exc}\nItem: {item}") from exc

    return principles


def _principle_from_dict(d: dict) -> ArchitecturalPrinciple:
    weight = float(d["weight"])
    return ArchitecturalPrinciple(
        name=str(d["name"]),
        title=str(d["title"]),
        description=str(d["description"]),
        trigger=str(d["trigger"]),
        ignore=str(d["ignore"]),
        chunk_level=str(d["chunk_level"]),
        weight=weight,
        mandatory=weight >= 1.0,
        eval_cases=list(d.get("eval_cases", [])),
        source_section=str(d.get("source_section", "")),
    )
