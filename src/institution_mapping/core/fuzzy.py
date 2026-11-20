"""Fuzzy name similarity on the standard library (same definitions as rapidfuzz's token_set_ratio and
token_sort_ratio). A faster library would score slightly differently and change which candidates are found, so
the standard-library version is kept."""

import re
from difflib import SequenceMatcher


def tokens(s):
    """Set of lower-case words of a text."""
    return set(re.sub(r"[^0-9a-z]+", " ", s.lower()).split())


def ratio(a, b):
    """Similarity of two strings, 0-100."""
    if not a and not b:
        return 100.0
    return 200.0 * SequenceMatcher(None, a, b).ratio() / 2 * 1.0


def token_set_ratio(a, b):
    """Similarity of the word sets: shared words count fully, extra words on one side count against."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    inter = " ".join(sorted(ta & tb))
    da = " ".join(sorted(ta - tb))
    db = " ".join(sorted(tb - ta))
    s2 = (inter + " " + da).strip()
    s3 = (inter + " " + db).strip()
    return max(ratio(inter, s2) if inter else 0, ratio(inter, s3) if inter else 0, ratio(s2, s3))


def token_sort_ratio(a, b):
    """Similarity of the texts with their words sorted."""
    return ratio(" ".join(sorted(tokens(a))), " ".join(sorted(tokens(b))))


def score(a, b):
    """Average of token-set and token-sort similarity: rewards the same words and penalises a short generic name
    inside a long one."""
    return (token_set_ratio(a, b) + token_sort_ratio(a, b)) / 2
