"""Rule 3a (rulebook): owner, not organisation.

IF a row is coded to a government body (a ministry, a government, a state or local government) AND the rest of the
answer also names an institution (university, college, polytechnic, academy, school, institute, hospital, clinic)
THEN the government body is the institution's owner and is not used. The institution decides the row:
  - the rest of the answer is (or contains) the name of exactly one ROR record in the learner's country -> that
    record (rule code ROR-EXACT / ROR-CONTAINED);
  - otherwise the row is released (uncoded, reason recorded) for a recorded decision (ledger batch `decisions`,
    applied by the next stage) or a web search.
Departments, directorates, services and programmes of a ministry are not institutions: they still roll up (6.5).
"""

import re

from ..core.org_types import type_from_name
from ..core.ror import Ror
from ..core.table import ensure_columns, id_fields, set_row
from ..core.text import fold

GOVERNMENT_NAME = (
    r"\b(ministry|ministere|ministerio|ministerium|government|govt|state government|local government"
    r"|county government|district council)\b"
)
INSTITUTION = r"\b(universit\w*|college|polytechnic|academy|school|institute|institut|hospital|clinic)\b"
UNIT = r"^\W*(department|directorate|division|unit|programme|program|service|laboratory)\b"
GOVERNMENT_SPAN = (
    r"\b(federal |state |national )?(ministry|ministere|ministerio)( of| de la| du| de)? [a-z ,]*?"
    r"(health|education|agriculture|defen[cs]e|justice|finance|interior|planning|labour|labor)"
    r"( and [a-z ]+?)?\b"
    r"|\b[a-z]+ (state|county|district|local) government\b|\bgovernment of [a-z ]+\b"
)


class OwnerRule:
    """Rule 3a on a mapping: the ROR names per country and the text left when the owner is removed."""

    def __init__(self, ror_dir):
        self.ror = ror = Ror(ror_dir)
        self.countries = sorted({fold(x) for x in ror.orgs.country.unique() if x}, key=lambda x: (-len(x), x))
        # ROR names per country (display, label, alias; not acronyms; not government records)
        n = ror.names
        n = n[n.ror_id.isin(ror.active) & (n.name_kind != "acronym")]
        self.names_in = {}
        for rid, name in zip(n.ror_id, n.name):
            if "government" not in ror.types(rid):
                self.names_in.setdefault(ror.cc(rid), []).append((fold(name), rid))

    def rest_of(self, text):
        """The answer without the government body's name, country names and linking words."""
        t = re.sub(GOVERNMENT_SPAN, " ", fold(text))
        t = re.sub(r"\b(ministry|ministere|government)\b", " ", t)
        for c in self.countries:
            t = re.sub(rf"\b{re.escape(c)}\b", " ", t)
        t = re.sub(r"\b(of the|of|the|under|affiliated to)\s*$", " ", re.sub(r"\s+", " ", t).strip())
        return re.sub(r"^\s*(of the|of|the)\b", " ", t).strip()

    def institution(self, rest, cc):
        """(ROR ID, rule code) of the one record in the learner's country named by the rest, else (None, '')."""
        names = self.names_in.get(cc, [])
        exact = {rid for n, rid in names if n == rest}
        if len(exact) == 1:
            return exact.pop(), "ROR-EXACT"
        inside = {rid for n, rid in names if len(n.split()) >= 2 and re.search(rf"(^| ){re.escape(n)}( |$)", rest)}
        if len(inside) == 1:
            return inside.pop(), "ROR-CONTAINED"
        return None, ""

    def apply(self, m):
        """Recode or release every row the rule covers; returns (row, answer, country, owner, outcome) per row."""
        done = []
        gov = m[
            (m.status == "final")
            & (m.institution_id != "")
            & (m.org_type == "GOVERNMENT")
            & m.canonical_name.map(lambda x: bool(re.search(GOVERNMENT_NAME, fold(x))))
        ]
        for i, r in gov.iterrows():
            rest = self.rest_of(r.raw_institution)
            if not re.search(INSTITUTION, rest) or re.search(UNIT, rest):
                continue
            owner = re.sub(r"\s*\([^()]*\)$", "", r.canonical_name)
            prior = " Earlier client decision withdrawn 17 Oct 2026" if "client" in r.rule else ""
            rid, code = self.institution(rest, r.country)
            if rid:
                name = self.ror.name(rid)
                why = f"rule 3a: {owner} is the owner, not the organisation"
                set_row(
                    m,
                    i,
                    **id_fields(rid),
                    canonical_name=name,
                    org_type=self.ror.org_type(rid),
                    status="final",
                    rule=f"{why}; {name} (ROR name in the answer)",
                    rule_code=code,
                    evidence_text=f"{why}; coded {name} (ROR name in the answer).{prior}",
                )
            else:
                rule = (
                    f"rule 3a: {owner} is the owner, not the organisation; institution not in ROR in the learner's "
                    "country -> needs a decision"
                )
                set_row(
                    m,
                    i,
                    **id_fields(""),
                    status="uncoded",
                    canonical_name=re.sub(r"\s+", " ", rest).strip().title(),
                    org_type=type_from_name(rest),
                    rule=rule,
                    rule_code="UNC-NOTFOUND",
                    evidence_text=rule + prior,
                )
            done.append((i, r.raw_institution, r.country, owner, m.at[i, "institution_id"] or "released"))
        return done


def run(ctx):
    m = ctx.read_previous(__name__)
    ensure_columns(m, "rule_code", "evidence_text")
    done = OwnerRule(ctx.ror_dir).apply(m)
    ctx.write(__name__, m)
    print("rule 3a rows:", len(done))
    for d in done:
        print("  ", d)
