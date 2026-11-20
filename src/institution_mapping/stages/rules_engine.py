"""Stage 6: the rulebook's rules on every spelling the earlier stages left open, per learner country.

The engine runs twice: first on the spellings the reviewer decided on 14 Oct (ledger batch reviewer_14oct) to
validate the rules against the reviewer (work/validation_result.csv), then on every open spelling.
Inputs it decides: the fuzzy-stage spellings, the named organisations stage 4 typed by keyword, and the spellings
stage 3 matched in some of their countries only (work/engine_input.csv).
Reads  work/ outputs of stages 1-5, coding_rules.json, the research views written from the ledger (research.csv,
       research_deepdive.csv, decisions_expected.csv) and the LOCAL register
Writes work/engine_input.csv, work/validation_engine.csv, work/validation_result.csv, work/full_engine.csv:
       clean, country, id_kind, institution_id, canonical_name, org_type, rule, pending, suggestion_id
The rule labels written to `rule` (R1-R6, P1-P4) are mapped to the rule codes of the output by stage 28 (finalise).
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import get_close_matches

import pandas as pd

from ..core.org_types import org_type_from_ror
from ..core.ror import Ror
from ..core.text import compact, key, specific, tidy_answer, without_brackets
from .common_rules import KeywordTypes, country_phrases, read_research, strip_countries

UNIT_WORDS = {
    "college",
    "faculty",
    "department",
    "dept",
    "school",
    "institute",
    "centre",
    "center",
    "unit",
    "campus",
    "division",
    "programme",
    "program",
    "laboratory",
    "lab",
}


def outcome(kind="", i="", name="", typ="", rule="", pending=False, suggestion=""):
    """One decision of the engine (the columns of full_engine.csv)."""
    return dict(
        id_kind=kind,
        institution_id=i,
        canonical_name=name,
        org_type=typ,
        rule=rule,
        pending=pending,
        suggestion_id=suggestion,
    )


@dataclass
class Case:
    """One spelling and learner country being decided."""

    clean: str
    cc: str
    k: str  # text.key of the spelling
    force: str = None  # org_type forced by an earlier rule (teaching hospital)


class Engine:
    """The rules engine. decide() tries the rules in RULES order; the first that decides the case ends it."""

    def __init__(self, ctx):
        self.S = S = ctx.settings
        self.ror = Ror(ctx.ror_dir)
        self.o = o = self.ror.orgs
        rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
        self.sp = pd.read_csv(ctx.w("spellings.csv"), keep_default_na=False).set_index("clean")
        sc = pd.read_csv(ctx.w("spelling_country.csv"), keep_default_na=False)
        self.cand = pd.read_csv(ctx.w("candidates_step5.csv"), keep_default_na=False).set_index("clean")
        self.res = read_research(ctx).set_index("clean")
        m2 = pd.read_csv(ctx.w("matched_step2.csv"), keep_default_na=False)
        self.done_cc = m2[m2.country != ""].groupby("clean").country.apply(set).to_dict()
        nh = pd.read_csv(ctx.w("norhed.csv"), dtype=str, keep_default_na=False)
        self.norhed_local = set(nh.institution_id[nh.institution_id.str.startswith("LOCAL")])
        self.reg = ctx.register()
        self.active = self.ror.active
        self.cname = dict(zip(o.country_code, o.country))
        self.kw = KeywordTypes(S)
        self._index_names(rn)
        self.country_phr = country_phrases(self.cname)
        self.ids_by_cc = defaultdict(list)
        for i in self.active:
            self.ids_by_cc[self.cc_of(i)].append(i)
        self.ucs = sc.groupby("clean").country.apply(list).to_dict()
        self.learners = self.sp.user_count.to_dict()
        self.res_name_learners = defaultdict(int)  # learners per researched organisation name
        for c, r in self.res.iterrows():
            if r["name"]:
                self.res_name_learners[key(r["name"])] += self.learners.get(c, 0)
        self.RULES = [
            self.generic_answers,
            self.name_cluster,
            self.generic_exact,
            self.ministry_per_country,
            self.nhs_body,
            self.teaching_hospital,
            self.research_record,
            self.unit_of_university,
            self.exact_name,
            self.branch,
            self.word_coverage,
            self.fuzzy_candidate,
        ]

    def _index_names(self, rn):
        """ROR names and acronyms -> final IDs; words of each record's official names."""
        self.name_idx, self.acr_idx = defaultdict(set), defaultdict(set)
        for i, c, kind in zip(rn.ror_id, rn.clean, rn.name_kind):
            f = self.ror.resolve(i)
            if not f:
                continue
            if kind == "acronym":
                self.acr_idx[compact(c)].add(f)
                continue
            self.name_idx[key(c)].add(f)
            if "(" in c:
                self.name_idx[key(without_brackets(c))].add(f)
            if kind in ("display", "label") and "," in c and len(c.split(",")[0].split()) >= 2:
                self.name_idx[key(c.split(",")[0])].add(f)
        self.id_tokens = defaultdict(set)  # words of official names (display + label) only
        for i, c, kind in zip(rn.ror_id, rn.clean, rn.name_kind):
            if kind in ("display", "label"):
                self.id_tokens[i] |= set(key(without_brackets(c)).split())

    # ---- small lookups ----
    def cc_of(self, i):
        """A record's country code."""
        return self.o.at[i, "country_code"]

    def types(self, i):
        """A record's ROR types."""
        return self.ror.types(i)

    def display(self, i):
        """A record's display name."""
        return self.o.at[i, "display_name"]

    def strip_countries(self, k):
        """The key without country names."""
        return strip_countries(k, self.country_phr)

    def org_type(self, i, name):
        """org_type of a record coded under this name: settings override, else ROR type, else keywords; a hospital named
        as a teaching hospital is TEACHING_HOSPITAL."""
        if i in self.S["org_type_overrides"]:
            return self.S["org_type_overrides"][i]
        t = org_type_from_ror(self.types(i))
        t2 = self.kw.type(name)
        return t2 if t == "HOSPITAL" and t2 == "TEACHING_HOSPITAL" else t or t2

    def allowed(self, i, cc):
        """May record i code a learner in country cc (rule 5.2)?"""
        if not cc or self.cc_of(i) == cc:
            return True
        t = set(self.types(i))
        intl = self.S["international"]
        if i in intl["ror_ids"] or (t & set(intl["ror_types"]) and not t & {"education", "healthcare"}):
            return True
        return self.country_exception(i, cc)

    def country_exception(self, i, cc):
        """True if coding_rules.json lets learners of this country use this foreign record."""
        return any(i == e["ror_id"] and cc in e["countries"] for e in self.S["country_exceptions"])

    def tidy(self, clean):
        """The coded name of an uncoded spelling: its most common raw spelling, tidied."""
        return tidy_answer(self.sp.at[clean, "example_raw_spelling"] if clean in self.sp.index else clean)

    def candidate_scores(self, clean, cc):
        """[(score, id)] of the fuzzy candidates in country cc."""
        return [
            (float(self.cand.at[clean, f"c{j}_score"] or 0), self.cand.at[clean, f"c{j}_id"])
            for j in (1, 2, 3)
            if self.cand.at[clean, f"c{j}_id"] and self.cc_of(self.cand.at[clean, f"c{j}_id"]) == cc
        ]

    def in_country_alt(self, clean, cc):
        """The best fuzzy candidate in the learner's country scoring at least fuzzy_in_country_alternative."""
        if clean not in self.cand.index:
            return None
        best = []
        for j in (1, 2, 3):
            i = self.cand.at[clean, f"c{j}_id"] if f"c{j}_id" in self.cand.columns else ""
            if (
                i
                and self.cc_of(i) == cc
                and float(self.cand.at[clean, f"c{j}_score"] or 0) >= self.S["fuzzy_in_country_alternative"]
            ):
                best.append((float(self.cand.at[clean, f"c{j}_score"]), i))
        return max(best)[1] if best else None

    def fuzzy_accept(self, clean, cc):
        """A clear in-country fuzzy candidate: min_score reached and margin ahead of the next."""
        if clean not in self.cand.index:
            return None
        sc_ = sorted(self.candidate_scores(clean, cc), reverse=True)
        fa = self.S["fuzzy_accept"]
        if sc_ and sc_[0][0] >= fa["min_score"] and (len(sc_) == 1 or sc_[0][0] - sc_[1][0] >= fa["margin"]):
            return sc_[0][1]
        return None

    # ---- outcomes ----
    def ror_outcome(self, i, rule, typ=None, cc=""):
        """A ROR outcome with the record's name and type; NHS bodies in the UK become the National Health Service."""
        nhs = self.S["nhs"]
        if cc == nhs["country"] and any(re.search(p, key(self.display(i))) for p in nhs["patterns"]):
            i, rule = nhs["ror_id"], "P5/R2 NHS"
        n = self.display(i)  # campus and college names are given by stage 7 for every ROR row
        return outcome("ROR", i, n, typ or self.org_type(i, n), rule)

    def named_not_in_ror(self, name, cc, typ, verified, n_learn, rule, searched=False):
        """A named organisation without a ROR record: LOCAL ID when verified and with enough learners."""
        lid = self.reg.find(name, cc)
        if lid in self.norhed_local:
            return outcome("LOCAL", lid, name, typ, rule + " (NORHED local ID)")
        if verified and n_learn >= self.S["local_min_learners"]:
            return outcome("LOCAL", self.reg.issue(name, cc, source="rules engine (step 7)"), name, typ, rule)
        need = n_learn >= self.S["local_min_learners"] and not verified and not searched
        suffix = " (needs online search)" if need else (" (searched, not found)" if searched and not verified else "")
        return outcome("", "", name, typ, rule + suffix, pending=need)

    def uncoded(self, case, rule, typ=None):
        """An uncoded outcome with the tidied name and the type from the keywords."""
        return outcome(name=self.tidy(case.clean), typ=typ or case.force or self.kw.type(case.clean), rule=rule)

    # ---- the rules, in order ----
    def generic_answers(self, case):
        """R4: listed generic answers, no-affiliation phrases, answers that stay uncoded without a search."""
        S = self.S
        if case.clean in S["generic_keep_type_no_name"]:
            return outcome(typ=self.kw.type(case.clean), rule="R4 generic, type kept")
        if any(re.search(p, case.k) for p in S["not_applicable_patterns"]):
            return outcome(typ="NOT_APPLICABLE", rule="R4 no-affiliation phrase")
        return None

    def name_cluster(self, case):
        """R6: the many spellings of one named organisation (settings name_clusters)."""
        for cl in self.S["name_clusters"]:
            if re.search(cl["pattern"], case.k):
                n = cl["name"]
                nl = sum(v for c_, v in self.learners.items() if re.search(cl["pattern"], key(c_)))
                hit = [i for i in self.name_idx.get(key(n), ()) if self.allowed(i, case.cc)]
                if len(hit) == 1:
                    return self.ror_outcome(hit[0], "R6 cluster", cl["org_type"], case.cc)
                return self.named_not_in_ror(
                    n, cl.get("country") or "", cl["org_type"], cl.get("verified", False), nl, "R6 cluster"
                )
        return None

    def generic_exact(self, case):
        """R4: an answer that is only a kind of organisation (settings generic_exact)."""
        for typ, lst in self.S["generic_exact"].items():
            if not typ.startswith("_") and re.sub(r"\s+", " ", case.clean).strip() in lst:
                return outcome(typ=typ, rule="R4 generic")
        return None

    def ministry_per_country(self, case):
        """R5: "Ministry of Health" and the like: the learner's country's body (ROR record, else one LOCAL ID)."""
        stripped = " ".join(w for w in self.strip_countries(case.k).split() if w != "the")
        for g, conf in self.S["per_country_generic"].items():
            if g.startswith("_") or stripped != g:
                continue
            if not case.cc:
                return outcome(typ=conf["org_type"], name=self.tidy(case.clean), rule="R5 MoH, no country")
            hits = self.government_records(case.cc, g) or self.government_records(case.cc, "federal " + g)
            if hits:
                return outcome("ROR", hits[0], self.display(hits[0]), conf["org_type"], "R5 MoH ROR")
            n = conf["local_name"].format(country=self.cname.get(case.cc, case.cc))
            return outcome(
                "LOCAL", self.reg.issue(n, case.cc, source="rules engine (step 7)"), n, conf["org_type"], "R5 MoH local"
            )
        return None

    def government_records(self, cc, prefix):
        """Government records of a country whose name starts with prefix, shortest name first."""
        hits = [
            i
            for i in sorted(self.active)
            if self.cc_of(i) == cc and "government" in self.types(i) and key(self.display(i)).startswith(prefix)
        ]
        return sorted(hits, key=lambda i: (len(self.display(i)), i))

    def nhs_body(self, case):
        """R2: an NHS body named by a learner in the United Kingdom -> National Health Service."""
        nhs = self.S["nhs"]
        if case.cc == nhs["country"] and any(re.search(p, case.k) for p in nhs["patterns"]):
            i = nhs["ror_id"]
            return outcome("ROR", i, self.display(i), self.org_type(i, self.display(i)), "R2 NHS")
        return None

    def teaching_hospital(self, case):
        """R1: a teaching hospital: its own ROR record, else its university's record with "<name> Teaching Hospital".
        Sets case.force = TEACHING_HOSPITAL for the later rules."""
        k = case.k
        if not ("teaching" in k.split() and "hospital" in k.split()):
            return None
        case.force = "TEACHING_HOSPITAL"
        own = [i for i in self.name_idx.get(k, ()) if self.cc_of(i) == case.cc and "healthcare" in self.types(i)]
        if len(own) == 1:
            return outcome("ROR", own[0], self.display(own[0]), case.force, "R1 TH own ROR")
        ws = k.split("teaching hospital")[0].split()
        while len(ws) >= 2:
            unis = [
                i
                for i in self.name_idx.get(" ".join(ws), ())
                if self.cc_of(i) == case.cc and "education" in self.types(i)
            ]
            if len(unis) == 1:
                u = self.display(unis[0])
                city = key(self.o.at[unis[0], "city"])
                if ((self.o.display_name == u).sum() > 1 or city in k) and city not in key(u):
                    u += " " + self.o.at[unis[0], "city"]
                return outcome("ROR", unis[0], u + " Teaching Hospital", case.force, "R1 TH -> university ID")
            ws = ws[:-1]
        return None

    def research_record(self, case):
        """The 14-15 Oct research of this spelling (research.csv, research_deepdive.csv)."""
        if case.clean not in self.res.index:
            return None
        r = self.res.loc[case.clean]
        verified = r.evidence == "web-searched"
        searched = r.evidence in ("web-searched", "searched, not found")
        decide = {
            "SUGGEST": self.research_suggest,
            "ROR": self.research_ror,
            "NOT_IN_ROR": self.research_not_in_ror,
            "TYPE": self.research_type,
        }.get(r.outcome)
        if decide:
            return decide(case, r, verified, searched)
        if verified:  # UNKNOWN after a search
            return self.uncoded(case, "searched, not identified -> uncoded")
        return None

    def research_suggest(self, case, r, verified, searched):
        """The deep dive found a candidate, not a decision: suggested."""
        i = r.ror_id
        return outcome(
            name=self.tidy(case.clean),
            typ=case.force or self.org_type(i, self.display(i)),
            rule=f"deep dive (suggested): {r.note}",
            suggestion=i,
        )

    def research_ror(self, case, r, verified, searched):
        """The research found a ROR record: used if allowed in the learner's country, else an in-country alternative,
        else uncoded."""
        i = self.ror.resolve(r.ror_id) or r.ror_id
        if self.allowed(i, case.cc):
            o_ = self.ror_outcome(i, f"research ({r.evidence})", case.force, case.cc)
            if r["name"]:
                o_["canonical_name"] = r["name"]
                o_["org_type"] = case.force or self.kw.type(r["name"]) or o_["org_type"]
            return o_
        alt = self.in_country_alt(case.clean, case.cc)
        if alt:
            return self.ror_outcome(alt, "R2 in-country alternative", case.force, case.cc)
        return self.uncoded(case, "R2 research match in other country -> uncoded")

    def research_not_in_ror(self, case, r, verified, searched):
        """The research confirmed an organisation that is not in ROR: a LOCAL ID when confirmed with 2+ learners
        (one learner: stage replay.known_organisations, rule 7.1), else uncoded with the name."""
        typ = case.force or r.org_type or self.kw.type(r["name"])
        if case.cc and r.country and case.cc != r.country:
            return outcome(name=r["name"], typ=typ, rule="R2 not-in-ROR org in other country -> uncoded")
        return self.named_not_in_ror(
            r["name"], r.country, typ, verified, self.res_name_learners[key(r["name"])], "R5 not in ROR", searched
        )

    def research_type(self, case, r, verified, searched):
        """The research found only a name or a type: the ROR record of that name, a LOCAL ID, or the type."""
        if r.org_type in ("NOT_APPLICABLE", "NOT_SPECIFIED"):
            return outcome(typ=r.org_type, rule="research: no organisation")
        n = r["name"] or self.tidy(case.clean)
        if case.cc and r.country and case.cc != r.country:
            return outcome(name=n, typ=case.force or r.org_type, rule="R2 named org in other country -> uncoded")
        hit = [i for i in self.name_idx.get(key(n), ()) if self.allowed(i, case.cc)]
        if len(hit) == 1:
            return self.ror_outcome(hit[0], "research name in ROR", case.force or r.org_type, case.cc)
        nl = self.res_name_learners[key(n)] if r["name"] else self.learners.get(case.clean, 0)
        return self.named_not_in_ror(
            n,
            r.country if r["name"] else case.cc,
            case.force or r.org_type,
            verified,
            nl,
            f"R0 type {r.org_type}",
            searched,
        )

    def unit_of_university(self, case):
        """R1: "<unit>, <university>": one part is exactly one in-country university, the others are units."""
        parts = [key(x) for x in re.split(r"[,/;()|]| - ", case.clean) if key(x)]
        if len(parts) < 2:
            return None
        hit = {
            i
            for p_ in parts
            for i in self.name_idx.get(p_, ())
            if self.cc_of(i) == case.cc and "education" in self.types(i)
        }
        rest = [p_ for p_ in parts if not any(self.cc_of(i) == case.cc for i in self.name_idx.get(p_, ()))]
        if (
            len(hit) == 1
            and rest
            and not any("hospital" in p_.split() for p_ in rest)
            and all(set(p_.split()) & UNIT_WORDS or self.strip_countries(p_) == "" for p_ in rest)
        ):
            i = hit.pop()
            return outcome("ROR", i, self.display(i), self.org_type(i, self.display(i)), "R1 unit -> university")
        return None

    def exact_name(self, case):
        """R2/R3: the spelling is a ROR name (or, for one word, an acronym)."""
        clean, cc, k = case.clean, case.cc, case.k
        ids = set(self.name_idx.get(k, set())) or set(self.name_idx.get(key(without_brackets(clean)), set()))
        if " " not in k and 2 <= len(k) <= 8:
            ids |= self.acr_idx.get(compact(k), set())
        if not ids:
            return None
        inc = sorted(i for i in ids if self.cc_of(i) == cc)
        if len(inc) == 1 or (not cc and len(ids) == 1):
            return self.ror_outcome((inc or list(ids))[0], "R2 exact in country", case.force, cc)
        if len(inc) > 1:
            return self.headquarters(case, inc)
        ok = [i for i in ids if self.allowed(i, cc)]
        if (
            len(ok) == 1
            and cc
            and self.cc_of(ok[0]) != cc
            and not self.checked_abroad(ok[0], cc)
            and (" " not in k or not specific(k, ngo=True))
        ):
            ok = []  # rule 5.2: one-word or generic NGO/company names are not coded abroad
        if len(ok) == 1:
            return self.ror_outcome(ok[0], "R2 international/exception", case.force, cc)
        alt = self.in_country_alt(clean, cc)
        if alt:
            return self.ror_outcome(alt, "R2 in-country alternative", case.force, cc)
        if " " in k and all(self.types(i) and self.types(i)[0] == "government" for i in ids):
            return self.named_not_in_ror(
                self.tidy(clean),
                cc,
                "GOVERNMENT",
                False,
                self.learners.get(clean, 0),
                "P2 government body abroad -> own country's body",
            )
        return self.uncoded(case, "R2 exact match only in other country -> uncoded")

    def checked_abroad(self, i, cc):
        """International body, record checked by hand (settings abroad_checked) or country exception."""
        return (
            i in self.S["international"]["ror_ids"]
            or i in self.S["abroad_checked"]["ror_ids"]
            or self.country_exception(i, cc)
        )

    def headquarters(self, case, inc):
        """P1/R3: several in-country records with the name: the one the others hang under, else uncoded."""
        same = {i for i in self.active if key(self.display(i)) == key(self.display(inc[0]))}
        hq = [i for i in inc if any(i in self.o.at[j, "parent_ids"].split(";") for j in same)]
        if len(hq) == 1:
            return self.ror_outcome(hq[0], "P1 several in country -> headquarters", case.force, case.cc)
        return self.uncoded(case, "R3 several institutions in country -> uncoded")

    def branch(self, case):
        """R3: "<shared name> <place>": the branch record in that place, else a branch not in ROR."""
        ws = case.k.split()
        for n in range(len(ws) - 1, 1, -1):
            base, rest = " ".join(ws[:n]), ws[n:]
            inc = sorted(i for i in self.name_idx.get(base, ()) if self.cc_of(i) == case.cc)
            if len(inc) > 1:
                br = [i for i in inc if key(self.o.at[i, "city"]) and key(self.o.at[i, "city"]) in " ".join(rest)]
                if len(br) == 1:
                    return self.ror_outcome(br[0], "R3 branch in ROR", case.force, case.cc)
                return self.named_not_in_ror(
                    self.tidy(case.clean),
                    case.cc,
                    case.force or self.kw.type(case.clean),
                    False,
                    self.learners.get(case.clean, 0),
                    "R3 branch not in ROR",
                )
        return None

    def distinctive_words(self, case):
        """(words, distinctive words) of the spelling: without countries and stopwords; the second also without generic
        words."""
        ws = set(self.strip_countries(case.k).split()) - set(self.S["coverage_stopwords"])
        return ws, ws - set(self.S["generic_words"])

    def word_coverage(self, case):
        """P3: exactly one in-country candidate holds every word of the spelling (suggestion only)."""
        ws, distinctive = self.distinctive_words(case)
        if case.clean not in self.cand.index or not distinctive:
            return None
        gen = set(self.S["generic_words"]) | set(self.S["coverage_stopwords"])

        def extra_distinctive(i):  # distinctive words of the candidate's name that the spelling lacks
            own = set(self.strip_countries(key(without_brackets(self.display(i)))).split())
            return own - gen - ws - {key(self.o.at[i, "city"])}

        cov = [
            i
            for i in (self.cand.at[case.clean, f"c{j}_id"] for j in (1, 2, 3))
            if i and self.cc_of(i) == case.cc and ws <= self.id_tokens[i] and not extra_distinctive(i)
        ]
        rivals = [j for j in self.ids_by_cc.get(case.cc, ()) if j not in cov and ws <= self.id_tokens.get(j, set())]
        if len(set(cov)) == 1 and not rivals:
            return outcome(
                name=self.tidy(case.clean),
                typ=case.force or self.org_type(cov[0], self.display(cov[0])),
                rule="P3 word coverage (suggested)",
                suggestion=cov[0],
            )
        return None

    def fuzzy_candidate(self, case):
        """P4: a clear in-country fuzzy candidate whose names hold a close match of every distinctive word
        (suggestion only); otherwise the spelling stays uncoded ("no match")."""
        _, distinctive = self.distinctive_words(case)
        f = self.fuzzy_accept(case.clean, case.cc) if distinctive else None
        if f and any(
            len(w) >= 3 and not get_close_matches(w, list(self.id_tokens[f]), n=1, cutoff=0.75) for w in distinctive
        ):
            f = None
        if f:
            return outcome(
                name=self.tidy(case.clean),
                typ=case.force or self.org_type(f, self.display(f)),
                rule="P4 fuzzy (suggested)",
                suggestion=f,
            )
        return self.named_not_in_ror(
            self.tidy(case.clean),
            case.cc,
            case.force or self.kw.type(case.clean),
            False,
            self.learners.get(case.clean, 0),
            "no match",
        )

    def decide(self, clean, cc):
        """The outcome of one spelling and country: the first rule in RULES that decides it."""
        case = Case(clean, cc, key(clean))
        for rule in self.RULES:
            result = rule(case)
            if result is not None:
                return result
        raise AssertionError("the last rule always decides")

    def decide_all(self, todo, force_of):
        """One row per spelling and learner country not decided by stage 2."""
        rows = []
        for c in todo:
            for cc in [x for x in dict.fromkeys(self.ucs.get(c, [""])) if x not in self.done_cc.get(c, set())]:
                r_ = self.decide(c, cc)
                ft = force_of.get(c, "")
                no_org = r_["org_type"] in ("NOT_APPLICABLE", "NOT_SPECIFIED")  # rule 4.1-4.2 wins over a keyword
                if (
                    ft
                    and not no_org
                    and r_["id_kind"] != "ROR"
                    and r_["org_type"] != "TEACHING_HOSPITAL"
                    and not r_["suggestion_id"]
                ):
                    kt = self.kw.type(r_["canonical_name"] or c)
                    r_["org_type"] = kt if kt in ("HOSPITAL", "GOVERNMENT", "EDUCATION", "RESEARCH") else ft
                    r_["rule"] += f" | step-4 type {ft}" + (f" -> name says {kt}" if r_["org_type"] != ft else "")
                rows.append(dict(clean=c, country=cc, **r_))
        return pd.DataFrame(rows)


def run_engine(ctx, cleans_csv, out_csv):
    """Decide every spelling of cleans_csv (column clean, optional force_type) and save the issued LOCAL IDs."""
    todo_df = pd.read_csv(cleans_csv, keep_default_na=False)
    force_of = dict(zip(todo_df.clean, todo_df.force_type)) if "force_type" in todo_df else {}
    engine = Engine(ctx)
    res = engine.decide_all(todo_df.clean.tolist(), force_of)
    res.to_csv(out_csv, index=False)
    engine.reg.save()
    print(
        f"{out_csv.rsplit('/', 1)[-1]}: {len(res)} rows | new LOCAL IDs: {len(engine.reg.new)} "
        f"| pending research: {int(res.pending.sum())}"
    )


def write_research_views(ctx):
    """The 14-15 Oct research and reviewer decisions as the tables the engine reads (views of the ledger)."""
    led = ctx.ledger
    r = led.batch("research_14oct")
    r.rename(columns={"target": "outcome", "org_country": "country_"}).assign(country=lambda d: d.country_)[
        ["clean", "ror_id", "name", "country", "org_type", "evidence", "source", "note", "outcome", "date"]
    ].to_csv(ctx.w("research.csv"), index=False)
    d = led.batch("deepdive_15oct")
    d.rename(columns={"target": "outcome"}).assign(country=lambda x: x.org_country)[
        ["clean", "outcome", "ror_id", "name", "country", "org_type", "evidence", "source", "note", "date"]
    ].to_csv(ctx.w("research_deepdive.csv"), index=False)
    e = led.batch("reviewer_14oct")
    e.rename(columns={"note": "decision", "target": "exp_kind", "ror_id": "exp_id", "org_type": "exp_type"})[
        ["clean", "country", "decision", "exp_kind", "exp_id", "exp_type"]
    ].to_csv(ctx.w("decisions_expected.csv"), index=False)
    pd.DataFrame({"clean": list(dict.fromkeys(e.clean))}).to_csv(ctx.w("validation_cleans.csv"), index=False)


def write_engine_input(ctx):
    """engine_input.csv: the fuzzy-stage spellings, stage 4's named organisations (except generic answers) and the
    spellings stage 3 matched in some countries only."""
    rd = lambda f: pd.read_csv(ctx.w(f), keep_default_na=False, dtype=str)  # noqa: E731
    cand, c4, m3 = rd("candidates_step5.csv"), rd("codes_step4.csv"), rd("matched_step3.csv")
    generic = set(ctx.settings["generic_keep_type_no_name"])
    rows = [dict(clean=c, force_type="", source="review") for c in cand.clean]
    rows += [
        dict(clean=r.clean, force_type=r.code, source="step4")
        for r in c4.itertuples(index=False)
        if r.code in ("HOSPITAL", "GOVERNMENT", "COMPANY_OR_NGO") and r.clean not in generic
    ]
    done = {r["clean"] for r in rows}
    rows += [
        dict(clean=c, force_type="", source="step3 partial")
        for c in dict.fromkeys(m3[m3.country != ""].clean)
        if c not in done
    ]
    pd.DataFrame(rows).to_csv(ctx.w("engine_input.csv"), index=False)


def validation_status(r):
    """MATCH / MISMATCH_ID / MISMATCH_TYPE / PENDING_RESEARCH of one reviewer decision."""
    pend = str(r.pending) == "True"
    if r.exp_kind == "MOH":
        id_ok = r.rule.startswith("R5 MoH")
    elif r.exp_kind == "?":
        id_ok = True
    elif r.exp_kind == "ROR":
        id_ok = r.id_kind == "ROR" and r.institution_id == r.exp_id
    elif r.exp_kind == "LOCAL":
        id_ok = r.id_kind == "LOCAL"
        if not id_ok and pend:
            return "PENDING_RESEARCH"
    else:
        id_ok = r.id_kind == ""
    type_ok = r.exp_type == "?" or r.exp_type == r.org_type
    if id_ok and type_ok:
        return "MATCH"
    return "MISMATCH_ID" if not id_ok else "MISMATCH_TYPE"


def validate(ctx):
    """Compare the engine with the reviewer's decisions of 14 Oct (suggestions and overrides count as answers)."""
    e = pd.read_csv(ctx.w("decisions_expected.csv"), keep_default_na=False)
    g = pd.read_csv(ctx.w("validation_engine.csv"), keep_default_na=False)
    x = e.merge(g, on=["clean", "country"], how="left").astype({"pending": str})
    ov = ctx.ledger.overrides()
    for j, r in x.iterrows():
        if r.suggestion_id:
            x.at[j, "id_kind"], x.at[j, "institution_id"] = "ROR", r.suggestion_id
        k = f"{r.clean}|{r.country}"
        if k in ov:
            x.at[j, "id_kind"], x.at[j, "institution_id"], x.at[j, "pending"] = ("ROR" if ov[k] else ""), ov[k], "False"
    x["status"] = x.apply(validation_status, axis=1)
    o = Ror(ctx.ror_dir).orgs

    def label(i):
        return f"{o.at[i, 'display_name']} ({o.at[i, 'country_code']})" if i in o.index else i

    expected_kind = {"": "no ID", "?": "any", "LOCAL": "local ID", "MOH": "MoH rule"}
    x["expected"] = [
        (label(i) if k == "ROR" else expected_kind[k]) + f" / {t}" for i, k, t in zip(x.exp_id, x.exp_kind, x.exp_type)
    ]
    x["engine"] = [
        (label(i) if k == "ROR" else (i or "no ID")) + f" / {t or '-'}"
        for i, k, t in zip(x.institution_id, x.id_kind, x.org_type)
    ]
    x.to_csv(ctx.w("validation_result.csv"), index=False)
    print("validation against the reviewer's decisions:", x.status.value_counts().to_dict())
    for r in x[x.status != "MATCH"].itertuples(index=False):
        print(f"  {r.status}: {r.clean[:55]} [{r.country}] expected {r.expected} | engine {r.engine} | rule {r.rule}")


def run(ctx):
    write_engine_input(ctx)
    write_research_views(ctx)
    run_engine(ctx, ctx.w("validation_cleans.csv"), ctx.w("validation_engine.csv"))
    validate(ctx)
    run_engine(ctx, ctx.w("engine_input.csv"), ctx.w("full_engine.csv"))
