"""Replay of the client's check of the suggested rows (16 Oct 2026).

Ledger batches: client_check_16oct (Y = accept the suggested ID), client_corrections_16oct (the client's correction
of a row; target NO_ID = no ID), name_fixes_16oct (coded names corrected by hand).
Also: uncoded names keep the learner's capitals for acronym-like words (ABI, CSIR-ARI), and two IDs sharing a coded
name get the organisation's country.
"""

import re
from collections import Counter

from ...core import ror as ror_snapshot
from ...core.ledger import present
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import coded_lookups, id_fields, row_of, set_row

SMALL_WORDS_TITLE = r"(?<=\S )(Of|For|And|De|Del|Des|La|Le|In|At|On|Et)(?= )"


class AcronymCase:
    """Which words of an answer are acronyms, judged by how ROR writes each word."""

    def __init__(self, ror_names):
        self.upper, self.title = Counter(), Counter()
        for t in ror_names:
            for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", t):
                (self.upper if w.isupper() and len(w) >= 2 else self.title)[w.lower()] += 1

    def is_acronym(self, w):
        """True if ROR writes the word in capitals more often than not (or a short word ROR never uses)."""
        lo = w.lower()
        return self.upper[lo] > self.title[lo] or (self.upper[lo] + self.title[lo] == 0 and len(w) <= 5)

    def acronyms(self, raw):
        """The words of an answer that are acronyms."""
        toks = [t for t in re.findall(r"[A-Za-z0-9]+", raw) if len(t) >= 2 and not t.isdigit()]
        caps = [t for t in toks if t.isupper()]
        paren = set(re.findall(r"\(([A-Z][A-Z0-9]{1,9})\)", raw))  # (DAWASA)
        if not toks:  # one letter or digits only: no acronym
            return set()
        if len(re.findall(r"[A-Za-z0-9]+", raw)) == 1:  # one word: an acronym candidate (ABI, aiims)
            return {toks[0].upper()} if len(toks[0]) <= 6 and (toks[0].isupper() or toks[0].islower()) else set()
        if len(caps) < len(toks):  # mixed case: the learner marked the acronyms
            return set(caps)
        return {t for t in caps if self.is_acronym(t)} | paren  # all capitals: only words ROR treats as acronyms

    def restore(self, name, raw):
        """The coded name with the answer's acronyms in capitals and small words in lower case."""
        for a in sorted(self.acronyms(raw), key=lambda x: (-len(x), x)):
            name = re.sub(rf"(?<![A-Za-z]){re.escape(a)}(?![A-Za-z])", a, name, flags=re.I)
        name = re.sub(SMALL_WORDS_TITLE, lambda x: x.group(1).lower(), name)
        return re.sub(r"(?<=[a-z])'S\b", "'s", name)  # Children'S -> Children's


def apply_checks(m, checks, corrections, set_id):
    """The client's Y/N on each suggested row; a correction replaces the suggestion (also on rows not checked)."""
    done = 0
    for _, r in checks.iterrows():
        d = "N" if (r.raw_institution, r.country) in corrections else str(r.decision).strip().upper()
        idx = m[(m.raw_institution == r.raw_institution) & (m.country == r.country) & (m.status == "suggested")].index
        assert len(idx) == 1, (r.raw_institution, r.country, len(idx))
        if d == "Y":
            rid = re.findall(r"\[([0-9a-zA-Z-]+)\]", r.suggestion)[-1]
            set_id(idx[0], rid, "", "client check 16 Oct: suggestion accepted")
        elif d == "N":
            fix = corrections[(r.raw_institution, r.country)]
            set_id(idx[0], fix["institution_id"], fix["org_type"], "client check 16 Oct: corrected")
        else:
            continue
        done += 1
    for (raw, cc), fix in corrections.items():
        i = row_of(m, raw, cc)
        if m.at[i, "rule"] != "client check 16 Oct: corrected":
            set_id(i, fix["institution_id"], fix["org_type"], "client check 16 Oct: corrected")
    return done


def fix_names(m, case, name_fixes):
    """Uncoded names keep the answer's acronyms in capitals; then the client's name fixes."""
    for i in m[m.status == "uncoded"].index:
        name = case.restore(m.at[i, "canonical_name"], m.at[i, "raw_institution"])
        if name != m.at[i, "canonical_name"]:
            set_row(m, i, canonical_name=name, client_check="name")
    for (raw, cc), name in name_fixes.items():
        set_row(m, row_of(m, raw, cc), canonical_name=name, client_check="name")


def add_country_to_shared_names(m, o):
    """Two IDs sharing a coded name: each gets its record's country."""
    ids = m[m.institution_id != ""]
    dup = ids.groupby("canonical_name").institution_id.nunique()
    for name in dup[dup > 1].index:
        for rid in ids[ids.canonical_name == name].institution_id.unique():
            if rid in o.index:
                m.loc[m.institution_id == rid, "canonical_name"] = f"{name} ({o.at[rid, 'country']})"


def run(ctx):
    m = ctx.read_previous(__name__)
    led = ctx.ledger
    o = orgs_by_id(ctx.ror_dir)
    checks = present(led.batch("client_check_16oct"), m, "client_check_16oct").rename(
        columns={"target": "decision", "extra": "suggestion"}
    )
    corrections = {
        (r.raw_institution, r.country): dict(
            institution_id="" if r.target == "NO_ID" else r.target, org_type=r.org_type
        )
        for r in present(led.batch("client_corrections_16oct"), m, "client_corrections_16oct").itertuples(index=False)
    }
    name_fixes = {
        (r.raw_institution, r.country): r["name"]
        for _, r in present(led.batch("name_fixes_16oct"), m, "name_fixes_16oct").iterrows()
    }
    canon, typ = coded_lookups(m)

    def set_id(i, rid, org_type, rule):
        ror_type = org_type_from_types_field(o.at[rid, "types"]) if rid in o.index else ""
        set_row(
            m,
            i,
            **id_fields(rid),
            canonical_name="" if not rid else (canon.get(rid) or o.at[rid, "display_name"]),
            org_type=org_type or typ.get(rid) or ror_type,
            status="final",
            rule=rule,
            client_check="yes",
        )

    m["client_check"] = ""
    done = apply_checks(m, checks, corrections, set_id)
    m["typo_pass"] = m.typo_pass.where(m.client_check != "yes", "")
    fix_names(m, AcronymCase(ror_snapshot.read_names(ctx.ror_dir).name), name_fixes)
    add_country_to_shared_names(m, o)
    ctx.write(__name__, m)
    print("applied", done, "| still suggested", (m.status == "suggested").sum())
