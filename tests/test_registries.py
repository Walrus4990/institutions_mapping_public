"""Rules 1.4 and 7.6 on made-up data: the published mapping carries answers forward, and LOCAL names code answers."""

import pandas as pd

from institution_mapping import build_input
from institution_mapping.core.register import Register
from institution_mapping.stages.apply_decisions import code_local_names

REGISTER = pd.DataFrame(
    [
        ["LOCAL-0001", "Mater Hospital", "mater hospital", "Mater Misericordiae Hospital", "KE", "active", "", "", "x"],
        ["LOCAL-0002", "Global Network", "global network", "", "", "active", "", "", "x"],
        ["LOCAL-0003", "Old School", "old school", "", "KE", "retired", "LOCAL-0001", "dup", "x"],
    ],
    columns=Register.COLS,
)


def register(tmp_path):
    path = tmp_path / "local_ids.csv"
    REGISTER.to_csv(path, index=False)
    return Register(path)


def mapping(rows):
    cols = [
        "raw_institution",
        "country",
        "institution_id",
        "id_kind",
        "ror_url",
        "canonical_name",
        "org_type",
        "status",
        "rule",
        "rule_code",
        "evidence_text",
        "decision_applied",
    ]
    return pd.DataFrame([dict(dict.fromkeys(cols, ""), **r) for r in rows], columns=cols)


def test_names_in(tmp_path):
    names = register(tmp_path).names_in("KE")
    assert names["mater misericordiae hospital"] == {"LOCAL-0001"}  # a former name counts
    assert names["global network"] == {"LOCAL-0002"}  # an international ID counts in every country
    assert "old school" not in names  # retired IDs do not


def test_code_local_names(tmp_path):
    m = mapping(
        [
            dict(raw_institution="Mater Misericordiae Hospital", country="KE", status="uncoded"),
            dict(raw_institution="Mater Misericordiae Hospital", country="UG", status="uncoded"),
            dict(raw_institution="Global Network", country="NG", status="uncoded", decision_applied="D00001"),
        ]
    )
    assert code_local_names(m, register(tmp_path), {}) == 1
    assert m.at[0, "institution_id"] == "LOCAL-0001" and m.at[0, "status"] == "final"
    assert m.at[1, "institution_id"] == ""  # another country
    assert m.at[2, "institution_id"] == ""  # a person decided this row: the decision wins


def test_published_answers_are_carried_forward(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    pd.DataFrame(
        {"raw_institution": ["Kept Org", "In Export"], "country": ["KE", "KE"], "learners": ["2", "5"]}
    ).to_excel(out / "institution_mapping_2026-01-01.xlsx", sheet_name="mapping", index=False)
    monkeypatch.setattr(build_input, "OUTPUT", out)
    carried = build_input.published_answers({("In Export", "KE")})
    assert carried[0]["raw institution"].tolist() == ["Kept Org"]
    assert carried[0].learners.tolist() == ["2"]


def test_remove_decision(tmp_path, monkeypatch):
    coding = tmp_path / "coding"
    coding.mkdir()
    pd.DataFrame(
        {
            "batch": ["decisions", "decisions", "review_16oct"],
            "raw_institution": ["A ", "B", "C"],
            "country": ["KE", "KE", "KE"],
            "target": ["REMOVE", "NS", "REMOVE"],
        }
    ).to_csv(coding / "decisions.csv", index=False)
    monkeypatch.setattr(build_input, "CODING", coding)
    assert build_input.removed_answers() == {("A", "KE")}


class FakeRor:
    """The parts of core.ror.Ror that rule 7.6 uses."""

    def __init__(self, records):
        self.records = records  # {ror_id: (name, country)}
        self.active = set(records)
        self.names = pd.DataFrame(
            [(rid, name, "display") for rid, (name, _) in records.items()], columns=["ror_id", "name", "name_kind"]
        )

    def cc(self, rid):
        return self.records[rid][1]

    def name(self, rid):
        return self.records[rid][0]

    def org_type(self, rid):
        return "HOSPITAL"


def test_retire_locals_in_ror(tmp_path):
    from institution_mapping.stages.apply_decisions import retire_locals_in_ror

    reg = register(tmp_path)
    m = mapping(
        [
            dict(
                raw_institution="Mater",
                country="KE",
                institution_id="LOCAL-0001",
                id_kind="LOCAL",
                status="final",
                org_type="HOSPITAL",
            )
        ]
    )
    # one ROR record with LOCAL-0001's former name in Kenya: the rows move, the LOCAL ID is retired
    moved = retire_locals_in_ror(m, reg, FakeRor({"0aaaaaa01": ("Mater Misericordiae Hospital", "KE")}))
    assert moved == {"LOCAL-0001": "0aaaaaa01"}
    assert m.at[0, "institution_id"] == "0aaaaaa01" and m.at[0, "id_kind"] == "ROR"
    assert reg.status("LOCAL-0001") == "retired" and reg.replaced_by("LOCAL-0001") == "0aaaaaa01"


def test_several_ror_records_are_not_switched(tmp_path):
    from institution_mapping.stages.apply_decisions import retire_locals_in_ror

    reg = register(tmp_path)
    m = mapping([dict(raw_institution="Mater", country="KE", institution_id="LOCAL-0001", status="final")])
    two = FakeRor({"0aaaaaa01": ("Mater Hospital", "KE"), "0aaaaaa02": ("Mater Hospital", "KE")})
    assert retire_locals_in_ror(m, reg, two) == {}  # left for the stop in stage finalise
    assert m.at[0, "institution_id"] == "LOCAL-0001"
