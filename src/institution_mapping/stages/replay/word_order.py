"""Replay of the 16 Oct word-order pass: an uncoded spelling ("no match") whose words, typos corrected and small
words ignored, are exactly the words of one ROR name in the learner's country gets that ID ("Bonn University" =
"University of Bonn"). "student at/of" and "I am a student in" are dropped first."""

import html
import re
import unicodedata
from collections import defaultdict

from ...core import ror as ror_snapshot
from ...core.org_types import org_type_from_types_field
from ...core.ror import orgs_by_id
from ...core.table import coded_lookups, id_fields, set_row

TYPO = {
    "univeristy": "university",
    "universty": "university",
    "unversity": "university",
    "univesity": "university",
    "univercity": "university",
    "universiy": "university",
    "univerity": "university",
    "universit": "university",
    "universisty": "university",
    "univerisity": "university",
    "univrsity": "university",
    "univ": "university",
    "uni": "university",
    "universitas": "university",
    "universiti": "university",
    "universidad": "university",
    "universidade": "university",
    "universite": "university",
    "universita": "university",
    "universitat": "university",
    "collage": "college",
    "institue": "institute",
    "insitute": "institute",
    "institut": "institute",
    "instituto": "institute",
    "centre": "center",
    "centro": "center",
    "programme": "program",
    "organisation": "organization",
    "hopital": "hospital",
    "hospitalier": "hospital",
    "national": "national",
    "nacional": "national",
    "nationale": "national",
    "sciences": "science",
    "studies": "study",
}
STOP = {
    "of",
    "the",
    "and",
    "at",
    "in",
    "for",
    "de",
    "du",
    "la",
    "le",
    "des",
    "del",
    "di",
    "degli",
    "studi",
    "da",
    "do",
    "dos",
    "y",
    "et",
    "a",
    "e",
}
STUDENT_PREFIX = r"^(i am a student (in|at)|student (at|of|in)|i am a student)\s+"


def toks(s):
    """The set of meaningful words of a name (the student prefix is removed before punctuation)."""
    s = html.unescape(str(s)).replace("&", " and ").lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"['’`.]", "", s)
    s = re.sub(STUDENT_PREFIX, "", s.strip())
    w = [TYPO.get(t, t) for t in re.sub(r"[^0-9a-z]+", " ", s).split()]
    return frozenset(t for t in w if t not in STOP)


def run(ctx):
    m = ctx.read_previous(__name__)
    o = orgs_by_id(ctx.ror_dir, active_only=True)
    n = ror_snapshot.read_names(ctx.ror_dir)
    n = n[n.name_kind.isin(["display", "label", "alias"]) & n.ror_id.isin(o.index)]
    idx = defaultdict(set)
    for name, rid in zip(n.name, n.ror_id):
        t = toks(name)
        if len(t) >= 2:
            idx[(o.at[rid, "country_code"], t)].add(rid)
    canon = coded_lookups(m)[0]
    hits = 0
    for i, r in m[(m.status == "uncoded") & m.rule.str.startswith("no match")].iterrows():
        ids = idx.get((r.country, toks(r.raw_institution)))
        if not ids or len(ids) != 1:
            continue
        rid = next(iter(ids))
        if re.search(r"hospital|clinic", r.raw_institution, re.I) and "healthcare" not in o.at[rid, "types"]:
            continue
        set_row(
            m,
            i,
            **id_fields(rid),
            canonical_name=canon.get(rid) or o.at[rid, "display_name"],
            org_type=org_type_from_types_field(o.at[rid, "types"], m.at[i, "org_type"]),
            status="final",
            rule="16 Oct word-order match",
        )
        hits += 1
    ctx.write(__name__, m)
    print("coded", hits)
