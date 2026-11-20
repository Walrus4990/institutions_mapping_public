"""ROR candidates for each not-identified answer, in the learner's country, to speed up the web search.

Sources: an acronym in brackets or the whole answer = a ROR acronym; a ROR name (2+ words) contained in the answer;
the fuzzy score on names sharing a distinctive word. The logic is institution_mapping.search.ror_candidates.

Usage: python tools/ror_candidates.py WORKLIST_CSV ROR_DIR OUT_CSV
  WORKLIST_CSV  columns raw_institution, country, learners, org_type, and optionally row and priority
                (e.g. the not-identified rows of OUT_DIR/mapping_final.csv)
  ROR_DIR       an unzipped ROR snapshot (a run's OUT_DIR/work/ror)
"""

import sys

import pandas as pd

from institution_mapping.search import ror_candidates


def main(argv):
    """Read the worklist, write OUT_CSV and print how many answers have a good candidate."""
    worklist, ror_dir, out = argv[:3]
    d = ror_candidates(pd.read_csv(worklist, keep_default_na=False), ror_dir)
    d.to_csv(out, index=False)
    print(
        len(d),
        "| with a candidate >= 80:",
        (d.c1_s >= 80).sum(),
        "| 60-79:",
        d.c1_s.between(60, 79).sum(),
        "| none:",
        (d.c1_s < 60).sum(),
    )


if __name__ == "__main__":
    main(sys.argv[1:])
