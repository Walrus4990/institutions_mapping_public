"""Looks up ROR records by words (for a web search): prints id, name, city, country, types and status.

Usage: python tools/find_ror.py OUT_DIR/work ROR_DIR 'search words|CC' ...
  OUT_DIR/work  a run's work folder: its ror_names_clean.csv has every name cleaned as the rules see it
  ROR_DIR       the unzipped ROR snapshot (a run's OUT_DIR/work/ror)
  CC            optional: only records in this country
Every word must start a word of the name; up to six records per query.
"""

import re
import sys

import pandas as pd


def find(names, words, cc=""):
    """ROR IDs (at most six, in order of appearance) whose cleaned name has a word starting with each of `words`."""
    m = names
    for w in words.lower().split():
        m = m[m.key.str.contains(r"\b" + re.escape(w), regex=True)]
    if cc:
        m = m[m.country_code == cc]
    return list(dict.fromkeys(m.ror_id))[:6]


def main(argv):
    """Print the records found for each query."""
    work, ror_dir = argv[:2]
    names = pd.read_csv(f"{work}/ror_names_clean.csv", dtype=str, keep_default_na=False)
    orgs = pd.read_csv(f"{ror_dir}/ror_orgs.csv", dtype=str, keep_default_na=False).set_index("ror_id")
    names["key"] = names.clean.str.replace(r"[^0-9a-z]+", " ", regex=True)
    for q in argv[2:]:
        words, _, cc = q.partition("|")
        print(f"# {q}")
        for i in find(names, words, cc):
            r = orgs.loc[i]
            print(f"   {i} | {r.display_name} | {r.city}, {r.country_code} | {r.types} | {r.status}")


if __name__ == "__main__":
    main(sys.argv[1:])
