"""Replay of the 16 Oct web search of every remaining unchecked entry (country + user-entered name; ledger batch
search_all_16oct).

target: LOCAL (confirmed, not in ROR: LOCAL ID; the same name gets the same ID, also across countries for a network),
ROR:<id> (in ROR, or rolls up to it), TH:<id> (teaching hospital of that university or college, rule 6.3), NS / NA (type
only / not an organisation), UNC (not found or not confirmed: stays uncoded, the reason recorded).
"""

from ...core.ledger import present
from ...core.org_types import org_type_from_types_field, type_from_name
from ...core.ror import orgs_by_id
from ...core.table import id_counts, id_fields, row_of, set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    d = present(ctx.ledger.batch("search_all_16oct"), m, "search_all_16oct")
    rows = [row_of(m, a, b) for a, b in zip(d.raw_institution, d.country)]
    assert len(set(rows)) == len(rows), "two decisions for one answer"
    o = orgs_by_id(ctx.ror_dir)
    reg = ctx.register()
    m["search_all_16_oct"] = ""
    for i, r in zip(rows, d.itertuples(index=False)):
        t, src = r.target, r.source
        m.at[i, "search_all_16_oct"] = "yes"
        if t == "UNC":
            m.at[i, "rule"] = f"16 Oct search (country + name): {src}"
        elif t in ("NS", "NA"):
            set_row(
                m,
                i,
                **id_fields(""),
                canonical_name="",
                status="final",
                rule=f"16 Oct search: {src}",
                org_type="NOT_SPECIFIED" if t == "NS" else "NOT_APPLICABLE",
            )
        elif t == "LOCAL":
            lid = reg.issue(r.name, m.at[i, "country"], source=f"web search 16 Oct: {src}", any_country=True)
            set_row(
                m,
                i,
                **id_fields(lid),
                canonical_name=r.name,
                status="final",
                rule=f"16 Oct search: confirmed, not in ROR -> local ID ({src})",
            )
            if m.at[i, "org_type"] in ("", "NOT_SPECIFIED", "NOT_APPLICABLE"):
                m.at[i, "org_type"] = type_from_name(r.name)  # rulebook 3.3 point 3
        else:
            kind, rid = t.split(":", 1)
            assert rid in o.index and o.at[rid, "status"] == "active", (i, rid)
            set_row(m, i, **id_fields(rid), status="final")
            if kind == "TH":
                set_row(
                    m,
                    i,
                    canonical_name=r.name,
                    org_type="TEACHING_HOSPITAL",
                    rule=f"16 Oct search: teaching hospital, not in ROR -> the university/college's ID (rule 5) "
                    f"({src})",
                )
            else:
                set_row(
                    m,
                    i,
                    canonical_name=o.at[rid, "display_name"],
                    rule=f"16 Oct search: {src}",
                    org_type=org_type_from_types_field(o.at[rid, "types"], m.at[i, "org_type"]),
                )
    reg.save()
    ctx.write(__name__, m)
    x = m[m.search_all_16_oct == "yes"]
    uncoded = (x.status == "uncoded").sum()
    print(f"searched {len(x)} | {id_counts(x)} | still uncoded {uncoded} | new local IDs {len(reg.new)}")
