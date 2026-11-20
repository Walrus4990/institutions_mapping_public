"""Replay of the 17 Oct client review.

1. Duplicate LOCAL IDs (ledger batch merge_17oct): one organisation got two LOCAL IDs from two passes. The older ID
   is kept with the agreed name; the newer one is retired (never reused) and its rows move to the older ID.
2. LOCAL IDs of organisations that are in ROR (local_to_ror_17oct) are retired; their rows get the ROR ID and name.
3. Country-level institution (country_level_17oct): an answer that matches a ROR record abroad, while an institution
   of that name exists in the learner's own country, goes to the in-country institution's LOCAL ID.
4. Human-review case decisions (human_review_17oct): not rules, never applied to new names.
In these batches the column ror_id holds the ID that is replaced and target the ID that replaces it.
"""

from ...core.ledger import present
from ...core.table import id_fields, row_of, set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    led = ctx.ledger
    reg = ctx.register()
    m["review_17_oct"] = ""
    for r in led.batch("merge_17oct").itertuples(index=False):
        new, old = r.ror_id, r.target
        for i in m.index[m.institution_id.isin([new, old])]:
            if m.at[i, "institution_id"] == new:
                set_row(
                    m,
                    i,
                    review_17_oct="merged",
                    rule=m.at[i, "rule"] + f" | 17 Oct: duplicate local ID {new} retired -> {old} ({r.note})",
                )
            set_row(m, i, institution_id=old, canonical_name=r.name)
        reg.rename(old, r.name)
        reg.retire(new, old, "same organisation as the LOCAL ID it was merged into")
    for r in led.batch("local_to_ror_17oct").itertuples(index=False):
        lid, rid = r.ror_id, r.target
        for i in m.index[m.institution_id == lid]:
            set_row(
                m,
                i,
                **id_fields(rid),
                canonical_name=r.name,
                review_17_oct="local->ROR",
                rule=m.at[i, "rule"] + f" | 17 Oct: in ROR -> LOCAL ID {lid} retired, ROR ID {rid}",
            )
        reg.retire(lid, rid, "organisation is in ROR")
    for r in present(led.batch("country_level_17oct"), m, "country_level_17oct").itertuples(index=False):
        i = row_of(m, r.raw_institution, r.country)
        lid = reg.issue(r.name, r.country, source=r.note)
        set_row(
            m,
            i,
            **id_fields(lid),
            canonical_name=r.name,
            status="final",
            review_17_oct="country-level",
            rule=f"17 Oct: same-name institution in the user's country -> its local ID ({r.note})",
        )
    for r in present(led.batch("human_review_17oct"), m, "human_review_17oct").itertuples(index=False):
        i = row_of(m, r.raw_institution, r.country)
        set_row(
            m,
            i,
            **id_fields(r.target),
            canonical_name=r.name,
            status="final",
            rule=r.note,
            review_17_oct="human review",
        )
    reg.save()
    ctx.write(__name__, m)
    print(m.review_17_oct.value_counts().to_dict(), "| new local IDs", [x["local_id"] for x in reg.new])
