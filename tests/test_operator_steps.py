"""The operator's steps after a run: the worklist (step 7), the judgement-call draft (9.5) and the release's changes
log and version check. With IM_RUN_DIR the worklist and the draft also run on a real run."""

import openpyxl
import pandas as pd
import pytest

from institution_mapping import changes, judgement_calls, worklist

MAP_COLUMNS = ["raw_institution", "country", "learners", "canonical_name", "institution_id", "org_type", "status"]
MAP_COLUMNS += ["rule", "evidence", "ror_parent_ids"]
DONE = "coding complete"


def mapping(rows):
    return pd.DataFrame([r + [""] * (len(MAP_COLUMNS) - len(r)) for r in rows], columns=MAP_COLUMNS)


@pytest.mark.parametrize(
    ("status", "rule", "ledger", "expected"),
    [
        ("", "", "", "removed"),
        (DONE, "ROR-SEARCH", "same_country", "decided"),
        (DONE, "ROR-EXACT", "not_in_ledger", "rules"),
        ("not identified", "UNC-ABROAD", "not_in_ledger", "abroad"),
        ("not identified", "UNC-NOTFOUND", "same_country", "searched"),
        ("not identified", "UNC-NOTFOUND", "other_country", "other_country"),
        ("not identified", "UNC-NOTFOUND", "not_in_ledger", "search"),
    ],
)
def test_worklist_outcomes(status, rule, ledger, expected):
    assert worklist.outcome(status, rule, ledger) == expected


def test_worklist_report_counts_answers_and_learners():
    b = pd.DataFrame(
        [["l1", "3", "rules"], ["l1", "2", "search"], ["l1", "4", "search"]], columns=["list", "learners", "outcome"]
    )
    r = worklist.report(b)
    assert r.values.tolist() == [["l1", worklist.OUTCOMES["rules"], 1, 3], ["l1", worklist.OUTCOMES["search"], 2, 6]]


def test_judgement_call_flags():
    m = mapping(
        [
            ["KNH", "KE", "9", "Kenyatta National Hospital", "02kn1", "HOSPITAL", DONE, "ROR-SEARCH", "web search"],
            ["UoN", "KE", "5", "University of Nairobi", "02y9nww90", "EDUCATION", DONE, "ROR-ACRONYM", ""],
            ["Harvard programme", "KE", "4", "Harvard University", "03vek6s52", "EDUCATION", DONE, "ROR-SEARCH", ""],
            ["WHO Kenya", "KE", "4", "World Health Organization", "01f80g185", "GOVERNMENT", DONE, "ROR-CLIENT", ""],
            ["St Mary's Mission Hospital", "KE", "3", "Diocese of X", "LOCAL-0901", "HOSPITAL", DONE, "LOCAL-ROLLUP"],
            ["Bharatpur Eye Hospital", "NP", "2", "Bharatpur Eye Hospital", "LOCAL-0833", "HOSPITAL", DONE, "LOCAL"],
            [
                "UoN and KNH",
                "KE",
                "2",
                "University of Nairobi",
                "02y9nww90",
                "EDUCATION",
                DONE,
                "ROR-CONTAINED",
                "two organisations named; coded University of Nairobi (EDUCATION); not coded: KNH",
            ],
            ["Makerere University", "UG", "8", "Makerere University", "03dmz0111", "EDUCATION", DONE, "ROR-EXACT"],
            ["Harvard University", "KE", "2", "Harvard University", "03vek6s52", "EDUCATION", DONE, "ROR-EXACT"],
            ["MIT", "ET", "1", "Mekelle University", "04bpyvy69", "EDUCATION", DONE, "ROR-CLIENT"],
            ["xyz", "KE", "1", "", "", "", "not identified", "UNC-NOTFOUND"],
        ]
    )
    home = {"03vek6s52": "US", "01f80g185": "CH", "02y9nww90": "KE", "LOCAL-0901": "KE", "03dmz0111": "UG"}
    d = judgement_calls.draft(m, home, {"01f80g185"}, {("Bharatpur Eye Hospital", "NP")}, judged={("MIT", "ET")})
    flags = dict(zip(d.raw_institution, d.flag))
    assert flags == {
        "KNH": "acronym",
        "UoN": "acronym",
        "Harvard programme": "abroad",
        "St Mary's Mission Hospital": "owner",
        "Bharatpur Eye Hospital": "owner",
        "UoN and KNH": "two organisations",
    }
    # not flagged: WHO (international by rule), Makerere (plain), Harvard (its own name), MIT (decided by a person
    # already), xyz (not coded)
    assert d.columns.tolist() == judgement_calls.COLUMNS and (d.answer == "").all()
    assert d.gid.tolist() == list(range(1, len(d) + 1))  # row numbers for tools/add_decisions.py
    assert "alternative" in d.set_index("raw_institution").at["St Mary's Mission Hospital", "why_check"]


def workbook(path, version, rows):
    wb = openpyxl.Workbook()
    wb.active.title = "read me"
    wb.active.append([f"Institution mapping – v{version}"])
    ws = wb.create_sheet("mapping")
    ws.append(MAP_COLUMNS)
    for r in rows:
        ws.append(r + [""] * (len(MAP_COLUMNS) - len(r)))
    wb.save(path)
    return path


ROWS = [
    ["A college", "KE", "3", "A College", "LOCAL-0001", "EDUCATION", DONE, "LOCAL", "web search"],
    ["B hospital", "UG", "2", "", "", "HOSPITAL", "not identified", "UNC-NOTFOUND", "searched"],
]


def test_changes_log_lists_added_removed_and_changed_rows():
    before = mapping(ROWS)
    after = mapping(
        [
            ROWS[0],
            ["B hospital", "UG", "2", "B Hospital", "LOCAL-0002", "HOSPITAL", DONE, "LOCAL", "found"],
            ["C school", "TZ", "1", "", "", "NOT_SPECIFIED", DONE, "NS", "generic"],
        ]
    )
    log = changes.changes_log(before, after, 26, 27)
    assert log.raw_institution.tolist() == ["B hospital", "C school"]
    assert log.columns[:5].tolist() == [
        "raw_institution",
        "country",
        "learners",
        "canonical_name_v26",
        "canonical_name_v27",
    ]
    assert log.set_index("raw_institution").at["B hospital", "institution_id_v27"] == "LOCAL-0002"
    gone = changes.changes_log(after, before, 27, 28)
    assert "C school" in gone.raw_institution.tolist()


def test_release_refuses_a_wrong_version_number(tmp_path, monkeypatch):
    monkeypatch.setattr(changes, "REPO", tmp_path)
    (tmp_path / "docs" / "releases").mkdir(parents=True)
    (tmp_path / "docs" / "qa").mkdir()
    (tmp_path / "archive").mkdir()
    published = workbook(tmp_path / "published.xlsx", 26, ROWS)
    changed = [ROWS[0], ["B hospital", "UG", "2", "B Hospital", "LOCAL-0002", "HOSPITAL", DONE, "LOCAL", "found"]]
    with pytest.raises(SystemExit, match="set VERSION to 27"):
        changes.check_and_log(workbook(tmp_path / "new.xlsx", 26, changed), published)
    with pytest.raises(SystemExit, match="no row changed"):
        changes.check_and_log(workbook(tmp_path / "same.xlsx", 27, ROWS), published)
    changes.check_and_log(workbook(tmp_path / "same.xlsx", 26, ROWS), published)  # nothing to do
    assert not list((tmp_path / "docs" / "releases").iterdir())


def test_release_writes_the_changes_log_and_archives_the_previous_one(tmp_path, monkeypatch):
    monkeypatch.setattr(changes, "REPO", tmp_path)
    (tmp_path / "docs" / "releases").mkdir(parents=True)
    (tmp_path / "docs" / "qa").mkdir()
    (tmp_path / "archive" / "v25").mkdir(parents=True)
    (tmp_path / "docs" / "releases" / "changes_log_v26.csv").write_text("x\n")
    (tmp_path / "docs" / "qa" / "codes_to_check_v26.csv").write_text("x\n")
    published = workbook(tmp_path / "published.xlsx", 26, ROWS)
    new = workbook(tmp_path / "new.xlsx", 27, [ROWS[0]])
    changes.check_and_log(new, published, log=lambda s: None)
    assert (tmp_path / "docs" / "releases" / "changes_log_v27.csv").exists()
    assert (tmp_path / "archive" / "v26" / "changes_log_v26.csv").exists()
    assert (tmp_path / "archive" / "v26" / "codes_to_check_v26.csv").exists()
    assert (tmp_path / "archive" / "old" / "v25").is_dir() and not (tmp_path / "archive" / "v25").exists()


def test_on_a_run(run_dir, capsys):
    """With IM_RUN_DIR: the worklist and the draft run on a real run and write their files."""
    worklist.run(run_dir)
    judgement_calls.run(run_dir, every_row=True)
    assert (run_dir / "worklist_report.csv").exists() and (run_dir / "judgement_calls.csv").exists()
    d = pd.read_csv(run_dir / "judgement_calls.csv", dtype=str, keep_default_na=False)
    assert set(d.flag) <= {"acronym", "abroad", "owner", "two organisations"} and len(d)
