"""Rulebook 9.5: the draft list of judgement calls, written by code after the decisions are applied.

python -m institution_mapping judgement-calls OUT_DIR [--all] writes OUT_DIR/judgement_calls.csv: the rows of this
round (new, or coded differently from the published mapping; --all: every row) that have more than one reasonable
reading, each with the reason and the alternative. The operator AI goes through it with the person in the loop in
the chat (CLAUDE.md, "Judgement calls"); it is also the spreadsheet of HIL.md step 4.
"""

import json
import re
from pathlib import Path

import pandas as pd

from . import precedents
from .pipeline import CODING, OUTPUT, REGISTRIES

COLUMNS = ["gid", "answer", "flag", "raw_institution", "country", "learners", "institution_id", "coded_name"]
COLUMNS += ["why_check", "rules", "precedent"]
RULES = {  # flag -> the rulebook rules a proposal rests on
    "acronym": "step 3 (acronyms), 5.2 (an acronym is never coded abroad)",
    "abroad": "5.2 (records abroad), 6.1 (programmes run abroad), 6.4 (international organisations)",
    "owner": "rule 3a (owner, not organisation), 6.6 (institutions in their own right), 6.7 (run by an NGO)",
    "two organisations": "5.5 (two organisations named; a university and its teaching hospital: 6.3), 6.1-6.3",
}
OWNER_WORDS = re.compile(
    r"\b(catholic|anglican|lutheran|adventist|methodist|baptist|presbyterian|pentecostal|evangelical|mission|missionary"
    r"|diocese|diocesan|church|ccap|elct|christian|islamic|muslim|red cross|red crescent|ngo)\b",
    re.I,
)
RUN_BY_KIND = re.compile(r"hospital|clinic|health cent|dispensary|college|school|institute", re.I)
ACRONYM = re.compile(r"[A-Z][A-Z0-9&.\-]{1,4}")  # a short answer in capitals: KNH, UDSM, MUHAS
NOT_ROLLED = "its own organisation (its own LOCAL ID)"
# codes abroad that are a reading of the answer, not its own name: roll-ups, searches, LOCAL IDs (9.5, 2)
ABROAD_RULES = {"ROR-ROLLUP", "LOCAL-ROLLUP", "ROR-SEARCH", "LOCAL"}


def acronym(r):
    """9.5 (1): coded from an acronym, by rule or by a search."""
    by_acronym = r.rule == "ROR-ACRONYM" or "acronym" in r.evidence.lower()
    if r.institution_id and (by_acronym or ACRONYM.fullmatch(r.raw_institution.strip())):
        return "acronym: other organisations may share it; alternative: not identified"
    return ""


def abroad(r, home, international):
    """9.5 (2): coded to an organisation whose country is not the learner's."""
    where = home.get(r.institution_id, "")
    if r.rule in ABROAD_RULES and r.country and where and where != r.country and r.institution_id not in international:
        return (
            f"the organisation is in {where}, the learner in {r.country} (a programme, network, country office or "
            "branch?); alternative: not identified, or an organisation in the learner's country"
        )
    return ""


def owner(r, local_parent_rows):
    """9.5 (3): an organisation run by a church, an NGO or a ministry: part of its owner, or its own organisation?"""
    if (r.raw_institution, r.country) in local_parent_rows:
        return (
            f"run by the NGO in ror_parent_ids; alternative: coded to the NGO itself (rule 6.7 keeps it {NOT_ROLLED})"
        )
    if r.institution_id and OWNER_WORDS.search(r.raw_institution) and RUN_BY_KIND.search(r.raw_institution):
        if r.rule in ("ROR-ROLLUP", "LOCAL-ROLLUP"):
            return f"coded to its owner (rolled up); alternative: {NOT_ROLLED}"
        return "run by a church or an NGO: coded as its own organisation; alternative: coded to its owner"
    return ""


def two_organisations(r):
    """9.5 (4): the answer names two organisations; rule 5.5 chose one."""
    if "two organisations named" in r.evidence:
        return "two organisations named; rule 5.5 chose this one; alternative: the other one, or not identified"
    return ""


def homes(out):
    """Organisation country per ID: ROR records (the run's snapshot) and LOCAL IDs (the run's register)."""
    o = pd.read_csv(out / "work" / "ror" / "ror_orgs.csv", dtype=str, keep_default_na=False)
    home = dict(zip(o.ror_id, o.country_code))
    reg = out / "work" / "coding" / "registries" / "local_ids.csv"
    reg = pd.read_csv(reg if reg.exists() else REGISTRIES / "local_ids.csv", dtype=str, keep_default_na=False)
    home |= {i: c for i, c in zip(reg.local_id, reg.country) if c and c != "*"}
    return home


def internationals():
    """IDs that are coded for learners in any country by rule (5.2, 6.4, 10.1): no judgement call."""
    settings = json.loads((CODING / "coding_rules.json").read_text(encoding="utf-8"))
    nets = pd.read_csv(REGISTRIES / "international_networks.csv", dtype=str, keep_default_na=False)
    return set(settings["international"]["ror_ids"]) | set(nets.international_ror_id) | set(nets.member_ror_id)


def this_round(m):
    """Rows that are new, or whose ID or status differ from the published mapping."""
    files = sorted(OUTPUT.glob("institution_mapping_*.xlsx"))
    if not files:
        return m
    p = pd.read_excel(files[-1], sheet_name="mapping", dtype=str, keep_default_na=False)
    before = {(a, c): (i, s) for a, c, i, s in zip(p.raw_institution, p.country, p.institution_id, p.status)}
    now = zip(m.raw_institution, m.country, m.institution_id, m.status)
    return m[[before.get((a, c)) != (i, s) for a, c, i, s in now]]


def already_judged():
    """(answer, country) of rows a person has decided already (client or human-review decision)."""
    d = pd.read_csv(CODING / "decisions.csv", dtype=str, keep_default_na=False)
    d = d[d.rationale_type.isin(["client decision", "human-review decision"])]
    return set(zip(d.raw_institution, d.country))


def draft(m, home, international, local_parent_rows, judged, precedents=None):
    """One row per flagged mapping row (the first flag that applies, in the order of rule 9.5), with the rules the
    proposal rests on and, with `precedents` (precedents.Precedents), how similar answers were coded before."""
    rows = []
    for r in m[m.status == "coding complete"].itertuples(index=False):
        if (r.raw_institution, r.country) in judged:
            continue
        for flag, why in (
            ("acronym", acronym(r)),
            ("abroad", abroad(r, home, international)),
            ("owner", owner(r, local_parent_rows)),
            ("two organisations", two_organisations(r)),
        ):
            if why:
                before = precedents.summary(r.raw_institution, r.country, r.institution_id) if precedents else ""
                rows.append(
                    [0, "", flag, r.raw_institution, r.country, r.learners, r.institution_id, r.canonical_name, why]
                    + [RULES[flag], before]
                )
                break
    d = pd.DataFrame(rows, columns=COLUMNS)
    d["n"] = pd.to_numeric(d.learners, errors="coerce").fillna(0)
    d = d.sort_values(["flag", "n"], ascending=[True, False]).drop(columns="n")
    d["gid"] = range(1, len(d) + 1)  # row numbers, for tools/add_decisions.py
    return d


def run(out_dir, every_row=False):
    """Write OUT_DIR/judgement_calls.csv and print the count per flag."""
    out = Path(out_dir).resolve()
    if not (out / "mapping_final.csv").exists():
        raise SystemExit(f"{out / 'mapping_final.csv'} is missing: run the mapping into {out} first")
    m = pd.read_csv(out / "mapping_final.csv", dtype=str, keep_default_na=False)
    rows = m if every_row else this_round(m)
    lp = pd.read_csv(REGISTRIES / "local_parents.csv", dtype=str, keep_default_na=False)
    names = set(zip(lp.name, lp.country))
    local_parent_rows = {(a, c) for a, c, n in zip(m.raw_institution, m.country, m.canonical_name) if (n, c) in names}
    d = draft(rows, homes(out), internationals(), local_parent_rows, already_judged(), precedents.load(out))
    d.to_csv(out / "judgement_calls.csv", index=False)
    print(f"rows considered: {len(rows)} ({'every row' if every_row else 'new or coded differently'})")
    print(d.flag.value_counts().to_string() if len(d) else "no judgement calls")
    print(f"-> {out / 'judgement_calls.csv'}")
