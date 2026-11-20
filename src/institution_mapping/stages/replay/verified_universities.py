"""Replay of the 16 Oct client rule: a university or college confirmed by its website gets a LOCAL ID, also with one
learner (rule 7.1; the rules engine issues LOCAL IDs only with 2+ learners).

Applies to the NAME rows of the client review and the web search with org_type EDUCATION (not secondary schools:
ledger batch not_a_university_16oct), the earlier research (verified_unis_extra_16oct) and the websites the client
found (client_urls_16oct). Spellings with the same verified name in the same country share one ID. IDs issued here
and later found in ROR under an older name are retired (local_to_ror_16oct_b): the number stays reserved.
"""

import pandas as pd

from ...core.ledger import present
from ...core.table import id_fields, row_of, set_row


def decisions(ledger, m):
    """The verified-university decisions for answers in this mapping."""
    named = ledger.batches("client_unis_16oct", "search_16oct")
    named = named[(named.target == "NAME") & (named.org_type == "EDUCATION")]
    schools = set(ledger.batch("not_a_university_16oct").raw_institution)
    named = named[~named.raw_institution.isin(schools)]
    extra = ledger.batches("verified_unis_extra_16oct", "client_urls_16oct")
    return present(pd.concat([named, extra]), m, "verified universities 16 Oct")


def run(ctx):
    m = ctx.read_previous(__name__)
    reg = ctx.register()
    m["verified_uni_16_oct"] = ""
    for _, r in decisions(ctx.ledger, m).iterrows():
        i, name = row_of(m, r.raw_institution, r.country), r["name"]
        lid_now = m.at[i, "institution_id"]
        if m.at[i, "status"] != "uncoded" and lid_now and lid_now == reg.find(name, r.country):
            continue  # with more learners an earlier rule gave the same LOCAL ID
        assert m.at[i, "status"] == "uncoded" and lid_now == "", r.raw_institution
        src = r.note.replace("client: ", "").replace("; not in ROR", "")
        lid = reg.issue(
            name, r.country, source=f"website found (16 Oct): {src}; 1 learner, ID because existence is confirmed"
        )
        set_row(
            m,
            i,
            **id_fields(lid),
            canonical_name=name,
            status="final",
            verified_uni_16_oct="yes",
            rule=m.at[i, "rule"] + " -> local ID: university/college confirmed by its website (client, 16 Oct)",
        )
    for r in ctx.ledger.batch("local_to_ror_16oct_b").itertuples(index=False):
        lid = reg.find(r.ror_id, any_country=True)  # column ror_id holds the LOCAL name in this batch
        for i in m.index[m.institution_id == lid]:
            set_row(
                m,
                i,
                **id_fields(r.target),
                canonical_name=r.name,
                rule=f"16 Oct web search: {r.note}",
                verified_uni_16_oct="",
            )
        reg.retire(lid, r.target, "organisation is in ROR")
        reg.new = [x for x in reg.new if x["local_id"] != lid]
    reg.save()
    ctx.write(__name__, m)
    x = m[m.verified_uni_16_oct == "yes"]
    print("rows", len(x), "| learners", x.learners.sum(), "| new local IDs", len(reg.new))
