"""Replay of the 16 Oct unique-name rule (client decision; rulebook 5.2, rule code ROR-UNIQUE).

An uncoded spelling that equals the name (display, label, or the part before a comma) of exactly ONE active ROR record
worldwide is coded to it, wherever the record is (study abroad, distance, online). Also: the same words as one
university's or college's English display name ("Cambridge University" = "University of Cambridge"). Not used for
one-word answers, generic names (text.specific), names the ledger records as not unique in a country
(not_unique_16oct), records in the learner's own country (decided earlier) and government bodies (rule 6.5).
The same test codes an uncoded spelling to a LOCAL ID whose name is unique.
"""

import re

import pandas as pd

from ...core import ror as ror_snapshot
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import coded_lookups, id_fields, set_row
from ...core.text import fold, specific

TYPO = {
    "univeristy": "university",
    "universty": "university",
    "unversity": "university",
    "univesity": "university",
    "univ": "university",
    "universiti": "university",
    "universitas": "university",
    "universitat": "university",
    "universidad": "university",
    "universidade": "university",
    "universite": "university",
    "universita": "university",
    "collage": "college",
    "colledge": "college",
    "institue": "institute",
    "centre": "center",
    "the": "",
}
STOPW = {"of", "the", "and", "at", "in", "for", "de", "du", "la", "le", "des", "del", "di", "da", "do", "y", "et"}
BRACKETS = r"\([^)]*\)"


def norm(s):
    """fold() with generic-word typos corrected and 'the' dropped."""
    return " ".join(x for x in (TYPO.get(t, t) for t in fold(s).split()) if x)


def word_set(k):
    """The words of a key without small words."""
    return frozenset(w for w in k.split() if w not in STOPW)


class UniqueNames:
    """The ROR names (display, label, and the part before a comma) of active records, by key and by word set."""

    def __init__(self, ror_dir):
        self.o = o = orgs_by_id(ror_dir, active_only=True)
        n = ror_snapshot.read_names(ror_dir)
        n = n[n.ror_id.isin(o.index) & n.name_kind.isin(["display", "label"])]  # aliases are too loose
        n["key"] = n.name.map(norm)
        pre = n[n.name.str.contains(",")].copy()
        pre["key"] = pre.name.str.split(",").str[0].map(norm)
        self.exact = pd.concat([n, pre]).groupby("key").ror_id.agg(lambda s: sorted(set(s))).to_dict()
        display = n[n.name_kind == "display"]
        self.word_order = display.groupby(display.key.map(word_set)).ror_id.agg(lambda s: sorted(set(s))).to_dict()
        self.country_words = {norm(c) for c in o.country.unique()} | {"uk", "usa", "us", "ksa", "uae"}
        self.city_words = {norm(c) for c in o.city.unique() if c}

    def place(self, w):
        """True for a country or city word."""
        return w in self.country_words or w in self.city_words

    def variants(self, raw):
        """The spelling as given, without brackets, and without a trailing country or city ("University of X, UK")."""
        unbracketed = re.sub(BRACKETS, " ", raw)
        base = norm(unbracketed)
        out = [norm(raw), base]
        parts = [norm(p) for p in re.split(r"[,/]", unbracketed) if norm(p)]
        if len(parts) > 1 and all(self.place(p) for p in parts[1:]):
            out.append(parts[0])
        w = base.split()
        while len(w) > 2 and (self.place(w[-1]) or " ".join(w[-2:]) in self.country_words):
            w = w[:-2] if " ".join(w[-2:]) in self.country_words else w[:-1]
            out.append(" ".join(w))
        return list(dict.fromkeys(out))

    def find(self, raw):
        """(matched key, record IDs, how) for an answer."""
        for v in self.variants(raw):
            if self.exact.get(v):
                return v, self.exact[v], "only ROR record with this name worldwide"
        for v in dict.fromkeys([norm(raw), norm(re.sub(BRACKETS, " ", raw))]):
            if ({"university", "college"} & set(v.split())) and self.word_order.get(word_set(v)):
                return v, self.word_order[word_set(v)], "only ROR record with these words worldwide (word order)"
        return norm(raw), [], "only ROR record with this name worldwide"


def code_unique_ror(m, un, not_unique, typ):
    """Code uncoded rows to the only ROR record worldwide with their name."""
    o = un.o
    todo = m[
        (m.institution_id == "")
        & ~m.org_type.isin(["NOT_APPLICABLE", "NOT_SPECIFIED"])
        & ((m.status == "uncoded") | m.rule.str.contains("override"))
    ]
    for i, r in todo.iterrows():
        k, ids, how = un.find(r.raw_institution)
        if len(k.split()) < 2 or len(ids) != 1:
            continue
        if not specific(k) or (k, r.country) in not_unique:
            continue
        rid = ids[0]
        if r.country and o.at[rid, "country_code"] == r.country:
            continue  # in-country matches were decided by the earlier stages
        if "government" in o.at[rid, "types"]:
            continue  # rule 6.5: a government body abroad means the learner's own country's
        set_row(
            m,
            i,
            **id_fields(rid),
            canonical_name=o.at[rid, "display_name"],
            org_type=org_type_from_types_field(o.at[rid, "types"]) or typ.get(rid, ""),
            status="final",
            rule=f"16 Oct unique name: {how} ({o.at[rid, 'country_code']})",
            unique_16_oct="yes",
        )


def code_unique_local(m):
    """Code uncoded rows to the only LOCAL ID with their name."""
    loc = m[(m.id_kind == "LOCAL") & (m.status == "final")]
    lname = loc.groupby(loc.canonical_name.map(norm)).institution_id.agg(lambda s: sorted(set(s))).to_dict()
    lcanon = loc.groupby("institution_id").canonical_name.first().to_dict()
    for i, r in m[(m.status == "uncoded") & (m.institution_id == "")].iterrows():
        k = norm(r.raw_institution)
        ids = lname.get(k, [])
        if len(ids) != 1 or len(k.split()) < 2 or not specific(k):
            continue
        lid = ids[0]
        otype = loc[loc.institution_id == lid].org_type.iloc[0]
        if otype == "GOVERNMENT":
            continue
        set_row(
            m,
            i,
            institution_id=lid,
            id_kind="LOCAL",
            canonical_name=lcanon[lid],
            org_type=otype,
            status="final",
            rule="16 Oct unique name: only local ID with this name",
            unique_16_oct="yes",
        )


def run(ctx):
    m = ctx.read_previous(__name__)
    typ = coded_lookups(m)[1]
    # Bayero University (KE): the earlier client "uncoded" decision is no longer an override; the rules decide
    for i in m[
        (m.raw_institution.str.lower() == "bayero university") & (m.country == "KE") & (m.institution_id == "")
    ].index:
        set_row(
            m, i, status="uncoded", rule="close spelling of a ROR record abroad (Bayero University Kano) -> uncoded"
        )
    not_unique = {(r.clean, r.country): r.note for r in ctx.ledger.batch("not_unique_16oct").itertuples(index=False)}
    m["unique_16_oct"] = ""
    code_unique_ror(m, UniqueNames(ctx.ror_dir), not_unique, typ)
    code_unique_local(m)
    ctx.write(__name__, m)
    x = m[m.unique_16_oct == "yes"]
    print("coded", len(x), "| learners", x.learners.sum())
