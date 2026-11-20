"""Applies the decisions recorded in ledger batch `decisions`, then rules 3.6 and 6.4.

This is the one way to add a decision (rulebook step 7): a web search, a review or a client decision becomes a row
of decisions.csv in batch `decisions` (see tools/add_decisions.py). The replay stages apply the passes of 16-17 Oct
with their own conventions and take no new decisions.

A decision row: raw_institution, country, target, name, org_type, org_country, source/note, rationale_type,
rationale, and optionally rule_code and evidence_text (written to the mapping as given, else derived from target).
  target   <ROR ID>     the organisation's ROR record (name: optional coded name, e.g. a campus)
           TH:<ROR ID>  teaching hospital on its university's ROR record (rulebook 6.3); name required
           LOCAL        confirmed to exist, not in ROR (rulebook 7.1); name required; org_country = the
                        organisation's country ("*" = an international organisation: one ID in every country)
           NS / NA      NOT_SPECIFIED / NOT_APPLICABLE (rulebook 4.1-4.2)
           TYPE:<type>  type only (rulebook 4.3)
           UNC          searched, stays uncoded; the reason goes in note
Safeguards (a decision that fails one is refused and reported in decisions_report.csv, never half-applied):
  - it needs a rationale (rationale_type other than 'none recorded'): a source, a rule, or a named client decision;
  - it applies only to a row that is still uncoded, unless extra contains 'override' (a deliberate correction);
  - a ROR record in another country than the learner's is refused unless rule 5.2 allows it (an international
    organisation in coding_rules.json, a ROR nonprofit or company record, or "rule 5.2" in the rationale);
  - a LOCAL decision reuses the organisation's existing LOCAL ID (register lookup by name and country).
"""

import os

import pandas as pd

from ..core.org_types import type_from_name
from ..core.ror import Ror
from ..core.table import coded_lookups, ensure_columns, id_fields, set_row
from ..core.text import key, pipeline_key, same_answer_groups

DEFAULT_CODE = {"NS": "NS", "NA": "NA", "UNC": "UNC-NOTFOUND", "LOCAL": "LOCAL"}
OUTCOME = [
    "canonical_name",
    "institution_id",
    "id_kind",
    "ror_url",
    "org_type",
    "status",
    "rule",
    "rule_code",
    "evidence_text",
]
REPORT_COLS = ["id", "raw_institution", "country", "target", "result", "reason"]


class Refused(Exception):
    """A decision that fails a safeguard."""


def default_rule_code(target):
    """The rule code of a decision that records none (rulebook 3.5)."""
    if target.startswith("TYPE:"):
        return "TYPE"
    if target.startswith("TH:"):
        return "ROR-ROLLUP"
    return DEFAULT_CODE.get(target, "ROR-SEARCH")


def append_note(text, note):
    """Text with a note appended after ' | '."""
    return (text + " | " if text else "") + note


class Decisions:
    """The ledger decisions applied to one mapping."""

    def __init__(self, m, ror, register, international_ids):
        self.m, self.ror, self.reg, self.intl = m, ror, register, international_ids
        self.canon, self.typ = coded_lookups(m)
        self.keys = m.raw_institution.map(pipeline_key)
        self.report = []

    def note(self, r, result, reason=""):
        """Record the result of a decision for decisions_report.csv."""
        self.report.append(
            dict(
                id=r.id,
                raw_institution=r.raw_institution,
                country=r.country,
                target=r.target,
                result=result,
                reason=reason,
            )
        )

    def row(self, r):
        """The mapping row of a decision: same answer and country, else the same answer under the pipeline key (3.6)."""
        m = self.m
        idx = m.index[(m.raw_institution == r.raw_institution) & (m.country == r.country)]
        if len(idx) == 0:
            idx = m.index[(self.keys == pipeline_key(r.raw_institution)) & (m.country == r.country)]
        return idx[0] if len(idx) else None

    def outcome(self, r, i):
        """The new values of the row for this decision (raises Refused)."""
        m, t = self.m, r.target
        new = dict(**id_fields(""), canonical_name="", org_type=m.at[i, "org_type"], status="final")
        if t in ("NS", "NA"):
            new["org_type"] = "NOT_SPECIFIED" if t == "NS" else "NOT_APPLICABLE"
        elif t.startswith("TYPE:"):
            new["org_type"] = t[5:]
        elif t == "UNC":
            coded = bool(m.at[i, "institution_id"])
            name = m.at[i, "canonical_name"]
            if coded:  # a correction of a coded row: the coded name was the record's; use the answer (rule 8.3)
                name = " ".join(r.raw_institution.split()).strip(" .,;-")
                name = name.upper() if " " not in name and name.islower() and len(name) <= 6 else name
            new.update(
                canonical_name=name, status="uncoded", org_type=r.org_type or ("" if coded else m.at[i, "org_type"])
            )
        elif t == "LOCAL":
            new.update(self.local_outcome(r))
        else:
            new.update(self.ror_outcome(r))
        return new

    def local_outcome(self, r):
        """A LOCAL decision: the organisation's existing LOCAL ID, or a new one (or the ROR ID that replaced it)."""
        if not r["name"]:
            raise Refused("LOCAL decision without the organisation's name")
        cc = "" if r.org_country == "*" else (r.org_country or r.country)
        lid = self.reg.issue(r["name"], cc, source=r.source or r.rationale)
        if self.reg.status(lid) == "retired":
            lid = self.reg.replaced_by(lid)
        if lid.startswith("LOCAL-"):
            return dict(
                **id_fields(lid),
                canonical_name=r["name"],
                org_type=r.org_type or self.typ.get(lid) or type_from_name(r["name"]),
            )
        return dict(
            **id_fields(lid),
            canonical_name=self.canon.get(lid) or self.ror.name(lid),
            org_type=r.org_type or self.typ.get(lid) or self.ror.org_type(lid),
        )

    def ror_outcome(self, r):
        """A ROR ID or TH:<ROR ID> decision, refused for a record abroad that rule 5.2 does not allow."""
        ror, t = self.ror, r.target
        th = t.startswith("TH:")
        rid = t[3:] if th else t
        if rid not in ror.active:
            raise Refused(f"{rid} is not an active ROR record")
        abroad_ok = rid in self.intl or {"nonprofit", "company"} & set(ror.types(rid)) or "rule 5.2" in r.rationale
        if r.country and ror.cc(rid) != r.country and not abroad_ok:
            raise Refused(f"ROR record is in {ror.cc(rid)}, learner in {r.country}: not allowed by rule 5.2")
        if th and not r["name"]:
            raise Refused("teaching hospital decision without its name")
        org_type = (
            "TEACHING_HOSPITAL"
            if th
            else (r.org_type or self.typ.get(rid) or ror.org_type(rid) or type_from_name(ror.name(rid)))
        )  # rule 3.3 point 2
        return dict(
            **id_fields(rid), canonical_name=r["name"] or self.canon.get(rid) or ror.name(rid), org_type=org_type
        )

    def apply(self, r):
        """Apply one decision to its row, or record why it is not applied."""
        m = self.m
        i = self.row(r)
        if i is None:
            return self.note(r, "not in this input")
        override = "override" in r.extra
        if m.at[i, "raw_institution"] != r.raw_institution and m.at[i, "status"] != "uncoded" and not override:
            return self.note(r, "same answer already decided", f"as '{m.at[i, 'raw_institution']}'")
        try:
            if r.rationale_type in ("", "none recorded"):
                raise Refused("no rationale recorded")
            if m.at[i, "status"] != "uncoded" and not override:
                raise Refused(
                    f"row is already decided ({m.at[i, 'rule']}); use extra=override for a deliberate correction"
                )
            new = self.outcome(r, i)
        except Refused as e:
            return self.note(r, "refused", str(e))
        t, why = r.target, (r.note or r.source or r.rationale)
        set_row(
            m,
            i,
            **new,
            decision_applied=r.id,
            rule=f"web search: {why}" if t != "UNC" else f"search (country + name): {why}",
        )
        # rule code and evidence: as recorded with the decision, else the code that fits the target (rulebook 3.5)
        code = r.get("rule_code", "") or default_rule_code(t)
        if code == "LOCAL" and m.at[i, "id_kind"] == "ROR":  # the LOCAL ID was retired for its ROR record
            code = "ROR-SEARCH"
        set_row(m, i, rule_code=code, evidence_text=r.get("evidence_text", "") or m.at[i, "rule"])
        self.note(r, "applied")


def ror_names_in(ror):
    """{(name key, country): {active ROR IDs}} over display names, labels and aliases."""
    n = ror.names
    n = n[n.ror_id.isin(ror.active) & (n.name_kind != "acronym")]
    out = {}
    for rid, name in zip(n.ror_id, n.name):
        out.setdefault((key(name), ror.cc(rid)), set()).add(rid)
    return out


def retire_locals_in_ror(m, reg, ror):
    """Rulebook 7.6: a LOCAL ID in use whose current or former name is the name of exactly one active ROR record in its
    country is that organisation (a LOCAL ID only stands in for an organisation without a ROR record, and no LOCAL
    name equals a ROR name in its country, 7.4): its rows move to the ROR record and the LOCAL ID is retired. A name
    held by several ROR records is left for the check in stage finalise. Returns {LOCAL ID: ROR ID}."""
    names = ror_names_in(ror)
    act = reg.df[(reg.df.status == "active") & reg.df.local_id.isin(set(m.institution_id)) & (reg.df.country != "")]
    moved = {}
    for r in act.itertuples(index=False):
        hits = set().union(
            *(names.get((key(x), r.country), set()) for x in [r.name] + [y for y in r.other_names.split(" | ") if y])
        )
        if len(hits) != 1:
            continue
        rid = hits.pop()
        rule = f"rule 7.6: {r.local_id} ({r.name}) is in ROR as {ror.name(rid)}; the LOCAL ID is retired"
        for i in m.index[m.institution_id == r.local_id]:
            set_row(
                m,
                i,
                **id_fields(rid),
                canonical_name=ror.name(rid),
                rule=rule,
                rule_code="ROR-SEARCH",
                evidence_text=rule,
            )
            if m.at[i, "org_type"] != "TEACHING_HOSPITAL":
                m.at[i, "org_type"] = ror.org_type(rid) or m.at[i, "org_type"]
        reg.retire(r.local_id, rid, "organisation is in ROR (rule 7.6)")
        moved[r.local_id] = rid
    return moved


def code_local_names(m, reg, typ):
    """Rulebook 7.6: a not-identified answer that no person has decided, and that is the current or former name of
    exactly one active LOCAL ID in the learner's country, gets that ID: ROR and the LOCAL register are searched
    together. Returns the number of rows coded."""
    names, n = {}, 0
    todo = m[
        (m.status == "uncoded")
        & (m.institution_id == "")
        & (m.decision_applied == "")
        & ~m.org_type.isin(["NOT_APPLICABLE", "NOT_SPECIFIED"])
    ]
    for i, r in todo.iterrows():
        if r.country not in names:
            names[r.country] = reg.names_in(r.country)
        ids = names[r.country].get(key(r.raw_institution), set())
        if len(ids) != 1:
            continue
        lid = next(iter(ids))
        name = reg.df.loc[reg.df.local_id == lid, "name"].iloc[0]
        rule = f"rule 7.6: the name of LOCAL ID {lid} ({name}) in the learner's country"
        set_row(
            m,
            i,
            **id_fields(lid),
            canonical_name=name,
            status="final",
            org_type=typ.get(lid) or type_from_name(name),
            rule=rule,
            rule_code="LOCAL",
            evidence_text=rule,
            decision_applied="local name",
        )
        n += 1
    return n


def code_same_answers(m):
    """Rulebook 3.6: answers in one country that clean to the same text or have the same pipeline key are the same
    answer. An open row (uncoded or suggested) takes the outcome of its decided twins IF they agree on one ID (or,
    without an ID, on one org_type); the twin with the most learners is followed. Twins decided differently are left
    as they are; the finalise stage stops the run and lists them."""
    n = 0
    for _, g in m.groupby(same_answer_groups(m)):
        done, open_ = g[g.status == "final"], g[g.status.isin(["uncoded", "suggested"])]
        if len(g) < 2 or done.empty or open_.empty:
            continue
        if done.institution_id.nunique() != 1 or (done.institution_id.iloc[0] == "" and done.org_type.nunique() != 1):
            continue
        src = (
            done.assign(_n=done.learners.astype(int))
            .sort_values(["_n", "raw_institution"], ascending=[False, True], kind="stable")
            .iloc[0]
        )
        note = f"same answer as '{src.raw_institution}' (differs only in capitals, accents or punctuation; rule 3.6)"
        for i in open_.index:
            set_row(m, i, **{c: src[c] for c in OUTCOME})
            set_row(
                m,
                i,
                rule=append_note(src.rule, note),
                evidence_text=append_note(src.evidence_text, note),
                decision_applied="twin",
            )
            n += 1
    return n


def roll_up_networks(m, net, ror, canon):
    """Rulebook 6.4: an international organisation with ROR records in several countries. IF ROR has a record of it in
    the learner's country THEN that record (the one already chosen stays when it is in the learner's country, or when
    there are several there); OTHERWISE the record for the whole organisation (its headquarters, or the main member's
    record; international_networks.csv, built by tools/make_networks.py)."""
    family = {}  # any record of the organisation -> (name, headquarters, records)
    for name, g in net.groupby("network"):
        hq = g.international_ror_id.iloc[0]
        records = [hq] + g.member_ror_id.tolist()
        for rid in records:
            family[rid] = (name, hq, records)
    moved = 0
    for i in m.index[(m.id_kind == "ROR") & m.institution_id.isin(list(family))]:
        cc, old = m.at[i, "country"], m.at[i, "institution_id"]
        name, hq, records = family[old]
        if cc and ror.cc(old) == cc:
            continue
        in_country = (
            [rid for rid in records if ror.cc(rid) == cc] if cc else []
        )  # no learner country: the whole organisation
        if len(in_country) > 1:
            continue
        new_id = in_country[0] if in_country else hq
        if new_id == old:
            continue
        why = "the record in the learner's country" if in_country else "the record for the whole organisation"
        note = f"rule 6.4: {name}, {why} ({new_id}; was {old}, {ror.cc(old)})"
        set_row(
            m,
            i,
            institution_id=new_id,
            ror_url=f"https://ror.org/{new_id}",
            canonical_name=canon.get(new_id) or ror.name(new_id),
            rule=m.at[i, "rule"] + " | " + note,
            rule_code="ROR-ROLLUP",
            evidence_text=append_note(m.at[i, "evidence_text"], note),
        )
        if ror.org_type(new_id):
            m.at[i, "org_type"] = ror.org_type(new_id)
        moved += 1
    return moved


def run(ctx):
    m = ctx.read_previous(__name__)
    ror = Ror(ctx.ror_dir)
    reg = ctx.register()
    d = ctx.ledger.batch("decisions", required=False)
    m["decision_applied"] = ""
    ensure_columns(m, "rule_code", "evidence_text")
    decisions = Decisions(m, ror, reg, set(ctx.settings["international"]["ror_ids"]))
    for _, r in d.iterrows():
        decisions.apply(r)
    print("rule 7.6 LOCAL IDs in ROR, retired:", retire_locals_in_ror(m, reg, ror))
    print("rule 7.6 answers coded to the LOCAL ID of their name:", code_local_names(m, reg, decisions.typ))
    print("rule 3.6 same-answer twins coded:", code_same_answers(m))
    if os.path.exists(ctx.registry("international_networks.csv")):
        net = pd.read_csv(ctx.registry("international_networks.csv"), dtype=str, keep_default_na=False)
        print("rule 6.4 international organisations:", roll_up_networks(m, net, ror, decisions.canon), "rows moved")
    reg.save()
    ctx.write(__name__, m)
    rep = pd.DataFrame(decisions.report, columns=REPORT_COLS)
    rep.to_csv(ctx.o("decisions_report.csv"), index=False)
    new_ids = [x["local_id"] for x in reg.new]
    print(f"decisions: {len(d)} | {rep.result.value_counts().to_dict()} | new LOCAL IDs: {new_ids}")
