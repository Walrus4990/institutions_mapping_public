"""Replay of the client's review of the unmatched-universities list (16 Oct; ledger batch client_unis_16oct).

The client's choice wins over any rule: a ROR ID codes the row to that record (also abroad); NS / NA =
NOT_SPECIFIED / NOT_APPLICABLE; NAME = verified name, no ID (not in ROR); UNC = stays uncoded (too ambiguous).
"""

from ...core.ledger import present
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import id_fields, row_of, set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    d = present(ctx.ledger.batch("client_unis_16oct"), m, "client_unis_16oct")
    o = orgs_by_id(ctx.ror_dir)
    m["client_unis_16_oct"] = ""
    for _, r in d.iterrows():
        i, t = row_of(m, r.raw_institution, r.country), r.target
        if t in ("NS", "NA"):
            set_row(
                m,
                i,
                **id_fields(""),
                canonical_name="",
                status="final",
                org_type="NOT_SPECIFIED" if t == "NS" else "NOT_APPLICABLE",
            )
        elif t in ("UNC", "NAME"):
            set_row(m, i, **id_fields(""), status="uncoded")
            if t == "NAME":
                set_row(m, i, canonical_name=r["name"], org_type=r.org_type or m.at[i, "org_type"])
        else:
            assert t in o.index and o.at[t, "status"] == "active", t
            set_row(
                m,
                i,
                **id_fields(t),
                canonical_name=o.at[t, "display_name"],
                status="final",
                org_type=org_type_from_types_field(o.at[t, "types"], m.at[i, "org_type"]),
            )
        set_row(m, i, rule="client review 16 Oct: " + r.note.replace("client: ", ""), client_unis_16_oct="yes")
    ctx.write(__name__, m)
    x = m[m.client_unis_16_oct == "yes"]
    print("rows", len(x), "| coded", (x.institution_id != "").sum(), "| uncoded", (x.status == "uncoded").sum())
