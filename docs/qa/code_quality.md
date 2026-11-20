# Code quality

Measured on 20 Nov 2026 on `src/` and `tools/`, with the settings in `pyproject.toml`; `make quality` repeats the
measures.

## Correctness first

- The output must not change unless a rule or a decision is meant to change it. A full run is compared with
  `tests/reference/reference_output.xlsx` cell for cell (`tools/compare_workbooks.py`, and the tests with
  `IM_RUN_DIR`).
- When code is restructured, the new code is run on the same input as the old, and their outputs are compared:
  for the 25 Oct 2026 restructure, 46 intermediate files and the workbook were identical; for the 20 Nov 2026
  restructure of the tools, every tool's output was identical (the candidate list up to the order of equal scores).
- `pytest` (275 tests): personal-data patterns, same-answer grouping, the rulebook's references to the code and
  back, the decision applier on made-up decisions, the client path (checks, lookup, list, log, sending with a fake
  GitHub), the worklist, the judgement-call draft, the release's version check, and the run against the reference.

## Measures

| Measure | Tool | Value | What it says |
|---|---|---|---|
| Lint findings | ruff (pycodestyle, pyflakes, bugbear, simplify, naming, complexity) | 0 | no style errors, unused names or likely bugs |
| Lines over 120 characters | ruff E501 | 0 | lines readable without scrolling |
| Functions and classes measured | radon cc | 423 | small, named steps |
| Average cyclomatic complexity | radon cc | 5.0 (A) | decisions per function; 10 or less is easy to follow |
| Functions ranked D-F (complexity > 20) | radon cc | 5 (none F; highest 32) | see "Remaining hot spots" |
| Docstring coverage | interrogate | 100 % | every module, class and function says what it does |
| Code inside functions or classes | own count (ast) | 77 % | the rest is docstrings and constant lists at module level (word lists, the NORHED partners, the networks) |

## Remaining hot spots

Five functions are above complexity 20: `ContainedNames.decide` (32), `TypoMatcher.fuzzy` (28),
`Engine.exact_name` (26), `replay/review.apply_review` (23) and `decide_acronym` (21). Each is one rule of the rulebook
written as an ordered list of IF/THEN cases. They were kept whole because the order of the cases is the rule; splitting
them would spread one rule over several functions. Their docstrings give the rulebook section.

The maintainability index (radon mi) ranks `stages/rules_engine.py` C. It is the longest module (the whole rules
engine, about 700 lines, with many regular expressions), and the index falls with module length and with the number of
distinct operators. All other modules rank A or B.

## Practices applied

- Layout: `src/` package (PyPA); `input/` for what people bring, `coding/` for what the code codes with (rules,
  decisions and the ROR and LOCAL registries side by side), `output/` for the one deliverable, `docs/` for people,
  `tests/`, and `tools/` for command-line helpers that are not part of a run.
- One entry point (`python -m institution_mapping`), one list of stages (`pipeline.STAGES`), one context object for
  paths (`pipeline.Run`), so no stage hard-codes a file location.
- README for orientation; the rules in `coding/RULEBOOK.md`, each naming its code; history in `CHANGELOG.md` (Keep a
  Changelog).
- Automated checks: ruff (lint and format), radon (complexity, maintainability), interrogate (docstrings), pytest.
