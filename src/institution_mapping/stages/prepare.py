"""Stage 1: remove personal data (rulebook step 0), clean every answer (step 1) and prepare the lookup tables.

Reads  IN_DIR/raw.csv (source, raw institution, country, learners) and the ROR snapshot.
Writes work/raw_with_clean.csv   one row per user-entered name and country, with its cleaned spelling
       work/spellings.csv        one row per cleaned spelling: learners, countries, most common raw spelling
       work/spelling_country.csv learners per cleaned spelling and country
       work/ror_names_clean.csv  every ROR name cleaned the same way, with the record's status and place
       work/norhed.csv           the NORHED partner list
Personal data is removed in memory, before any file is written; only the count is reported.
"""

import pandas as pd

from ..core import norhed, ror
from ..core.personal_data import personal_data
from ..core.text import clean


def read_answers(path, patterns):
    """raw.csv without personal data, one row per (raw, country) with learners summed, plus its cleaned spelling."""
    u = pd.read_csv(path, encoding="utf-8-sig", dtype={"raw institution": str, "country": str}, keep_default_na=False)
    u = u.rename(columns={"raw institution": "raw"})
    u["raw"] = u["raw"].str.strip()
    is_personal = u["raw"].map(lambda s: personal_data(s, patterns)) != ""
    print(
        f"step 0: answers removed as personal data: {int(is_personal.sum())} rows, "
        f"{int(u.loc[is_personal, 'learners'].astype(int).sum())} learners"
    )
    u = u[~is_personal]
    u = u[u["raw"] != ""].groupby(["raw", "country"], as_index=False, sort=False)["learners"].sum()
    u["clean"] = u["raw"].map(clean)
    return u


def most_common_raw(g):
    """The raw spelling with most learners; ties broken by the text."""
    return g.sort_values(["learners", "raw"], ascending=[False, True], kind="stable")["raw"].iloc[0]


def spellings(u):
    """One row per cleaned spelling, most learners first."""
    agg = (
        u.groupby("clean")
        .apply(
            lambda g: pd.Series(
                {
                    "user_count": g["learners"].sum(),
                    "user_countries": ";".join(
                        g.groupby("country")["learners"].sum().sort_values(ascending=False, kind="stable").index
                    ),
                    "example_raw_spelling": most_common_raw(g),
                    "n_raw_variants": g["raw"].nunique(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    return agg.sort_values("user_count", ascending=False, kind="stable")


def ror_names_clean(ror_dir):
    """Every ROR name with its cleaned form and the record's status, country and city."""
    o = ror.read_orgs(ror_dir)
    n = ror.read_names(ror_dir)
    n["clean"] = n["name"].map(clean)
    return n.merge(o[["ror_id", "status", "country", "country_code", "city"]], on="ror_id", how="left")


def run(ctx):
    u = read_answers(ctx.in_dir / "raw.csv", ctx.settings["personal_data"])
    u.to_csv(ctx.w("raw_with_clean.csv"), index=False)
    sp = spellings(u)
    sp.to_csv(ctx.w("spellings.csv"), index=False)
    u.groupby(["clean", "country"], as_index=False)["learners"].sum().to_csv(ctx.w("spelling_country.csv"), index=False)
    ror_names_clean(ctx.ror_dir).to_csv(ctx.w("ror_names_clean.csv"), index=False)
    norhed.table().to_csv(ctx.w("norhed.csv"), index=False)
    print(
        f"answers: {len(u)} rows, {u['learners'].sum()} learners | distinct raw {u['raw'].nunique()} "
        f"| distinct clean {len(sp)} | blank clean {(sp['clean'] == '').sum()}"
    )
