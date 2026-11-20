"""decisions.csv: every decision taken by hand (web searches, reviewer, client and human-review decisions).

Each row belongs to a batch. Batch `decisions` holds every decision taken since 18 Oct 2026 and is applied by
stages/apply_decisions.py; the other batches are the passes of 13-17 Oct, replayed by stages/replay/.
"""

from functools import lru_cache

import pandas as pd


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
