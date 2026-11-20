"""Before any web search: which answers of a raw-names file are already decided, or already searched?

Usage: python tools/check_against_ledger.py RAW_NAMES_CSV LEDGER_CSV [MAPPING_FINAL_CSV] OUT_CSV
  RAW_NAMES_CSV      columns 'raw institution', 'country', 'learners' (as OUT_DIR/work/input/raw.csv)
  LEDGER_CSV         coding/decisions.csv
  MAPPING_FINAL_CSV  optional: mapping_final.csv of a run on this file, to list only rows that ended uncoded
Each row gets `ledger_status`:
  same_country   a decision for this user-entered name (or its cleaned spelling) and country exists: do NOT search
  other_country  a decision exists for a learner in another country: read it before searching (same organisation?)
  not_in_ledger  never decided: search only if the run leaves it uncoded
Matching uses step 1's cleaning (case, accents, '&', trailing dots) and the pipeline's key (punctuation ignored), so
spelling variants that are the same answer under rule 3.6 match. The logic is institution_mapping.search.ledger_status.
"""

import sys

import pandas as pd

from institution_mapping.search import ledger_status


def main(argv):
    """Read the files named on the command line, write OUT_CSV and print the counts."""
    raw, ledger, out = argv[0], argv[1], argv[-1]
    mapping = argv[2] if len(argv) == 4 else None
    answers = pd.read_csv(raw, encoding="utf-8-sig", keep_default_na=False, dtype=str)
    answers = answers.rename(columns={"raw institution": "raw_institution"})
    led = pd.read_csv(ledger, keep_default_na=False, dtype=str)
    m = pd.read_csv(mapping, keep_default_na=False, dtype=str) if mapping else None
    d = ledger_status(answers, led, m)
    d.to_csv(out, index=False)
    print(
        d.ledger_status.value_counts().to_dict(),
        "| needs a search:",
        int(d.needs_search.sum()) if mapping else "(give MAPPING_FINAL_CSV)",
    )


if __name__ == "__main__":
    main(sys.argv[1:])
