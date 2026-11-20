"""Rulebook step 0 (personal data) on made-up answers: what must be removed and what must stay."""

import pytest

from institution_mapping.core.personal_data import personal_data

REMOVE = {
    "jane.doe@example.org": "email",
    "Works at uni, contact j.doe@uni.ac.ke": "email",
    "+254 712 345 678": "number",
    "0712-345678": "number",
    "123456": "number",
    "(01) 234 5678": "number",
    "AB1234567": "document",
    "X123456": "document",
}
KEEP = [
    "21 September University",
    "461 NAF Hospital",
    "REG/PWF/OO1",
    "MRC@LSHTM",
    "University of Ghana",
    "Punjab Agricultural University, Ludhiana, 141004, India",
    "12345",
    "ABCD123456",
    "COVID-19 unit 2020",
]


@pytest.mark.parametrize(("answer", "kind"), REMOVE.items())
def test_removed(answer, kind, settings):
    assert personal_data(answer, settings["personal_data"]) == kind


@pytest.mark.parametrize("answer", KEEP)
def test_kept(answer, settings):
    assert personal_data(answer, settings["personal_data"]) == ""
