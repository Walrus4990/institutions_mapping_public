"""Personal data checks (rulebook step 0 and 8.8). The patterns are in coding_rules.json, key `personal_data`."""

import re

ROR_ID_RE = re.compile(r"0[a-z0-9]{6}[0-9]{2}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?")


def personal_data(s, patterns):
    """Kind of personal data the WHOLE answer is ('email', 'number' or 'document'), or '' if none.
    An e-mail address anywhere in the answer counts."""
    s = "" if s is None else str(s).strip()
    if re.search(patterns["email_anywhere"], s):
        return "email"
    if re.fullmatch(patterns["number_whole"], s) and len(re.sub(r"\D", "", s)) >= patterns["number_min_digits"]:
        return "number"
    if re.fullmatch(patterns["document_whole"], s):
        return "document"
    return ""


def is_identifier(part):
    """True for values that are never personal data: ROR IDs, LOCAL IDs and dates."""
    return bool(ROR_ID_RE.fullmatch(part) or DATE_RE.fullmatch(part) or part.startswith("LOCAL-"))


def cell_has_personal_data(value, patterns):
    """True IF a text cell, or one of its " | "-separated parts, is personal data."""
    if not isinstance(value, str) or value == "":
        return False
    for part in [value] + value.split(" | "):
        part = part.strip()
        if not is_identifier(part) and personal_data(part, patterns):
            return True
    return False


def personal_data_in_table(df, patterns, where=""):
    """Rulebook 8.8: every text cell of an output table is checked. Returns 'where:row:column' for each hit."""
    return [
        f"{where}:{i}:{col}" for col in df.columns for i, v in df[col].items() if cell_has_personal_data(v, patterns)
    ]
