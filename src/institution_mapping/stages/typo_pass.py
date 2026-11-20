"""Stage 8: typos and close spellings, in the learner's country only (rulebook step 5 A and D, rule code ROR-TYPO).

Works on rows still uncoded or suggested; decided rows are left alone. In this order:
  A  exact     the answer, after punctuation removal and typo correction, equals a ROR name (display, label, alias,
               or the part before the first comma) or an already-coded spelling; also compared without spaces
  B  segment   one part of the text (split on , ; / ( ) | - "at") is such a name and the rest are unit words or places
  C  contained a ROR name of 2+ words sits inside the text, with only unit words before it and only places or unit
               words after it
  D  fuzzy     best score >= 92, 5+ points ahead of any other record, and every distinctive word matched both ways
A suggested row is confirmed only when the pass lands on the suggested ID. Rows the rules left uncoded on purpose
(R2, R3, overrides), teaching-hospital answers on non-hospital records and 'affiliated' texts are skipped.
Reads  work/assembled_mapping.csv and the ROR snapshot
Writes work/mapping_09_typo_pass.csv
"""

import html
import re
from collections import defaultdict
from difflib import SequenceMatcher
from functools import lru_cache

import pandas as pd

from ..core import ror as ror_snapshot
from ..core.fuzzy import score
from ..core.org_types import org_type_from_types_field
from ..core.ror import Ror
from ..core.table import coded_lookups, id_fields, set_row
from ..core.text import fold

TYPO = {  # common misspellings of generic words
    "university": [
        "univeristy",
        "universty",
        "unversity",
        "univesity",
        "univercity",
        "uiniversity",
        "universiy",
        "univerity",
        "universit",
        "universisty",
        "univerisity",
        "univrsity",
        "unniversity",
        "univeresity",
        "universitiy",
        "univeersity",
        "unuversity",
        "univesrity",
        "universitty",
        "universtiy",
        "univ",
        "uni",
    ],
    "college": ["collage", "colege", "collège", "colleg", "colledge", "collegue"],
    "institute": ["institue", "insitute", "instutute", "institude", "instiute", "institut", "inst"],
    "technology": ["technolgy", "techonology", "tecnology", "technlogy", "technoloy"],
    "polytechnic": ["polyetcnic", "polytecnic", "politechnic", "polythecnic", "polytechinic"],
    "sciences": ["scienses", "sceinces"],
    "science": ["sceince", "scince"],
    "nursing": ["nusring", "nurshing"],
    "hospital": ["hospitl", "hopital", "hosptal"],
    "teaching": ["teachng", "teching"],
    "federal": ["fedral", "feberal"],
    "medical": ["medial", "medicial"],
    "agriculture": ["agricultre", "agricuture"],
    "of": ["0f"],
}
TYPO_MAP = {w: right for right, wrongs in TYPO.items() for w in wrongs}
LITTLE = {"of", "the", "and", "in", "for", "at", "de", "la", "du", "da", "a"}
UNIT_KINDS = {"faculty", "department", "dept", "school", "college", "campus", "centre", "center", "unit", "division"}
SKIP_RULES = re.compile(r"^R2 |^R3 |override|R7")


def base(s):
    """Lower case, accents and apostrophes removed, punctuation-insensitive."""
    return fold(s, drop=r"['’`]")


def norm(s):
    """base() with generic-word typos corrected and a leading 'the' dropped."""
    w = [TYPO_MAP.get(t, t) for t in base(s).split()]
    if w and w[0] == "the":
        w = w[1:]
    return " ".join(w)


def no_spaces(s):
    """Text without spaces."""
    return s.replace(" ", "")


def wsim(x, y):
    """Two words are close: ratio 0.8 when their lengths differ by at most one letter, else 0.9."""
    r = SequenceMatcher(None, x, y).ratio()
    return r >= 0.8 if abs(len(x) - len(y)) <= 1 else r >= 0.9


def covered(a, b):
    """Every meaningful word of a has a close word in b."""
    wb = b.split()
    return all(any(wsim(x, y) for y in wb) for x in a.split() if x not in LITTLE and len(x) > 1)


def one(ids):
    """The ID if exactly one, else None."""
    return next(iter(ids)) if len(ids) == 1 else None


class TypoMatcher:
    """ROR names per country, normalised with norm(), and the already-coded spellings of the mapping."""

    def __init__(self, ror_dir, settings, m):
        self.st = st = settings
        self.ror = Ror(ror_dir)
        self.o = o = self.ror.orgs
        n = ror_snapshot.read_names(ror_dir)
        n["fid"] = n.ror_id.map(self.ror.resolve)
        n = n[n.fid.notna()]
        n["cc"] = n.fid.map(o.country_code)
        full = n[n.name_kind.isin(["display", "label", "alias"])].copy()
        full["key"] = full.name.map(norm)
        pre = full[full.name.str.contains(",")].copy()
        pre["key"] = pre.name.str.split(",").str[0].map(norm)
        names = pd.concat([full, pre])
        names = names[names.key.str.len() > 2]
        self.by_key, self.by_compact, self.names_cc = defaultdict(set), defaultdict(set), defaultdict(list)
        for k, cc, fid in zip(names.key, names.cc, names.fid):
            self.by_key[(cc, k)].add(fid)
            self.by_compact[(cc, no_spaces(k))].add(fid)
            self.names_cc[cc].append((k, fid))
        self.vocab_all = set(w for k in names.key for w in k.split())
        self.vocab_cc = defaultdict(set)
        for k, cc in zip(names.key, names.cc):
            self.vocab_cc[cc].update(w for w in k.split() if len(w) >= 5)

        self.unit = set(st["unit_words"]) | {
            "faculty",
            "dept",
            "department",
            "of",
            "the",
            "and",
            "school",
            "college",
            "graduate",
            "medicine",
            "medical",
            "pharmacy",
            "nursing",
            "sciences",
            "science",
            "health",
            "studies",
        }
        self.stop = set(st["coverage_stopwords"]) | {
            "university",
            "college",
            "institute",
            "school",
            "of",
            "the",
            "and",
            "state",
            "federal",
            "national",
            "hospital",
            "teaching",
            "centre",
            "center",
            "polytechnic",
        }
        self.generic = (
            self.stop
            | self.unit
            | set(st["generic_words"])
            | set(st["subject_words"])
            | {
                "technology",
                "research",
                "studies",
                "development",
                "university",
                "my",
                "our",
                "group",
                "society",
                "foundation",
                "organisation",
                "organization",
            }
        )
        self.small = (
            set(st["unit_words"])
            | set(st["subject_words"])
            | {
                "faculty",
                "department",
                "dept",
                "of",
                "the",
                "and",
                "in",
                "at",
                "for",
                "graduate",
                "postgraduate",
                "studies",
                "medicine",
                "medical",
                "pharmacy",
                "nursing",
                "sciences",
                "science",
                "health",
            }
        )

        coded = m[(m.status == "final") & (m.institution_id != "")]
        self.coded_key = defaultdict(set)
        for k, cc, i in zip(coded.key, coded.country, coded.institution_id):
            self.coded_key[(cc, k)].add(i)
            self.coded_key[(cc, no_spaces(k))].add(i)
        self.place_words = defaultdict(set)
        for cc_, c in zip(o.country_code, o.city):
            self.place_words[cc_].update(norm(c).split())
        for cc_, c in zip(o.country_code, o.country):
            self.place_words[cc_].update(norm(c).split())
        self.country_words = {cc_: set(norm(c).split()) for cc_, c in zip(o.country_code, o.country)}

    def org_type(self, rid):
        """A record's org_type (settings override first)."""
        if rid in self.st["org_type_overrides"]:
            return self.st["org_type_overrides"][rid]
        return org_type_from_types_field(self.o.at[rid, "types"])

    def city_words(self, rid):
        """The words of a record's city."""
        return set(norm(self.o.at[rid, "city"] if rid in self.o.index else "").split())

    @lru_cache(maxsize=None)  # noqa: B019 (one instance per stage)
    def fix_word(self, w, cc):
        """A word that exists nowhere in ROR -> its single closest in-country ROR word (ratio >= .86)."""
        if len(w) < 6 or w in self.vocab_all:
            return w
        best = sorted(
            ((SequenceMatcher(None, w, v).ratio(), v) for v in self.vocab_cc.get(cc, ()) if abs(len(v) - len(w)) <= 2),
            reverse=True,
        )[:2]
        if best and best[0][0] >= 0.86 and (len(best) == 1 or best[0][0] - best[1][0] >= 0.04):
            return best[0][1]
        return w

    def fix_words(self, s, cc):
        """Every word with its typo corrected."""
        return " ".join(self.fix_word(w, cc) for w in s.split())

    def distinctive(self, s, cc=""):
        """Words that are not generic, not a place in the country and longer than two letters."""
        return [w for w in s.split() if w not in self.generic and w not in self.place_words.get(cc, ()) and len(w) > 2]

    def tail_ok(self, words, cc, rid):
        """Words around a matched name may only be unit words, the record's own city or the learner's country."""
        ok = self.small | self.city_words(rid) | self.country_words.get(cc, set())
        return all(w in ok for w in words)

    def places_in(self, k, cc):
        """Place names (not the country) mentioned in a key."""
        return {
            w
            for w in k.split()
            if w in self.place_words.get(cc, ())
            and w not in self.country_words.get(cc, set())
            and w not in self.generic
        }

    def lookup(self, k, cc):
        """(ID, rule) for a key equal to a ROR name, or to a spelling already coded, in the country."""
        ids = self.by_key.get((cc, k)) or self.by_compact.get((cc, no_spaces(k)))
        if ids:
            return one(ids), "A exact (typo-corrected)"
        ids = self.coded_key.get((cc, k)) or self.coded_key.get((cc, no_spaces(k)))
        if ids:
            return one(ids), "A same as a coded spelling"
        return None, ""

    def segment(self, raw, cc):
        """An answer naming one organisation in several parts ('X, Y'): the ID if every coded part agrees."""
        segs = [
            self.fix_words(norm(p), cc)
            for p in re.split(r"[,;/()|]| - |–| at ", html.unescape(str(raw)), flags=re.I)
            if p.strip()
        ]
        if len(segs) < 2:
            return None
        hits = {}
        for sgm in segs:
            r, _ = self.lookup(sgm, cc)
            if r:
                hits[sgm] = r
        others = [s for s in segs if s not in hits]
        if len(set(hits.values())) == 1:
            rid0 = next(iter(hits.values()))
            if all(self.tail_ok(s.split(), cc, rid0) for s in others):
                return rid0
        return None

    def contained(self, k, cc):
        """The longest ROR name inside the key, if the words around it allow it."""
        best = None
        for name_key, fid in self.names_cc.get(cc, ()):
            if len(name_key.split()) < 2 or not self.distinctive(name_key, cc) or name_key == k:
                continue
            mm = re.search(rf"(?:^| ){re.escape(name_key)}(?: |$)", k)
            if mm and (best is None or len(name_key) > len(best[0])):
                best = (name_key, fid, mm)
        if not best:
            return None
        name_key, fid, mm = best
        same = {f for kk, f in self.names_cc[cc] if kk == name_key}
        before, after = k[: mm.start()].split(), k[mm.end() :].split()
        after_ok = self.tail_ok(after, cc, fid) and (
            not after
            or after[0] in UNIT_KINDS
            or all(w in self.city_words(fid) | self.country_words.get(cc, set()) for w in after)
        )
        if len(same) == 1 and all(w in self.small for w in before) and after_ok:
            return fid
        return None

    def fuzzy(self, k, cc):
        """The closest ROR name in the country by fuzzy score, if clearly ahead of the next one."""
        scores = defaultdict(float)
        kd = [w for w in k.split() if w not in self.generic and len(w) > 2]  # names, places included
        if not kd:
            return None, ""
        for name_key, fid in self.names_cc.get(cc, ()):
            if abs(len(name_key) - len(k)) > 15 or name_key[0] != k[0] and not set(kd) & set(name_key.split()):
                continue
            s = score(k, name_key)
            if s > scores[fid]:
                scores[fid] = s
                if s >= 92 and not (covered(k, name_key) and covered(name_key, k)):
                    scores[fid] = 0
        top = sorted(scores.items(), key=lambda x: -x[1])[:2]
        if not (top and top[0][1] >= 92 and (len(top) == 1 or top[0][1] - top[1][1] >= 5)):
            return None, ""
        rid = top[0][0]
        own = self.city_words(rid) | {w for kk, f in self.names_cc[cc] if f == rid for w in kk.split()}
        if not self.places_in(k, cc) <= own:
            return None, ""
        rivals = {
            f
            for kk, f in self.names_cc[cc]
            if f != rid and all(any(wsim(x, y) for y in kk.split()) for x in kd) and score(k, kk) >= 88
        }
        if rivals:
            return None, ""
        return rid, "D close spelling (score %d)" % top[0][1]

    def match(self, raw, cc):
        """(record, how) for one answer, or (None, '')."""
        if "affiliat" in base(raw):
            return None, ""
        k = self.fix_words(norm(raw), cc)
        rid, how = self.lookup(k, cc)
        if rid:
            return rid, how
        rid = self.segment(raw, cc)
        if rid:
            return rid, "B part of the text"
        rid = self.contained(k, cc)
        if rid:
            return rid, "C name inside the text"
        return self.fuzzy(k, cc)


def run(ctx):
    m = pd.read_csv(ctx.w("assembled_mapping.csv"), keep_default_na=False, dtype={"institution_id": str})
    m = m.drop(columns=["clean"])
    m["key"] = m.raw_institution.map(norm)
    tm = TypoMatcher(ctx.ror_dir, ctx.settings, m)
    canon = coded_lookups(m)[0]
    todo = m[
        m.status.isin(["uncoded", "suggested"])
        & ~m.rule.str.contains(SKIP_RULES)
        & ~m.org_type.isin(["NOT_APPLICABLE", "NOT_SPECIFIED"])
    ]
    overrides = ctx.ledger.overrides()
    found = []
    for i, r in todo.iterrows():
        if f"{norm(r.raw_institution)}|{r.country}" in overrides or not r.country:
            continue
        rid, how = tm.match(r.raw_institution, r.country)
        if not rid:
            continue
        if (
            re.search(r"hospital|\bclinic", r.key)
            and not str(rid).startswith("LOCAL")
            and tm.org_type(rid) != "HOSPITAL"
        ):
            continue
        if (
            r.country == "GB"
            and rid in tm.o.index
            and re.search(r"\bnhs\b|national health service", tm.o.at[rid, "display_name"].lower())
        ):
            rid, how = ctx.settings["nhs"]["ror_id"], how + " -> NHS (R2)"
        if r.status == "suggested":
            if rid in re.findall(r"\[([0-9a-zA-Z-]+)\]", r.suggestion):
                found.append((i, rid, "confirmed suggestion: " + how))
        else:
            found.append((i, rid, how))
    new = m.copy()
    new["typo_pass"] = ""
    for i, rid, how in found:
        local = str(rid).startswith("LOCAL")
        set_row(
            new,
            i,
            **id_fields(rid),
            canonical_name=canon.get(rid) or tm.o.at[rid, "display_name"],
            org_type=new.at[i, "org_type"] if local else (tm.org_type(rid) or new.at[i, "org_type"]),
            status="final",
            rule="R13 " + how,
            typo_pass="yes",
        )
    new.drop(columns=["key"]).to_csv(ctx.mapping("typo_pass"), index=False)
    print(new[new.typo_pass == "yes"].rule.str.replace(r" \(score \d+\)", "", regex=True).value_counts().to_string())
