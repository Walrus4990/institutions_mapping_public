"""Replay of the 16 Oct grouping: similar uncoded spellings checked as one organisation (ledger batch groups_16oct).

One ledger row per user-entered name; the rows of one group share `extra` (the group number). target: a ROR ID,
LOCAL:<name> (confirmed, not in ROR: its LOCAL ID) or NAME:<name> (spelling aligned, not verified).
"""

from ...core.ledger import present
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import coded_lookups, id_fields, set_row


def groups(ctx, m):
    """(raw names, country, target, org_type, name, source) per group, in ledger order."""
    g = present(ctx.ledger.batch("groups_16oct"), m, "groups_16oct")
    for _, grp in g.groupby("extra", sort=False):
        r0 = grp.iloc[0]
        yield grp.raw_institution.tolist(), r0.country, r0.target, r0.org_type, r0["name"], r0.source or r0.note


def run(ctx):
    m = ctx.read_previous(__name__)
    o = orgs_by_id(ctx.ror_dir)
    canon, typ = coded_lookups(m)
    reg = ctx.register()
    m["group_16_oct"] = ""
    for raws, cc, target, otype, cname, src in groups(ctx, m):
        idx = m[m.raw_institution.isin(raws) & (m.country == cc)].index
        assert len(idx) == len(raws), (raws, len(idx))
        if target.startswith("NAME:"):
            rid, name = "", target[5:]
        elif target.startswith("LOCAL:"):
            name = target[6:]
            rid = reg.issue(name, cc, source=src, any_country=True)
        else:
            rid = target
            name = cname or canon.get(rid) or o.at[rid, "display_name"]
            if not otype:
                otype = typ.get(rid) or org_type_from_types_field(o.at[rid, "types"])
        kind = id_fields(rid)["id_kind"]
        rule = "16 Oct grouping: " + (
            "ROR" if kind == "ROR" else "local ID (verified, 2+ learners)" if kind else "spelling aligned, not verified"
        )
        for i in idx:
            set_row(
                m,
                i,
                **id_fields(rid),
                canonical_name=name,
                org_type=otype or m.at[i, "org_type"],
                status="final" if rid else "uncoded",
                rule=rule,
                group_16_oct="yes",
            )
    reg.save()
    ctx.write(__name__, m)
    g = m[m.group_16_oct == "yes"]
    print("rows changed", len(g), "| learners", g.learners.sum(), "| new local IDs", len(reg.new))
