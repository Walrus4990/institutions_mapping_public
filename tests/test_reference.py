"""T1: a run's workbook equals tests/reference/reference_output.xlsx (the output of this code version) cell for cell.

Needs a run (IM_RUN_DIR). After an intended change of the output, `python -m institution_mapping release` replaces the
reference; the changed rows are listed in the release's changes log (docs/releases/).
"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "tools"))
from compare_workbooks import load, mapping_diffs, sheet_diffs  # noqa: E402

REFERENCE = HERE / "reference" / "reference_output.xlsx"


def test_same_as_reference(run_dir):
    c, r = load(run_dir / "institution_mapping_final.xlsx"), load(REFERENCE)
    d = mapping_diffs(c["mapping"], r["mapping"])
    assert d is not None, "different rows"
    assert d.empty, d.head(20).to_string()
    for sheet, (only_c, only_r) in sheet_diffs(c, r).items():
        assert not only_c and not only_r, sheet
