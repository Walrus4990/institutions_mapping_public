"""Stage 2: the cleaned spelling equals a ROR name (rulebook step 2).

Official names (display, label) are tried first, aliases only if no official name matches. An inactive record is
replaced by its one active successor. A name held by one record codes the spelling for its learners in the record's
country (and everywhere when the name is specific); a name held by several records is decided per learner country.
Reads  work/spellings.csv, work/spelling_country.csv, work/ror_names_clean.csv
Writes work/matched_step2.csv      clean, country ('' = every country), institution_id, method
       work/review_flags_step2.csv spellings left for the later stages, with the reason and the candidate IDs
"""

import pandas as pd

from ..core.ror import Ror
from ..core.text import specific, words


def name_index(rn, kinds):
    """cleaned name -> sorted ROR IDs, for the given name kinds."""
    t = rn[rn.name_kind.isin(kinds) & (rn.clean != "")]
    return t.groupby("clean")["ror_id"].apply(lambda s: sorted(set(s))).to_dict()


def candidates(c, tiers, resolve):
    """(tier, {final ROR ID: came via a successor}) for the first tier that holds the spelling."""
    for tier, idx in tiers:
        out = {}
        for rid in idx.get(c, []):
            fid = resolve(rid)
            if fid:
                out[fid] = out.get(fid, True) and fid != rid
        if out:
            return tier, out
    return None, {}


def decide_one_record(c, fid, via, ucs, o):
    """Matches and review flags for a spelling whose name has one record."""
    rcc = o.at[fid, "country_code"]
    method = "exact+successor" if via else "exact"
    if rcc in ucs and set(ucs) - {rcc} and not specific(words(c)):
        # learners in other countries get a record abroad only for a specific name (rule 5.2)
        return [(c, rcc, fid, method)], [
            (c, "exact match is in another country than some users; name not specific", fid)
        ]
    if rcc in ucs or not ucs:
        return [(c, "", fid, method)], []
    return [], [(c, "exact match is in another country than all users", fid)]


def decide_several_records(c, cands, ucs, o):
    """Matches and review flags for a spelling whose name has several records: one record per learner country."""
    picks = {}
    for cc in ucs:
        hit = [f for f in cands if o.at[f, "country_code"] == cc]
        picks[cc] = hit[0] if len(hit) == 1 else None
    ok = {cc: f for cc, f in picks.items() if f}
    rest = [cc for cc, f in picks.items() if not f]
    if ok and not rest and len(set(ok.values())) == 1:
        return [(c, "", next(iter(ok.values())), "exact+country")], []
    matches = [(c, cc, f, "exact+country") for cc, f in ok.items()]
    review = []
    if rest or not ok:
        review.append((c, "several institutions with this name; countries " + ",".join(rest or ucs), ";".join(cands)))
    return matches, review


def run(ctx):
    sp = pd.read_csv(ctx.w("spellings.csv"), keep_default_na=False)
    sc = pd.read_csv(ctx.w("spelling_country.csv"), keep_default_na=False)
    rn = pd.read_csv(ctx.w("ror_names_clean.csv"), dtype=str, keep_default_na=False)
    ror = Ror(ctx.ror_dir)
    o = ror.orgs
    tiers = [("name", name_index(rn, ["display", "label"])), ("alias", name_index(rn, ["alias"]))]
    matches, review = [], []
    for c in sp["clean"]:
        if not c:
            continue
        _, cands = candidates(c, tiers, ror.resolve)
        if not cands:
            continue
        ucs = list(sc[(sc.clean == c) & (sc.country != "")].sort_values("learners", ascending=False).country)
        if len(cands) == 1:
            fid, via = next(iter(cands.items()))
            mt, rv = decide_one_record(c, fid, via, ucs, o)
        else:
            mt, rv = decide_several_records(c, cands, ucs, o)
        matches += mt
        review += rv
    info = sp[["clean", "user_count", "example_raw_spelling", "user_countries"]]
    m = pd.DataFrame(matches, columns=["clean", "country", "institution_id", "method"]).merge(info, on="clean")
    m.to_csv(ctx.w("matched_step2.csv"), index=False)
    rv = pd.DataFrame(review, columns=["clean", "reason", "candidate_ids"]).merge(
        sp[["clean", "user_count", "user_countries", "example_raw_spelling"]], on="clean"
    )
    rv.to_csv(ctx.w("review_flags_step2.csv"), index=False)
    full = set(m[m.country == ""].clean) - set(rv.clean)
    print(
        f"fully matched spellings: {len(full)} | matched for some countries only: {m[m.country != ''].clean.nunique()} "
        f"| review: {len(rv)}"
    )
