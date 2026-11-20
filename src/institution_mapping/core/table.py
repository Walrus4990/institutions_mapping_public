"""The mapping table: one row per user-entered name (raw_institution) and learner country.

Working columns: raw_institution, country, learners, canonical_name (the coded name), institution_id, id_kind
(ROR | LOCAL | empty), ror_url, org_type, status (final | uncoded | suggested), rule (how the row was decided).
"""


def id_kind(rid):
    """'ROR', 'LOCAL' or '' for an ID."""
    return "" if not rid else ("LOCAL" if str(rid).startswith("LOCAL") else "ROR")


def id_fields(rid):
    """institution_id, id_kind and ror_url for an ID ('' clears all three)."""
    kind = id_kind(rid)
    return dict(institution_id=rid, id_kind=kind, ror_url=f"https://ror.org/{rid}" if kind == "ROR" else "")


def set_row(m, i, **fields):
    """Write several columns of one row."""
    for col, value in fields.items():
        m.at[i, col] = value


def row_of(m, raw, cc):
    """Index of the one row for (user-entered name, country); the key of every ledger decision."""
    idx = m.index[(m.raw_institution == raw) & (m.country == cc)]
    assert len(idx) == 1, (raw, cc, len(idx))
    return idx[0]


def ensure_columns(m, *cols):
    """Add empty columns that a stage writes to, if missing."""
    for c in cols:
        if c not in m:
            m[c] = ""


def shortest(names):
    """The shortest of a set of names; ties broken alphabetically."""
    return sorted(set(names), key=lambda x: (len(x), x))[0]


def coded_lookups(m):
    """For IDs already coded (status final): the shortest coded name and the most frequent org_type per ID."""
    coded = m[(m.status == "final") & (m.institution_id != "")]
    canon = coded.groupby("institution_id").canonical_name.agg(lambda s: shortest(s)).to_dict()
    typ = coded.groupby("institution_id").org_type.agg(lambda s: s.value_counts().index[0]).to_dict()
    return canon, typ


def add_place_suffix(m, o):
    """Rulebook 8.1 as applied by the 16 Oct passes: a coded name shared by two or more IDs gets "(City, Country)" when
    all of them are in one country, else "(Country)"; names that already end in a bracket are left alone."""
    ids = m[m.institution_id != ""].copy()
    ids["base"] = ids.canonical_name.str.replace(r" \([^()]*\)$", "", regex=True)
    for base, g in ids.groupby("base"):
        rids = [x for x in g.institution_id.unique() if x in o.index]
        if g.institution_id.nunique() < 2 or not rids:
            continue
        ccs = {o.at[x, "country_code"] for x in rids} | set(g[~g.institution_id.isin(rids)].country)
        for x in rids:
            sfx = f"{o.at[x, 'city']}, {o.at[x, 'country']}" if len(ccs) == 1 else o.at[x, "country"]
            rows = g[(g.institution_id == x) & (g.canonical_name == g.base)].index  # only names without a suffix
            m.loc[rows, "canonical_name"] = f"{base} ({sfx})"
    return m


def learners(d):
    """Total learners of a table."""
    return int(d.learners.sum())


def id_counts(d):
    """'ROR n | LOCAL n' for a table, for the stage summaries."""
    return f"ROR {(d.id_kind == 'ROR').sum()} | LOCAL {(d.id_kind == 'LOCAL').sum()}"
