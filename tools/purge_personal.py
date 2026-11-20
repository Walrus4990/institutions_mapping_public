"""Delete rows holding personal data (rulebook step 0 patterns) from every CSV and XLSX file under the given folders.

Usage: python tools/purge_personal.py coding/coding_rules.json FOLDER...   (step 0 clean-up of stored files)
A row goes IF one of its cells, or one " | "-separated part of a cell, is personal data; ROR IDs, LOCAL IDs and
dates never are. Prints only file names and counts, never the rows removed.
"""

import csv
import json
import os
import sys

import openpyxl

from institution_mapping.core.personal_data import cell_has_personal_data


def purge_csv(path, patterns):
    """Rewrite a CSV file without its rows that hold personal data; the number of rows removed."""
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
        rows = list(csv.reader(fh))
    keep = [r for r in rows if not any(cell_has_personal_data(v, patterns) for v in r)]
    if len(keep) < len(rows):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, lineterminator="\n").writerows(keep)
    return len(rows) - len(keep)


def purge_xlsx(path, patterns):
    """Save a workbook without its rows (below the first) that hold personal data; the number of rows removed."""
    wb = openpyxl.load_workbook(path)
    n = 0
    for ws in wb:
        for r in range(ws.max_row, 1, -1):
            if any(cell_has_personal_data(c.value, patterns) for c in ws[r]):
                ws.delete_rows(r)
                n += 1
    if n:
        wb.save(path)
    return n


def main(argv):
    """Purge every CSV and XLSX file under the folders; print each file changed and its count."""
    with open(argv[0], encoding="utf-8") as fh:
        patterns = json.load(fh)["personal_data"]
    for folder in argv[1:]:
        for root, _, files in os.walk(folder):
            for fn in files:
                path = os.path.join(root, fn)
                purge = purge_csv if fn.endswith(".csv") else purge_xlsx if fn.endswith(".xlsx") else None
                n = purge(path, patterns) if purge else 0
                if n:
                    print(path, "rows removed:", n)


if __name__ == "__main__":
    main(sys.argv[1:])
