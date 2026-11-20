"""The client path (rulebook section 11): checks, lookup, NORHED, the coded copy, the list and the log."""

import openpyxl
import pandas as pd
import pytest

from institution_mapping import code_sheet as cs


def mapping(rows):
    cols = ["raw_institution", "country", "learners", "canonical_name", "institution_id", "org_type", "status"]
    return cs.Mapping(pd.DataFrame(rows, columns=cols))


DONE = "coding complete"
M = mapping(
    [
        ["St. Xavier's College", "NP", "5", "St. Xavier's College", "LOCAL-0068", "EDUCATION", DONE],
        ["Univ of Nairobi", "KE", "9", "University of Nairobi", "02y9nww90", "EDUCATION", DONE],
        ["Univ of Nairobi", "UG", "1", "University of Nairobi", "02y9nww90", "EDUCATION", DONE],
        ["Mercy Hospital", "KE", "3", "Mercy Hospital, Nairobi", "LOCAL-0900", "HOSPITAL", DONE],
        ["Mercy Hospital", "UG", "2", "Mercy Hospital, Kampala", "LOCAL-0901", "HOSPITAL", DONE],
        ["Mercy Hospital", "", "1", "", "", "HOSPITAL", "not identified"],
        ["retired", "KE", "4", "", "", "NOT_APPLICABLE", DONE],
        ["student", "KE", "4", "", "", "NOT_SPECIFIED", DONE],
        ["private clinic", "KE", "2", "", "", "HOSPITAL", DONE],
        ["XYZ", "KE", "1", "", "", "", "not identified"],
    ]
)


def test_same_answer_in_the_same_country():
    """11.3: capitals, accents and punctuation do not matter; the country does."""
    assert M.lookup("st xaviers college", "NP") == ("St. Xavier's College", "LOCAL-0068", "no", cs.CODED)
    assert M.lookup("ST. XAVIERS COLLEGE.", "NP")[1] == "LOCAL-0068"
    assert M.lookup("st xaviers college", "IN")[3] == cs.NOT_IN_MAPPING


def test_outcomes_without_an_id():
    assert M.lookup("Retired", "KE")[3] == cs.NO_ORGANISATION["NOT_APPLICABLE"]
    assert M.lookup("student", "KE")[3] == cs.NO_ORGANISATION["NOT_SPECIFIED"]
    assert M.lookup("private clinic", "KE")[3] == "type only (HOSPITAL)"
    assert M.lookup("xyz", "KE") == ("", "", "", cs.NOT_IDENTIFIED)


MERCY_KE_UG = [
    ["Mercy Hospital", "KE", "3", "Mercy Hospital, Nairobi", "LOCAL-0900", "HOSPITAL", DONE],
    ["Mercy Hospital", "UG", "2", "Mercy Hospital, Kampala", "LOCAL-0901", "HOSPITAL", DONE],
]


def test_without_a_country():
    """11.4: the row without a country first; otherwise one outcome in every country, or 'country needed'."""
    assert M.lookup("univ of nairobi", "")[1] == "02y9nww90"
    assert M.lookup("Mercy Hospital", "")[3] == cs.NOT_IDENTIFIED
    m = mapping(MERCY_KE_UG)
    assert m.lookup("mercy hospital", "")[3] == cs.COUNTRY_NEEDED
    assert M.lookup("Nowhere College", "")[3] == cs.NOT_IN_MAPPING


def test_norhed():
    """11.5: yes when the ID is on the partner list, no for any other ID, empty without an ID."""
    assert M.lookup("Univ of Nairobi", "KE")[2] == "yes"
    assert M.lookup("Mercy Hospital", "KE")[2] == "no"
    assert M.lookup("retired", "KE")[2] == ""


def test_country_names():
    table = cs.country_codes({"KE"})
    for value, code in [("Kenya", "KE"), ("ke", "KE"), ("Tanzania, the United Republic of", "TZ"), ("DRC", "CD")]:
        assert table[cs.pipeline_key(value)] == code


def test_unmapped_list_groups_spellings():
    t = cs.unmapped_table([("Nowhere College", "KE"), ("nowhere college.", "KE"), ("Nowhere College", "UG")])
    assert t.columns.tolist() == ["raw institution", "country", "learners"]
    assert t.values.tolist() == [["Nowhere College", "KE", 2], ["Nowhere College", "UG", 1]]


def workbook(path, rows, header_at=1):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "data"
    for _ in range(header_at - 1):
        ws.append(["Learner survey"])
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


ROWS = [
    ["id", "Institution", "Country", "score"],
    [1, "University of Nairobi", "Kenya", "=1+1"],
    [2, "someone@example.org", "Kenya", 3],
    [3, "Nowhere College of Imaginary Studies", "KE", 4],
    [4, "nowhere college of imaginary studies", "Kenia", 4],
    [5, None, "KE", 5],
]


def test_codes_a_sheet(tmp_path):
    f = workbook(tmp_path / "survey.xlsx", ROWS)
    assert cs.run(f, "institution", "country") == 0  # headers are found in any capitals
    ws = openpyxl.load_workbook(tmp_path / "survey_coded.xlsx")["data"]
    assert [c.value for c in ws[1]] == ["id", "Institution", "Country", "score", *cs.ADDED]
    assert ws["D2"].value == "=1+1"  # the client's own cells are kept
    assert [c.value for c in ws[2]][4:] == ["University of Nairobi", "02y9nww90", "yes", cs.CODED]
    assert ws["H3"].value == cs.PERSONAL and ws["F3"].value is None
    assert ws["H4"].value == cs.NOT_IN_MAPPING and ws["H6"].value == cs.NO_ANSWER
    (listed,) = tmp_path.glob("unmapped_institutions_*_survey.xlsx")
    u = pd.read_excel(listed, dtype=str, keep_default_na=False)
    assert u.values.tolist() == [
        ["Nowhere College of Imaginary Studies", "KE", "1"],
        ["nowhere college of imaginary studies", "", "1"],
    ]
    log = (tmp_path / "survey_coding_log.txt").read_text(encoding="utf-8")
    assert "WARNING country values not recognised (1 rows" in log and "'Kenia': 1" in log
    assert "WARNING 1 answers are personal data" in log
    assert "Nairobi" not in log and "someone" not in log and "Nowhere" not in log  # no answer text in the log


def test_check_only_writes_only_the_log(tmp_path):
    f = workbook(tmp_path / "survey.xlsx", ROWS)
    assert cs.run(f, "Institution", check_only=True) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["survey.xlsx", "survey_coding_log.txt"]
    assert "WARNING no country column was given" in (tmp_path / "survey_coding_log.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("make", "args", "error"),
    [
        (lambda p: workbook(p / "s.xlsx", ROWS, header_at=3), ("Institution",), "run again with --header-row 3"),
        (lambda p: workbook(p / "s.xlsx", ROWS), ("Organisation",), "the headers there are ['id', 'Institution'"),
        (lambda p: workbook(p / "s.xlsx", ROWS), ("Institution", "Land"), "there is no country column 'Land'"),
        (lambda p: workbook(p / "s.xlsx", [["Institution"], [None]]), ("Institution",), "has no answers"),
        (lambda p: (p / "s.xls").write_bytes(b"old") and p / "s.xls", ("Institution",), "old .xls format"),
        (lambda p: (p / "s.xlsx").write_text("not a workbook") and p / "s.xlsx", ("Institution",), "cannot be read"),
    ],
)
def test_checks_that_stop(tmp_path, make, args, error):
    f = make(tmp_path)
    assert cs.run(f, *args) == 1
    log = (tmp_path / f"{f.stem}_coding_log.txt").read_text(encoding="utf-8")
    assert "ERROR " in log and error in log, log
    assert not list(tmp_path.glob("*_coded.*"))


def test_csv_with_semicolons(tmp_path):
    f = tmp_path / "export.csv"
    f.write_text("Institution;Country\nUniversity of Nairobi;KE\n", encoding="utf-8")
    assert cs.run(f, "Institution", "Country") == 0
    out = (tmp_path / "export_coded.csv").read_text(encoding="utf-8-sig").splitlines()
    assert out[0].split(",") == ["Institution", "Country", *cs.ADDED]
    assert out[1].split(",") == ["University of Nairobi", "KE", "University of Nairobi", "02y9nww90", "yes", "coded"]
