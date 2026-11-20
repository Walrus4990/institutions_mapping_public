"""Stage 4: answers that name no organisation (NOT_APPLICABLE) and answers typed by keyword (rulebook 4.1, 4.3).

NOT_APPLICABLE: the exact no-organisation phrases, the patterns, the case decisions of 13 Oct (ledger batch
na_judged_13oct) and country names. A named organisation that is not an academic institution is typed GOVERNMENT,
HOSPITAL or COMPANY_OR_NGO by keyword, unless ROR may hold it (its acronym, or all its distinctive words in a ROR name
of the learner's country): then stage 5 proposes a record instead.
Reads  work/unmatched_after3.csv, work/spelling_country.csv, work/ror_names_clean.csv
Writes work/codes_step4.csv (clean, code, method) and work/unmatched_after4.csv (the rest)
"""

import re

import pandas as pd

from ..core import ror as ror_snapshot
from ..core.text import ARABIC_CYRILLIC, compact, words

NA_EXACT = set(
    """n/a|na|n a|not applicable|non applicable|no applicable|not ap|none|nil|nill|nilnil|no|non|nope|null|nothing
|not|not any|not now|no one|no organization|no organisation|no affiliation|don't have|i don't have
|i dont have|self|myself|me|self employed|self-employed|self employment|independent|independent researcher
|independent research|independet researcher|independent consultant|independent learner|individual
|private individual|freelance|freelancer|freelance consultant|consultant|retired|unemployed|personal|home
|ninguna|ninguno|independiente|travailleur independant|khong co|tidak ad|لا يوجد|ні|private practice
|petty business|home tution|none at the moment|not employed|not working|job seeker|nothing yet
|no institution|not affiliated|unaffiliated""".replace("\n", "").split("|")
)
# rule 4.2: the answer implies an organisation but does not name it (a role, a kind, junk, "other", "yes")
NS_EXACT = set(
    """yes|not available|unsure|confidential|other|others|student|students|private|priv|scholar|academic|test|x|xxx
|yy|bbb|gg|my organization|organization|institution|institutions|n/b|n/1|nose|he|se|research|public|academia
|nan""".replace("\n", "").split("|")
)
NS_PATTERNS = [r"^\W*$", r"^[\d\W]+$", r"^not available"]  # junk, numbers only, "not available"
NA_PATTERNS = [
    r"self[ -]?employ",
    r"^independent ",
    r"freelanc",
    r"unemploy",
    r"^not applicable",
    r"^no(t)? (affiliation|institution|organi[sz]ation|company|employer)",
    r"@[a-z0-9-]+\.(com|org|net)$",
]

EDU = (
    r"universit|college|institut|polytechni|school|academ|faculty|campus|research|laborator|\bcentre for\b"
    r"|\bcenter for\b|seminary|recherche|investigacion|forschung|lycee|liseyi|colegio"
)
GOV = (
    r"\bministr(y|e|ies|ere|erio)\b|\bministere\b|\bministerio\b|\bgovernment\b|\bgovt\b|\bgov\b|county government"
    r"|\bcouncil\b|\bagency\b|\bauthority\b|\bcommission\b|\bjudiciary\b|\bpolice\b|\barmy\b|air ?force|\bnavy\b"
    r"|\bparliament\b|\bbureau\b|\bdirectorate\b|\bsecretariat\b|municipal|\bdistrict health\b"
    r"|\bhealth (office|directorate|department|service)\b|\beducation service\b|\bbasic education\b"
    r"|\bstate ministry\b|\bwereda\b|\bworeda\b|hospital management board|\bfcdo\b|\bsenate\b|\bembassy\b"
)
HOSP = (
    r"hospital|hospitas|hopital|hôpital|clinic|clinique|polyclinic|poly clinic|medical cent(re|er)"
    r"|health cent(re|er)|dispensary|health post|maternity|\brrh\b|mosptial|مستشفى"
)
COMP = (
    r"\bltd\b|limited|\bplc\b|\binc\b|\bllc\b|gmbh|company|\bcompanies\b|consult|\bngo\b|\bong\b|foundation"
    r"|fundation|association|society|\btrust\b|initiative|network|organi[sz]ation|pharmacy|pharma\b|\bbank\b"
    r"|\bgroup\b|enterprise|ventures|solutions|\bfarms?\b|boutique|designs?\b|\bmedia\b|\bfm\b|magazine|airways"
    r"|airline|broadband|digital|technologies|\btech\b|entertainment|analytics|partners|partnership|\bchurch\b"
    r"|\bagency\b|marketing|law firm|cooperative|\bwomen\b.*\bnetwork\b|\bcharity\b|\bfund\b|diagnostics"
    r"|healthcare|\bindustries\b|\bconstruction\b|\bservices?\b|\bunicef\b|\bwfp\b|\bunhcr\b|\bundp\b"
    r"|\bunfpa\b|\bfao\b|\bfhi ?360\b|\bgiz\b|\biqvia\b|\bgenpact\b|world vision|save the children|\bmsf\b"
    r"|red cross|\bamref\b|\bpath\b"
)
KEYWORD_TYPES = [
    ("GOVERNMENT", r"management board|\bhealth service(s)? commission\b"),
    ("HOSPITAL", HOSP),
    ("GOVERNMENT", GOV),
    ("COMPANY_OR_NGO", COMP),
]
GENERIC = set(
    """the of and for in de la du ministry ministere ministerio government govt council agency authority commission
department state national federal county district regional hospital hospitals clinic clinique medical centre
center health general teaching specialist referral polyclinic poly ltd limited plc inc llc company
foundation association society trust initiative network organization organisation pharmacy group services
service private public international africa nigeria kenya ghana uganda tanzania ethiopia ngo""".split()
)


def key(s):
    """Punctuation-insensitive word string that keeps Arabic and Cyrillic letters."""
    return words(s, ARABIC_CYRILLIC)


class RorGuard:
    """Does ROR perhaps hold the organisation? Then the keyword type is not used."""

    def __init__(self, rn, active_orgs, countries_of):
        self.acronyms = set(rn[rn.name_kind == "acronym"].clean.map(compact))
        self.countries_of = countries_of
        city = dict(zip(active_orgs.ror_id, active_orgs.city.str.lower()))
        self.by_cc = {}
        for rid, cc, n in rn[rn.status == "active"][["ror_id", "country_code", "clean"]].itertuples(index=False):
            ws = set(key(n).split()) | set(key(city.get(rid, "")).split())
            ws |= {"center" for w in ws if w == "centre"} | {"centre" for w in ws if w == "center"}
            self.by_cc.setdefault(cc, []).append((ws, rid))
        self.generic = GENERIC | {c for c in countries(active_orgs)}

    def may_have(self, c):
        """True if ROR may hold the organisation (an acronym, or its distinctive words in a ROR name in the learner's
        country): then a keyword does not decide the type."""
        if compact(c) in self.acronyms:
            return True
        dist = set(key(c).split()) - self.generic
        if not dist:
            return False
        return any(any(dist <= ws for ws, _ in self.by_cc.get(cc, [])) for cc in self.countries_of.get(c, set()))


def countries(active_orgs):
    """Country names (lower case) that are not organisations."""
    return set(active_orgs.country.str.lower()) | {"united states", "usa", "uk"}


def classify(c, na_judged, country_names, guard):
    """'NOT_SPECIFIED' (rule 4.2), 'NOT_APPLICABLE' (4.1), a keyword org_type (4.3), or None."""
    k = c.strip()
    if k in NS_EXACT or k in country_names or any(re.search(p, k) for p in NS_PATTERNS):
        return "NOT_SPECIFIED"
    if k in NA_EXACT or k in na_judged or any(re.search(p, k) for p in NA_PATTERNS):
        return "NOT_APPLICABLE"
    if re.search(EDU, k):
        return None
    code = next((name for name, pat in KEYWORD_TYPES if re.search(pat, k)), None)
    return None if code and guard.may_have(k) else code


def run(ctx):
    t = pd.read_csv(ctx.w("unmatched_after3.csv"), keep_default_na=False)
    sc = pd.read_csv(ctx.w("spelling_country.csv"), keep_default_na=False)
    rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
    o = ror_snapshot.read_orgs(ctx.ror_dir)
    o = o[o.status == "active"]
    na_judged = set(ctx.ledger.batch("na_judged_13oct").clean)  # case decisions (rulebook 4.2)
    guard = RorGuard(rn, o, sc[sc.country != ""].groupby("clean").country.apply(set).to_dict())
    country_names = countries(o)
    out = [(c, code) for c in t.clean if (code := classify(c, na_judged, country_names, guard))]
    r4 = pd.DataFrame(out, columns=["clean", "code"]).merge(
        t[["clean", "user_count", "user_countries", "example_raw_spelling"]], on="clean"
    )
    r4["method"] = "keyword"
    r4.loc[r4.clean.isin(na_judged), "method"] = "judgement"
    r4.to_csv(ctx.w("codes_step4.csv"), index=False)
    left = t[~t.clean.isin(r4.clean)]
    left.to_csv(ctx.w("unmatched_after4.csv"), index=False)
    print(r4.groupby("code").agg(spellings=("clean", "size"), learners=("user_count", "sum")).to_string())
    print("still unmatched:", len(left))
