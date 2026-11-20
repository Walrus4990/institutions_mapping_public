"""The rulebook and the code refer to each other correctly.

1. Every module and function a rulebook **Code:** line names exists.
2. Every rulebook section the code cites ("rulebook 5.2", "rule 6.4", "step 7", "rule 3a") exists in the rulebook.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "institution_mapping"
RULEBOOK = (REPO / "coding" / "RULEBOOK.md").read_text(encoding="utf-8")


def rulebook_sections():
    """Section numbers (3.6), steps (step 0-8) and rule 3a defined in the rulebook."""
    found = set(re.findall(r"^#{2,3} (\d+(?:\.\d+)?)\b", RULEBOOK, flags=re.M))
    found |= set(re.findall(r"^(\d+\.\d+) \*\*", RULEBOOK, flags=re.M))
    found |= {f"step {n}" for n in re.findall(r"^\*\*Step (\d+) ", RULEBOOK, flags=re.M)}
    found |= {f"rule {r}" for r in re.findall(r"^\*\*Rule (\d+[a-z]) ", RULEBOOK, flags=re.M)}
    return found


def code_references():
    """(path, [names]) for every module named on a **Code:** line (names: the functions in brackets after it)."""
    refs = []
    for line in re.findall(r"Code:(.*?)(?:\n\n|\n\*\*|\n-|\n\d|$)", RULEBOOK, flags=re.S):
        line = " ".join(line.split())
        for path, names in re.findall(r"`([\w/]+\.py)`(?: \(([^)]*)\))?", line):
            refs.append((path, re.findall(r"`([\w.]+)`", names or "")))
    return refs


def source(path):
    for base in (PACKAGE, REPO):
        if (base / path).exists():
            return (base / path).read_text(encoding="utf-8")
    return None


def test_rulebook_names_code():
    assert len(code_references()) > 40


@pytest.mark.parametrize(("path", "names"), code_references())
def test_code_reference_exists(path, names):
    text = source(path)
    assert text is not None, f"{path} does not exist"
    for name in names:
        last = name.split(".")[-1]
        assert re.search(rf"^\s*(def|class) {last}\b|^\s*{last} = |self\.{last} = ", text, flags=re.M), (
            f"{name} not found in {path}"
        )


def cited_sections():
    """(file, citation) for every rulebook section cited in the code."""
    out = set()
    for f in PACKAGE.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(?:rulebook|[Rr]ule|section)s? (\d+\.\d+)", text):
            out.add((f.name, m.group(1)))
        for m in re.finditer(r"\b[Rr]ulebook step (\d+)|\(step (\d+)\)", text):
            out.add((f.name, f"step {m.group(1) or m.group(2)}"))
        for m in re.finditer(r"\b[Rr]ule (\d+[a-z])\b", text):
            out.add((f.name, f"rule {m.group(1)}"))
    return sorted(out)


@pytest.mark.parametrize(("file", "citation"), cited_sections())
def test_cited_section_exists(file, citation):
    assert citation in rulebook_sections(), f"{file} cites {citation}, which is not in coding/RULEBOOK.md"
