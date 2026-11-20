"""The ROR snapshot: ror_orgs.csv (one row per record) and ror_names.csv (one row per name)."""

from functools import lru_cache

import pandas as pd

from .org_types import org_type_from_ror


@lru_cache(maxsize=None)
def _read(path):
    """A snapshot file as text, read once per run."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def read_orgs(ror_dir):
    """ror_orgs.csv as a table of strings (a fresh copy; the file is read once per run)."""
    return _read(f"{ror_dir}/ror_orgs.csv").copy()


def read_names(ror_dir):
    """ror_names.csv as a table of strings (a fresh copy; the file is read once per run)."""
    return _read(f"{ror_dir}/ror_names.csv").copy()


def orgs_by_id(ror_dir, active_only=False):
    """ror_orgs.csv indexed by ror_id; active records only if asked."""
    o = read_orgs(ror_dir)
    if active_only:
        o = o[o.status == "active"]
    return o.set_index("ror_id")


class Ror:
    """The ROR snapshot with the lookups every stage needs."""

    def __init__(self, ror_dir):
        self.ror_dir = ror_dir
        self.orgs = orgs_by_id(ror_dir)
        self._names = None
        self.active = set(self.orgs.index[self.orgs.status == "active"])

    @property
    def names(self):
        """ror_names.csv: every name of every record (read when first needed)."""
        if self._names is None:
            self._names = read_names(self.ror_dir)
        return self._names

    def resolve(self, rid):
        """Rulebook step 2: an active record is itself; an inactive one with exactly one ACTIVE successor is that
        successor; anything else is None."""
        if rid in self.active:
            return rid
        if rid not in self.orgs.index:
            return None
        succ = [s for s in self.orgs.at[rid, "successor_ids"].split(";") if s in self.active]
        return succ[0] if len(succ) == 1 else None

    def types(self, rid):
        """A record's ROR types (education, healthcare, ...)."""
        return [t for t in self.orgs.at[rid, "types"].split(";") if t]

    def org_type(self, rid, default=""):
        """A record's org_type (rulebook 3.3 point 2)."""
        return org_type_from_ror(self.types(rid), default)

    def name(self, rid):
        """A record's display name."""
        return self.orgs.at[rid, "display_name"]

    def cc(self, rid):
        """A record's country code."""
        return self.orgs.at[rid, "country_code"]

    def parent_chains(self, rid, seen=()):
        """Every chain of ROR parents above a record, nearest parent first (a cycle is cut)."""
        if rid not in self.orgs.index or rid in seen:
            return []
        chains = []
        for p in sorted(x for x in self.orgs.at[rid, "parent_ids"].split(";") if x):
            up = self.parent_chains(p, seen + (rid,))
            chains += [[p] + c for c in up] if up else [[p]]
        return chains

    def parent_ids(self, rid):
        """ror_parent_ids format (rulebook 3.2): chains joined by "|", IDs within a chain by "/"."""
        return "|".join("/".join(c) for c in self.parent_chains(rid))


def label(o, rid, country="country_code"):
    """'<ROR name> (<city>, <country>)' for messages and review sheets."""
    return f"{o.at[rid, 'display_name']} ({o.at[rid, 'city']}, {o.at[rid, country]})"
