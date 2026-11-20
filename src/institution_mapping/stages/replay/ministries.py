"""Replay of the 16 Oct ministry rule (client decision; rulebook 6.5), ledger batch ministries_16oct.

Every ministry is handled like the Ministry of Health: one ID per ministry per country (national) or per state
(state/provincial), at any learner count; the ROR record where it exists, otherwise one LOCAL ID. Units and services
of a ministry roll up; central banks follow the same rules. target: ROR ID (optionally "|<current name>", given to
every row of that ID) or LOCAL:<name>. LOCAL IDs given to a ministry that has a ROR record are retired (ledger batch
local_to_ror_16oct). Church "ministries" are not government.
"""

from ...core.ledger import present
from ...core.ror import orgs_by_id
from ...core.table import add_place_suffix, id_counts, id_fields, row_of, set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    o = orgs_by_id(ctx.ror_dir)
    led = ctx.ledger
    decisions = {
        (r.raw_institution, r.country): (r.target, r.note[len("rule 6.5 (ministries)") :].lstrip(": "))
        for r in present(led.batch("ministries_16oct"), m, "ministries_16oct").itertuples(index=False)
    }
    retire = {r.ror_id: r.target for r in led.batch("local_to_ror_16oct").itertuples(index=False)}
    reg = ctx.register()
    m["ministry_16_oct"] = ""

    def code(i, rid, name, note):
        set_row(
            m,
            i,
            **id_fields(rid),
            canonical_name=name,
            org_type="GOVERNMENT",
            status="final",
            rule="16 Oct ministry rule" + (f": {note}" if note else ""),
            ministry_16_oct="yes",
        )

    for (raw, cc), (t, note) in decisions.items():
        i = row_of(m, raw, cc)
        if t.startswith("LOCAL:"):
            name = t[6:]
            source = (
                "ministry rule (16 Oct): one ID per ministry, any learner count"
                if "Bank" not in name
                else "central bank: ministry rules (16 Oct)"
            )
            code(i, reg.issue(name, cc, any_country=True, source=source), name, note)
        else:
            t, _, current_name = t.partition("|")
            assert o.at[t, "country_code"] == cc and o.at[t, "status"] == "active", (raw, t)
            code(i, t, current_name or o.at[t, "display_name"], note)
            if current_name:
                m.loc[m.institution_id == t, "canonical_name"] = current_name
    for old, rid in retire.items():
        for i in m[m.institution_id == old].index:
            code(i, rid, o.at[rid, "display_name"], f"{old} retired: ROR record exists")
        reg.retire(old, rid, "organisation is in ROR")
    for i in m[m.raw_institution.str.contains(r"\bInternational Ministries\b", case=False)].index:
        m.at[i, "org_type"] = "COMPANY_OR_NGO"
    add_place_suffix(m, o)
    reg.save()
    ctx.write(__name__, m)
    x = m[m.ministry_16_oct == "yes"]
    print(f"rows {len(x)} | {id_counts(x)} | new local IDs {len(reg.new)}")
