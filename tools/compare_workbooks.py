"""Compares a workbook (or mapping CSV) with a reference workbook, row by row.

Usage: python tools/compare_workbooks.py CANDIDATE(.xlsx|.csv) REFERENCE.xlsx [ALLOWED_DIFFS.csv] [-v]
Rows are matched on (raw_institution, country). Compared: every column the client sees on the mapping sheet, and the
sheets local IDs, retired local IDs and organisations as sets of rows. ALLOWED_DIFFS.csv (raw_institution, country,
column; column "*" = any) lists expected differences: they are reported, not failures.
Exit code 0 = identical apart from allowed differences.
"""

import sys

import pandas as pd

COLUMNS = [
    "canonical_name",
    "institution_id",
    "id_kind",
    "ror_url",
    "org_type",
    "status",
    "rule",
    "rule_description",
    "evidence",
    "ror_parent_ids",
]
SET_SHEETS = ["local IDs", "retired local IDs", "organisations"]


def load(path):
    """{sheet name: table as text}: every sheet of a workbook, or {'mapping': ...} for a mapping CSV."""
    if str(path).endswith(".csv"):
        return {"mapping": pd.read_csv(path, keep_default_na=False, dtype=str)}
    return pd.read_excel(path, sheet_name=None, keep_default_na=False, dtype=str)


def mapping_diffs(a, b, allowed=frozenset()):
    """Differing cells of two mapping sheets (None if the rows differ)."""
    ka, kb = list(zip(a.raw_institution, a.country)), list(zip(b.raw_institution, b.country))
    if len(a) != len(b) or set(ka) != set(kb):
        return None
    if ka != kb:  # the same rows in another order (the order of raw.csv)
        b = b.set_index(["raw_institution", "country"]).loc[ka].reset_index()
    diffs = []
    for col in [c for c in COLUMNS if c in a.columns and c in b.columns]:
        for i in a.index[a[col].values != b[col].values]:
            raw, cc = a.at[i, "raw_institution"], a.at[i, "country"]
            diffs.append(
                dict(
                    row=i,
                    raw_institution=raw,
                    country=cc,
                    column=col,
                    candidate=a.at[i, col],
                    reference=b.at[i, col],
                    allowed=(raw, cc, col) in allowed or (raw, cc, "*") in allowed,
                )
            )
    return pd.DataFrame(
        diffs, columns=["row", "raw_institution", "country", "column", "candidate", "reference", "allowed"]
    )


def sheet_diffs(c, r):
    """{sheet: (rows only in candidate, rows only in reference)} for the sheets compared as sets."""
    out = {}
    for sh in SET_SHEETS:
        if sh in c and sh in r:
            x, y = set(map(tuple, c[sh].astype(str).values)), set(map(tuple, r[sh].astype(str).values))
            out[sh] = (x - y, y - x)
    return out


def compare(candidate, reference, allowed_csv=None, verbose=False):
    """Print the comparison; True if identical apart from allowed differences."""
    c, r = load(candidate), load(reference)
    allowed = set()
    if allowed_csv:
        al = pd.read_csv(allowed_csv, keep_default_na=False, dtype=str)
        allowed = set(zip(al.raw_institution, al.country, al.column))
    d = mapping_diffs(c["mapping"], r["mapping"], allowed)
    if d is None:
        print("FAIL: the candidate and the reference have different rows")
        return False
    unexpected = d[~d.allowed]
    print(
        f"mapping: {len(c['mapping'])} rows | differing cells {len(d)} (allowed {int(d.allowed.sum())}, "
        f"unexpected {len(unexpected)})"
    )
    if len(unexpected):
        print(unexpected.groupby("column").size().to_string())
        print(unexpected.head(40).to_string(max_colwidth=60))
    for sh, (only_c, only_r) in sheet_diffs(c, r).items():
        print(f"{sh}: only in candidate {len(only_c)}, only in reference {len(only_r)}")
        if verbose:
            for t in sorted(only_c)[:10]:
                print("   +", t)
            for t in sorted(only_r)[:10]:
                print("   -", t)
    ok = unexpected.empty
    print("RESULT:", "PASS" if ok else "FAIL")
    return ok


def main(argv):
    """Compare the files named on the command line; exit code 0 if identical apart from allowed differences."""
    args = [a for a in argv if a != "-v"]
    return 0 if compare(*args[:3], verbose="-v" in argv) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
