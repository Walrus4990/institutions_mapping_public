"""The delivered workbook (OUT/institution_mapping_final.xlsx).

Sheets: read me (counts as live formulas over the mapping sheet, and what every column and code means), mapping,
organisations (one row per ID), local IDs (in use), retired local IDs, research log (every decision in decisions.csv).
The run stops before saving if any sheet holds personal data (rulebook step 8, point 6).
"""

import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .. import TITLE
from ..core.personal_data import personal_data_in_table
from ..core.table import shortest

MAPPING_COLUMNS = [
    ("raw_institution", "User-entered name: the answer exactly as the learner typed it. Read by the pipeline."),
    (
        "country",
        "Learner's country (ISO 2-letter code) as given by the learner; empty if not given. Read by the pipeline.",
    ),
    ("learners", "Number of learners who typed this user-entered name in this country."),
    (
        "canonical_name",
        "Coded name. With a ROR ID: the ROR name, or '<ROR name> Teaching Hospital' / '<ROR name> – "
        "<campus>' for a teaching hospital or a campus in another town. With a LOCAL ID: the "
        "organisation's own name. Uncoded: the tidied user-entered name. Empty for NOT_APPLICABLE, "
        "NOT_SPECIFIED and type-only rows. Read by the pipeline.",
    ),
    (
        "institution_id",
        "ROR ID or LOCAL ID (LOCAL-nnnn). Empty if the row has no organisation or is uncoded. Read by the pipeline.",
    ),
    ("id_kind", "ROR, LOCAL, or empty."),
    ("ror_url", "https://ror.org/<ROR ID> for ROR IDs."),
    (
        "ror_parent_ids",
        "Every ROR parent of the ROR record, followed upwards: each chain from the nearest parent to "
        "the top, IDs separated by '/'; a record with two or more parents has one chain per parent, "
        "separated by '|'. Empty for LOCAL IDs, rows without an ID, and ROR records that ROR lists "
        "without a parent (most universities are top-level records, so the column is mostly empty). "
        "Used by the pipeline to set the NORHED flag. Read by the pipeline.",
    ),
    ("org_type", "Kind of organisation; see the org_type list below. Read by the pipeline."),
    (
        "status",
        "Exactly two values. coding complete = the row is decided (coded with a ROR or LOCAL ID, or "
        "NOT_APPLICABLE / NOT_SPECIFIED / type only). not identified = an organisation is named but could "
        "not be identified safely; no ID. (The pipeline uses 'uncoded' for answers not yet in the mapping.) "
        "Read by the pipeline.",
    ),
    ("rule", "Code of the rule that decided the row; see the rule list below and section 3 of the rulebook."),
    ("rule_description", "The rule code in words."),
    (
        "evidence",
        "What the decision rests on for this row: the match found, the web source, or the reason it stays uncoded.",
    ),
]
ORG_TYPES = [
    ("EDUCATION", "University, college, polytechnic, school or other teaching institution."),
    ("TEACHING_HOSPITAL", "Teaching hospital of a university or medical college."),
    ("HOSPITAL", "Hospital, clinic or health centre that is not a teaching hospital."),
    ("RESEARCH", "Research institute or centre that is not part of a university."),
    (
        "GOVERNMENT",
        "Ministry, government agency, regulator, local government, intergovernmental body (UN agencies, WHO).",
    ),
    ("COMPANY_OR_NGO", "Company, NGO, foundation, association, church or other non-governmental organisation."),
    ("NOT_APPLICABLE", "The person has no organisation (none, self-employed, unemployed, retired …)."),
    (
        "NOT_SPECIFIED",
        "The person has an organisation, but the answer does not name it ('University', 'student', a "
        "place, a person's name …).",
    ),
    ("(empty)", "Uncoded row whose name does not show what kind of organisation it is."),
]
OTHER_SHEETS = [
    (
        "organisations",
        "One row per ROR ID or LOCAL ID: coded name, other coded names on the same ID (teaching "
        "hospital, campus), org_type, learners, number of user-entered names, learners' countries, ROR "
        "parent IDs.",
    ),
    ("local IDs", "Every LOCAL ID in use: name, organisation's country, source that confirms the organisation exists."),
    ("retired local IDs", "LOCAL IDs no longer used, what replaced them and why. Their numbers are never reused."),
    (
        "research log",
        "Every decision taken by hand, from decisions.csv: web searches (with source), reviewer, client and "
        "human-review decisions. One row per decision: date, batch (the pass it was taken in), the "
        "user-entered name and country (or the cleaned spelling for 14-15 Oct research), the decision, "
        "and what it rests on (rationale_type: source, rule, client decision, reviewer decision, searched "
        "not found, reason given, none recorded).",
    ),
]
HEADINGS = ("Outcome", "Total", "org_type", "rule", "Other sheets", "Columns of the 'mapping' sheet")
WIDTHS = {
    "mapping": [45, 8, 9, 50, 14, 8, 30, 24, 18, 9, 15, 50, 60],
    "organisations": [16, 8, 50, 50, 18, 9, 10, 25, 24],
    "local IDs": [12, 55, 8, 80],
    "retired local IDs": [12, 22, 50],
    "research log": [8, 11, 22, 40, 8, 30, 14, 12, 40, 16, 8, 40, 60, 18, 30],
}


def research_log(ledger):
    """Every recorded decision, with plain column names."""
    log = ledger.rename(
        columns={
            "raw_institution": "user_entered_name",
            "clean": "cleaned_spelling",
            "target": "decision",
            "org_country": "organisation_country",
            "extra": "remark",
        }
    )
    return log[
        [
            "id",
            "date",
            "batch",
            "user_entered_name",
            "country",
            "cleaned_spelling",
            "decision",
            "ror_id",
            "name",
            "org_type",
            "organisation_country",
            "source",
            "note",
            "rationale_type",
            "remark",
        ]
    ]


def main_org_type(types):
    """The org_type of an ID's rows other than TEACHING_HOSPITAL."""
    rest = sorted(set(types) - {"TEACHING_HOSPITAL"})
    return rest[0] if rest else "TEACHING_HOSPITAL"


def organisations(coded):
    """One row per ID; the name is the shortest coded name (without a teaching-hospital or campus suffix)."""
    orgs = (
        coded.groupby(["institution_id", "id_kind"])
        .agg(
            coded_name=("canonical_name", shortest),
            other_coded_names=("canonical_name", lambda s: " | ".join(sorted(set(s), key=lambda x: (len(x), x))[1:])),
            org_type=("org_type", main_org_type),
            learners=("learners", "sum"),
            user_entered_names=("raw_institution", "size"),
            learner_countries=("country", lambda s: ", ".join(sorted(set(s) - {""}))),
            ror_parent_ids=("ror_parent_ids", "first"),
        )
        .reset_index()
    )
    orgs = orgs.rename(columns={"institution_id": "ROR ID or LOCAL ID", "id_kind": "kind"})
    return orgs.sort_values("learners", ascending=False)


def local_ids(coded, register):
    """LOCAL IDs in use: the name from the mapping, country and source (without pass dates) from the register."""
    names = coded[coded.id_kind == "LOCAL"].groupby("institution_id").canonical_name.agg(shortest)
    reg = register.set_index("local_id")
    return pd.DataFrame(
        {
            "local_id": names.index,
            "name": names.values,
            "country": [reg.country.get(i, "") for i in names.index],
            "source": [re.sub(r"\s*\(?1[4-7] Oct\)?:?\s*", " ", reg.source.get(i, "")).strip() for i in names.index],
        }
    )


def retired_ids(register):
    """Retired LOCAL IDs with what replaced them and why."""
    return register[register.status == "retired"].rename(columns={"replaced_by": "replaced by"})[
        ["local_id", "replaced by", "reason"]
    ]


def font(**k):
    """Arial 10."""
    return Font(name="Arial", size=10, **k)


def read_me(ws, m):
    """Counts as COUNTIFS/SUMIFS over the mapping sheet, so they stay right when the sheet is filtered or edited."""
    col = {c: chr(65 + i) for i, c in enumerate(m.columns)}

    def rng(c):
        return f"mapping!${col[c]}$2:${col[c]}${len(m) + 1}"

    ws.append([TITLE])
    ws.append([])
    ws.append(["Outcome", "User-entered names (rows)", "Learners"])
    for label, cond in [
        ("Coded with a ROR ID", f'{rng("id_kind")},"ROR"'),
        ("Coded with a LOCAL ID", f'{rng("id_kind")},"LOCAL"'),
        ("No organisation: NOT_APPLICABLE", f'{rng("org_type")},"NOT_APPLICABLE"'),
        ("Organisation not named: NOT_SPECIFIED", f'{rng("org_type")},"NOT_SPECIFIED"'),
        ("Type only, no organisation named (rule TYPE)", f'{rng("rule")},"TYPE"'),
        ("Uncoded: not found, ambiguous, or in ROR only abroad", f'{rng("status")},"not identified"'),
    ]:
        ws.append([label, f"=COUNTIFS({cond})", f"=SUMIFS({rng('learners')},{cond})"])
    ws.append(["Total", "=SUM(B4:B9)", "=SUM(C4:C9)"])
    ws.append([])
    ws.append(["Columns of the 'mapping' sheet", ""])
    for row in MAPPING_COLUMNS:
        ws.append(list(row))
    ws.append([])
    ws.append(["org_type", ""])
    for row in ORG_TYPES:
        ws.append(list(row))
    ws.append([])
    ws.append(["rule", ""])
    for code, desc in m.drop_duplicates("rule").set_index("rule").rule_description.sort_index().items():
        ws.append([code, desc])
    ws.append([])
    ws.append(["Other sheets", ""])
    for row in OTHER_SHEETS:
        ws.append(list(row))
    ws["A1"].font = Font(name="Arial", size=13, bold=True)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = font(bold=c.column == 1 and c.value in HEADINGS)
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for r in range(4, 11):
        for c in "BC":
            ws[f"{c}{r}"].number_format = "#,##0"
    for c, w in zip("ABC", (48, 110, 12)):
        ws.column_dimensions[c].width = w


def add_sheet(wb, name, df):
    """A sheet with a bold header, filters, frozen first row and column widths."""
    s = wb.create_sheet(name)
    s.append(list(df.columns))
    for r in df.itertuples(index=False):
        s.append(list(r))
    for c in s[1]:
        c.font = font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDDDDD")
    for i, w in enumerate(WIDTHS[name]):
        s.column_dimensions[chr(65 + i)].width = w
    s.freeze_panes = "A2"
    s.auto_filter.ref = s.dimensions


def run(ctx):
    m = ctx.read_previous(__name__, dtype=str)
    m["learners"] = m.learners.astype(int)
    register = pd.read_csv(ctx.registry("local_ids.csv"), keep_default_na=False, dtype=str)
    coded = m[m.institution_id != ""]
    sheets = {
        "mapping": m,
        "organisations": organisations(coded),
        "local IDs": local_ids(coded, register),
        "retired local IDs": retired_ids(register),
        "research log": research_log(ctx.ledger.table),
    }
    wb = Workbook()
    ws = wb.active
    ws.title = "read me"
    read_me(ws, m)
    for name, df in sheets.items():
        add_sheet(wb, name, df)
    patterns = ctx.settings["personal_data"]
    hits = sum((personal_data_in_table(df, patterns, name) for name, df in sheets.items()), [])
    assert not hits, f"personal data in the workbook (rulebook step 8, point 6): {hits[:20]}"
    wb.save(ctx.o("institution_mapping_final.xlsx"))
    counts = " | ".join(f"{name} {len(df)}" for name, df in sheets.items() if name != "research log")
    print(f"saved | {counts}")
