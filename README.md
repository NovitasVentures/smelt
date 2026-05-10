# ⬡ Smelt

**Spec-driven autonomous code generation with convergence guarantees.**

You describe what to build. Smelt doesn't stop until the code 
provably satisfies it.

→ [runsmelt.dev](https://runsmelt.dev)

---

## The idea

NVIDIA's NVCell system takes a hardware spec and loops overnight — 
generating candidate layouts, scoring them against design rules, 
fixing violations — until it produces results that match or exceed 
what 8 engineers previously built in 10 months [The Batch](https://www.deeplearning.ai/the-batch/issue-352).

Smelt applies the same architecture to software.

Give it a spec and a set of test goals. It generates a test suite, 
locks it, then loops: generate code → score compliance × test pass 
rate → reprompt with exact failures → repeat. The loop exits when 
the code passes every frozen test and meets your compliance 
threshold.

The tests are immutable once frozen. The only exit is correct, 
compliant code.

---

## How it works

**Phase 1 — Test synthesis**

Smelt generates a test suite from your spec and test goals, then 
validates it with a mutation engine before freezing. Tests that 
don't kill 70% of mutations get rejected and regenerated. Weak 
tests don't freeze.

**Phase 2 — Generation loop**

generate code
→ run frozen tests        → goal score (0.0–1.0)
→ run compliance scorer   → compliance score (0.0–1.0)
→ composite = compliance × goal
→ if score ≥ threshold: exit CONVERGED
→ else: reprompt with exact failures → repeat

The reprompt always includes specific failure detail — rule IDs, 
line numbers, failing test names. Never just a score.

---

## Quickstart

```bash
pip install smelt

smelt --spec my_spec.md --goals my_goals.md
```

---

## Standards profiles

| Profile | Language | Scorer | Test runner |
|---|---|---|---|
| `python_default` | Python | ruff + mypy | pytest |
| `c_misra` | C | misra (cppcheck) + clang-tidy | gtest |
| `cpp_autosar` | C++ | clang-tidy + cppcheck | gtest |

Custom profiles via `smelt.toml`. Scorer interface is pluggable — 
drop in any tool that returns a score and a list of violations.

---

## Roadmap

- [x] Python / ruff / pytest
- [x] C / MISRA / gtest  
- [ ] C++ / AUTOSAR / gtest
- [ ] GitHub Action
- [ ] K8s / Terraform / Helm profiles
- [ ] Crasis semantic scorer integration — architectural pattern 
      enforcement beyond what any linter can express

---

## Why the tests freeze

Without immutable tests the LLM optimizes the metric, not the 
intent. It will hardcode return values, weaken assertions, or write 
tests that pass trivially. Freezing tests with a mutation gate 
closes that hole. The loop has no escape hatch except writing 
correct code.

This is Goodhart's Law applied to code generation. Smelt's 
architecture is the fix.

---

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

Built by [Novitas Ventures](https://novitasventures.com).

---

## License

MIT — see [LICENSE](LICENSE).
