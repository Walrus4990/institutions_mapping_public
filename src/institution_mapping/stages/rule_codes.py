"""The output's rule code, rule description and evidence of a row (rulebook 3.5), derived from the working column
`rule`.

Every stage records in `rule` how it decided a row, in its own words; the patterns below read those texts. They name
the internal labels the stages write (step 2-4, R0-R13 of the rules engine, P1-P5 of the assembly, dated passes),
so a change to a stage's rule text must keep these patterns in step.
"""

import re

# rule code -> rule_description (rulebook 3.5)
DESCRIPTION = {
    "ROR-EXACT": "ROR ID: the user-entered name equals a ROR name",
    "ROR-CONTAINED": "ROR ID: a ROR name is contained in the user-entered name",
    "ROR-ACRONYM": "ROR ID: the user-entered name is the ROR acronym of an organisation in the learner's country",
    "ROR-TYPO": "ROR ID: typo or close spelling of a ROR name in the learner's country",
    "ROR-UNIQUE": "ROR ID: the only ROR record worldwide with this name (or these words)",
    "ROR-ROLLUP": "ROR ID of the parent: unit, campus, teaching hospital, country office or ministry department",
    "ROR-SEARCH": "ROR ID found by review or web search",
    "ROR-CLIENT": "ROR ID set by a client decision",
    "LOCAL": "LOCAL ID: organisation confirmed to exist, not in ROR",
    "LOCAL-ROLLUP": "LOCAL ID of the parent: unit or department of an organisation not in ROR",
    "NA": "NOT_APPLICABLE: the person has no organisation",
    "NS": "NOT_SPECIFIED: an organisation is implied but not named",
    "TYPE": "Type only: the answer names a kind of organisation, no ID",
    "UNC-ABROAD": "Uncoded: matches a ROR record only in another country, and the name is not unique",
    "UNC-AMBIGUOUS": "Uncoded: several organisations fit, or two organisations are named",
    "UNC-NOTFOUND": "Uncoded: the organisation could not be found or confirmed",
}

# internal working labels -> plain words, applied in this order
PLAIN = [
    (r"search \(country \+ name\):\s*(search:\s*)?", "web search (country + name): "),
    (r"\bstep[- ]2 exact\+successor\b", "exact ROR name of a former record; its successor record used"),
    (r"\bstep[- ]2 exact\+country\b", "exact ROR name, record in the learner's country"),
    (r"\bstep[- ]2 exact\b", "exact ROR name"),
    (r"\bstep[- ]3 contained\b", "ROR name contained in the answer"),
    (r"\bstep[- ]3 acronym\+country\b", "ROR acronym, record in the learner's country"),
    (r"\bstep[- ]4 keyword\b", "keyword list (section 3, step 4)"),
    (r"\bstep-4 type (\w+)", r"type \1 from the name"),
    (r"\bR2 exact match only in other country -> uncoded", "exact ROR name, but only a record in another country"),
    (r"\bR2 exact in country\b", "exact ROR name, record in the learner's country"),
    (r"\bR2 international/exception\b", "international organisation: ROR record used for learners anywhere"),
    (r"\bR2 in-country alternative\b", "record in the learner's country preferred"),
    (r"\bR2 NHS\b", "NHS body -> National Health Service"),
    (r"\bR1 TH\b", "teaching hospital"),
    (r"\bR1 teaching hospital\b", "teaching hospital"),
    (r"\bR1 unit\b", "unit rolls up"),
    (r"\bR3 branch in ROR\b", "branch named, branch record"),
    (r"\bR4 recoded from NOT_APPLICABLE\b", "not a 'no organisation' answer"),
    (r"\bR4 generic, type kept\b", "type only"),
    (r"\bR4 generic\b", "type only"),
    (r"\bR4 no-affiliation phrase\b", "no-affiliation phrase"),
    (r"\bR5 MoH ROR\b", "ministry of health, ROR record"),
    (r"\bR5 MoH local\b", "ministry of health, LOCAL ID"),
    (r"\bR5 not in ROR\b", "confirmed, not in ROR"),
    (r"\bR6 cluster\b", "spellings of one organisation grouped"),
    (r"\bR0 type (\w+)", r"type \1"),
    (r"\bR13 confirmed suggestion: ", "typo pass: "),
    (r"\bR13 ", "typo pass: "),
    (r"-> P5 NHS\b", "-> National Health Service"),
    (r"\bP1 ", ""),
    (r"\bP2 ", ""),
    # the client's unmatched-universities list: its rows referred to in words
    (
        r"\brow (\d+) not marked = suggested record approved",
        r"suggested record approved by the client (unmatched-universities list, row \1)",
    ),
    (r"^row (\d+), ", r"client (unmatched-universities list, row \1): "),
    (r"\bP3 word coverage\b", "all words of the ROR name in the answer"),
    (r"\bP4 fuzzy\b", "close spelling"),
    (r"\bresearch \(deep dive\)", "web research"),
    (r"\bresearch \(ROR lookup\)", "ROR lookup"),
    (r"\bNA check: ", ""),
    (r"\bgrouping: ", "spellings grouped: "),
]

UNC_ABROAD = r"other country|abroad|not coded abroad|ngo rule"
UNC_AMBIGUOUS = (
    r"ambig|shared|several|two organisations|not unique|not specific|common name|acronym|many"
    r"|aga khan"
)
ROLLUP = (
    r"roll|unit|campus|\bth\b|country office|group rule|network|cluster|ministry|department|part of"
    r"|constituent|subsidiar|programme of|centre of|institute of|faculty|school of|research group"
)
# (pattern on the rule text, code) for a ROR ID that is not a client decision or a roll-up, first match wins
ROR_CODES = [
    (r"^step 2 exact|r2 exact in country|exact\+", "ROR-EXACT"),
    (r"^step 3 acronym", "ROR-ACRONYM"),
    (r"^step 3 contained|r13 [bc] |p3 word", "ROR-CONTAINED"),
    (r"r13 a|r13 d|p4 fuzzy|r13 confirmed|typo", "ROR-TYPO"),
    (r"unique name|word-order|word order", "ROR-UNIQUE"),
]


def evidence(rule):
    """The rule text in plain words, without pass dates."""
    t = re.sub(r"\(client, 1[4-7] Oct\)", "(client)", rule)  # first, or the next line leaves '(client, )'
    t = re.sub(r"\b(client( human)? (review|check) )?1[4-7] Oct( 2026)?:?\s*", "", t)
    for pattern, plain in PLAIN:
        t = re.sub(pattern, plain, t)
    return re.sub(r"\s+\|\s+", " | ", t).strip(" |:")


def rule_code(r, ror_names):
    """The rule code of a row (a namedtuple or Series with rule, status, id_kind, org_type, canonical_name,
    institution_id); ror_names maps a ROR ID to its display name."""
    t, kind = r.rule.lower(), r.id_kind
    if r.status == "uncoded":
        if re.search(UNC_ABROAD, t):
            return "UNC-ABROAD"
        return "UNC-AMBIGUOUS" if re.search(UNC_AMBIGUOUS, t) else "UNC-NOTFOUND"
    if kind == "":
        return {"NOT_APPLICABLE": "NA", "NOT_SPECIFIED": "NS"}.get(r.org_type, "TYPE")
    rollup = (
        (r.org_type == "TEACHING_HOSPITAL" and (kind == "LOCAL" or r.canonical_name != ror_names[r.institution_id]))
        or " – " in r.canonical_name
        or re.search(ROLLUP, t)
    )
    if kind == "LOCAL":
        return "LOCAL-ROLLUP" if rollup and re.search(r"roll|unit|department|ministry", t) else "LOCAL"
    if re.search(r"client|reviewer decision|human review|settings", t):
        return "ROR-CLIENT"
    if rollup:
        return "ROR-ROLLUP"
    return next((code for pattern, code in ROR_CODES if re.search(pattern, t)), "ROR-SEARCH")
