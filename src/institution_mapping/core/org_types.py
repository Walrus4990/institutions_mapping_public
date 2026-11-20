"""org_type of an organisation, from its ROR record types or from its name (rulebook 3.3)."""

import re

# ROR record type -> org_type. The FIRST type on the record that maps decides (rulebook 3.3 point 2).
ROR_TYPE = {
    "education": "EDUCATION",
    "healthcare": "HOSPITAL",
    "government": "GOVERNMENT",
    "facility": "RESEARCH",
    "nonprofit": "COMPANY_OR_NGO",
    "company": "COMPANY_OR_NGO",
}


def org_type_from_ror(types, default=""):
    """org_type of the first ROR type in `types` (a list) that maps, else `default`."""
    return next((ROR_TYPE[t] for t in types if t in ROR_TYPE), default)


def org_type_from_types_field(types_field, default=""):
    """org_type from a ROR `types` field as stored in ror_orgs.csv ("education;funder")."""
    return org_type_from_ror(types_field.split(";"), default)


_NAME_TYPES = [
    (
        "EDUCATION",
        r"\b(university|universit[eé]|universidad|college|polytechnic|institute of technology|school|academy"
        r"|lyc[eé]e|liceo|pesantren)\b",
    ),
    (
        "HOSPITAL",
        r"\b(hospital|h[oô]pital|rumah sakit|clinic|medical cent(er|re)|eye cent(er|re)|treatment cent(er|re)"
        r"|ear care|fistula)\b",
    ),
    (
        "GOVERNMENT",
        r"\b(ministry|minist[eè]re|department|government|commission|authority|agency|board|badan|direction"
        r"|judicial|coordinating mechanism)\b",
    ),
    ("RESEARCH", r"\b(research|recherche|investigaci[oó]n)\b"),
]


def type_from_name(name):
    """org_type of a confirmed organisation from its name (rulebook 3.3 point 3); COMPANY_OR_NGO if no keyword fits."""
    n = name.lower()
    return next((typ for typ, pattern in _NAME_TYPES if re.search(pattern, n)), "COMPANY_OR_NGO")
