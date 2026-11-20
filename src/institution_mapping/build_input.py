"""Builds raw.csv, the input of a run: every answer to code, with its learner country and learner count.

Three sources, in this order:
1. the exports in input/historical_exports/ (an answer's learners are counted here when it is in an export):
     moodle_questionnaire_institution.csv   text = 'questionnaire institution text', else 'questionnaire other text';
                                            country = 'moodle country', else 'questionnaire country' as an ISO code
     moodle_custom_field_norhed.csv         text = 'custom institution text', country, 'n learners'
     moodle_builtin_field_institution.csv   text = 'institution', country, 'n users'
2. every answer of the published mapping (output/) that is in neither the exports nor the newest batch, with its
   learners: the mapping is the record of every answer ever coded, so no answer drops out when an export no longer
   holds it;
3. the M&E pipeline's batches at the root of input/ (unmapped_institutions_YYYY-MM-DD.xlsx: 'raw institution',
   'country', 'learners'), keeping only answers that are new under the pipeline's lookup key.
An answer leaves the mapping only by a recorded decision with target REMOVE (rulebook 9.2). Rows with an empty answer
are dropped. Personal data is NOT removed here: stage 1 removes it in memory, so raw.csv must stay outside the
repository (it holds what the learners typed).
"""

from pathlib import Path

import pandas as pd

from .core.ror import read_orgs
from .core.text import pipeline_key
from .pipeline import CODING, INPUT, OUTPUT

# questionnaire country spellings that ROR writes differently
COUNTRY_SPELLINGS = {
    "Tanzania, the United Republic of": "TZ",
    "Korea (the Republic of)": "KR",
    "Iran (Islamic Republic of)": "IR",
    "Viet Nam": "VN",
}
COLUMNS = ["source", "raw institution", "country", "learners"]


def _read(name):
    """An export from input/historical_exports/, as text."""
    return pd.read_csv(INPUT / "historical_exports" / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


EXPORTS = [
    "moodle_questionnaire_institution.csv",
    "moodle_custom_field_norhed.csv",
    "moodle_builtin_field_institution.csv",
]


def client_exports(ror_dir):
    """The three exports as tables with columns source, raw institution, country, learners. The exports are
    optional (rulebook 1.4): without them, every earlier answer comes from the published mapping, with its learners."""
    present = [n for n in EXPORTS if (INPUT / "historical_exports" / n).exists()]
    if not present:
        print("no exports in input/historical_exports/: the answers come from the published mapping and the batches")
        return []
    missing = sorted(set(EXPORTS) - set(present))
    assert not missing, f"input/historical_exports/ lacks {missing}: give all three exports, or none"
    q = _read("moodle_questionnaire_institution.csv")
    c = _read("moodle_custom_field_norhed.csv")
    b = _read("moodle_builtin_field_institution.csv")
    o = read_orgs(ror_dir)
    code_of = dict(zip(o.country, o.country_code)) | COUNTRY_SPELLINGS
    text = q["questionnaire institution text"].where(
        q["questionnaire institution text"] != "", q["questionnaire other text"]
    )
    missing = set(q.loc[q["moodle country"] == "", "questionnaire country"]) - set(code_of) - {""}
    assert not missing, f"questionnaire countries without an ISO code: {missing}"
    cc = q["moodle country"].where(
        q["moodle country"] != "", q["questionnaire country"].map(lambda x: code_of.get(x, ""))
    )
    return [
        pd.DataFrame({"source": "questionnaire", "raw institution": text, "country": cc, "learners": q["n learners"]}),
        pd.DataFrame(
            {
                "source": "custom field",
                "raw institution": c["custom institution text"],
                "country": c.country,
                "learners": c["n learners"],
            }
        ),
        pd.DataFrame(
            {"source": "moodle field", "raw institution": b.institution, "country": b.country, "learners": b["n users"]}
        ),
    ]


def pipeline_batches():
    """The M&E pipeline's batches at the root of input/, oldest first."""
    return sorted(INPUT.glob("unmapped_institutions_*.xlsx"))


def published_answers(exclude):
    """The answers of the published mapping that are not in `exclude` (a set of (answer, country))."""
    files = sorted(OUTPUT.glob("institution_mapping_*.xlsx"))
    if not files:
        return []
    m = pd.read_excel(files[-1], sheet_name="mapping", dtype=str, keep_default_na=False)
    m = m[[(a.strip(), c) not in exclude for a, c in zip(m.raw_institution, m.country)]]
    print(files[-1].name, "| answers carried forward", len(m))
    return [
        pd.DataFrame(
            {
                "source": "published mapping",
                "raw institution": m.raw_institution,
                "country": m.country,
                "learners": m.learners,
            }
        )
    ]


def removed_answers():
    """(answer, country) of the recorded decisions with target REMOVE."""
    d = pd.read_csv(CODING / "decisions.csv", dtype=str, keep_default_na=False)
    d = d[(d.batch == "decisions") & (d.target == "REMOVE")]
    return {(a.strip(), c) for a, c in zip(d.raw_institution, d.country)}


def new_pipeline_answers(parts):
    """The pipeline's unmapped lists: only answers whose pipeline key (rulebook 3.6) is new for their country. The
    pipeline normalises both sides of a lookup, so another spelling of a known answer is found without a row of its
    own; adding it would count its learners twice."""
    known = {(pipeline_key(a), c) for d in parts for a, c in zip(d["raw institution"], d.country)}
    out = []
    for f in pipeline_batches():
        u = pd.read_excel(f, dtype=str, keep_default_na=False)
        new = [(pipeline_key(a), c) not in known for a, c in zip(u["raw institution"], u.country)]
        print(f.name, "| answers", len(u), "| new under the pipeline key", sum(new))
        u = u[new]
        known |= {(pipeline_key(a), c) for a, c in zip(u["raw institution"], u.country)}
        out.append(
            pd.DataFrame(
                {
                    "source": "pipeline " + f.stem,
                    "raw institution": u["raw institution"],
                    "country": u.country,
                    "learners": u.learners,
                }
            )
        )
    return out


def build(ror_dir, out_csv):
    """Write raw.csv: the exports, the published mapping's other answers and the pipeline's new answers."""
    parts = client_exports(ror_dir)
    batch = {
        (str(a).strip(), c)
        for f in pipeline_batches()
        for a, c in pd.read_excel(f, dtype=str, keep_default_na=False)[["raw institution", "country"]].values
    }
    seen = {(a.strip(), c) for d in parts for a, c in zip(d["raw institution"], d.country)}
    parts += published_answers(seen | batch)
    parts += new_pipeline_answers(parts)
    u = pd.concat(parts, ignore_index=True)
    u = u[u["raw institution"].str.strip() != ""]
    removed = removed_answers()
    u = u[[(a.strip(), c) not in removed for a, c in zip(u["raw institution"], u.country)]]
    u["learners"] = u.learners.astype(int)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    u.to_csv(out_csv, index=False)
    print("rows", len(u), "| learners", int(u.learners.sum()), "|", u.groupby("source").size().to_dict())
