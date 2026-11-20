"""Before the web search (rulebook step 7): group the uncoded rows so that similar answers are searched together.

Usage: python tools/group_uncoded.py MAPPING_FINAL_CSV LEDGER_CSV CANDIDATES_CSV OUT_CSV [SKIP_PAIRS_CSV]
  MAPPING_FINAL_CSV  mapping_final.csv of a run
  LEDGER_CSV         coding/decisions.csv: rows already decided for this name and country are left out
  CANDIDATES_CSV     output of tools/ror_candidates.py for the same rows (ROR candidates in the learner's country)
  SKIP_PAIRS_CSV     optional: raw_institution,country pairs to leave out (e.g. the rows of an earlier mapping)
Groups, in this order:
  1. country (most uncoded learners first)
  2. kind: no organisation / not named (text that looks like a sentence or a role), university or college, hospital,
     government, research, company or NGO, school, other
  3. cluster: answers that name the same organisation in different spellings (same distinctive words, or a close
     spelling score >= 88), so that one search decides the whole cluster
Output: one row per uncoded row with group, kind, cluster and the best ROR candidates; sorted for the search. The
logic is institution_mapping.search.group_uncoded.
"""

import sys

import pandas as pd

from institution_mapping.search import group_uncoded


def main(argv):
    """Read the files named on the command line, write OUT_CSV and print the counts per kind."""
    mapping, ledger, candidates, out = argv[:4]
    read = lambda f: pd.read_csv(f, keep_default_na=False, dtype=str)  # noqa: E731
    skip = set()
    if len(argv) > 4:
        s = read(argv[4])
        skip = set(zip(s.raw_institution, s.country))
    u = group_uncoded(read(mapping), read(ledger), read(candidates), skip)
    u.to_csv(out, index=False)
    u["learners"] = u.learners.astype(int)
    print(
        "uncoded rows to search:",
        len(u),
        "| learners:",
        u.learners.sum(),
        "| clusters:",
        u.groupby(["country", "cluster"]).ngroups,
        "| countries:",
        u.country.nunique(),
    )
    print(u.groupby("kind").agg(rows=("learners", "size"), learners=("learners", "sum")).to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
