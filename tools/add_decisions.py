"""Add review and web-search decisions to decisions.csv (batch `decisions`, rulebook step 7), from a short worksheet.
Usage: python tools/add_decisions.py GROUPS_CSV WORKSHEET ROR_DIR LEDGER_CSV DATE [--dry] [--to DECISIONS_FILE]
  GROUPS_CSV  a list with a `gid` column (row number): OUT_DIR/worklist.csv, or OUT_DIR/judgement_calls.csv
  WORKSHEET   one decision per line, fields separated by " | ":
                 GIDS | TARGET | NAME | ORG_TYPE | ORG_COUNTRY | RATIONALE_TYPE | SOURCE | NOTE [| override]
              GIDS: one or more row numbers, "12,15" or "12-15", or "c<cluster>" for every row of that cluster
                    in the country of the first row named before it ("NG c31" is also accepted)
              TARGET, NAME, ORG_TYPE, ORG_COUNTRY: as in stages/apply_decisions.py (ROR id, TH:<id>, LOCAL, NS, NA,
                    TYPE:<org_type>, UNC); empty fields allowed
              RATIONALE_TYPE: source | rule | searched, not found | reason given | client decision |
                    human-review decision
              override: the row is decided already and this decision corrects it (a judgement call)
              Lines starting with # and empty lines are ignored.
  --to        write the decisions to a client session's decisions file in input/ (rulebook 9.6), numbered
              <file name>-0001, ..., instead of appending them to LEDGER_CSV (D-numbers)
Checks before anything is written: every row exists and is still undecided in the ledger; a ROR target is an active
record; a ROR record in another country needs 'rule 5.2' in the note, or is refused later by apply_decisions.py;
LOCAL and TH: need a name; every decision has a rationale type and a source or note.
The evidence written to the mapping is the note.
"""

import csv
import re
import sys
from pathlib import Path

import pandas as pd

RATIONALE_TYPES = {"source", "rule", "searched, not found", "reason given", "client decision", "human-review decision"}
ROR_ID = re.compile(r"0[a-z0-9]{8}")
BY_A_PERSON = {"client decision", "human-review decision"}  # a ROR ID they set has rule code ROR-CLIENT


def gids(spec, last_cc, groups):
    """The row numbers a worksheet line names: "12", "12,15", "12-15", or "c31" / "NG c31" (every row of that cluster
    in that country; without a country, in the country of the row named before)."""
    out = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        mm = re.fullmatch(r"(?:([A-Z]{2}) )?c(\d+)", part)
        if mm:
            cc = mm.group(1) or last_cc
            out += list(groups.index[(groups.country == cc) & (groups.cluster == mm.group(2))])
        elif "-" in part:
            a, b = part.split("-")
            out += [str(x) for x in range(int(a), int(b) + 1)]
        else:
            out.append(part)
    return out


def target_error(target, r, note, orgs):
    """Why a target cannot be recorded for row r ('' if it can, 'abroad: ...' for a ROR record abroad without
    rule 5.2 in the note: reported, but the line is still checked)."""
    rid = target[3:] if target.startswith("TH:") else target
    if ROR_ID.fullmatch(rid):
        if rid not in orgs.index or orgs.at[rid, "status"] != "active":
            return f"{rid} is not an active ROR record"
        if r.country and orgs.at[rid, "country_code"] != r.country and "rule 5.2" not in note:
            return (
                f"abroad: ROR {rid} is in {orgs.at[rid, 'country_code']}, learner in {r.country} "
                "(add 'rule 5.2: ...' to the note if allowed)"
            )
    elif not (target in ("LOCAL", "NS", "NA", "UNC") or target.startswith("TYPE:")):
        return f"unknown target {target!r}"
    return ""


def field_error(target, name, rtype, source, note):
    """What is missing from a worksheet line ('' if nothing): a name for LOCAL and TH:, a known rationale type, a
    source or a note."""
    if (target == "LOCAL" or target.startswith("TH:")) and not name:
        return f"{target} needs a name"
    if rtype not in RATIONALE_TYPES:
        return f"rationale type {rtype!r}"
    if not (source or note):
        return "no source or note"
    return ""


def decision(did, r, fields, date):
    """One row of decisions.csv (batch `decisions`) for row r of the groups."""
    target, name, otype, ocountry, rtype, source, note, extra = fields
    rid = target[3:] if target.startswith("TH:") else target
    return dict(
        id=did,
        batch="decisions",
        raw_institution=r.raw_institution,
        country=r.country,
        clean="",
        target=target,
        ror_id=rid if ROR_ID.fullmatch(rid) else "",
        name=name,
        org_type=otype,
        org_country=ocountry,
        evidence="",
        source=source,
        note=note,
        extra=extra,
        date=date,
        rationale_type=rtype,
        rationale=note or source,
        rule_code="ROR-CLIENT" if ROR_ID.fullmatch(rid) and rtype in BY_A_PERSON else "",  # rulebook 3.5
        evidence_text=note or source,
    )


def read_worksheet(lines, groups, orgs, decided, new_id, date):
    """The decisions of a worksheet, and every error found (nothing is written if there is one). new_id(n) gives
    the ID of the n-th new decision."""
    rows, errors, seen, last_cc = [], [], set(), ""
    for ln, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        f = [x.strip() for x in line.split(" | ")]
        f += [""] * (9 - len(f))
        spec, fields = f[0], f[1:9]
        target, name, _, _, rtype, source, note, extra = fields
        if extra not in ("", "override"):
            errors.append(f"line {ln}: the ninth field is 'override' or nothing, not {extra!r}")
            continue
        ids = gids(spec, last_cc, groups)
        if not ids:
            errors.append(f"line {ln}: no rows for {spec!r}")
            continue
        for gid in ids:
            if gid not in groups.index:
                errors.append(f"line {ln}: row {gid} not in the groups")
                continue
            r = groups.loc[gid]
            last_cc = r.country
            key = (r.raw_institution, r.country)
            if key in seen or (key in decided and extra != "override"):
                errors.append(f"line {ln}: row {gid} already has a decision")
                continue
            seen.add(key)
            why = target_error(target, r, note, orgs)
            if why.startswith("abroad: "):
                errors.append(f"line {ln}: row {gid}: {why.removeprefix('abroad: ')}")
            elif why:
                errors.append(f"line {ln}: {why}")
                continue
            why = field_error(target, name, rtype, source, note)
            if why:
                errors.append(f"line {ln}: {why}")
                continue
            rows.append(decision(new_id(len(rows) + 1), r, fields, date))
    return rows, errors


def main(argv):
    """Check the worksheet against the groups, the ROR snapshot and the ledger (and the decisions file of --to);
    write the decisions unless --dry or an error was found. Returns the exit code."""
    groups_csv, worksheet, ror_dir, ledger_csv, date = argv[:5]
    to = Path(argv[argv.index("--to") + 1]) if "--to" in argv else None
    groups = pd.read_csv(groups_csv, keep_default_na=False, dtype=str).set_index("gid")
    orgs = pd.read_csv(f"{ror_dir}/ror_orgs.csv", keep_default_na=False, dtype=str).set_index("ror_id")
    led = pd.read_csv(ledger_csv, keep_default_na=False, dtype=str)
    mine = led[led.batch == "decisions"]
    if to is not None and to.exists():
        mine = pd.concat([mine, pd.read_csv(to, keep_default_na=False, dtype=str)])
    decided = set(zip(mine.raw_institution, mine.country))
    if to is None:
        first = max(int(x[1:]) for x in led.id) + 1
        new_id = lambda n: f"D{first + n - 1:05d}"  # noqa: E731
    else:
        done = len(pd.read_csv(to, dtype=str)) if to.exists() else 0
        new_id = lambda n: f"{to.stem}-{done + n:04d}"  # noqa: E731
    with open(worksheet, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    rows, errors = read_worksheet(lines, groups, orgs, decided, new_id, date)
    if errors:
        print("NOT WRITTEN:", len(errors), "errors")
        print("\n".join(errors[:60]))
        return 1
    kinds = [r["target"] if not re.fullmatch(r"(TH:)?0[a-z0-9]{8}", r["target"]) else "ROR" for r in rows]
    print("decisions:", len(rows), "| by target:", pd.Series(kinds).value_counts().to_dict())
    if "--dry" not in argv:
        target = to or Path(ledger_csv)
        new_file = not target.exists()
        with open(target, "a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(led.columns), lineterminator="\n")
            if new_file:
                w.writeheader()
            for r in rows:
                w.writerow(r)
        print("written to", target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
