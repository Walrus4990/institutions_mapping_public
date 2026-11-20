"""Shared code of the three replays of the 16 Oct review of uncoded spellings (ROR candidates checked by hand,
quick searches): ledger batches review_16oct, review_unis_16oct and review_16oct_b.

A decision: user-entered name + country, target (ROR ID | NS = NOT_SPECIFIED | NA = NOT_APPLICABLE), org_type,
name, note. A ROR ID must be active and in the learner's country, unless it is an international body (nonprofit or
company record, settings international, the UN), the NHS, or a client decision (note "client:").
"""

from ...core.ledger import present
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import add_place_suffix, coded_lookups, id_fields, row_of, set_row

NHS = "02wnqcb97"
UN_BODIES = {"04xkhqm66", "006kxhp52"}  # UN Women, United Nations: a UN agency is coded to its headquarters record


def apply_review(ctx, stage, batch):
    """Apply one review batch to the mapping before `stage` and write that stage's mapping."""
    m = ctx.read_previous(stage)
    d = present(ctx.ledger.batch(batch), m, batch)
    d["row"] = [str(row_of(m, a, b)) for a, b in zip(d.raw_institution, d.country)]
    assert not d.row.duplicated().any(), d[d.row.duplicated()].row.tolist()
    o = orgs_by_id(ctx.ror_dir)
    international = set(ctx.settings["international"]["ror_ids"]) | UN_BODIES
    typ = coded_lookups(m)[1]
    problems = []
    m["review_16_oct"] = ""
    for _, r in d.iterrows():
        i, t = int(r.row), r.target
        if m.at[i, "status"] != "uncoded" and m.at[i, "institution_id"] == t:
            continue  # already decided this way by an earlier rule
        assert m.at[i, "status"] == "uncoded", (i, m.at[i, "raw_institution"], m.at[i, "status"])
        if t in ("NS", "NA"):
            set_row(
                m, i, **id_fields(""), canonical_name="", org_type="NOT_SPECIFIED" if t == "NS" else "NOT_APPLICABLE"
            )
        else:
            if t not in o.index or o.at[t, "status"] != "active":
                problems.append((i, t, "not an active ROR id"))
                continue
            cc, types = o.at[t, "country_code"], o.at[t, "types"]
            intl = any(x in types for x in ("nonprofit", "company")) or t in international
            if m.at[i, "country"] and cc != m.at[i, "country"] and not intl and t != NHS and "client:" not in r.note:
                problems.append((i, t, f"ROR country {cc} vs user {m.at[i, 'country']}"))
                continue
            set_row(
                m,
                i,
                **id_fields(t),
                canonical_name=r["name"] or o.at[t, "display_name"],
                org_type=r.org_type or typ.get(t) or org_type_from_types_field(types),
            )
        set_row(m, i, status="final", rule="16 Oct review" + (f": {r.note}" if r.note else ""), review_16_oct="yes")
    add_place_suffix(m, o)
    for p in problems:
        print("SKIPPED", p, m.at[p[0], "raw_institution"])
    ctx.write(stage, m)
    x = m[m.review_16_oct == "yes"]
    print("applied", len(x), "| learners", x.learners.sum(), "| with ID", (x.institution_id != "").sum())
