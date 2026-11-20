"""stages/apply_decisions.py on 12 made-up decisions, one per case the applier must handle.

Needs a run (IM_RUN_DIR, IM_ROR_DIR): the decisions are applied to that run's mapping before apply_decisions, in a
temporary folder; nothing of the run or the repository changes.
"""

import shutil

import pandas as pd
import pytest

from institution_mapping.pipeline import CODING, Run
from institution_mapping.stages import apply_decisions


def decision(id_, columns, **fields):
    r = dict.fromkeys(columns, "")
    r.update(id=id_, batch="decisions", date="2026-10-18", **fields)
    return r


CASES = [  # (id, decision, expected result)
    (
        "T01",
        dict(
            raw_institution="Acasus",
            country="NG",
            target="LOCAL",
            name="Acasus",
            org_country="NG",
            source="https://acasus.com",
            rationale_type="source",
            rationale="https://acasus.com",
        ),
        "applied",
    ),
    ("T02", dict(raw_institution="Adrita", country="BD", target="NS", rationale_type="none recorded"), "refused"),
    (
        "T03",
        dict(
            raw_institution="21September University for Medicine and Applied Sciences",
            country="YE",
            target="05b8hjk91",
            rationale_type="source",
            rationale="x",
        ),
        "refused",
    ),
    (
        "T04",
        dict(
            raw_institution="21September University for Medicine and Applied Sciences",
            country="YE",
            target="05b8hjk91",
            extra="override",
            name="Test name",
            rationale_type="client decision",
            rationale="client: test",
        ),
        "applied",
    ),
    (
        "T05",
        dict(raw_institution="ABI", country="NG", target="04snhqa82", rationale_type="source", rationale="test"),
        "applied",
    ),
    (
        "T06",
        dict(raw_institution="ABI", country="NG", target="00ma0mg56", rationale_type="source", rationale="test"),
        "refused",
    ),
    (
        "T07",
        dict(
            raw_institution="ADEOYE FARMS",
            country="NG",
            target="LOCAL",
            name="Mwai Kibaki Referral Hospital",
            org_country="KE",
            rationale_type="source",
            rationale="test",
        ),
        "applied",
    ),
    (
        "T08",
        dict(
            raw_institution="Adullam Development Research Centre",
            country="NG",
            target="LOCAL",
            name="National University, Bangladesh",
            org_country="BD",
            rationale_type="source",
            rationale="test",
        ),
        "applied",
    ),
    (
        "T09",
        dict(raw_institution="No such answer", country="NG", target="NS", rationale_type="rule", rationale="4.2"),
        "not in this input",
    ),
    (
        "T10",
        dict(
            raw_institution="AEM GUINEA", country="GN", target="TH:04snhqa82", rationale_type="rule", rationale="test"
        ),
        "refused",
    ),
    (
        "T11",
        dict(
            raw_institution="AEMC benin",
            country="BJ",
            target="UNC",
            note="searched: several candidates",
            rationale_type="searched, not found",
            rationale="several",
        ),
        "applied",
    ),
    (
        "T12",
        dict(
            raw_institution="Advanced Material Solutions",
            country="GB",
            target="TYPE:COMPANY_OR_NGO",
            rationale_type="rule",
            rationale="4.3",
        ),
        "applied",
    ),
]


@pytest.fixture(scope="module")
def applied(run_dir, ror_dir, tmp_path_factory):
    ctx = Run(None, ror_dir, tmp_path_factory.mktemp("decisions"))
    shutil.copytree(CODING, ctx.coding)
    shutil.copyfile(
        Run(None, None, run_dir).previous_mapping("apply_decisions"), ctx.previous_mapping("apply_decisions")
    )
    ledger = pd.read_csv(ctx.c("decisions.csv"), keep_default_na=False, dtype=str)
    ledger = ledger[ledger.batch != "decisions"]  # only the test's own decisions
    test_rows = [decision(i, ledger.columns, **d) for i, d, _ in CASES]
    pd.concat([ledger, pd.DataFrame(test_rows)]).to_csv(ctx.c("decisions.csv"), index=False)
    apply_decisions.run(ctx)
    report = pd.read_csv(ctx.o("decisions_report.csv"), keep_default_na=False, dtype=str).set_index("id")
    m = pd.read_csv(ctx.mapping("apply_decisions"), keep_default_na=False, dtype=str)
    return report, m.set_index(["raw_institution", "country"])


@pytest.mark.parametrize(("id_", "expected"), [(i, e) for i, _, e in CASES])
def test_result(applied, id_, expected):
    report, _ = applied
    assert report.at[id_, "result"] == expected


def test_outcomes(applied):
    _, m = applied
    row = m.loc
    assert row[("Acasus", "NG"), "id_kind"] == "LOCAL" and row[("Acasus", "NG"), "institution_id"] > "LOCAL-0614"
    assert row[("ADEOYE FARMS", "NG"), "institution_id"] == "LOCAL-0044"  # existing LOCAL ID reused
    assert row[("Adullam Development Research Centre", "NG"), "institution_id"] == "045p37n96"  # retired -> ROR
    assert row[("AEMC benin", "BJ"), "status"] == "uncoded"
    assert row[("Advanced Material Solutions", "GB"), "org_type"] == "COMPANY_OR_NGO"
    assert row[("Advanced Material Solutions", "GB"), "institution_id"] == ""
