"""Stage 5: up to three close ROR candidates for every spelling still open (rulebook step 5).

Candidates are university, facility and healthcare records sharing a distinctive word with the spelling (a misspelt
word is replaced by its closest ROR words, first among the learner's countries). They are scored with fuzzy.score;
records in a learner's country get a 10-point bonus for the ranking. Candidates are evidence for the rules engine
(stage 6) and the typo pass; they never code a row by themselves.
Reads  work/unmatched_after4.csv, work/review_flags_step2.csv, work/review_flags_step3.csv, work/spellings.csv,
       work/spelling_country.csv, work/ror_names_clean.csv
Writes work/candidates_step5.csv: clean, best_score, c1..c3 _id/_label/_score/_in_country
"""

from collections import Counter, defaultdict
from difflib import get_close_matches
from functools import lru_cache

import pandas as pd

from ..core.fuzzy import score
from ..core.ror import orgs_by_id
from ..core.text import words as key

CANDIDATE_TYPES = {"education", "facility", "healthcare"}


class CandidateIndex:
    """Inverted index from distinctive words to ROR names."""

    def __init__(self, rn, o):
        keep = {r for r in o.index[o.status == "active"] if CANDIDATE_TYPES & set(o.at[r, "types"].split(";"))}
        names = rn[rn.ror_id.isin(keep) & rn.name_kind.isin(["display", "label", "alias"])].copy()
        names["key"] = names.clean.map(key)
        names = names.drop_duplicates(["ror_id", "key"])
        names["cc"] = names.ror_id.map(o.country_code)
        df = Counter(w for k in names.key for w in set(k.split()))
        self.common = {w for w, n in df.items() if n > 1500} | {"of", "the", "and", "de", "la", "for", "in"}
        self.inv = defaultdict(set)
        self.vocab_cc = defaultdict(set)
        self.rows = list(zip(names.ror_id, names.key, names.cc))
        for i, (_, k, cc) in enumerate(self.rows):
            for w in set(k.split()) - self.common:
                self.inv[w].add(i)
                self.vocab_cc[cc].add(w)
        self.vocab_all = list(self.inv)

    @lru_cache(maxsize=None)  # noqa: B019 (one instance per stage)
    def close_words(self, w, countries):
        """Words of the index close to an unknown word: among the learners' countries first, then anywhere."""
        pool = set().union(*(self.vocab_cc[cc] for cc in countries)) if countries else set()
        close = get_close_matches(w, pool, n=3, cutoff=0.8) if pool and len(w) > 3 else []
        if not close and len(w) > 4:
            close = get_close_matches(w, self.vocab_all, n=3, cutoff=0.85)
        return close

    def candidates(self, c, countries):
        """[(ror_id, score, in learner's country)] for the best three records."""
        hit = set()
        for w in set(key(c).split()) - self.common:
            if w in self.inv:
                hit |= self.inv[w]
            else:
                for cw in self.close_words(w, frozenset(countries)):
                    hit |= self.inv[cw]
        best = {}
        for i in sorted(hit):
            rid, k, cc = self.rows[i]
            s = score(c, k)
            if s > best.get(rid, (0,))[0]:
                best[rid] = (s, cc in countries)
        ranked = sorted(best.items(), key=lambda x: (-(x[1][0] + (10 if x[1][1] else 0)), x[0]))[:3]
        return [(rid, round(s), inc) for rid, (s, inc) in ranked]


def run(ctx):
    sc = pd.read_csv(ctx.w("spelling_country.csv"), keep_default_na=False)
    sp = pd.read_csv(ctx.w("spellings.csv"), keep_default_na=False)
    rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
    o = orgs_by_id(ctx.ror_dir)
    todo = set(pd.read_csv(ctx.w("unmatched_after4.csv"), keep_default_na=False).clean)
    for f in ["review_flags_step2", "review_flags_step3"]:
        todo |= set(pd.read_csv(ctx.w(f"{f}.csv"), keep_default_na=False).clean)
    todo.discard("")
    index = CandidateIndex(rn, o)
    ucs = sc[sc.country != ""].groupby("clean").country.apply(lambda s: list(dict.fromkeys(s))).to_dict()
    out = []
    for c in sorted(todo):
        cs = index.candidates(c, set(ucs.get(c, [])))
        row = {"clean": c, "best_score": max([s for _, s, _ in cs], default=0)}
        for j, (rid, s, inc) in enumerate(cs, 1):
            row[f"c{j}_id"] = rid
            row[f"c{j}_label"] = f"{o.at[rid, 'display_name']} ({o.at[rid, 'city']}, {o.at[rid, 'country']})"
            row[f"c{j}_score"] = s
            row[f"c{j}_in_country"] = inc
        out.append(row)
    r5 = pd.DataFrame(out).merge(sp[["clean", "user_count", "user_countries", "example_raw_spelling"]], on="clean")
    r5.to_csv(ctx.w("candidates_step5.csv"), index=False)
    print(f"spellings given candidates: {len(r5)} | best score 90+: {(r5.best_score >= 90).sum()}")
