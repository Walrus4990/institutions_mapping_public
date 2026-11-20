"""Replay of the 16 Oct NGO/company rule and "if we know an organisation exists, it gets an ID" (client decisions).

1. Case decisions (ledger batch known_orgs_16oct): acronyms and short names are not coded abroad by the NGO-company
   exception (UNC); ones checked by hand stay (KEEP: INASP, ARROW). Country branches of a network roll up to the
   network's record unless ROR has the branch; a government acronym is the learner's own country's body.
2. Every organisation confirmed to exist (website or reliable page) that still has no ID gets a LOCAL ID, at any
   learner count and of any type (school, hospital, NGO, company, government body).
"""

import pandas as pd

from ...core.ror import orgs_by_id
from ...core.table import id_fields, row_of, set_row

CONFIRMED = r"(?<!not )verified|R5 not in ROR"  # rule texts of rows whose organisation was confirmed to exist
# a source found after the research log was written
SOURCE_FIXES = {
    "Adjoafua Community Senior High School": (
        "https://ghanahighschools.com/ghs_schools/adjoafua-comm-senior-high/ (Western North)"
    ),
}


def acronym_case(raw):
    """Rule 8.3: a one-word answer in lower case is an acronym, written in capitals."""
    raw = raw.strip()
    return raw.upper() if len(raw.split()) == 1 and raw.islower() else raw


def apply_case_decisions(m, decisions, o):
    """Batch known_orgs_16oct: UNC, KEEP or a new ID per answer."""

    def code(i, rid, why, name=""):
        set_row(
            m,
            i,
            **id_fields(rid),
            canonical_name=name or o.at[rid, "display_name"],
            status="final",
            rule="16 Oct NGO rule: " + why,
            known_org_16_oct="yes",
        )

    answers = set(zip(m.raw_institution, m.country))  # KEEP rows name several answers ("A|B"), so no present()
    for d in decisions.itertuples(index=False):
        if d.target == "KEEP":
            names = {n.upper() for n in d.raw_institution.split("|")}
            for i in m.index[m.raw_institution.str.upper().isin(names)]:
                m.at[i, "rule"] += " | 16 Oct: " + d.note
        elif (d.raw_institution, d.country) not in answers:
            continue
        elif d.target == "UNC":
            i = row_of(m, d.raw_institution, d.country)
            set_row(
                m,
                i,
                **id_fields(""),
                status="uncoded",
                canonical_name=acronym_case(m.at[i, "raw_institution"]),
                rule="16 Oct NGO rule: " + d.note,
                known_org_16_oct="yes",
            )
        else:
            i = row_of(m, d.raw_institution, d.country)
            code(i, d.target, d.note, d.name)
            if d.org_type:
                m.at[i, "org_type"] = d.org_type


def issue_confirmed(m, reg, research):
    """Every uncoded organisation confirmed to exist gets a LOCAL ID, with its source."""
    known = m[(m.institution_id == "") & (m.status == "uncoded") & m.rule.str.contains(CONFIRMED, regex=True)]
    for i, r in known.iterrows():
        name, source = r.canonical_name, r.rule
        if "R5" in r.rule:  # the 14 Oct research found it: cite the source it recorded
            hit = research[research.name.str.lower() == name.lower()]
            source = hit.source.iloc[0] if len(hit) else source
        source = SOURCE_FIXES.get(name, source) or source
        lid = reg.issue(name, r.country, source=f"existence confirmed (16 Oct): {source}")
        set_row(
            m,
            i,
            **id_fields(lid),
            canonical_name=name,
            status="final",
            known_org_16_oct="yes",
            rule=r.rule + " -> local ID: organisation confirmed to exist (client, 16 Oct)",
        )


def run(ctx):
    m = ctx.read_previous(__name__)
    m["known_org_16_oct"] = ""
    apply_case_decisions(m, ctx.ledger.batch("known_orgs_16oct"), orgs_by_id(ctx.ror_dir))
    reg = ctx.register()
    issue_confirmed(m, reg, pd.read_csv(ctx.w("research.csv"), keep_default_na=False, dtype=str))
    reg.save()
    ctx.write(__name__, m)
    print("rows", (m.known_org_16_oct == "yes").sum(), "| new local IDs", [(d["local_id"], d["name"]) for d in reg.new])
