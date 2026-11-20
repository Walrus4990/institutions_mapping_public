"""Helpers shared by the rules engine (stage 6) and the assembly (stage 7)."""

import re
from functools import lru_cache

import pandas as pd

from ..core.text import key


class KeywordTypes:
    """org_type from keywords in a name (settings name_keywords: [pattern, org_type], first match wins)."""

    def __init__(self, settings):
        self.patterns = settings["name_keywords"]

    def type(self, text):
        """org_type from the keyword lists in coding_rules.json, '' if none fits."""
        t = key(text)
        return next((typ for pat, typ in self.patterns if re.search(pat, t)), "")


def country_phrases(country_names):
    """Country names as matching keys, longest first (code -> name dict as input)."""
    return tuple(sorted({key(v) for v in country_names.values() if v}, key=lambda x: (-len(x), x)))


@lru_cache(maxsize=None)
def strip_countries(k, phrases):
    """A key without the country names in it."""
    for ph in phrases:
        k = re.sub(rf"\b{re.escape(ph)}\b", " ", k)
    return re.sub(r"\s+", " ", k).strip()


def read_research(ctx):
    """The 14 Oct research (research.csv) with the 15 Oct deep dive replacing the spellings it covers."""
    res = pd.read_csv(ctx.w("research.csv"), keep_default_na=False)
    dd = pd.read_csv(ctx.w("research_deepdive.csv"), keep_default_na=False)
    return pd.concat([res[~res.clean.isin(set(dd.clean))], dd])
