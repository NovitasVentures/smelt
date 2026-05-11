# Smelt × Crasis — CLAUDE.md

You are building the **Crasis scorer integration for Smelt**: a pipeline that ingests a
Software Architecture Document (SAD / ISO 42010), extracts architectural principles, generates
Crasis specialist specs for each principle, and produces a `CrasisScorer` that plugs into
Smelt's existing compliance scoring interface.

Read this entire file before writing any code.

---

## Repository context

This work spans two separate repositories. Do not consolidate them.

```
github.com/NovitasVentures/smelt     ← code generation loop (you are working here)
github.com/crasis-ai/crasis          ← distillation pipeline (consumed as a dependency)
```

Crasis is a **dependency**, not a submodule. Install it with:

```bash
pip install "crasis[train]"   # build pipeline
pip install crasis            # inference only (production)
```

Crasis produces ONNX binary classifiers from plain-English specs. The Smelt scorer loads
those ONNX files at runtime. No Crasis training code runs during Smelt's generation loop.

---

## What you are building

Four components, in this order:

```
smelt/
├── scorers/
│   ├── crasis_scorer.py          ← 1. CrasisScorer (Smelt BaseScorer implementation)
│   └── chunker.py                ← 2. Code chunker (function / class / file / module)
├── arch/
│   ├── extractor.py              ← 3. Principle extractor (arch doc → structured principles)
│   └── spec_generator.py         ← 4. Spec generator (principles → Crasis YAML specs)
├── cli/
│   └── arch_import.py            ← 5. CLI entry point: smelt arch-import
└── tests/
    ├── test_crasis_scorer.py
    ├── test_chunker.py
    ├── test_extractor.py
    └── fixtures/
        ├── sample_arch_doc.md    ← provided by user during iteration
        └── sample_specs/         ← expected YAML output for fixture doc
```

Supporting files added to repo root:

```
specialists/                      ← trained ONNX specialists live here (gitignored binaries)
  └── <principle-name>/
      ├── spec.yaml
      ├── model-onnx/
      └── eval_results.json
specs/                            ← generated specs awaiting human review + crasis build
  └── <principle-name>.yaml
```

---

## Component 1 — `CrasisScorer`

File: `smelt/scorers/crasis_scorer.py`

Implements `BaseScorer` from `smelt/scorers/base.py`. Study the existing interface before
writing anything — do not change the base class.

```python
from crasis import CrasisToolkit, Specialist
from smelt.scorers.base import BaseScorer, ScorerResult, Violation
from smelt.scorers.chunker import chunk_code, ChunkLevel

class CrasisScorer(BaseScorer):
    """
    Scores code against architectural principles using a swarm of Crasis ONNX specialists.
    Each specialist covers one principle extracted from the project's architecture document.
    No API calls at runtime. All inference is local, <3ms per specialist per chunk.
    """

    def __init__(
        self,
        models_dir: str,
        chunk_level: ChunkLevel = ChunkLevel.FUNCTION,
        confidence_threshold: float = 0.85,
        weights: dict[str, float] | None = None,
    ):
        self.toolkit = CrasisToolkit.from_dir(models_dir)
        self.chunk_level = chunk_level
        self.confidence_threshold = confidence_threshold
        self.weights = weights or {}

    def score(self, code: str, filepath: str = "<unknown>") -> ScorerResult:
        chunks = chunk_code(code, level=self.chunk_level, filepath=filepath)
        violations: list[Violation] = []

        for chunk in chunks:
            for specialist in self.toolkit.specialists:
                result = specialist.classify(chunk.text)
                if (
                    result["label"] == "violation"
                    and result["confidence"] >= self.confidence_threshold
                ):
                    violations.append(Violation(
                        principle=specialist.name,
                        location=chunk.location,   # "filepath:start_line–end_line"
                        confidence=result["confidence"],
                        weight=self.weights.get(specialist.name, 1.0),
                        detail=chunk.signature,    # function/class name if available
                    ))

        score = self._aggregate(violations, len(chunks))
        return ScorerResult(score=score, violations=violations, scorer="crasis")

    def _aggregate(self, violations: list[Violation], n_chunks: int) -> float:
        if n_chunks == 0 or not self.toolkit.specialists:
            return 1.0
        max_possible = n_chunks * len(self.toolkit.specialists)
        weighted = sum(v.confidence * v.weight for v in violations)
        return max(0.0, 1.0 - (weighted / max_possible))
```

**Rules:**
- Do not call any LLM or external API inside `score()`. Inference is always local ONNX.
- The `violations` list must be non-empty and specific when score < 1.0 — Smelt's reprompt
  builder uses it directly to construct feedback. Vague violations break the loop.
- `location` must be machine-parseable (`filepath:start–end`), not human prose.
- If `models_dir` is empty or no specialists are found, log a warning and return
  `ScorerResult(score=1.0, violations=[], scorer="crasis")` — do not raise.

---

## Component 2 — `chunker.py`

File: `smelt/scorers/chunker.py`

Code chunking is **not** one-size-fits-all. Architectural principles operate at different
granularities. Some violations only manifest at the file level (wrong imports), others at
the function level (wrong call patterns), others at the module level (wrong dependencies).

```python
from enum import Enum
from dataclasses import dataclass

class ChunkLevel(Enum):
    FUNCTION = "function"   # one chunk per function/method
    CLASS    = "class"      # one chunk per class (includes its methods)
    FILE     = "file"       # whole file as one chunk
    MODULE   = "module"     # all files in a directory as one chunk

@dataclass
class CodeChunk:
    text: str            # the source text fed to the classifier
    location: str        # "filepath:start_line–end_line"
    signature: str       # "ClassName.method_name" or "function_name" or filename
    level: ChunkLevel

def chunk_code(code: str, level: ChunkLevel, filepath: str = "<unknown>") -> list[CodeChunk]:
    ...
```

**Implementation notes:**
- Use `ast` (Python), `tree-sitter` (C/C++), or regex fallback for languages without
  tree-sitter bindings. Do not assume Python only — Smelt targets multiple languages.
- The `text` fed to the classifier should include enough context to be self-contained:
  for `FUNCTION` level, include the enclosing class signature if there is one.
- Chunk size guard: if a chunk exceeds 512 tokens (BERT's limit), split it and score
  each part. Never silently truncate — truncation produces false negatives.
- `MODULE` level: concatenate all files in the directory with a `# --- filepath ---`
  separator. Useful for dependency and layering violations.

---

## Component 3 — `extractor.py`

File: `smelt/arch/extractor.py`

This is the **highest-leverage component**. It reads the architecture document and
extracts discrete, scoreable principles. Everything downstream — spec quality, training
data quality, scorer accuracy — depends on this step.

```python
from dataclasses import dataclass

@dataclass
class ArchitecturalPrinciple:
    name: str                  # slug, e.g. "layering-violation"
    title: str                 # human title, e.g. "Strict layer access"
    description: str           # full text of the principle from the doc
    trigger: str               # what a VIOLATION looks like (for Crasis spec)
    ignore: str                # what is acceptable / edge cases to exclude
    chunk_level: str           # "function" | "class" | "file" | "module"
    weight: float              # importance 0.0–1.0 (1.0 = must-not-violate)
    eval_cases: list[str]      # tricky cases the specialist must handle correctly
    source_section: str        # section/page reference in the original doc

def extract_principles(doc_text: str, model: str = "claude-sonnet-4-20250514") -> list[ArchitecturalPrinciple]:
    """
    Calls Claude to extract architectural principles from the doc.
    Returns a list of structured principles ready for spec generation.
    """
    ...
```

**Extraction prompt design — read this carefully:**

The prompt must instruct Claude to:

1. Read the full document before extracting anything.
2. Extract only **enforceable** principles — things that can be true or false about a
   code snippet. Discard aspirational statements ("the system should be maintainable")
   unless they resolve to a concrete check ("no function exceeds 50 lines").
3. For each principle, write `trigger` and `ignore` as if describing a **binary
   classification task to a non-expert**. The trigger must describe the violation
   (positive class = violation), not the rule. Example:
   - BAD trigger: "Code follows the layering architecture"
   - GOOD trigger: "Code in the service layer directly imports from the database layer,
     bypassing the repository layer"
4. Set `chunk_level` based on where the violation manifests:
   - Import violations → `file`
   - Call pattern violations → `function`
   - Inheritance / composition violations → `class`
   - Dependency direction violations → `module`
5. Set `weight` based on the doc's language: "must", "shall" → 1.0; "should" → 0.7;
   "may", "recommended" → 0.4.
6. Generate `eval_cases` — 3–5 edge cases that a weak classifier would get wrong.
   These become the `quality.eval_on` field in the Crasis spec.
7. Output **only** valid JSON. No prose, no markdown fences, no preamble.

The extraction call is expensive (large context). Cache the result to disk so re-runs
during iteration don't re-spend tokens.

```python
# Cache path: .smelt_cache/arch/<doc_hash>.json
```

---

## Component 4 — `spec_generator.py`

File: `smelt/arch/spec_generator.py`

Converts `ArchitecturalPrinciple` objects into Crasis YAML spec files.
This is deterministic — no LLM calls. Pure data transformation.

```python
import yaml
from pathlib import Path
from smelt.arch.extractor import ArchitecturalPrinciple

CRASIS_SPEC_VERSION = "v1"
DEFAULT_TRAINING_VOLUME = 3000
DEFAULT_MIN_ACCURACY = 0.93
DEFAULT_MAX_MODEL_SIZE_MB = 20
DEFAULT_MAX_INFERENCE_MS = 10

def generate_spec(principle: ArchitecturalPrinciple, output_dir: Path) -> Path:
    """
    Writes a Crasis YAML spec file for the given principle.
    Returns the path to the written file.
    File is written to output_dir/<principle.name>.yaml
    """
    spec = {
        "crasis_spec": CRASIS_SPEC_VERSION,
        "name": principle.name,
        "description": principle.description,
        "task": {
            "type": "binary_classification",
            "trigger": principle.trigger,
            "ignore": principle.ignore,
        },
        "constraints": {
            "max_model_size_mb": DEFAULT_MAX_MODEL_SIZE_MB,
            "max_inference_ms": DEFAULT_MAX_INFERENCE_MS,
            "connectivity": "none",
        },
        "quality": {
            "min_accuracy": DEFAULT_MIN_ACCURACY,
            "eval_on": principle.eval_cases,
        },
        "training": {
            "strategy": "synthetic",
            "volume": DEFAULT_TRAINING_VOLUME,
        },
        "_smelt_meta": {
            "source_section": principle.source_section,
            "chunk_level": principle.chunk_level,
            "weight": principle.weight,
        },
    }

    output_path = output_dir / f"{principle.name}.yaml"
    output_path.write_text(yaml.dump(spec, sort_keys=False, allow_unicode=True))
    return output_path

def generate_all_specs(
    principles: list[ArchitecturalPrinciple],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [generate_spec(p, output_dir) for p in principles]
```

**Note:** `_smelt_meta` is a non-standard extension key. Crasis ignores unknown top-level
keys beginning with `_`. This lets us carry Smelt-specific metadata (chunk level, weight)
through the spec file so the scorer can read it back at load time.

---

## Component 5 — `arch_import` CLI command

File: `smelt/cli/arch_import.py`

```
smelt arch-import --doc path/to/architecture.md --specs-dir ./specs/

  Reads the architecture document
  Extracts principles (with LLM, cached)
  Generates Crasis YAML specs into --specs-dir
  Prints a summary table of extracted principles for human review
  Exits without training anything — human reviews specs before crasis build runs
```

Output format (printed to stdout after extraction):

```
Extracted 8 principles from architecture.md

  #  name                      weight  chunk    trigger (truncated)
  1  layering-violation          1.0   file     Code in service layer imports from db...
  2  loose-coupling              0.7   class    Class depends on concrete impl rather...
  3  naming-convention           0.4   function Function name does not follow <domain>_...
  ...

Review specs in ./specs/ before running:
  crasis build --spec specs/<name>.yaml   (per specialist)
  smelt arch-build --specs-dir ./specs/   (all at once, with quality gates)
```

Add a second CLI command:

```
smelt arch-build --specs-dir ./specs/ [--models-dir ./specialists/]

  Runs crasis build for each spec in --specs-dir
  Enforces quality gate: skips any spec whose eval accuracy < min_accuracy
  Logs failed specialists with their synthetic-real gap for crasis mix later
  Writes trained ONNX models to --models-dir
```

`arch-build` is the budget-spend step. It should refuse to run without explicit
`--confirm` flag so it cannot be triggered accidentally in a loop.

---

## Smelt reprompt integration

The violations list from `CrasisScorer.score()` feeds into the existing reprompt builder.
Make sure the reprompt template handles Crasis violations specifically:

```python
# In smelt/core/reprompt.py — extend the existing violation formatter

def format_crasis_violation(v: Violation) -> str:
    return (
        f"[ARCH] {v.location}: violates '{v.principle}' "
        f"(confidence {v.confidence:.0%}, weight {v.weight:.1f})\n"
        f"  Failing code: {v.detail}"
    )
```

The reprompt must tell the LLM **which principle** was violated and **where**, not just
that the score was low. Vague reprompts produce thrashing, not convergence.

---

## Design decisions — do not relitigate these

These were decided before you started. Work within them.

| Decision | Rationale |
|---|---|
| Separate repos (smelt / crasis) | Different audiences, independent release cadence, Crasis is a standalone product |
| Crasis consumed as a pip dependency | Not a submodule. `pip install crasis` is the interface |
| Human review gate before `crasis build` | Bad specs waste training budget. `arch-import` generates; human approves; `arch-build` trains |
| ONNX specialists only at runtime | No LLM calls inside the Smelt generation loop for scoring |
| `trigger` describes the violation (positive = bad) | Crasis convention — classifier fires when it detects the trigger |
| `chunk_level` is per-principle, not global | Architectural violations manifest at different granularities |
| `_smelt_meta` extension key in spec YAML | Carries Smelt-specific metadata through spec files without forking Crasis |
| `crasis mix` planned from day one | Synthetic-real gap is real. Collect real violations during first deployments |

---

## Testing strategy

### Unit tests

- `test_chunker.py` — fixture Python files with known function/class boundaries.
  Assert chunk count, locations, signatures. Include a >512-token function to test
  the split guard.
- `test_extractor.py` — fixture arch doc (see `tests/fixtures/sample_arch_doc.md`).
  Assert principle count, that `trigger` strings describe violations not rules,
  that `chunk_level` assignments match the principle type.
- `test_crasis_scorer.py` — mock `CrasisToolkit` (do not require trained models in CI).
  Test aggregation math, threshold filtering, empty-models-dir graceful handling,
  violation list structure.

### Integration test (manual, not CI)

Once at least two specialists are trained from the sample arch doc:

```bash
smelt run \
  --spec tests/fixtures/sample_spec.md \
  --goals tests/fixtures/sample_goals.md \
  --scorer crasis \
  --models-dir ./specialists/
```

Confirm the loop reprompts with specific architectural violations, not just a low score.

### Holdout fixtures

For each generated specialist, hand-author 20 holdout examples:
- 10 clear violations
- 5 edge cases that should NOT trigger (legitimate patterns that look suspicious)
- 5 edge cases that SHOULD trigger (subtle violations)

These go in `tests/fixtures/<specialist-name>.jsonl`. Run with:

```bash
crasis eval -s specs/<name>.yaml -m ./specialists/<name>-onnx \
    --holdout tests/fixtures/<name>.jsonl
```

If holdout accuracy < 0.80, the specialist is not ready. Collect the failures for
`crasis mix` before declaring that principle covered.

---

## Language and style

- Python 3.11+
- Type annotations everywhere. No `Any` unless truly unavoidable.
- `pathlib.Path` for all file paths, never `os.path`.
- Dataclasses for structured data, not dicts.
- No bare `except`. Catch specific exceptions and log with context.
- Logging via `logging` module, not `print`. `DEBUG` for verbose pipeline steps,
  `INFO` for human-visible progress, `WARNING` for skipped/degraded cases.
- All LLM calls go through `smelt/llm/client.py` — do not instantiate Anthropic clients
  directly in business logic.

---

## What to build first

Start here, in order:

1. `smelt/scorers/chunker.py` — pure Python, no dependencies, fully testable.
   Get the chunking logic right before building anything that depends on it.

2. `smelt/scorers/crasis_scorer.py` — mock the toolkit in tests. Nail the interface
   and aggregation math. Do not block on having real trained models.

3. `smelt/arch/extractor.py` — draft the extraction prompt and test it against the
   user-supplied architecture document. Iterate on the prompt until the extracted
   `trigger`/`ignore` pairs are crisp and violation-oriented.

4. `smelt/arch/spec_generator.py` — straightforward once extraction is solid.

5. `smelt/cli/arch_import.py` — wire the pipeline together and confirm the end-to-end
   flow from doc to reviewable specs.

6. `crasis build` on the generated specs — first real training run. Evaluate holdout
   accuracy. Flag any specialists with gap > 0.15 for `crasis mix`.

When the user supplies the architecture document, start at step 3 and validate the
extraction output before proceeding. Show the extracted principles table and ask for
confirmation before generating specs.