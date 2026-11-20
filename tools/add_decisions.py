"""Add review and web-search decisions to decisions.csv (batch `decisions`, rulebook step 7), from a short worksheet.
Usage: python tools/add_decisions.py GROUPS_CSV WORKSHEET ROR_DIR LEDGER_CSV DATE [--dry]
  GROUPS_CSV  output of group_uncoded.py with a `gid` column (row number)
  WORKSHEET   one decision per line, fields separated by " | ":
                 GIDS | TARGET | NAME | ORG_TYPE | ORG_COUNTRY | RATIONALE_TYPE | SOURCE | NOTE
              GIDS: one or more row numbers, "12,15" or "12-15", or "c<cluster>" for every row of that cluster
                    in the country of the first row named before it ("NG c31" is also accepted)
              TARGET, NAME, ORG_TYPE, ORG_COUNTRY: as in stages/apply_decisions.py (ROR id, TH:<id>, LOCAL, NS, NA,
                    TYPE:<org_type>, UNC); empty fields allowed
              RATIONALE_TYPE: source | rule | searched, not found | reason given
              Lines starting with # and empty lines are ignored.
Checks before anything is written: every row exists and is still undecided in the ledger; a ROR target is an active
record; a ROR record in another country needs 'rule 5.2' in the note, or is refused later by apply_decisions.py;
LOCAL and TH: need a name; every decision has a rationale type and a source or note.
The evidence written to the mapping is the note.
"""

import csv
import re
import sys

import pandas as pd

RATIONALE_TYPES = {"source", "rule", "searched, not found", "reason given"}
ROR_ID = re.compile(r"0[a-z0-9]{8}")


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


def decision(did, r, fields, date):
    """One row of decisions.csv (batch `decisions`) for row r of the groups."""
    target, name, otype, ocountry, rtype, source, note = fields
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
        extra="",
        date=date,
        rationale_type=rtype,
        rationale=note or source,
        rule_code="",
        evidence_text=note or source,
    )


def read_worksheet(lines, groups, orgs, decided, next_id, date):
    """The decisions of a worksheet, and every error found (nothing is written if there is one)."""
    rows, errors, seen, last_cc = [], [], set(), ""
    for ln, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        f = [x.strip() for x in line.split(" | ")]
        f += [""] * (8 - len(f))
        spec, fields = f[0], f[1:8]
        target, name, _, _, rtype, source, note = fields
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
            if key in decided or key in seen:
                errors.append(f"line {ln}: row {gid} already has a decision")
                continue
            seen.add(key)
            why = target_error(target, r, note, orgs)
            if why.startswith("abroad: "):
                errors.append(f"line {ln}: row {gid}: {why.removeprefix('abroad: ')}")
            elif why:
                errors.append(f"line {ln}: {why}")
                continue
            if (target == "LOCAL" or target.startswith("TH:")) and not name:
                errors.append(f"line {ln}: {target} needs a name")
                continue
            if rtype not in RATIONALE_TYPES:
                errors.append(f"line {ln}: rationale type {rtype!r}")
                continue
            if not (source or note):
                errors.append(f"line {ln}: no source or note")
                continue
            rows.append(decision(f"D{next_id:05d}", r, fields, date))
            next_id += 1
    return rows, errors


def main(argv):
    """Check the worksheet against the groups, the ROR snapshot and the ledger; append the decisions unless --dry
    or an error was found. Returns the exit code."""
    groups_csv, worksheet, ror_dir, ledger_csv, date = argv[:5]
    groups = pd.read_csv(groups_csv, keep_default_na=False, dtype=str).set_index("gid")
    orgs = pd.read_csv(f"{ror_dir}/ror_orgs.csv", keep_default_na=False, dtype=str).set_index("ror_id")
    led = pd.read_csv(ledger_csv, keep_default_na=False, dtype=str)
    mine = led[led.batch == "decisions"]
    decided = set(zip(mine.raw_institution, mine.country))
    next_id = max(int(x[1:]) for x in led.id) + 1
    with open(worksheet, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    rows, errors = read_worksheet(lines, groups, orgs, decided, next_id, date)
    if errors:
        print("NOT WRITTEN:", len(errors), "errors")
        print("\n".join(errors[:60]))
        return 1
    kinds = [r["target"] if not re.fullmatch(r"(TH:)?0[a-z0-9]{8}", r["target"]) else "ROR" for r in rows]
    print("decisions:", len(rows), "| by target:", pd.Series(kinds).value_counts().to_dict())
    if "--dry" not in argv:
        with open(ledger_csv, "a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(led.columns), lineterminator="\n")
            for r in rows:
                w.writerow(r)
        print("written to", ledger_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
