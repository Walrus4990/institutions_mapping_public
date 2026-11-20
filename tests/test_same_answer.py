"""Rulebook 3.6 (same answer, same code): the pipeline key and the grouping of answers."""

import pandas as pd
import pytest

from institution_mapping.core.text import pipeline_key, same_answer_groups

KEY = {
    "St. Xavier's College": "st xaviers college",
    "St Xavier's College": "st xaviers college",
    "st xaviers college": "st xaviers college",
    "Université  de Lomé": "universite de lome",
    ".Bharatpur Eye Hospital": "bharatpur eye hospital",
    "Geospatial Research Forum (GRF)": "geospatial research forum grf",
    "A & B": "a b",
    "  Tanzania institute of accountancy ": "tanzania institute of accountancy",
}


@pytest.mark.parametrize(("answer", "key"), KEY.items())
def test_pipeline_key(answer, key):
    assert pipeline_key(answer) == key


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        (0, 1, True),
        (0, 2, False),  # same key, other country: not the same answer
        (3, 4, True),  # clean: & -> and
        (3, 5, True),  # pipeline key: & removed
        (4, 5, True),  # through the chain 4-3-5
        (5, 6, False),
    ],
)
def test_groups(a, b, same):
    m = pd.DataFrame(
        {
            "raw_institution": [
                "St. Xavier's College",
                "St Xavier's College",
                "St Xavier's College",
                "A & B",
                "A and B",
                "A B",
                "Other",
            ],
            "country": ["NP", "NP", "IN", "GH", "GH", "GH", "GH"],
        }
    )
    g = same_answer_groups(m).tolist()
    assert (g[a] == g[b]) == same
