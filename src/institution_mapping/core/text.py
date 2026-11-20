"""Text normalisation: the keys used to compare user-entered names with ROR names and with each other.

Several keys exist because different rules need different tolerances; each is documented with what it ignores.
"""

import html
import re
import unicodedata

import pandas as pd

ARABIC_CYRILLIC = "؀-ۿЀ-ӿ"  # character ranges kept as letters by the non-institution step (step 4)


def strip_accents(s):
    """Text without combining accents ("Université" -> "Universite")."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def is_missing(s):
    """True for None and NaN."""
    return s is None or (isinstance(s, float) and s != s)


def clean(s):
    """Rulebook step 1 cleaning: HTML decoded, "&" -> "and", spaces collapsed, trailing dots and commas dropped,
    lower case, accents removed. Punctuation inside the text is kept."""
    if is_missing(s):
        return ""
    s = html.unescape(str(s)).replace("&", " and ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[.,\s]+$", "", s).lower()
    return strip_accents(s)


PIPELINE_PUNCT = re.compile(r"""[.,;:'"!?()\[\]{}/\\\-_@#$%^&*+=<>|~`]""")


def pipeline_key(s):
    """The pipeline's lookup key (rulebook 3.6): lower case, accents removed, the listed punctuation deleted (not
    replaced by a space), spaces trimmed and collapsed.
    "St. Xavier's College" -> "st xaviers college"."""
    if is_missing(s):
        return ""
    s = strip_accents(str(s).lower())
    return re.sub(r"\s+", " ", PIPELINE_PUNCT.sub("", s)).strip()


def words(s, scripts=""):
    """Punctuation-insensitive word string of an already cleaned text. `scripts` adds character ranges that count
    as letters (e.g. ARABIC_CYRILLIC)."""
    return re.sub(r"\s+", " ", re.sub(rf"[^0-9a-z{scripts}]+", " ", s)).strip()


def key(s):
    """Matching key of the rules engine and of the LOCAL register: lower case, punctuation-insensitive, a leading
    "the" dropped."""
    k = words(str(s).lower())
    return k[4:] if k.startswith("the ") else k


def compact(s):
    """Letters and digits only ("st xaviers" -> "stxaviers"), for acronym lookups."""
    return re.sub(r"[^0-9a-z]", "", s)


def fold(s, drop=r"['’`.]"):
    """Raw text -> lower case, HTML decoded, "&" -> "and", accents removed, the characters in `drop` deleted (not
    replaced by a space), then punctuation-insensitive. With the default `drop`, "U.K." becomes "uk"; with
    drop=r"['’`]" (the typo pass) it becomes "u k"."""
    s = strip_accents(html.unescape(str(s)).replace("&", " and ").lower())
    s = re.sub(drop, "", s)
    return re.sub(r"[^0-9a-z]+", " ", s).strip()


def without_brackets(s):
    """Text with every "(...)" replaced by a space."""
    return re.sub(r"\(.*?\)", " ", s)


def tidy_answer(raw):
    """A user-entered name as a readable coded name: spaces collapsed, surrounding punctuation dropped, title case
    when the answer is all capitals or all lower case."""
    raw = re.sub(r"\s+", " ", str(raw)).strip(" .,;-")
    return raw.title() if raw.isupper() or raw.islower() else raw


def same_answer_groups(m):
    """Rulebook 3.6: a group number per row of the mapping. Two rows of the same learner country are the same answer
    IF their cleaned text (clean) is the same OR their pipeline key is the same; groups are closed under both (a
    chain of such pairs is one group)."""
    parent = list(range(len(m)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for keyf in (clean, pipeline_key):
        first = {}
        for i, (raw, cc) in enumerate(zip(m.raw_institution, m.country)):
            k = (keyf(raw), cc)
            if k in first:
                a, b = find(first[k]), find(i)
                if a != b:
                    parent[b] = a
            else:
                first[k] = i
    return pd.Series([find(i) for i in range(len(m))], index=m.index)


# ---- specific names (rulebook 5.2): a name is specific only if it has a proper-name word ----
SPECIFIC_GENERIC = set(
    """university universities college institute institution school academy faculty hospital clinic medical
medicine research center health clinical organization organisation national state international city
observatory management child children adolescent mental agriculture agricultural science sciences technology
applied of and for in at de la general community public private central federal regional district specialist
teaching training studies development government governmental graduate postgraduate degree""".split()
)
SPECIFIC_DESCRIPTIVE = set(
    """north south east west northern southern eastern western northeast northwest southeast southwest central
european europe africa african asian asia american america arab arabian international global world open
modern new royal metropolitan christian catholic islamic adventist methodist baptist evangelical evangel
presbyterian lutheran anglican technical polytechnic business management technology tourism economics law
arts languages language normal multimedia unity victoria women womens people peoples peace hope grace faith
mercy liberal free united first""".split()
)
NGO_GENERIC = set(
    """association associations foundation society network initiative initiatives organization organisation group
trust consultants consulting consultancy services service company corporation centre center project
programme program fund council alliance partnership partners agency institute""".split()
)
_LINK_WORDS = ("of", "and", "for", "in", "at", "the", "de", "la")


def specific(k, ngo=False):
    """True IF a word of the normalised text `k` is neither generic nor descriptive. ngo=True also treats the
    generic words of NGO and company names as generic (rulebook 5.2, the NGO/company exception)."""
    ws = [w for w in k.split() if w not in _LINK_WORDS]
    return bool(set(ws) - SPECIFIC_GENERIC - SPECIFIC_DESCRIPTIVE - (NGO_GENERIC if ngo else set()))
