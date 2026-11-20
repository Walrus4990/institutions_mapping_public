"""Shrink the ROR v2 data dump to the snapshot the mapping reads (coding/registries/ror/, rulebook section 2).

Usage: python tools/reduce_ror_dump.py DUMP_CSV OUT_ZIP
  DUMP_CSV  the schema v2 CSV of a ROR data dump (Zenodo), e.g. v2.14-2026-10-06-ror-data.csv
  OUT_ZIP   the snapshot, named after its release, e.g. coding/registries/ror/ror_v2.14_2026-10-06.zip
The zip holds
  ror_orgs.csv   one row per organisation: ror_id, display_name, status, types, country, country_code, city, domains,
                 website, parent_ids, successor_ids
  ror_names.csv  one row per name: ror_id, name, name_kind (display / label / alias / acronym), language prefix
                 removed
Kept: every active organisation, in every country, and inactive or withdrawn ones that name a successor (used only
to redirect old names). Remove the previous snapshot from coding/registries/ror/: a run reads the only zip there.
"""

import csv
import io
import re
import sys
import zipfile

COLS = {
    "id": "id",
    "status": "status",
    "types": "types",
    "display": "names.types.ror_display",
    "label": "names.types.label",
    "alias": "names.types.alias",
    "acronym": "names.types.acronym",
    "country": "locations.geonames_details.country_name",
    "country_code": "locations.geonames_details.country_code",
    "city": "locations.geonames_details.name",
    "domains": "domains",
    "website": "links.type.website",
    "relationships": "relationships",
}
LANG_PREFIX = re.compile(r"^\s*(no_lang_code|[a-z]{2,3}(?:[_-][A-Za-z]+)*)\s*:\s+")
ROR_URL = re.compile(r"https?://ror\.org/([0-9a-z]{9})")
REL_TYPES = ("parent", "child", "related", "successor", "predecessor")


def split_multi(value):
    """Split a multi-value cell on ';' and trim each part."""
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def first(value):
    """The first value of a multi-value cell ('' if none)."""
    parts = split_multi(value)
    return parts[0] if parts else ""


def clean_name(value):
    """A name without its language prefix ("en: ...")."""
    return LANG_PREFIX.sub("", value).strip()


def short_id(url):
    """The 9-character ROR ID of a ROR URL."""
    m = ROR_URL.search(url or "")
    return m.group(1) if m else (url or "").strip()[-9:]


def relations(cell):
    """Return {relation_type: [ror_id, ...]} from the relationships cell.

    Tolerant of both 'type: url' and 'url (type)' layouts: each ROR URL is
    assigned to the nearest relation word written before it.
    """
    out = {t: [] for t in REL_TYPES}
    text = cell or ""
    word_re = re.compile(r"\b(" + "|".join(REL_TYPES) + r")\b", re.I)
    last_type = None
    pos = 0
    for m in ROR_URL.finditer(text):
        words = word_re.findall(text[pos : m.start()])
        if words:
            last_type = words[-1].lower()
        else:
            # try a type written right after the URL, e.g. 'url (parent)'
            after = word_re.match(text[m.end() :].lstrip(" (:-"))
            if after:
                last_type = after.group(1).lower()
        if last_type:
            out[last_type].append(m.group(1))
        pos = m.end()
    return out


def read_dump(path):
    """The dump's rows; stops if a column of COLS is missing."""
    csv.field_size_limit(2**31 - 1)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLS.values() if c not in reader.fieldnames]
        if missing:
            sys.exit("Missing columns: " + ", ".join(missing))
        return list(reader)


def names_of(r, rid):
    """The rows of ror_names.csv for one dump row: each name and kind once."""
    out, seen = [], set()
    for kind in ("display", "label", "alias", "acronym"):
        for n in split_multi(r[COLS[kind]]):
            n = clean_name(n)
            if n and (n, kind) not in seen:
                seen.add((n, kind))
                out.append({"ror_id": rid, "name": n, "name_kind": kind})
    return out


def reduce(rows_in):
    """(orgs, names, counts): the rows of ror_orgs.csv (sorted by country and name) and ror_names.csv."""
    orgs, names = [], []
    counts = {"active": 0, "inactive_with_successor": 0}
    for r in rows_in:
        status = r[COLS["status"]].strip()
        rel = relations(r[COLS["relationships"]])
        if status == "active":
            counts["active"] += 1
        elif rel["successor"]:
            counts["inactive_with_successor"] += 1
        else:
            continue
        rid = short_id(r[COLS["id"]])
        orgs.append(
            {
                "ror_id": rid,
                "display_name": clean_name(first(r[COLS["display"]])),
                "status": status,
                "types": ";".join(split_multi(r[COLS["types"]].replace(",", ";"))),
                "country": first(r[COLS["country"]]),
                "country_code": first(r[COLS["country_code"]]),
                "city": first(r[COLS["city"]]),
                "domains": ";".join(split_multi(r[COLS["domains"]])),
                "website": first(r[COLS["website"]]),
                "parent_ids": ";".join(rel["parent"]),
                "successor_ids": ";".join(rel["successor"]),
            }
        )
        names += names_of(r, rid)
    orgs.sort(key=lambda x: (x["country"], x["display_name"]))
    return orgs, names, counts


def as_csv(rows, fieldnames):
    """Rows as CSV text."""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv):
    """Read the dump, write the snapshot zip and print what was kept."""
    dump, out_zip = argv[:2]
    rows_in = read_dump(dump)
    print(f"Read {len(rows_in)} records.")
    orgs, names, counts = reduce(rows_in)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("ror_orgs.csv", as_csv(orgs, list(orgs[0].keys())))
        z.writestr("ror_names.csv", as_csv(names, ["ror_id", "name", "name_kind"]))
    print(
        f"Kept {len(orgs)} organisations ({counts['active']} active, {counts['inactive_with_successor']} inactive "
        f"with a successor) and {len(names)} names -> {out_zip}"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
