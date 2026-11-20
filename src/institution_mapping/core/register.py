"""The permanent LOCAL ID register, local_ids.csv (rulebook 7.5)."""

import pandas as pd

from .text import key


class Register:
    """LOCAL IDs for organisations confirmed to exist that have no ROR record.

    Columns: local_id, name, name_key (text.key of the name), other_names (former names, " | "), country,
    status (active | retired), replaced_by, reason, source.
    IDs are never renumbered or reused: a new ID is the highest number ever issued + 1. A retired ID keeps its name,
    so meeting that name again finds the same ID; an active ID with the same name is preferred."""

    COLS = ["local_id", "name", "name_key", "other_names", "country", "status", "replaced_by", "reason", "source"]
    NEW_COLS = ["local_id", "name", "country", "source"]

    def __init__(self, path):
        self.path = path
        self.df = pd.read_csv(path, keep_default_na=False, dtype=str)[self.COLS]
        self.new = []  # IDs issued since the register was opened

    def _row(self, lid):
        """Index of a LOCAL ID's row."""
        return self.df.index[self.df.local_id == lid]

    def find(self, name, cc="", any_country=False):
        """ID for this name (current or former), or None. Same country only (rulebook 7.2), unless any_country
        (rule 7.3: one ID for a network active in several countries) or the country is not known (empty cc)."""
        k = key(name)
        alias = self.df.other_names.map(lambda o: k in {key(x) for x in o.split(" | ") if x})
        d = self.df[(self.df.name_key == k) | alias]
        if not any_country and cc:
            d = d[d.country == cc]
        if d.empty:
            return None
        act = d[d.status == "active"]
        return (act if len(act) else d).local_id.iloc[0]

    def issue(self, name, cc, source="", any_country=False):
        """The organisation's ID: the existing one if the name is known, else a new one."""
        lid = self.find(name, cc, any_country)
        if lid:
            return lid
        lid = f"LOCAL-{max(int(x[6:]) for x in self.df.local_id) + 1:04d}"
        self.df.loc[len(self.df)] = [lid, name, key(name), "", cc, "active", "", "", source]
        self.new.append(dict(local_id=lid, name=name, country=cc, source=source))
        return lid

    def names_in(self, cc):
        """{name key: {active LOCAL IDs}} for country cc, current and former names; IDs without a country
        (international organisations, rule 7.3) count in every country."""
        out = {}
        act = self.df[(self.df.status == "active") & self.df.country.isin([cc, ""])]
        for r in act.itertuples(index=False):
            for n in [r.name] + [x for x in r.other_names.split(" | ") if x]:
                out.setdefault(key(n), set()).add(r.local_id)
        return out

    def status(self, lid):
        """active or retired."""
        return self.df.loc[self._row(lid), "status"].iloc[0]

    def replaced_by(self, lid):
        """The ID that replaced a retired LOCAL ID."""
        return self.df.loc[self._row(lid), "replaced_by"].iloc[0]

    def retire(self, lid, replaced_by, reason):
        """Retire an ID (its number is never reused): what replaced it and why."""
        i = self._row(lid)
        assert len(i) == 1, lid
        self.df.loc[i, ["status", "replaced_by", "reason"]] = ["retired", replaced_by, reason]

    def rename(self, lid, name):
        """New current name; the former name stays findable under other_names."""
        i = self._row(lid)
        old = self.df.at[i[0], "name"]
        if key(old) != key(name):
            others = [x for x in self.df.at[i[0], "other_names"].split(" | ") if x and key(x) != key(name)]
            self.df.loc[i, "other_names"] = " | ".join(sorted(set(others) | {old}, key=key))
        self.df.loc[i, ["name", "name_key"]] = [name, key(name)]

    def save(self, new_ids_csv=None):
        """Write the register; optionally the IDs issued since it was opened (always with a header)."""
        self.df.sort_values("local_id").to_csv(self.path, index=False)
        if new_ids_csv:
            pd.DataFrame(self.new, columns=self.NEW_COLS).to_csv(new_ids_csv, index=False)
