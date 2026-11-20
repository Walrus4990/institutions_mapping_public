"""Stage 3: a ROR name or acronym inside the cleaned spelling (rulebook step 3).

Contained names: the longest ROR name (2+ words) found in the spelling, standing on its own (not glued to other
name words), decides it when it is the only record with that name in the learner's country (or the only one in the
world for learners without a country). Records that differ only by a city, teaching hospitals and spellings that name
two institutions go to review. Acronyms: the whole answer is the ROR acronym of one record in the learner's country.
Research units roll up to their parent university, also for stage 2 matches.
Reads  work/spellings.csv, work/spelling_country.csv, work/ror_names_clean.csv, work/matched_step2.csv,
       work/review_flags_step2.csv
Writes work/matched_step3.csv, work/review_flags_step3.csv, work/matched_step2.csv (with roll-ups),
       work/unmatched_after3.csv (spellings that stages 2-3 neither matched nor flagged)
"""

import re
from collections import defaultdict

import pandas as pd

from ..core.ror import Ror
from ..core.text import compact, words as key

GENERIC = set(
    """university universities universite universidad universidade universitas college colleges institute
institut instituto institution school academy centre center national state federal regional international public private
medical medicine health sciences science technology technological technical research studies study education educational
teaching hospital hospitals of and the for in on at de la du des management agriculture agricultural applied polytechnic
nursing pharmacy open catholic christian islamic methodist baptist adventist community development ministry department
council authority commission board agency office service services general central city africa african american european
asian arts business law engineering humanities social economic economics environmental training professional higher
advanced allied women memorial new modern global world foundation trust society association network specialist
specialized referral district county unit graduate postgraduate post faculty clinical laboratory laboratories
system""".split()
)
UNIT = {
    "department",
    "dept",
    "faculty",
    "school",
    "college",
    "centre",
    "center",
    "institute",
    "unit",
    "division",
    "campus",
    "laboratory",
    "lab",
    "programme",
    "program",
    "hospital",
    "clinic",
    "library",
    "office",
    "directorate",
    "the",
}
NOT_ACRONYM = {
    "na",
    "n a",
    "nil",
    "none",
    "no",
    "non",
    "nan",
    "null",
    "self",
    "nill",
    "nothing",
    "not",
    "yes",
    "student",
    "private",
    "test",
}
SEPARATOR = r"[,;:/()|\-]"


def separated(clean_text, before_words, after_words):
    """True IF the punctuation-keeping text has a separator between the two word sequences."""
    pat = r"\W+".join(map(re.escape, before_words)) + r"(\W+)" + r"\W+".join(map(re.escape, after_words))
    mm = re.search(pat, clean_text)
    return bool(mm and re.search(SEPARATOR, mm.group(1)))


def delimited(clean_text, nk, s):
    """True IF the name starting at word s starts the text or follows punctuation."""
    if s == 0:
        return True
    return separated(clean_text, key(clean_text).split()[:s], nk.split())


def boundaries_ok(clean_text, k, s, e):
    """The matched words s..e stand on their own: not glued to other name words before or after them."""
    w = k.split()
    tail = w[e : e + 1]
    if tail and tail[0] in {"of", "for", "and", "in", "de"} and not separated(clean_text, w[:e], [w[e]]):
        return False
    if s == 0 or delimited(clean_text, " ".join(w[s:e]), s):
        return True
    return bool(UNIT & set(w[:s]))


class ContainedNames:
    """ROR names of 2+ words, and the records that differ only by their city."""

    def __init__(self, rn, ror):
        self.ror, self.o = ror, ror.orgs
        nm = rn[rn.name_kind.isin(["display", "label"])].copy()
        nm["key"] = nm.clean.map(key)
        nm = nm[nm.key.str.count(" ") >= 1]
        self.ids = defaultdict(set)
        for k, rid in zip(nm.key, nm.ror_id):
            f = ror.resolve(rid)
            if f:
                self.ids[k].add(f)
        self.maxlen = max(k.count(" ") + 1 for k in self.ids)
        self.city_key = {rid: key(self.o.at[rid, "city"].lower()) for rid in ror.active}
        self.family = defaultdict(set)  # (name without city, country) -> cities used by sibling records
        for k, ids in self.ids.items():
            for rid in ids:
                ck = self.city_key.get(rid, "")
                if ck and k.endswith(" " + ck):
                    self.family[(k[: -len(ck) - 1], self.o.at[rid, "country_code"])].add(ck)

    def spans(self, text):
        """(start, end, name) of the ROR names in the text, longest first, without overlaps."""
        t = text.split()
        found = []
        for n in range(min(self.maxlen, len(t)), 1, -1):
            for i in range(len(t) - n + 1):
                k = " ".join(t[i : i + n])
                if k in self.ids and not any(i < e and i + n > s for s, e, _ in found):
                    found.append((i, i + n, k))
        return sorted(found)

    def types(self, f):
        """A record's ROR types."""
        return self.o.at[f, "types"].split(";")

    def parent_uni(self, f):
        """The one active parent university of a record that is not itself a university or hospital."""
        ps = [x for x in self.o.at[f, "parent_ids"].split(";") if x in self.ror.active]
        if len(ps) == 1 and "education" in self.types(ps[0]) and not {"education", "healthcare"} & set(self.types(f)):
            return ps[0]
        return None

    def decide(self, c, countries):
        """('match', id) | ('review', multi, reason, ids) | None for one spelling."""
        k = key(c)
        sps = [
            x
            for x in self.spans(k)
            if any(len(t) > 1 for t in x[2].split())
            and (not all(w in GENERIC for w in x[2].split()) or delimited(c, x[2], x[0]))
            and boundaries_ok(c, k, x[0], x[1])
        ]
        if not sps:
            return None
        picks = []
        for s, e, nk in sps:
            ids = self.ids[nk]
            inside = sorted(i for i in ids if self.o.at[i, "country_code"] in countries)
            if not countries and len(ids) == 1:  # rule 5.1: learners without a country keep a unique match
                inside = sorted(ids)
            picks.append((nk, s, e, inside, ids))
        insts = {(p[3] or list(p[4]))[0] for p in picks if len(p[3]) == 1 or (not p[3] and len(p[4]) == 1)}
        insts = {self.parent_uni(i) if self.parent_uni(i) in insts else i for i in insts}  # unit + its parent -> parent
        if len(insts) > 1:
            return ("review", "yes", "text names more than one institution", ";".join(sorted(insts)))
        nk, s, e, inside, ids = max(picks, key=lambda p: p[2] - p[1])
        left = k.split()[:s] + k.split()[e:]
        if len(inside) > 1:
            return ("review", "", "contained name matches several institutions in country", ";".join(sorted(inside)))
        if len(inside) != 1:
            return None  # name only in other countries: left for the fuzzy stage
        fid = inside[0]
        if self.parent_uni(fid) and len(picks) > 1:
            fid = self.parent_uni(fid)
        cc = self.o.at[fid, "country_code"]
        if self.family.get((nk, cc), set()) and self.city_key.get(fid, "") not in left:
            return ("review", "", "name has campuses in other cities", fid)
        if "hospital" in left and "healthcare" not in self.types(fid):
            return ("review", "", "teaching hospital: use hospital record, not university", fid)
        if len(ids) > 1 and countries - {cc}:
            return ("review", "", "users in several countries; same name exists elsewhere", ";".join(sorted(ids)))
        return ("match", fid)


def acronym_index(rn, resolve):
    """ROR acronym (letters and digits only) -> final ROR IDs."""
    ac = rn[rn.name_kind == "acronym"].copy()
    ac["k"] = ac.clean.map(compact)
    acr = defaultdict(set)
    for k, rid in zip(ac.k, ac.ror_id):
        f = resolve(rid)
        if f and len(k) >= 2:
            acr[k].add(f)
    return acr


def decide_acronym(c, sc, acr, o):
    """(matches, reviews) for a spelling that may be an acronym."""
    if key(c) in NOT_ACRONYM or " " in key(c) and len(key(c).replace(" ", "")) > 8:
        return [], []
    k = compact(c)
    if k not in acr:
        return [], []
    countries = sc[(sc.clean == c) & (sc.country != "")].sort_values("learners", ascending=False).country.tolist()
    ok, unclear = {}, []
    for cc in countries:
        hit = [i for i in acr[k] if o.at[i, "country_code"] == cc]
        if len(hit) == 1:
            ok[cc] = hit[0]
        elif len(hit) > 1:
            unclear.append(cc)
    if ok and len(set(ok.values())) == 1 and not unclear and len(ok) == len(countries):
        return [(c, "", next(iter(ok.values())), "acronym+country")], []
    matches, reviews = [], []
    if len(ok) and len(countries) > 1:
        matches = [(c, cc, f, "acronym+country") for cc, f in ok.items()]
    elif len(ok) == 1:
        matches = [(c, "", next(iter(ok.values())), "acronym+country")]
    if unclear:
        ids = {i for i in acr[k] if o.at[i, "country_code"] in unclear}
        reviews.append(
            (c, "", "acronym fits several institutions in country " + ",".join(unclear), ";".join(sorted(ids)))
        )
    return matches, reviews


def write_unmatched_after3(ctx, sp):
    """Spellings that stages 2-3 neither matched nor flagged (input of stage 4)."""
    done = set()
    for f in ["matched_step2", "matched_step3", "review_flags_step2", "review_flags_step3"]:
        done |= set(pd.read_csv(ctx.w(f"{f}.csv"), keep_default_na=False).clean)
    sp[~sp.clean.isin(done)].to_csv(ctx.w("unmatched_after3.csv"), index=False)


def run(ctx):
    sp = pd.read_csv(ctx.w("spellings.csv"), keep_default_na=False)
    sc = pd.read_csv(ctx.w("spelling_country.csv"), keep_default_na=False)
    rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
    m2 = pd.read_csv(ctx.w("matched_step2.csv"), keep_default_na=False)
    r2 = pd.read_csv(ctx.w("review_flags_step2.csv"), keep_default_na=False)
    ror = Ror(ctx.ror_dir)
    o = ror.orgs
    todo = sp[~sp.clean.isin(set(m2.clean) | set(r2.clean)) & (sp.clean != "")]
    countries = sc[sc.country != ""].groupby("clean")["country"].apply(set).to_dict()

    names = ContainedNames(rn, ror)
    contained, review = [], []
    for c in todo.clean:
        d = names.decide(c, countries.get(c, set()))
        if d and d[0] == "match":
            contained.append((c, "", d[1], "contained"))
        elif d:
            review.append((c,) + d[1:])
    decided = {x[0] for x in contained} | {x[0] for x in review}
    acr = acronym_index(rn, ror.resolve)
    acro = []
    for c in todo[~todo.clean.isin(decided)].clean:
        mt, rv = decide_acronym(c, sc, acr, o)
        acro += mt
        review += rv

    def roll_up(df):
        df["rolled_up_from"] = df.institution_id.map(lambda f: f if names.parent_uni(f) else "")
        df["institution_id"] = df.institution_id.map(lambda f: names.parent_uni(f) or f)
        return df

    m3 = roll_up(pd.DataFrame(contained + acro, columns=["clean", "country", "institution_id", "method"]))
    m2r = roll_up(m2.copy())
    m2r.to_csv(ctx.w("matched_step2.csv"), index=False)
    m3 = m3.merge(sp[["clean", "user_count", "example_raw_spelling", "user_countries"]], on="clean")
    m3.to_csv(ctx.w("matched_step3.csv"), index=False)
    rv = pd.DataFrame(review, columns=["clean", "multi", "reason", "candidate_ids"]).merge(
        sp[["clean", "user_count", "user_countries", "example_raw_spelling"]], on="clean"
    )
    rv.to_csv(ctx.w("review_flags_step3.csv"), index=False)
    write_unmatched_after3(ctx, sp)
    print(
        f"spellings considered: {len(todo)} | contained/acronym matches: {m3.clean.nunique()} | review: {len(rv)} "
        f"| rolled up to the parent university: step 2 {(m2r.rolled_up_from != '').sum()}, "
        f"step 3 {(m3.rolled_up_from != '').sum()}"
    )
