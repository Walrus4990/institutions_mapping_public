"""The final mapping (OUT/mapping_final.csv): output conventions, rule codes, ROR parents and the checks that stop
the run.

1. org_type belongs to the organisation: every row with one ID carries one org_type, except teaching-hospital rows
   (TEACHING_HOSPITAL). Types set by hand: ledger batches org_type_17oct and org_type.
2. Coded names: two ROR IDs with the same ROR name get " (Country)", or " (City, Country)" when they are in one
   country; a teaching hospital on its university's record is "<ROR name> Teaching Hospital" (rulebook 6.3, 8.1).
3. Answers saying the person has no organisation are NOT_APPLICABLE; a rules-engine suggestion is not a decision:
   the row is uncoded, the candidate kept in the evidence.
4. The working column `rule` becomes rule (code), rule_description and evidence (rule_codes.py); a code and
   evidence recorded by a stage (rule 3a, decisions) are kept.
5. ror_parent_ids: every chain of ROR parents from the nearest to the top, IDs separated by "/", chains by "|";
   empty for rows without a ROR ID, except LOCAL IDs run by an NGO with a ROR record (local_parents.csv, rule 6.7).
6. status: "coding complete" or "not identified".
A row that breaks a consistency check (rulebook 3.4-3.6) or carries personal data (8.8) stops the run.
"""

import html
import re

import pandas as pd

from ..core.personal_data import personal_data_in_table
from ..core.ror import Ror
from ..core.text import key, same_answer_groups, strip_accents, words
from .rule_codes import DESCRIPTION, evidence, rule_code

COLUMNS = [
    "raw_institution",
    "country",
    "learners",
    "canonical_name",
    "institution_id",
    "id_kind",
    "ror_url",
    "ror_parent_ids",
    "org_type",
    "status",
    "rule",
    "rule_description",
    "evidence",
]
STATUS_OUT = {"final": "coding complete", "uncoded": "not identified"}
COUNTRY_SHORT = {"Tanzania, United Republic of": "Tanzania"}
NO_AFFILIATION = re.compile(r"\b(?:not affiliated|no affiliation|unaffiliated)\b", re.I)


def name_key(x):
    """A name compared without capitals, accents and punctuation."""
    return words(strip_accents(x.lower()))


def one_org_type_per_id(m, by_hand):
    """Apply the org_types set by hand and check one org_type per ID (rule 3.3)."""
    for i in m.index[m.institution_id.isin(by_hand) & (m.org_type != "TEACHING_HOSPITAL")]:
        m.at[i, "org_type"] = by_hand[m.at[i, "institution_id"]]
    c = m[(m.institution_id != "") & (m.org_type != "TEACHING_HOSPITAL")]
    mixed = c.groupby("institution_id").org_type.agg(lambda s: set(s)).map(len) > 1
    assert not mixed.any(), mixed[mixed].index.tolist()
    assert not (c.org_type == "").any(), c[c.org_type == ""].institution_id.tolist()


def shared_ror_names(m, o):
    """Rows with the plain ROR name of an ID whose ROR name another ID in the output shares get a place suffix;
    rows that already carry a bracket (or a teaching-hospital or campus name) keep theirs."""
    ids = m[m.id_kind == "ROR"].institution_id.drop_duplicates()
    grp = pd.DataFrame({"id": ids, "k": ids.map(lambda x: name_key(o.at[x, "display_name"]))})
    grp = grp[grp.k.duplicated(keep=False)]
    for k, g in grp.groupby("k"):
        same_cc = g.id.map(lambda x: o.at[x, "country_code"]).duplicated(keep=False)
        for rid, sc in zip(g.id, same_cc):
            country = COUNTRY_SHORT.get(o.at[rid, "country"], o.at[rid, "country"])
            place = f"{o.at[rid, 'city']}, {country}" if sc else country
            for i in m.index[m.institution_id == rid]:
                if name_key(m.at[i, "canonical_name"]) == k:
                    done = m[(m.institution_id == rid) & m.canonical_name.str.endswith(")")].canonical_name
                    m.at[i, "canonical_name"] = done.iloc[0] if len(done) else f"{o.at[rid, 'display_name']} ({place})"


def teaching_hospitals(m, o, own_record):
    """A teaching hospital with its own ROR record uses it (ledger batch own_teaching_hospital_17oct); one on a
    university's record (not itself a hospital) is named "<ROR name> Teaching Hospital"."""
    for i in m.index[(m.org_type == "TEACHING_HOSPITAL") & m.institution_id.isin(own_record)]:
        rid = own_record[m.at[i, "institution_id"]]
        m.at[i, "institution_id"], m.at[i, "ror_url"] = rid, f"https://ror.org/{rid}"
        m.at[i, "canonical_name"] = o.at[rid, "display_name"]
        m.at[i, "rule"] += " | teaching hospital has its own ROR record"
    for i in m.index[(m.org_type == "TEACHING_HOSPITAL") & (m.id_kind == "ROR")]:
        rid = m.at[i, "institution_id"]
        if "healthcare" not in o.at[rid, "types"] and "hospital" not in o.at[rid, "display_name"].lower():
            m.at[i, "canonical_name"] = f"{o.at[rid, 'display_name']} Teaching Hospital"


def open_rows(m):
    """No-affiliation answers are NOT_APPLICABLE; suggestions become uncoded (rulebook step 7); the coded name of a
    not-identified row has HTML entities decoded (rule 8.3)."""
    for i in m.index[(m.institution_id == "") & m.raw_institution.str.contains(NO_AFFILIATION)]:
        m.loc[i, ["org_type", "canonical_name", "status", "rule"]] = [
            "NOT_APPLICABLE",
            "",
            "final",
            "no-affiliation phrase -> NOT_APPLICABLE",
        ]
    for i in m.index[m.status == "suggested"]:
        rule = m.at[i, "rule"].replace(" (suggested)", "")
        m.at[i, "rule"] = f"not decided by the rules; candidate for review: {m.at[i, 'suggestion']} ({rule})"
        m.loc[i, ["status", "institution_id", "id_kind", "ror_url"]] = ["uncoded", "", "", ""]
    for i in m.index[m.status == "uncoded"]:
        m.at[i, "canonical_name"] = html.unescape(m.at[i, "canonical_name"])


def parent_ids(m, ror, register, local_parents):
    """Fill ror_parent_ids: ROR's parent chains, and the NGO parent of LOCAL IDs (rule 6.7)."""
    chains = {
        rid: "|".join("/".join(c) for c in ror.parent_chains(rid)) for rid in set(m.institution_id[m.id_kind == "ROR"])
    }
    m["ror_parent_ids"] = [chains.get(i, "") if k == "ROR" else "" for i, k in zip(m.institution_id, m.id_kind)]
    for r in local_parents.itertuples(index=False):
        lid = register.find(r.name, r.country)
        assert r.parent_ror_id in ror.orgs.index, r.parent_ror_id
        up = ror.parent_chains(r.parent_ror_id)
        if lid:
            m.loc[m.institution_id == lid, "ror_parent_ids"] = (
                "|".join(r.parent_ror_id + "/" + "/".join(c) for c in up) if up else r.parent_ror_id
            )


def same_answer_conflicts(m):
    """Rule 3.6: rows of one same-answer group with different codes (org_type counts only on decided rows: on a
    not-identified row it is a guess)."""
    groups = same_answer_groups(m)
    differs = (
        m.assign(_k=groups)
        .groupby("_k")
        .apply(
            lambda g: (
                g.assign(_t=g.org_type.where(g.status == "final", ""))[["institution_id", "status", "_t"]]
                .drop_duplicates()
                .shape[0]
                > 1
            ),
            include_groups=False,
        )
    )
    return differs.reindex(groups).fillna(False).values


def registry_conflicts(m, ror, reg):
    """Rule 7.6: ROR and the LOCAL register are used together. Returns two row masks:
    rows on a LOCAL ID whose current or former name is the name of an active ROR record in the same country, and
    not-identified rows whose answer is the name of a LOCAL ID in their country (unless decided UNC-AMBIGUOUS)."""
    n = ror.names
    n = n[n.ror_id.isin(ror.active) & (n.name_kind != "acronym")]
    ror_keys = {(key(name), ror.cc(rid)) for rid, name in zip(n.ror_id, n.name)}
    act = reg.df[reg.df.status == "active"]
    dup = {
        r.local_id
        for r in act.itertuples(index=False)
        for x in [r.name] + [y for y in r.other_names.split(" | ") if y]
        if (key(x), r.country) in ror_keys
    }
    on_dup = m.institution_id.isin(dup)
    names = {}
    open_local = []
    for r in m.itertuples(index=False):
        if r.status != "uncoded" or r.rule == "UNC-AMBIGUOUS":
            open_local.append(False)
            continue
        if r.country not in names:
            names[r.country] = reg.names_in(r.country)
        open_local.append(key(r.raw_institution) in names[r.country])
    return on_dup, pd.Series(open_local, index=m.index)


def check(m, ror, reg):
    """Stop the run on a row that breaks the rulebook's consistency rules, listing the rows (rulebook step 8)."""
    kind = m.institution_id.map(lambda x: "" if not x else ("LOCAL" if x.startswith("LOCAL-") else "ROR"))
    url = m.apply(lambda r: f"https://ror.org/{r.institution_id}" if r.id_kind == "ROR" else "", axis=1)
    checks = {
        "rule code not in the rulebook list": m.rule_description.isna(),
        "uncoded row without an UNC code / UNC code on a decided row": (m.status == "uncoded")
        != m.rule.str.startswith("UNC"),
        "ID without a ROR/LOCAL code, or such a code without an ID": (m.institution_id != "")
        != m.rule.str.match(r"^(ROR|LOCAL)"),
        "ROR code on a LOCAL ID, or LOCAL code on a ROR ID": (m.rule.str.startswith("ROR") & (m.id_kind != "ROR"))
        | (m.rule.str.startswith("LOCAL") & (m.id_kind != "LOCAL")),
        "id_kind does not match the ID": m.id_kind != kind,
        "ror_url does not match the ID": m.ror_url != url,
        "NA/NS/TYPE row with a coded name": m.rule.isin(["NA", "NS", "TYPE"]) & (m.canonical_name != ""),
        "same answer (rule 3.6) with different codes": same_answer_conflicts(m),
    }
    on_dup, open_local = registry_conflicts(m, ror, reg)
    checks["LOCAL ID with the name of a ROR record in its country (rule 7.6)"] = on_dup
    checks["not identified, but the name of a LOCAL ID in its country (rule 7.6)"] = open_local
    bad = {k: m.index[v].tolist()[:10] for k, v in checks.items() if v.any()}
    for k, v in checks.items():
        if v.any():
            print("STOP:", k)
            print(
                m.loc[v, ["raw_institution", "country", "institution_id", "status", "org_type", "rule"]]
                .head(40)
                .to_string()
            )
    assert not bad, bad


def run(ctx):
    m = ctx.read_previous(__name__, dtype=str)
    ror = Ror(ctx.ror_dir)
    o = ror.orgs
    led = ctx.ledger
    by_hand = led.batch("org_type", required=False)
    assert not by_hand.rationale_type.isin(["", "none recorded"]).any(), "org_type decision without a rationale"
    org_types = {r.target: r.org_type for r in led.batch("org_type_17oct").itertuples(index=False)}
    org_types.update({r.target: r.org_type for r in by_hand.itertuples(index=False)})
    one_org_type_per_id(m, org_types)
    shared_ror_names(m, o)
    teaching_hospitals(
        m, o, {r.ror_id: r.target for r in led.batch("own_teaching_hospital_17oct").itertuples(index=False)}
    )
    open_rows(m)
    m["evidence"] = m.rule.map(evidence)
    names = o.display_name
    m["rule"] = [rule_code(r, names) for r in m.itertuples(index=False)]
    local_parents = pd.read_csv(ctx.registry("local_parents.csv"), dtype=str, keep_default_na=False)
    parent_ids(m, ror, ctx.register(), local_parents)
    for recorded, col in (("rule_code", "rule"), ("evidence_text", "evidence")):
        if recorded in m:
            k = m[recorded] != ""
            m.loc[k, col] = m.loc[k, recorded]
    m["rule_description"] = m.rule.map(DESCRIPTION)
    check(m, ror, ctx.register())
    assert set(m.status) <= set(STATUS_OUT), set(m.status) - set(STATUS_OUT)
    m["status"] = m.status.map(STATUS_OUT)
    hits = personal_data_in_table(m[COLUMNS], ctx.settings["personal_data"], "mapping")
    assert not hits, f"personal data in the mapping (rulebook step 8, point 6): {hits[:20]}"
    ctx.write(__name__, m[COLUMNS])
    m[COLUMNS].to_csv(ctx.o("mapping_final.csv"), index=False)
    print(m.rule.value_counts().to_dict())
