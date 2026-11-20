"""Stage 7: one outcome per cleaned spelling and learner country, then one row per user-entered name.

Order of precedence: stage 2-3 matches (a stage-3 contained match that is really part of another name, or an
affiliated college, is rejected); stage 4 codes not sent to the engine; the rules engine (stage 6), where reviewer
overrides of 14 Oct win and suggestions the reviewer confirmed on 14 Oct become final.
Coded names: a named campus or college in another town keeps its name ("<ROR name> – <Town> College", rule 6.2);
spellings of one uncoded organisation, and kept unit names under one ID, are aligned to the most common one; a coded
name shared by two IDs gets the organisation's country.
Reads  work/ outputs of stages 1-6, the research views, the LOCAL register
Writes work/assembled_pairs.csv (per cleaned spelling and country), work/assembled_mapping.csv (per user-entered
       name and country), work/institutions.csv, work/local_id_register_used.csv
"""

import re
from collections import Counter
from difflib import get_close_matches

import pandas as pd

from ..core.org_types import org_type_from_types_field
from ..core.ror import orgs_by_id
from ..core.text import key, tidy_answer, without_brackets
from .common_rules import KeywordTypes, country_phrases, read_research, strip_countries

UNIT_KINDS = ("college", "campus")
NOT_PLACE_EXTRA = {
    "main",
    "north",
    "south",
    "east",
    "west",
    "northern",
    "southern",
    "eastern",
    "western",
    "central",
    "sub",
    "city",
    "new",
    "old",
    "permanent",
    "temporary",
    "the",
    "and",
    "regional",
    "university",
    "polytechnic",
    "integrated",
    "of",
}
JOINED_OK = {"al", "el", "the", "a", "an", "of", "at", "student", "students"}


class Assembly:
    """Lookups for naming and typing the assembled rows."""

    def __init__(self, ctx):
        self.S = S = ctx.settings
        self.o = o = orgs_by_id(ctx.ror_dir)
        sp = pd.read_csv(ctx.w("spellings.csv"), keep_default_na=False).set_index("clean")
        self.spx = sp.example_raw_spelling.to_dict()
        self.kw = KeywordTypes(S)
        self.cname = dict(zip(o.country_code, o.country))
        self.country_phr = country_phrases(self.cname)
        rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
        self.id_tokens, self.names_by_id = {}, {}
        for i_, c_, kind_ in zip(rn.ror_id, rn.clean, rn.name_kind):
            if kind_ != "acronym":
                self.names_by_id.setdefault(i_, set()).add(key(c_))
            if kind_ in ("display", "label"):
                self.id_tokens.setdefault(i_, set()).update(key(without_brackets(c_)).split())
        self.drop = (
            set(S["generic_words"])
            | set(S["subject_words"])
            | set(S["unit_words"])
            | set(S["coverage_stopwords"])
            | {"s"}
        )
        self.not_place = self.drop | NOT_PLACE_EXTRA
        self.places_by_cc = {}
        for cc_, city_ in zip(o.country_code, o.city):
            if city_:
                self.places_by_cc.setdefault(cc_, set()).add(key(city_))
        self.known = set(S["known_places"])

    def strip_countries(self, k):
        """The key without country names."""
        return strip_countries(k, self.country_phr)

    def tidy(self, c):
        """The coded name of an uncoded spelling: its most common raw spelling, tidied."""
        return tidy_answer(self.spx.get(c, c))

    def org_type(self, i, name):
        """org_type of a ROR record coded under this name (settings override first)."""
        if i in self.S["org_type_overrides"]:
            return self.S["org_type_overrides"][i]
        t = org_type_from_types_field(self.o.at[i, "types"])
        t2 = self.kw.type(name)
        return t2 if t == "HOSPITAL" and t2 == "TEACHING_HOSPITAL" else t or t2

    def nhs(self, i, cc):
        """The National Health Service record for an NHS body named by a learner in the United Kingdom."""
        nhs = self.S["nhs"]
        if cc == nhs["country"] and any(re.search(p, key(self.o.at[i, "display_name"])) for p in nhs["patterns"]):
            return nhs["ror_id"]
        return i

    def unit_name(self, c, i):
        """Rule 6.2: a named college or campus in another town ('Huye College', 'Enugu Campus', 'campus Karachi')
        keeps its name: '<ROR name> – <Town> College/Campus'. Faculties, 'College of Medicine' etc. roll up."""
        dn = self.o.at[i, "display_name"]
        if set(self.S["unit_keep_name_words"]) & set(key(dn).split()):
            return dn
        parent = self.id_tokens.get(i, set()) | set(key(dn).split())
        home = key(self.o.at[i, "city"])
        towns = self.places_by_cc.get(self.o.at[i, "country_code"], set()) | self.known
        parts = re.split(r"[,;/()|:]| - | – ", c.lower())
        if any(w in key(c).replace("collage", "college").split() for w in UNIT_KINDS):
            parts = parts + [" ".join(parts) + " college"]  # a town named in another part ('College of X, Town')
        for part in parts:
            toks = self.strip_countries(key(part)).replace("collage", "college").split()
            kinds = [w for w in toks if w in UNIT_KINDS]
            if not kinds:
                continue
            kind = "Campus" if "campus" in kinds else "College"
            town = self.town_in(toks, home, parent, towns)
            if town:
                return f"{dn} – {town.title()} {kind}"
            if kind == "Campus":
                near = self.place_near_campus(toks, home, parent)
                if near:
                    return f"{dn} – {' '.join(near).title()} Campus"
        return dn

    def town_in(self, toks, home, parent, towns):
        """A known town (1-2 words) in the part, other than the record's own town (typos tolerated for listed towns)."""
        homec = home.replace(" ", "")
        for n in (2, 1):
            for j in range(len(toks) - n + 1):
                ph = " ".join(toks[j : j + n])
                if ph.replace(" ", "") == homec or get_close_matches(ph.replace(" ", ""), [homec], n=1, cutoff=0.85):
                    continue
                if j + n < len(toks) and toks[j + n] == "state":
                    continue
                if set(ph.split()) <= parent:
                    continue
                hit = ph if ph in towns else (get_close_matches(ph, sorted(self.known), n=1, cutoff=0.85) or [None])[0]
                if hit:
                    return hit
        return None

    def place_near_campus(self, toks, home, parent):
        """Campuses are named after places: '<x> campus' or 'campus <x>'."""
        homec = home.replace(" ", "")
        j = toks.index("campus")
        near = [
            t_
            for t_ in toks[max(0, j - 2) : j]
            if t_ not in self.not_place
            and t_ not in parent
            and t_ != home
            and not t_.isdigit()
            and not get_close_matches(t_, [homec], n=1, cutoff=0.85)
        ]
        if not near and j + 1 < len(toks) and toks[j + 1] not in self.not_place | parent | {home}:
            near = [toks[j + 1]]
        return near

    def wrong_contained(self, c, i):
        """A stage-3 'contained' match that is really part of another proper name, or an affiliated college."""
        low = c.lower()
        if re.search(r"\baffiliated\b", low):
            return True
        for n in sorted(self.names_by_id.get(i, ()), key=lambda x: (-len(x), x)):
            m = re.search(r"\b" + r"\W+".join(map(re.escape, n.split())) + r"\b", low)
            if not m:
                continue
            mm = re.search(r"([a-z]+) $", low[: m.start()])  # a word joined to the name by a plain space
            return bool(mm) and mm.group(1) not in self.drop | JOINED_OK
        return False


class Outcomes(dict):
    """{(clean, country): outcome}, filled from stages 2-4 and the rules engine, in that order."""

    def __init__(self, a, pairs):
        super().__init__()
        self.a, self.pairs = a, pairs

    def put(self, c, cc, **kw):
        """Set the outcome of one spelling and country."""
        self[(c, cc)] = dict(clean=c, country=cc, **kw)

    def countries_of(self, c):
        """The learner countries of a spelling."""
        return self.pairs[self.pairs.clean == c].country.tolist()

    def add_matches(self, m):
        """Stages 2-3: a ROR name equal to, or contained in, the spelling."""
        a, o = self.a, self.a.o
        for _, r in m.iterrows():
            ccs = [r.country] if r.country else self.countries_of(r.clean)
            if r.src == "step 3" and r.method == "contained" and a.wrong_contained(r.clean, r.institution_id):
                first = re.split(r"[,/;()|]| - |\baffiliated\b", a.tidy(r.clean), flags=re.I)[0].strip(" ,-")
                for cc in ccs:
                    self.put(
                        r.clean,
                        cc,
                        institution_id="",
                        id_kind="",
                        canonical_name=first,
                        org_type=a.kw.type(first),
                        status="uncoded",
                        suggestion_id="",
                        rule="step 3 contained -> rejected: part of another name / affiliated college",
                    )
                continue
            for cc in ccs:
                i = a.nhs(r.institution_id, cc)
                n = a.unit_name(r.clean, i) if i == r.institution_id else o.at[i, "display_name"]
                self.put(
                    r.clean,
                    cc,
                    institution_id=i,
                    id_kind="ROR",
                    canonical_name=n,
                    org_type=a.org_type(i, n),
                    status="final",
                    rule=f"{r.src} {r.method}" + (" -> P5 NHS" if i != r.institution_id else ""),
                    suggestion_id="",
                )

    def add_types(self, c4, engine_cleans, not_specified):
        """Stage 4 codes for spellings the rules engine did not decide."""
        for c, r in c4.iterrows():
            if c in engine_cleans:
                continue
            if c in not_specified:
                t, why = "NOT_SPECIFIED", "R4 recoded from NOT_APPLICABLE"
            else:
                t, why = r.code, "step 4 " + r.method
            for cc in self.countries_of(c):
                self.put(
                    c,
                    cc,
                    institution_id="",
                    id_kind="",
                    canonical_name="",
                    org_type=t,
                    status="final",
                    rule=why,
                    suggestion_id="",
                )

    def add_override(self, c, cc, ov, r):
        """A reviewer decision of 14 Oct that the rules do not reproduce ('' = uncoded)."""
        o = self.a.o
        if ov:
            self.put(
                c,
                cc,
                institution_id=ov,
                id_kind="ROR",
                canonical_name=o.at[ov, "display_name"],
                org_type=self.a.org_type(ov, o.at[ov, "display_name"]),
                status="final",
                rule="reviewer decision (override)",
                suggestion_id="",
            )
        else:
            self.put(
                c,
                cc,
                institution_id="",
                id_kind="",
                canonical_name=r.canonical_name,
                org_type=r.org_type,
                status="final",
                rule="reviewer decision (override): uncoded",
                suggestion_id="",
            )

    def add_engine(self, eng, overrides, confirmed, research_named):
        """The rules engine, for spellings not decided above (a reviewer override always wins)."""
        a, o = self.a, self.a.o
        for _, r in eng.iterrows():
            c, cc = r.clean, r.country
            ov = overrides.get(f"{c}|{cc}")
            if ov is not None:
                self.add_override(c, cc, ov, r)
                continue
            if (c, cc) in self:
                continue
            if r.suggestion_id and c in confirmed:  # the reviewer confirmed these suggestions on 14 Oct
                i = a.nhs(r.suggestion_id, cc)
                n = o.at[i, "display_name"]
                self.put(
                    c,
                    cc,
                    institution_id=i,
                    id_kind="ROR",
                    canonical_name=n,
                    org_type=a.org_type(i, n),
                    status="final",
                    rule=r.rule.replace("(suggested)", "(confirmed by reviewer)"),
                    suggestion_id="",
                )
                continue
            if r.suggestion_id:
                st = "suggested"
            elif r.id_kind == "":
                st = "uncoded" if r.canonical_name else "final"
            else:
                st = "final"
            nm = r.canonical_name
            if (
                r.id_kind == "ROR"
                and r.institution_id in o.index
                and not r.rule.startswith("R1 TH")
                and c not in research_named
            ):
                nm = a.unit_name(c, r.institution_id)
            self.put(
                c,
                cc,
                institution_id=r.institution_id,
                id_kind=r.id_kind,
                canonical_name=nm,
                org_type=r.org_type,
                status=st,
                rule=r.rule,
                suggestion_id=r.suggestion_id,
            )


def outcomes(ctx, a, pairs):
    """{(clean, country): outcome} from stages 2-4 and the rules engine."""
    m2 = pd.read_csv(ctx.w("matched_step2.csv"), keep_default_na=False).assign(src="step 2")
    m3 = pd.read_csv(ctx.w("matched_step3.csv"), keep_default_na=False).assign(src="step 3")
    c4 = pd.read_csv(ctx.w("codes_step4.csv"), keep_default_na=False).set_index("clean")
    eng = pd.read_csv(ctx.w("full_engine.csv"), keep_default_na=False, dtype=str)
    res = read_research(ctx)
    confirmed = set(pd.read_csv(ctx.w("decisions_expected.csv"), keep_default_na=False).clean)
    research_named = set(res[(res.outcome == "ROR") & (res["name"] != "")].clean)
    out = Outcomes(a, pairs)
    out.add_matches(m2)
    out.add_matches(m3)
    out.add_types(c4, set(eng.clean), a.S["generic_exact"]["NOT_SPECIFIED"])
    out.add_engine(eng, ctx.ledger.overrides(), confirmed, research_named)
    return out


def align_uncoded_names(f, stop):
    """Spellings of the same uncoded organisation (same country, same words) take the most common name."""

    def wkey(n):
        return " ".join(sorted(set(key(n).split()) - stop))

    u = f[(f.status == "uncoded") & (f.canonical_name != "")].copy()
    u["wk"] = u.canonical_name.map(wkey)
    best = u.groupby(["country", "wk"]).apply(
        lambda g: g.sort_values(
            ["learners", "canonical_name"], ascending=[False, True], kind="stable"
        ).canonical_name.iloc[0],
        include_groups=False,
    )
    f.loc[u.index, "canonical_name"] = [best[(cc, wk)] for cc, wk in zip(u.country, u.wk)]
    return (u.canonical_name.values != f.loc[u.index, "canonical_name"].values).sum()


def align_unit_names(f, stop, o):
    """Kept unit names under one ID: spellings of one name take the most common one; a name whose words contain
    (or are contained in) a more common name under the same ID takes that name (never the parent's own name)."""

    def ukey(n):
        return " ".join(sorted(set(key(n).replace("collage", "college").split()) - stop))

    k_ = f[(f.id_kind != "") & (f.canonical_name != "")].copy()
    k_["uk"] = [i + "|" + ukey(n) for i, n in zip(k_.institution_id, k_.canonical_name)]
    bestu = k_.groupby("uk").apply(
        lambda g: g.groupby("canonical_name").learners.sum().sort_values(ascending=False).index[0], include_groups=False
    )
    f.loc[k_.index, "canonical_name"] = k_.uk.map(bestu).values
    k_ = f.loc[k_.index]
    for i, g in k_.groupby("institution_id"):
        names = g.groupby("canonical_name").learners.sum().sort_values(ascending=False)
        if len(names) < 2:
            continue
        ws_ = {n: set(ukey(n).split()) for n in names.index}
        parent_name = o.at[i, "display_name"] if i in o.index else ""
        remap = {}
        for n in names.index:
            for m in names.index:
                if m == n or names[m] < names[n] or m in remap:
                    continue
                if m == parent_name or n == parent_name:
                    continue
                if ws_[n] and ws_[m] and (ws_[n] <= ws_[m] or ws_[m] <= ws_[n]):
                    remap[n] = m
                    break
        for n, m in remap.items():
            f.loc[g.index[g.canonical_name == n], "canonical_name"] = m


def add_country_to_shared_names(f, o, cname, reg):
    """A coded name shared by two IDs gets the organisation's country, or city and country within one country."""
    ids = f[f.institution_id != ""].drop_duplicates("institution_id")[["institution_id", "canonical_name", "id_kind"]]
    loc_cc = dict(zip(reg.local_id, reg.country))

    def inst_country(i):
        return (
            cname.get(o.at[i, "country_code"], "") if i in o.index else cname.get(loc_cc.get(i, ""), loc_cc.get(i, ""))
        )

    dup = ids.groupby("canonical_name").institution_id.nunique()
    dup = set(dup[dup > 1].index)
    mask = f.canonical_name.isin(dup) & (f.institution_id != "")

    def where(n, i):
        same = ids[ids.canonical_name == n].institution_id
        if len({inst_country(j) for j in same}) < len(set(same)) and i in o.index:
            return f"{o.at[i, 'city']}, {inst_country(i)}"
        return inst_country(i)

    f.loc[mask, "canonical_name"] = [
        f"{n} ({where(n, i)})" if where(n, i) else n
        for n, i in zip(f.loc[mask, "canonical_name"], f.loc[mask, "institution_id"])
    ]
    return dup, inst_country


def run(ctx):
    a = Assembly(ctx)
    o = a.o
    raw = pd.read_csv(ctx.w("raw_with_clean.csv"), keep_default_na=False)
    reg = pd.read_csv(ctx.registry("local_ids.csv"), keep_default_na=False, dtype=str)[
        ["local_id", "name_key", "country"]
    ]
    nh = pd.read_csv(ctx.w("norhed.csv"), dtype=str, keep_default_na=False)
    res = read_research(ctx)
    pairs = raw.groupby(["clean", "country"], as_index=False).learners.sum()
    final = outcomes(ctx, a, pairs)
    f = pairs.merge(pd.DataFrame(final.values()), on=["clean", "country"], how="left")
    missing = f[f.status.isna()]
    assert missing.empty, missing.head()
    stop = set(a.S["coverage_stopwords"])
    aligned = align_uncoded_names(f, stop)
    align_unit_names(f, stop, o)
    dup, inst_country = add_country_to_shared_names(f, o, a.cname, reg)
    f["suggestion"] = [
        f"{o.at[i, 'display_name']} ({o.at[i, 'city']}, {o.at[i, 'country_code']}) [{i}]" if i else ""
        for i in f.suggestion_id
    ]
    f["ror_url"] = ["https://ror.org/" + i if k == "ROR" else "" for i, k in zip(f.institution_id, f.id_kind)]
    f.to_csv(ctx.w("assembled_pairs.csv"), index=False)

    mp = raw.merge(f.drop(columns=["learners"]), on=["clean", "country"], how="left")
    mp = mp.rename(columns={"raw": "raw_institution"})[
        [
            "raw_institution",
            "country",
            "learners",
            "canonical_name",
            "institution_id",
            "id_kind",
            "org_type",
            "status",
            "suggestion",
            "rule",
            "ror_url",
            "clean",
        ]
    ]
    mp.to_csv(ctx.w("assembled_mapping.csv"), index=False)

    def most_common(s):
        return Counter(s).most_common(1)[0][0]

    inst = (
        f[f.institution_id != ""]
        .groupby(["institution_id", "id_kind"])
        .agg(
            canonical_name=("canonical_name", most_common),
            org_type=("org_type", most_common),
            learners=("learners", "sum"),
            spellings=("clean", "nunique"),
            user_countries=("country", lambda s: ";".join(sorted(set(s) - {""}))),
        )
        .reset_index()
    )
    inst["institution_country"] = inst.institution_id.map(inst_country)
    inst.sort_values("learners", ascending=False).to_csv(ctx.w("institutions.csv"), index=False)

    src = res[res.outcome.isin(["NOT_IN_ROR", "TYPE"]) & (res.evidence == "web-searched")].assign(
        nk=lambda d: d["name"].map(key)
    )
    reg2 = reg.merge(
        src[["nk", "source", "evidence"]].drop_duplicates("nk"), left_on="name_key", right_on="nk", how="left"
    ).drop(columns="nk")
    reg2["name"] = reg2.local_id.map(dict(zip(f.institution_id, f.canonical_name)))
    reg2.loc[reg2.local_id.isin(set(nh.institution_id)), "source"] = "NORHED partner file"
    reg2.loc[reg2.name_key.str.startswith("ministry of health"), "source"] = (
        "rule R5: national Ministry of Health, one ID per country"
    )
    reg2 = reg2[reg2.local_id.isin(set(f.institution_id))]
    reg2[["local_id", "name", "country", "source"]].to_csv(ctx.w("local_id_register_used.csv"), index=False)
    s = (
        f.assign(k=f.id_kind.replace("", "none"))
        .groupby(["status", "k"])
        .agg(pairs=("clean", "size"), learners=("learners", "sum"))
    )
    print(s.to_string())
    print(
        f"LOCAL IDs used: {len(reg2)} | institutions with an ID: {len(inst)} | uncoded names aligned: {aligned} "
        f"| names given a country: {len(dup)}"
    )
