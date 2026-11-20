"""Preparing the web search (rulebook step 7): which answers a person decided or searched before, the ROR candidates
of each answer to search, and groups of similar answers, so that one search decides a whole group.

Used by `python -m institution_mapping worklist` (worklist.py), and on their own through the scripts
tools/check_against_ledger.py, tools/ror_candidates.py and tools/group_uncoded.py.
"""

import re
from collections import defaultdict

import pandas as pd

from .core.fuzzy import score
from .core.text import clean, fold, pipeline_key

# words that do not tell two organisations apart
GENERIC = frozenset(
    """university college institute school faculty department of the and for in at center centre hospital national
    state federal health sciences science technology research medical teaching general district regional
    international public private community foundation organization organisation association society ltd limited
    company group network trust ministry government council agency board office unit campus de la du des del y
    et""".split()
)
CANDIDATE_GENERIC = GENERIC | {"program", "programme", "service", "services"}
KINDS = [  # the kind of an answer, for grouping: the first pattern that matches the cleaned text wins
    (
        "1 no organisation / not named",
        r"^(i |i'm |im |my |we |work |working |currently |not |no |none|nil|n/a|na$"
        r"|student|lecturer|teacher|self|retired|unemployed|independent|freelanc)",
    ),
    (
        "2 university or college",
        r"universit|college|polytechnic|academy|faculty"
        r"|institute of (technology|science|management|education|health|accountancy)|seminary",
    ),
    ("3 hospital", r"hospital|clinic|medical cent|health cent|dispensary|maternity"),
    (
        "4 government",
        r"ministry|government|county|council|municipal|district|authority|agency|commission|bureau|directorate"
        r"|department of|state of|national .* (service|board)",
    ),
    ("5 research", r"research|laborator|observatory|centre for|center for"),
    (
        "6 company or NGO",
        r"ltd|limited|plc|inc\b|company|consult|foundation|association|ngo|society|trust|initiative|network|group"
        r"|bank|church|ministries|enterprise",
    ),
    ("7 school", r"school|secondary|primary|academy"),
]
GROUP_COLUMNS = ["group", "country", "kind", "cluster", "cluster_size", "raw_institution", "learners", "org_type"]
GROUP_COLUMNS += ["evidence", "c1", "c2", "c3"]
NOT_IDENTIFIED = ["uncoded", "not identified"]  # an earlier mapping may say "uncoded"


def ledger_status(answers, ledger, mapping=None):
    """Each answer (columns raw_institution, country, ...) with what the ledger holds for it, and `ledger_status`:
    same_country (decided for this answer and country: do not search), other_country (decided for a learner in
    another country: read that first) or not_in_ledger. The same answer under rule 3.6 counts (cleaned text or
    pipeline key). With `mapping` (mapping_final.csv of a run on these answers), also its status and rule, and
    `needs_search` (not identified and not in the ledger)."""
    led = ledger.copy()
    led["k"] = [clean(r) if r else c for r, c in zip(led.raw_institution, led.clean)]
    out = answers.copy()
    out["k"] = out.raw_institution.map(clean)
    last = (
        led.groupby(["k", "country"])
        .agg(
            decisions=("id", "size"),
            last_decision=("target", "last"),
            last_batch=("batch", "last"),
            last_rationale=("rationale_type", "last"),
        )
        .reset_index()
    )
    anyc = (
        led.groupby("k")
        .country.agg(lambda s: ";".join(sorted(set(s) - {""})))
        .rename("decided_for_countries")
        .reset_index()
    )
    everywhere = set(led.k[led.country.isin(["", "*"])])  # decisions that apply to a spelling in every country
    out = out.merge(last, on=["k", "country"], how="left").merge(anyc, on="k", how="left").fillna("")
    led["pk"] = [pipeline_key(r) if r else pipeline_key(c) for r, c in zip(led.raw_institution, led.clean)]
    pk_cc, pk_any = set(zip(led.pk, led.country)), set(led.pk)
    pks = out.raw_institution.map(pipeline_key)
    out["ledger_status"] = [
        "same_country"
        if d or k in everywhere or (p, cc) in pk_cc
        else ("other_country" if c or p in pk_any else "not_in_ledger")
        for d, k, c, p, cc in zip(out.decisions, out.k, out.decided_for_countries, pks, out.country)
    ]
    if mapping is not None:
        f = mapping[["raw_institution", "country", "status", "rule"]]
        out = out.merge(f, on=["raw_institution", "country"], how="left")
        out["needs_search"] = out.status.isin(NOT_IDENTIFIED) & (out.ledger_status == "not_in_ledger")
    return out.drop(columns="k")


class RorIndex:
    """The active ROR records of a snapshot, indexed per country by acronym, by name and by distinctive word."""

    def __init__(self, ror_dir):
        o = pd.read_csv(f"{ror_dir}/ror_orgs.csv", dtype=str, keep_default_na=False)
        self.orgs = o[o.status == "active"].set_index("ror_id")
        n = pd.read_csv(f"{ror_dir}/ror_names.csv", dtype=str, keep_default_na=False)
        n = n[n.ror_id.isin(self.orgs.index)]
        self.acronyms = defaultdict(set)  # (country, acronym without spaces) -> ROR IDs
        self.names = defaultdict(list)  # country -> [(folded name, ROR ID)]
        self.by_word = defaultdict(lambda: defaultdict(set))  # country -> word -> positions in names[country]
        for k, cc, rid, kind in zip(n.name.map(fold), n.ror_id.map(self.orgs.country_code), n.ror_id, n.name_kind):
            if kind == "acronym":
                self.acronyms[(cc, k.replace(" ", ""))].add(rid)
            else:
                self.names[cc].append((k, rid))
                for w in set(k.split()) - CANDIDATE_GENERIC:
                    if len(w) > 2:
                        self.by_word[cc][w].add(len(self.names[cc]) - 1)

    def candidates(self, raw, cc):
        """{ROR ID: (score, how)} for an answer in the learner's country: its acronyms (in brackets, the whole
        one-word answer, or a word in capitals), ROR names of 2+ words inside it, and the fuzzy score of every name
        that shares a distinctive word with it."""
        k = fold(raw)
        best = {}

        def add(rid, s, how):
            if s > best.get(rid, (0, ""))[0]:
                best[rid] = (s, how)

        for a in (
            re.findall(r"\(([A-Za-z][A-Za-z0-9\- ]{1,12})\)", raw)
            + ([raw.strip()] if len(k.split()) == 1 else [])
            + re.findall(r"\b[A-Z]{3,8}\b", raw)
        ):
            ids = self.acronyms.get((cc, fold(a).replace(" ", "")), ())
            for rid in ids:
                add(rid, 90 if len(ids) == 1 else 70, "acronym " + a)
        near = set()
        for t in set(k.split()) - CANDIDATE_GENERIC:
            if len(t) > 2:
                near |= self.by_word[cc].get(t, set())
        for j in sorted(near):
            key, rid = self.names[cc][j]
            words = key.split()
            if len(words) >= 2 and set(words) - CANDIDATE_GENERIC and re.search(rf"(^| ){re.escape(key)}( |$)", k):
                add(rid, 88 + min(len(key), 40) / 10, "contained")
            add(rid, score(k, key), "fuzzy")
        return best


def ror_candidates(worklist, ror_dir):
    """The three best ROR candidates of each answer (columns raw_institution, country, learners, org_type, and
    optionally row and priority), in the learner's country: one row per answer with c1-c3 ('name (city) [ID] score
    how'), c1_id-c3_id and c1_s-c3_s. Equal scores are in the order of their ROR IDs."""
    index = RorIndex(ror_dir)
    w = worklist.copy()
    if "row" not in w:
        w["row"] = range(len(w))
    if "priority" not in w:
        w["priority"] = ""
    rows = []
    for r in w.itertuples(index=False):
        top = sorted(index.candidates(r.raw_institution, r.country).items(), key=lambda x: (-x[1][0], x[0]))[
            :3
        ]  # equal scores: by ROR ID
        rec = dict(
            row=r.row,
            raw=r.raw_institution,
            country=r.country,
            learners=r.learners,
            org_type=r.org_type,
            priority=r.priority,
        )
        for i in range(3):
            if i < len(top):
                rid, (s, how) = top[i]
                o = index.orgs.loc[rid]
                rec[f"c{i + 1}"] = f"{o.display_name} ({o.city}) [{rid}] {s:.0f} {how}"
                rec[f"c{i + 1}_id"], rec[f"c{i + 1}_s"] = rid, round(s)
            else:
                rec[f"c{i + 1}"] = rec[f"c{i + 1}_id"] = ""
                rec[f"c{i + 1}_s"] = 0
        rows.append(rec)
    return pd.DataFrame(rows)


def kind(raw):
    """The kind of an answer (KINDS), for grouping; '8 other' if none fits."""
    k = clean(raw)
    for name, pattern in KINDS:
        if re.search(pattern, k):
            return name
    return "8 other"


def distinct(raw):
    """The answer's distinctive words: neither GENERIC nor a single character."""
    return frozenset(t for t in re.sub(r"[^0-9a-z]+", " ", clean(raw)).split() if t not in GENERIC and len(t) > 1)


def clusters(u):
    """Per country, answers that name the same organisation in other spellings get one cluster (the same
    distinctive words, or a spelling score >= 88): a cluster ID per row of u (columns country, k, d)."""
    parent = {i: i for i in u.index}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for _, g in u.groupby("country"):
        idx = list(g.index)
        for n, a in enumerate(idx):
            for b in idx[n + 1 :]:
                da, db = u.at[a, "d"], u.at[b, "d"]
                if (da and da == db) or score(u.at[a, "k"], u.at[b, "k"]) >= 88:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[rb] = ra
    return [find(i) for i in u.index]


def group_uncoded(mapping, ledger, candidates, skip=()):
    """The not-identified rows of a run's mapping that no decision covers (and not in `skip`, a set of (answer,
    country)), grouped for the search: by country (most learners first), kind (KINDS) and cluster (clusters), with
    the best ROR candidates (`candidates`, from ror_candidates). Rows left uncoded by rule 5 (UNC-ABROAD) are not
    searched."""
    m = mapping.copy()
    m["learners"] = m.learners.astype(int)
    u = m[m.status.isin(NOT_IDENTIFIED) & (m.rule != "UNC-ABROAD")].copy()
    done = set(zip(ledger.raw_institution, ledger.country)) | set(skip)
    u = u[[(a, b) not in done for a, b in zip(u.raw_institution, u.country)]]
    u["kind"] = u.raw_institution.map(kind)
    u["k"] = u.raw_institution.map(clean)
    u["d"] = u.raw_institution.map(distinct)
    u["cluster"] = clusters(u)
    u = u.join(
        u.groupby("cluster").agg(cluster_learners=("learners", "sum"), cluster_size=("learners", "size")), on="cluster"
    )
    u = u.join(u.groupby("country").learners.sum().rename("country_learners"), on="country")
    c = candidates.rename(columns={"raw": "raw_institution"})[["raw_institution", "country", "c1", "c2", "c3"]]
    c = c.astype(str).drop_duplicates(["raw_institution", "country"])
    u = u.merge(c, on=["raw_institution", "country"], how="left").fillna("")
    u = u.sort_values(
        ["country_learners", "country", "kind", "cluster_learners", "cluster", "learners"],
        ascending=[False, True, True, False, True, False],
    )
    u["group"] = u.country + " | " + u.kind
    u["cluster"] = u.groupby("country").cluster.transform(lambda s: pd.factorize(s)[0] + 1)  # 1, 2, ... per country
    return u[GROUP_COLUMNS]
