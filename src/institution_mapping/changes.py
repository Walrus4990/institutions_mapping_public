"""The release's list of changed rows (docs/releases/changes_log_vNN.csv), written by code, and the version check.

A release compares the new workbook's mapping with the published one, row by row on (raw_institution, country). IF a
row is added, removed or changes one of COMPARED THEN the release needs the next version number, and the changed
rows are written to docs/releases/changes_log_vNN.csv; the previous version's files go to archive/vNN-1/, older
archive folders to archive/old/ (git-ignored; they stay in the git history). IF no row changes THEN the version stays.
"""

import re
import shutil

import pandas as pd

from .pipeline import REPO

COMPARED = ["canonical_name", "institution_id", "org_type", "status", "rule", "evidence"]
KEY = ["raw_institution", "country"]


def version_of(workbook):
    """The version number in the first line of a workbook's read-me sheet ("Institution mapping – v26" -> 26)."""
    first = pd.read_excel(workbook, sheet_name="read me", header=None, nrows=1).iat[0, 0]
    found = re.search(r"v(\d+)", str(first))
    if not found:
        raise SystemExit(f"{workbook}: no version number in the first line of the read-me sheet")
    return int(found.group(1))


def mapping_of(workbook):
    """The mapping sheet as text."""
    return pd.read_excel(workbook, sheet_name="mapping", dtype=str, keep_default_na=False)


def changes_log(before, after, v0, v1):
    """The rows added, removed or changed in COMPARED, with each compared column before and after side by side."""
    b = before.set_index(KEY)
    a = after.set_index(KEY)
    keys = list(a.index) + [k for k in b.index if k not in a.index]
    rows = []
    for k in keys:
        old = b.loc[k, COMPARED].tolist() if k in b.index else [""] * len(COMPARED)
        new = a.loc[k, COMPARED].tolist() if k in a.index else [""] * len(COMPARED)
        if old != new or k not in a.index or k not in b.index:
            learners = (a if k in a.index else b).at[k, "learners"]
            row = [*k, learners]
            for o, n in zip(old, new):
                row += [o, n]
            rows.append(row)
    cols = [*KEY, "learners"] + [f"{c}_v{v}" for c in COMPARED for v in (v0, v1)]
    return pd.DataFrame(rows, columns=cols)


def archive_previous(v0, log=print):
    """Move the previous version's release files to archive/v{v0}/ and older archive folders to archive/old/."""
    archive = REPO / "archive"
    for folder in archive.glob("v*"):
        n = re.fullmatch(r"v(\d+)", folder.name)
        if n and int(n.group(1)) < v0 and folder.is_dir():
            (archive / "old").mkdir(exist_ok=True)
            shutil.move(str(folder), str(archive / "old" / folder.name))
            log(f"moved archive/{folder.name} -> archive/old/ (git-ignored)")
    old_files = list((REPO / "docs" / "releases").glob(f"changes_log_v{v0}.csv"))
    old_files += list((REPO / "docs" / "qa").glob("codes_to_check_v*.csv"))
    for f in old_files:
        (archive / f"v{v0}").mkdir(exist_ok=True)
        shutil.move(str(f), str(archive / f"v{v0}" / f.name))
        log(f"moved {f.relative_to(REPO)} -> archive/v{v0}/")


def check_and_log(new_workbook, published, log=print):
    """Before a release: compare, check the version number, write the changes log. Stops (SystemExit) on a wrong
    version number, before anything is copied."""
    v0, v1 = version_of(published), version_of(new_workbook)
    changed = changes_log(mapping_of(published), mapping_of(new_workbook), v0, v1)
    if len(changed) and v1 <= v0:
        raise SystemExit(
            f"{len(changed)} rows are added, removed or coded differently, but the new workbook says v{v1}: set "
            f"VERSION to {v0 + 1} in src/institution_mapping/__init__.py, run again, then release"
        )
    if not len(changed) and v1 != v0:
        raise SystemExit(f"no row changed: the version stays v{v0}. Set VERSION back to {v0}, run again, then release")
    if not len(changed):
        log(f"no row changed: still v{v0}, no changes log")
        return
    archive_previous(v0, log)
    path = REPO / "docs" / "releases" / f"changes_log_v{v1}.csv"
    changed.to_csv(path, index=False)
    log(f"v{v0} -> v{v1}: {len(changed)} rows added, removed or coded differently -> {path.relative_to(REPO)}")
    log("update archive/README.md (what archive/ now holds) and add the CHANGELOG.md entry")
