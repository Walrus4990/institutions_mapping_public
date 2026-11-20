"""After a run: what became of the answers of the lists in input/, and what is left to search (rulebook step 7).

python -m institution_mapping worklist OUT_DIR writes two files into OUT_DIR:
  worklist_report.csv  per list in input/ and outcome: answers and learners (the outcomes in OUTCOMES)
  worklist.csv         the answers left to search, prepared for the web search: ROR candidates in the learner's
                       country, similar answers grouped so that one search decides them all, and a `gid` (row
                       number) that tools/add_decisions.py reads
It chains the three steps of search.py: decided or searched before (ledger_status), ROR candidates
(ror_candidates) and groups (group_uncoded). Run it again after `run --from-stage apply_decisions` to see what is
still left.
"""

from pathlib import Path

import pandas as pd

from .pipeline import CODING
from .search import group_uncoded, ledger_status, ror_candidates

OUTCOMES = {  # (status, ledger status or rule) -> outcome; checked in this order
    "removed": "left out (personal data, step 0, or a REMOVE decision)",
    "decided": "coded by a recorded decision",
    "rules": "coded by rules",
    "abroad": "not identified: an organisation abroad that rule 5 does not code (no search)",
    "searched": "searched before, not identified",
    "other_country": "to search: decided for a learner in another country, read that decision first",
    "search": "to search",
}
TO_SEARCH = ("other_country", "search")


def list_answers(out):
    """The answers that the lists in input/ added to the run (raw.csv rows with source 'pipeline <list name>')."""
    raw = pd.read_csv(out / "work" / "input" / "raw.csv", dtype=str, keep_default_na=False)
    b = raw[raw.source.str.startswith("pipeline ")]
    return pd.DataFrame(
        {
            "list": b.source.str.removeprefix("pipeline "),
            "raw_institution": b["raw institution"].str.strip(),
            "country": b.country,
            "learners": b.learners,
        }
    ).drop_duplicates(["raw_institution", "country"])


def outcome(status, rule, ledger_status):
    """The key of OUTCOMES for one answer."""
    if not status:
        return "removed"
    if status == "coding complete":
        return "decided" if ledger_status == "same_country" else "rules"
    if rule == "UNC-ABROAD":
        return "abroad"
    return {"same_country": "searched", "other_country": "other_country"}.get(ledger_status, "search")


def classify(out, ledger):
    """The list answers with their row of mapping_final.csv, their ledger status and their outcome."""
    b = list_answers(out)
    m = pd.read_csv(out / "mapping_final.csv", dtype=str, keep_default_na=False)
    b = b.merge(m[["raw_institution", "country", "status", "rule"]], how="left").fillna("")
    led = ledger_status(b[["raw_institution", "country", "learners"]], ledger)
    led = led[["raw_institution", "country", "ledger_status"]].drop_duplicates(["raw_institution", "country"])
    b = b.merge(led, how="left").fillna("")
    b["outcome"] = [outcome(s, r, ls) for s, r, ls in zip(b.status, b.rule, b.ledger_status)]
    return b, m


def report(b):
    """Per list and outcome: answers and learners, in the order of OUTCOMES."""
    b = b.assign(n=pd.to_numeric(b.learners, errors="coerce").fillna(0).astype(int))
    r = b.groupby(["list", "outcome"]).agg(answers=("n", "size"), learners=("n", "sum")).reset_index()
    r["order"] = r.outcome.map(list(OUTCOMES).index)
    r = r.sort_values(["list", "order"]).drop(columns="order")
    r["outcome"] = r.outcome.map(OUTCOMES)
    return r


def search_list(b, m, out, ledger):
    """The answers to search, with ROR candidates and groups, and a gid (row number) for add_decisions.py."""
    todo = b[b.outcome.isin(TO_SEARCH)]
    rows = m.merge(todo[["raw_institution", "country", "list", "ledger_status"]], how="inner")
    if rows.empty:
        return rows
    candidates = ror_candidates(rows[["raw_institution", "country", "learners", "org_type"]], out / "work" / "ror")
    g = group_uncoded(rows.drop(columns=["list", "ledger_status"]), ledger, candidates)
    g = g.merge(rows[["raw_institution", "country", "list", "ledger_status"]], how="left")
    g.insert(0, "gid", range(1, len(g) + 1))
    return g


def run(out_dir):
    """Write worklist_report.csv and worklist.csv into OUT_DIR; print the report."""
    out = Path(out_dir).resolve()
    for need in ("mapping_final.csv", "work/input/raw.csv", "work/ror/ror_orgs.csv"):
        if not (out / need).exists():
            raise SystemExit(f"{out / need} is missing: run the mapping into {out} first")
    ledger = pd.read_csv(CODING / "decisions.csv", dtype=str, keep_default_na=False)
    b, m = classify(out, ledger)
    if b.empty:  # empty files, so that an earlier run's are not taken for this one's
        empty = pd.DataFrame(columns=["list", "outcome", "answers", "learners"])
        empty.to_csv(out / "worklist_report.csv", index=False)
        pd.DataFrame(columns=["gid"]).to_csv(out / "worklist.csv", index=False)
        print("the run holds no answers from a list in input/: nothing to search")
        return
    r = report(b)
    r.to_csv(out / "worklist_report.csv", index=False)
    g = search_list(b, m, out, ledger)
    g.to_csv(out / "worklist.csv", index=False)
    print(r.to_string(index=False))
    print(f"\nto search: {len(g)} answers -> {out / 'worklist.csv'}")
