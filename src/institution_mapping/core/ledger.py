"""decisions.csv: every decision taken by hand (web searches, reviewer, client and human-review decisions).

Each row belongs to a batch. Batch `decisions` holds every decision taken since 18 Oct 2026 and is applied by
stages/apply_decisions.py; the other batches are the passes of 13-17 Oct, replayed by stages/replay/.
A client's session records its decisions in a decisions file in input/ (rulebook 9.6); a run reads them after the
ledger, and `take-in` moves them into the ledger before a release.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

DECISION_FILES = "decisions_*.csv"  # a client session's decisions, in input/ (rulebook 9.6)


def decision_files(input_dir):
    """The decisions files in input/, in the order a run reads them (by name: date, then file)."""
    return sorted(Path(input_dir).glob(DECISION_FILES))


def read_decision_file(path, columns):
    """A decisions file as text, with the ledger's columns (a missing column is an error)."""
    d = pd.read_csv(path, keep_default_na=False, dtype=str)
    missing = [c for c in columns if c not in d.columns]
    assert not missing, f"{Path(path).name} lacks the ledger columns {missing}"
    return d[columns]


def take_in(ledger_csv, input_dir):
    """Rule 9.6: append the decisions files of input/ to the ledger, in the order a run reads them, numbered on from
    the ledger's last D-number, and delete them. A run then applies the same decisions in the same order. Returns
    {file name: number of decisions}."""
    led = pd.read_csv(ledger_csv, keep_default_na=False, dtype=str)
    columns, n = list(led.columns), max(int(x[1:]) for x in led.id if x.startswith("D"))
    taken = {}
    for f in decision_files(input_dir):
        d = read_decision_file(f, columns)
        d["id"] = [f"D{n + k:05d}" for k in range(1, len(d) + 1)]
        n += len(d)
        d.to_csv(ledger_csv, mode="a", header=False, index=False, lineterminator="\n")
        taken[f.name] = len(d)
        f.unlink()
    return taken


def with_decision_files(ledger_csv, input_dir, out_csv):
    """Write the ledger followed by the decisions files of input/ (rulebook 9.6): what a run applies."""
    led = pd.read_csv(ledger_csv, keep_default_na=False, dtype=str)
    parts = [led] + [read_decision_file(f, list(led.columns)) for f in decision_files(input_dir)]
    pd.concat(parts, ignore_index=True).to_csv(out_csv, index=False)


@lru_cache(maxsize=None)
def _read(path):
    """decisions.csv as text, read once per run."""
    return pd.read_csv(path, keep_default_na=False, dtype=str)


class Ledger:
    """Read access to decisions.csv by batch."""

    def __init__(self, path):
        self.path = path

    @property
    def table(self):
        """The whole ledger."""
        return _read(self.path)

    def batch(self, name, required=True):
        """Rows of one batch, in ledger order."""
        d = self.table
        out = d[d.batch == name].reset_index(drop=True)
        assert len(out) or not required, f"no ledger rows for batch {name}"
        return out

    def batches(self, *names):
        """Rows of several batches, one after the other."""
        return pd.concat([self.batch(n) for n in names])

    def overrides(self):
        """Reviewer decisions of 14 Oct that the rules do not reproduce: {'clean|country': ror_id, or '' = uncoded}."""
        d = self.batch("overrides_14oct")
        return {f"{r.clean}|{r.country}": ("" if r.target == "UNC" else r.target) for r in d.itertuples(index=False)}


def present(d, m, where=""):
    """Ledger rows whose answer (user-entered name + country) is in this mapping. A decision for an answer that is
    no longer in the input is skipped and counted, not an error."""
    keys = set(zip(m.raw_institution, m.country))
    ok = [(a, b) in keys for a, b in zip(d.raw_institution, d.country)]
    if len(d) - sum(ok):
        print(f"{where}: {len(d) - sum(ok)} recorded decision(s) skipped: answer not in this input")
    return d[ok].reset_index(drop=True)
