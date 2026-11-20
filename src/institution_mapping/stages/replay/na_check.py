"""Replay of the 16 Oct re-check of NOT_APPLICABLE (ledger batch na_check_16oct; rulebook 4.1-4.2).

NOT_APPLICABLE = the person has no organisation. Answers that name a kind of organisation, a place, a person or junk
become NOT_SPECIFIED (target NS); real organisations hidden in NOT_APPLICABLE get their name back, and a ROR ID where
one exists (target NAME = name only, else the ROR ID).
"""

from ...core.table import set_row


def run(ctx):
    m = ctx.read_previous(__name__)
    batch = ctx.ledger.batch("na_check_16oct")
    to_ns = set(batch.query("target == 'NS'").clean)
    to_org = {
        (r.clean, r.country): (r["name"], r.org_type, "" if r.target == "NAME" else r.target)
        for _, r in batch.query("target != 'NS'").iterrows()
    }
    key = m.raw_institution.str.strip().str.lower()
    in_input = set(zip(key, m.country))  # decisions for answers not in this input are skipped
    to_org = {k: v for k, v in to_org.items() if k in in_input}
    to_ns &= set(key)
    na = m.org_type == "NOT_APPLICABLE"
    # stage 4 types listed unnamed answers NOT_SPECIFIED itself (rule 4.2); the decision still gives the evidence
    stage4_ns = (m.org_type == "NOT_SPECIFIED") & m.rule.str.startswith("step 4")
    m["na_check_16_oct"] = ""
    ns_idx = m[(na | stage4_ns) & key.isin(to_ns)].index
    m.loc[ns_idx, "org_type"] = "NOT_SPECIFIED"
    m.loc[ns_idx, "rule"] = "16 Oct NA check: no organisation not stated -> NOT_SPECIFIED"
    m.loc[ns_idx, "na_check_16_oct"] = "NS"
    for (k, cc), (name, otype, rid) in to_org.items():
        idx = m[na & (key == k) & (m.country == cc)].index
        assert len(idx) == 1, k
        set_row(
            m,
            idx[0],
            canonical_name=name,
            org_type=otype,
            institution_id=rid,
            id_kind="ROR" if rid else "",
            ror_url=f"https://ror.org/{rid}" if rid else "",
            status="final" if rid else "uncoded",
            rule="16 Oct NA check: real organisation",
            na_check_16_oct="ORG",
        )
    missing = to_ns - set(key[ns_idx])
    assert not missing, missing
    ctx.write(__name__, m)
    c = m[m.na_check_16_oct != ""]
    print(c.groupby("na_check_16_oct").agg(rows=("learners", "size"), learners=("learners", "sum")).to_string())
