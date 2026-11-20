"""A client's session (rulebook 9.6, 11.8): its decisions file is read after the ledger, taken in before a release,
written by tools/add_decisions.py --to (with overrides for judgement calls), and the sheet is coded again with the
session's own mapping."""

import importlib.util

import openpyxl
import pandas as pd
import pytest

from institution_mapping import __main__ as cli
from institution_mapping import code_sheet, pipeline
from institution_mapping.core.ledger import take_in, with_decision_files
from institution_mapping.pipeline import CODING, REPO

COLUMNS = list(pd.read_csv(CODING / "decisions.csv", nrows=0).columns)


def ledger_rows(ids, answer="x"):
    return pd.DataFrame(
        [
            {c: "" for c in COLUMNS}
            | dict(
                id=i,
                batch="decisions",
                raw_institution=f"{answer}{i}",
                country="KE",
                target="NS",
                rationale_type="rule",
            )
            for i in ids
        ]
    )


@pytest.fixture
def ledger_and_input(tmp_path):
    ledger = tmp_path / "decisions.csv"
    ledger_rows(["D00009", "D00010"]).to_csv(ledger, index=False)
    inp = tmp_path / "input"
    inp.mkdir()
    ledger_rows(["decisions_2026-11-21_b-0001"], "b").to_csv(inp / "decisions_2026-11-21_b.csv", index=False)
    ledger_rows(["decisions_2026-11-20_a-0001", "decisions_2026-11-20_a-0002"], "a").to_csv(
        inp / "decisions_2026-11-20_a.csv", index=False
    )
    return ledger, inp


def test_a_run_reads_the_decisions_files_after_the_ledger(ledger_and_input, tmp_path):
    ledger, inp = ledger_and_input
    with_decision_files(ledger, inp, tmp_path / "run.csv")
    d = pd.read_csv(tmp_path / "run.csv", dtype=str, keep_default_na=False)
    assert d.id.tolist() == [
        "D00009",
        "D00010",
        "decisions_2026-11-20_a-0001",
        "decisions_2026-11-20_a-0002",
        "decisions_2026-11-21_b-0001",
    ]
    assert d.columns.tolist() == COLUMNS


def test_take_in_keeps_the_order_and_numbers_on(ledger_and_input, tmp_path):
    ledger, inp = ledger_and_input
    with_decision_files(ledger, inp, tmp_path / "before.csv")
    assert take_in(ledger, inp) == {"decisions_2026-11-20_a.csv": 2, "decisions_2026-11-21_b.csv": 1}
    assert not list(inp.iterdir())
    after = pd.read_csv(ledger, dtype=str, keep_default_na=False)
    before = pd.read_csv(tmp_path / "before.csv", dtype=str, keep_default_na=False)
    assert after.id.tolist() == ["D00009", "D00010", "D00011", "D00012", "D00013"]
    assert after.drop(columns="id").equals(before.drop(columns="id"))  # the same decisions, in the same order


def test_release_waits_for_decisions_files(tmp_path, monkeypatch):
    (tmp_path / "decisions_2026-11-20_a.csv").write_text("id\n")
    monkeypatch.setattr(pipeline, "INPUT", tmp_path)
    with pytest.raises(SystemExit, match="take them in first"):
        cli.release(tmp_path / "out", "2026-11-20")


def add_decisions():
    spec = importlib.util.spec_from_file_location("add_decisions", REPO / "tools" / "add_decisions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_add_decisions_writes_the_session_file_with_overrides(tmp_path, capsys):
    groups = tmp_path / "judgement_calls.csv"
    pd.DataFrame(
        [dict(gid=1, raw_institution="New Clinic", country="KE"), dict(gid=2, raw_institution="Old Uni", country="KE")]
    ).to_csv(groups, index=False)
    ror = tmp_path / "ror"
    ror.mkdir()
    pd.DataFrame([dict(ror_id="02y9nww90", status="active", country_code="KE")]).to_csv(ror / "ror_orgs.csv")
    ledger = tmp_path / "decisions.csv"
    rows = ledger_rows(["D00010"])
    rows.loc[0, ["raw_institution", "target"]] = ["Old Uni", "LOCAL"]
    rows.to_csv(ledger, index=False)
    to = tmp_path / "decisions_2026-11-20_trial.csv"
    sheet = tmp_path / "ws.txt"
    args = [str(groups), str(sheet), str(ror), str(ledger), "2026-11-20", "--to", str(to)]

    sheet.write_text("2 | 02y9nww90 |  |  |  | client decision |  | the client: it is the university\n")
    assert add_decisions().main(args) == 1  # a decided row needs override
    assert "already has a decision" in capsys.readouterr().out

    sheet.write_text(
        "1 | LOCAL | New Clinic | HOSPITAL | KE | source | https://example.org | its website\n"
        "2 | 02y9nww90 |  |  |  | client decision |  | the client: it is the university | override\n"
    )
    assert add_decisions().main(args) == 0
    d = pd.read_csv(to, dtype=str, keep_default_na=False)
    assert d.id.tolist() == ["decisions_2026-11-20_trial-0001", "decisions_2026-11-20_trial-0002"]
    assert d.extra.tolist() == ["", "override"] and d.columns.tolist() == COLUMNS
    assert d.rule_code.tolist() == ["", "ROR-CLIENT"]  # a ROR ID set by a client (rulebook 3.5)
    assert len(pd.read_csv(ledger)) == 1  # the ledger is not touched


def test_the_sheet_is_coded_again_with_the_session_mapping(tmp_path):
    columns = ["raw_institution", "country", "learners", "canonical_name", "institution_id", "org_type", "status"]
    wb = openpyxl.Workbook()
    wb.active.title = "mapping"
    wb.active.append(columns)
    wb.active.append(
        ["Brand New Institute", "KE", "1", "Brand New Institute", "LOCAL-9999", "RESEARCH", "coding complete"]
    )
    wb.save(tmp_path / "session.xlsx")
    sheet = tmp_path / "survey.csv"
    sheet.write_text("Institution,Country\nbrand new institute,KE\n", encoding="utf-8")
    assert code_sheet.run(sheet, "Institution", "Country", mapping=tmp_path / "session.xlsx") == 0
    out = (tmp_path / "survey_coded.csv").read_text(encoding="utf-8-sig").splitlines()
    assert out[1].endswith("Brand New Institute,LOCAL-9999,no,coded")
    assert "session mapping: session.xlsx" in (tmp_path / "survey_coding_log.txt").read_text(encoding="utf-8")


def test_with_the_session_mapping_no_list_is_written(tmp_path):
    columns = ["raw_institution", "country", "learners", "canonical_name", "institution_id", "org_type", "status"]
    wb = openpyxl.Workbook()
    wb.active.title = "mapping"
    wb.active.append(columns)
    wb.save(tmp_path / "session.xlsx")
    sheet = tmp_path / "survey.csv"
    sheet.write_text("Institution,Country\nJane Doe,KE\n", encoding="utf-8")
    assert code_sheet.run(sheet, "Institution", "Country", mapping=tmp_path / "session.xlsx") == 0
    out = (tmp_path / "survey_coded.csv").read_text(encoding="utf-8-sig").splitlines()
    assert out[1].endswith(code_sheet.LEFT_OFF) and not list(tmp_path.glob("unmapped_institutions_*"))


class FakeRorIndex:
    """ROR candidates by acronym, as search.RorIndex.candidates gives them."""

    orgs = pd.DataFrame({"display_name": ["Kenyatta National Hospital"]}, index=["053sj8m08"])

    def candidates(self, raw, cc):
        return {"053sj8m08": (90, "acronym KNH")} if "KNH" in raw and cc == "KE" else {}


def test_precedents_show_the_organisations_earlier_codes_and_ror_links():
    from institution_mapping.precedents import Precedents

    columns = ["raw_institution", "country", "institution_id", "canonical_name", "status", "org_type"]
    done = "coding complete"
    m = pd.DataFrame(
        [
            ["Kenyatta National Hospital", "KE", "053sj8m08", "Kenyatta National Hospital", done, "HOSPITAL"],
            ["KNH Nairobi", "KE", "053sj8m08", "Kenyatta National Hospital", done, "HOSPITAL"],
            ["University of Nairobi", "KE", "02y9nww90", "University of Nairobi", done, "EDUCATION"],
            ["Nairobi Hospital", "KE", "", "", "not identified", "HOSPITAL"],
        ],
        columns=columns,
    )
    led = ledger_rows(["D00001"]).assign(
        raw_institution="KNH staff",
        rationale_type="client decision",
        target="053sj8m08",
        rationale="the client: the hospital",
    )
    orgs = pd.DataFrame({"ror_id": ["053sj8m08", "02y9nww90"], "parent_ids": ["", ""]})
    p = Precedents(m, led, orgs, FakeRorIndex())
    found = p.organisations("UoN / KNH", "KE", proposed="02y9nww90")
    assert found == [
        ("02y9nww90", "University of Nairobi", "proposed", 1, 1),
        ("053sj8m08", "Kenyatta National Hospital", "acronym KNH", 2, 2),
    ]
    text = "\n".join(p.report("UoN / KNH", "KE", "02y9nww90"))
    assert "'knh' in KE: 1 answers" in text and "no ROR link between these organisations" in text
    assert "decided by a person: 'KNH staff' (KE) -> 053sj8m08 [client decision]" in text
    orgs.loc[1, "parent_ids"] = "053sj8m08"
    assert "053sj8m08 is a ROR parent of 02y9nww90" in Precedents(m, led, orgs, FakeRorIndex()).summary(
        "UoN / KNH", "KE", "02y9nww90"
    )
