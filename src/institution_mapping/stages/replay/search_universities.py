"""Replay of the 16 Oct web search of every remaining unmatched university or college (ledger batch search_16oct).

Only rows still uncoded (the client's review wins). target: ROR ID (name optional: teaching hospital or campus in
another town), LOCAL:<name> (verified, not in ROR: its LOCAL ID), NAME (verified name, no ID), UNC (not found).
"""

from ...core.ledger import present
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import id_counts, id_fields, row_of, set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    d = present(ctx.ledger.batch("search_16oct"), m, "search_16oct")
    o = orgs_by_id(ctx.ror_dir)
    reg = ctx.register()
    m["search_16_oct"] = ""
    for _, r in d.iterrows():
        i, t = row_of(m, r.raw_institution, r.country), r.target
        if m.at[i, "status"] != "uncoded":
            continue
        if t == "NAME":
            set_row(m, i, canonical_name=r["name"], org_type=r.org_type or m.at[i, "org_type"])
        elif t.startswith("LOCAL:"):
            name = t[6:]
            lid = reg.issue(name, r.country, source="web search 16 Oct: " + r.note, any_country=True)
            set_row(m, i, **id_fields(lid), canonical_name=name, org_type=r.org_type, status="final")
        elif t != "UNC":
            assert t in o.index and o.at[t, "status"] == "active", t
            set_row(
                m,
                i,
                **id_fields(t),
                canonical_name=r["name"] or o.at[t, "display_name"],
                status="final",
                org_type=r.org_type or org_type_from_types_field(o.at[t, "types"], m.at[i, "org_type"]),
            )
        set_row(m, i, rule="16 Oct web search: " + r.note, search_16_oct="yes")
    reg.save()
    ctx.write(__name__, m)
    x = m[m.search_16_oct == "yes"]
    print(f"rows {len(x)} | {id_counts(x)} | new local {len(reg.new)}")
