"""Client path (rulebook section 11): codes the institution column of a spreadsheet from the published mapping.

The sheet is checked first (11.2). Then each answer is looked up in the published mapping (11.3, 11.4) and a copy of
the sheet is written with four columns added: canonical_name, institution_id, norhed (11.5) and coding_status. The
answers that are not in the mapping are written as a separate list in the format of the pipeline's batches (11.6),
to go into input/. No new code is made here (11.1).

Everything checked and found goes to a log beside the outputs, for the AI assistant that runs the command. The log
holds no answer text.
"""

import datetime
import json
import logging
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

from .build_input import COUNTRY_SPELLINGS
from .core import norhed
from .core.personal_data import personal_data
from .core.text import clean, pipeline_key
from .pipeline import CODING, OUTPUT, REGISTRIES

ADDED = ["canonical_name", "institution_id", "norhed", "coding_status"]
CODED = "coded"
NOT_IDENTIFIED = "not identified"
NOT_IN_MAPPING = "not in mapping"
LEFT_OFF = "not coded: left off the list"  # with a session's mapping: an answer the client took off the list
COUNTRY_NEEDED = "country needed"
PERSONAL = "personal data, not coded"
NO_ANSWER = "no answer"
NO_ORGANISATION = {
    "NOT_APPLICABLE": "no organisation (NOT_APPLICABLE)",
    "NOT_SPECIFIED": "organisation not named (NOT_SPECIFIED)",
}
# country spellings that neither ROR nor build_input.COUNTRY_SPELLINGS have
COUNTRY_ALIASES = {
    "UK": "GB",
    "Great Britain": "GB",
    "England": "GB",
    "USA": "US",
    "United States of America": "US",
    "DRC": "CD",
    "Democratic Republic of the Congo": "CD",
    "Congo DR": "CD",
    "Republic of the Congo": "CG",
    "Cote d'Ivoire": "CI",
    "Swaziland": "SZ",
    "Gambia": "GM",
    "Cape Verde": "CV",
    "Turkey": "TR",
    "Czech Republic": "CZ",
    "United Republic of Tanzania": "TZ",
}
LOGGER = "institution_mapping.code_sheet"


class Stop(Exception):
    """A check that stops the command (rulebook 11.2). The message says what is wrong and how to fix it."""


def text(value):
    """A cell as text: empty for an empty cell, whole numbers without '.0', spaces at the ends removed."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def find_header(headers, name):
    """Position of a header: the exact name first, then the name in any capitals; None if absent."""
    name = name.strip()
    for want in (lambda h: h == name, lambda h: h.casefold() == name.casefold()):
        for i, h in enumerate(headers):
            if want(h):
                return i
    return None


class Sheet:
    """The client's table: its rows as read (.xlsx or .csv), the header row, and the copy written with the codes."""

    def __init__(self, path, sheet_name, header_row, log):
        self.path, self.header_row, self.sheet_name, self.encoding = path, header_row, sheet_name, "utf-8-sig"
        self.rows = self._read_csv(log) if path.suffix.lower() == ".csv" else self._read_xlsx(log)
        if len(self.rows) < header_row:
            raise Stop(f"the sheet has {len(self.rows)} rows, so there is no header in row {header_row}")
        self.header = [text(v) for v in self.rows[header_row - 1]]
        log.info("sheet: %s | header row: %d | rows below it: %d", self.sheet_name or "-", header_row, self.n_data())

    def _read_xlsx(self, log):
        """The rows of the chosen sheet (default: the first, with a warning if there are several)."""
        wb = openpyxl.load_workbook(self.path, data_only=True)
        if self.sheet_name is None:
            self.sheet_name = wb.sheetnames[0]
            if len(wb.sheetnames) > 1:
                log.warning("the file has %d sheets %s; the first one was used", len(wb.sheetnames), wb.sheetnames)
        elif self.sheet_name not in wb.sheetnames:
            raise Stop(f"there is no sheet {self.sheet_name!r}; the sheets are {wb.sheetnames}")
        return [list(r) for r in wb[self.sheet_name].iter_rows(values_only=True)]

    def _read_csv(self, log):
        """The rows of a CSV file: separator detected, UTF-8 or else Windows text (with a warning)."""
        try:
            d = pd.read_csv(self.path, header=None, dtype=str, keep_default_na=False, sep=None, engine="python")
        except UnicodeDecodeError:
            self.encoding = "cp1252"
            log.warning("the file is not UTF-8; it was read as Windows text (cp1252)")
            d = pd.read_csv(
                self.path,
                header=None,
                dtype=str,
                keep_default_na=False,
                sep=None,
                engine="python",
                encoding=self.encoding,
            )
        return d.values.tolist()

    def n_data(self):
        """Number of rows below the header that hold anything."""
        return sum(1 for _ in self.data_rows())

    def data_rows(self):
        """(row number, cells) of each row below the header that is not empty."""
        for n, row in enumerate(self.rows[self.header_row :], start=self.header_row + 1):
            if any(text(v) for v in row):
                yield n, row

    def column(self, name, what):
        """Position of a column, or Stop with what was found instead (another header row, or the headers there)."""
        i = find_header(self.header, name)
        if i is not None:
            return i
        for n, row in enumerate(self.rows[:20], start=1):
            if n != self.header_row and find_header([text(v) for v in row], name) is not None:
                raise Stop(
                    f"the {what} column {name!r} is in row {n}, not in row {self.header_row}: "
                    f"run again with --header-row {n}"
                )
        found = [h for h in self.header if h]
        raise Stop(f"there is no {what} column {name!r} in row {self.header_row}; the headers there are {found}")

    def write(self, out_path, codes):
        """Write a copy of the file with the ADDED columns; codes: row number -> the four values. Columns with
        these names that are already there (an earlier run) are overwritten."""
        if self.path.suffix.lower() == ".csv":
            self._write_csv(out_path, codes)
        else:
            self._write_xlsx(out_path, codes)

    def _write_xlsx(self, out_path, codes):
        """The copy as a workbook: the client's cells and formulas kept, the ADDED columns written."""
        wb = openpyxl.load_workbook(self.path)  # not data_only: the client's formulas are kept
        ws = wb[self.sheet_name]
        free = max(len(self.header), ws.max_column) + 1
        for k, name in enumerate(ADDED):
            col = find_header(self.header, name)
            if col is None:
                col, free = free - 1, free + 1
            ws.cell(self.header_row, col + 1, name)
            for n, values in codes.items():
                ws.cell(n, col + 1, values[k] or None)
        wb.save(out_path)

    def _write_csv(self, out_path, codes):
        """The copy as a CSV file in the encoding it was read with, the ADDED columns written."""
        rows = [list(r) for r in self.rows]
        cols = []
        for name in ADDED:
            col = find_header(self.header, name)
            cols.append(col if col is not None else len(self.header) + len([c for c in cols if c >= len(self.header)]))
        width = max(max(len(r) for r in rows), max(cols) + 1)
        rows = [r + [""] * (width - len(r)) for r in rows]
        for k, col in enumerate(cols):
            rows[self.header_row - 1][col] = ADDED[k]
            for n, values in codes.items():
                rows[n - 1][col] = values[k]
        pd.DataFrame(rows).to_csv(out_path, header=False, index=False, encoding=self.encoding)


def read_snapshot_countries():
    """ROR's country names -> two-letter codes, read from the zipped snapshot in coding/registries/ror/."""
    (snapshot,) = (REGISTRIES / "ror").glob("*.zip")
    with zipfile.ZipFile(snapshot) as z, z.open("ror_orgs.csv") as f:
        o = pd.read_csv(f, usecols=["country", "country_code"], dtype=str, keep_default_na=False)
    o = o[(o.country != "") & (o.country_code != "")].drop_duplicates()
    return dict(zip(o.country, o.country_code))


def country_codes(mapping_countries):
    """Country name or code (as written by the client) -> two-letter code: ROR's country names, the questionnaire
    spellings of build_input, COUNTRY_ALIASES, and every two-letter code of ROR and of the mapping (rulebook 11.4)."""
    names = read_snapshot_countries()
    table = {pipeline_key(n): c for n, c in names.items()}
    table |= {pipeline_key(n): c for n, c in (COUNTRY_SPELLINGS | COUNTRY_ALIASES).items()}
    codes = set(names.values()) | {c for c in mapping_countries if c}
    table |= {c.lower(): c for c in codes}
    return table


def answer_keys(answer):
    """The two keys under which answers are the same answer (rulebook 3.6): pipeline key and cleaned text."""
    return [k for k in (("pipeline", pipeline_key(answer)), ("cleaned", clean(answer))) if k[1]]


class Mapping:
    """The published mapping, looked up by same answer (rulebook 3.6) and country (11.3, 11.4)."""

    def __init__(self, m):
        m = m.assign(n=pd.to_numeric(m.learners, errors="coerce").fillna(0))
        m = m.sort_values("n", ascending=False, kind="stable")
        self.by_country = defaultdict(list)  # (kind, key, country) -> rows, most learners first
        self.by_key = defaultdict(list)  # (kind, key) -> rows in every country
        cols = ["raw_institution", "country", "canonical_name", "institution_id", "org_type", "status", "n"]
        for r in m[cols].itertuples(index=False):
            for k in answer_keys(r.raw_institution):
                self.by_country[(*k, r.country)].append(r)
                self.by_key[k].append(r)
        self.partners = set(norhed.table().institution_id)

    def lookup(self, answer, country):
        """(canonical_name, institution_id, norhed, coding_status) of an answer and a two-letter country code.
        Without a country: the mapping's row without a country; otherwise the one outcome of every country."""
        keys = answer_keys(answer)
        if country:
            for k in keys:
                if self.by_country.get((*k, country)):
                    return self.result(self.by_country[(*k, country)][0])
            return "", "", "", NOT_IN_MAPPING
        for k in keys:  # the mapping's own row for the answer given without a country
            if self.by_country.get((*k, "")):
                return self.result(self.by_country[(*k, "")][0])
        found = [r for k in keys for r in self.by_key.get(k, [])]
        if not found:
            return "", "", "", NOT_IN_MAPPING
        if len({outcome(r) for r in found}) > 1:
            return "", "", "", COUNTRY_NEEDED
        return self.result(max(found, key=lambda r: r.n))

    def result(self, r):
        """The four added values for a mapping row."""
        if r.status != "coding complete":
            return "", "", "", NOT_IDENTIFIED
        if r.institution_id:
            return r.canonical_name, r.institution_id, self.norhed(r.institution_id), CODED
        return "", "", "", NO_ORGANISATION.get(r.org_type, f"type only ({r.org_type})")

    def norhed(self, institution_id):
        """Rulebook 11.5: 'yes' IF the ID is on the NORHED partner list, otherwise 'no'."""
        return "yes" if institution_id in self.partners else "no"


def outcome(r):
    """What two mapping rows must share to be one outcome: status, ID, and the org_type of a coded row without ID."""
    no_id_type = r.org_type if r.status == "coding complete" and not r.institution_id else ""
    return r.status, r.institution_id, no_id_type


def published_mapping(workbook=None):
    """The mapping sheet (as text) and the file name of a mapping workbook: by default the published one in output/;
    a client session gives its own run's workbook (rule 11.3)."""
    if workbook is None:
        files = sorted(OUTPUT.glob("institution_mapping_*.xlsx"))
        if not files:
            raise Stop(
                "the published mapping (output/institution_mapping_*.xlsx) is missing: download the repository again"
            )
        workbook = files[-1]
    workbook = Path(workbook)
    if not workbook.exists():
        raise Stop(f"the mapping workbook {workbook} does not exist: run the mapping first")
    return pd.read_excel(workbook, sheet_name="mapping", dtype=str, keep_default_na=False), workbook.name


@dataclass
class Job:
    """What the checks found: the sheet, and per data row (row number, answer, country code or '')."""

    sheet: Sheet
    rows: list = field(default_factory=list)
    personal: set = field(default_factory=set)


def open_sheet(path, sheet_name, header_row, log):
    """Rulebook 11.2: the file exists, has a supported format and can be read."""
    if not path.exists():
        raise Stop(f"the file {path} does not exist")
    suffix = path.suffix.lower()
    if suffix == ".xls":
        raise Stop("the file is in the old .xls format: open it in Excel and save it as 'Excel Workbook (.xlsx)'")
    if suffix not in (".xlsx", ".csv"):
        raise Stop(f"files of type {suffix or '(none)'} are not read: save the sheet as .xlsx or .csv")
    try:
        return Sheet(path, sheet_name, header_row, log)
    except PermissionError as e:
        raise Stop("the file cannot be opened: close it in Excel (or any other program) and run again") from e
    except Stop:
        raise
    except Exception as e:  # any other reason a file cannot be read: password, damaged file, not really .xlsx
        raise Stop(f"the file cannot be read ({type(e).__name__}: {e}); open it in Excel and save it again") from e


def resolve_countries(job, values, mapping_countries, log):
    """Rulebook 11.4: the country of each row as a two-letter code; unknown and empty values are reported."""
    table = country_codes(mapping_countries)
    unknown, empty = Counter(), 0
    for n, answer, value in values:
        code = table.get(pipeline_key(value), "") if value else ""
        if value and not code:
            unknown[value] += 1
        empty += not value
        job.rows.append((n, answer, code))
    if unknown:
        log.warning(
            "country values not recognised (%d rows; these rows are looked up as if they had no country): %s",
            sum(unknown.values()),
            dict(unknown.most_common()),
        )
    if empty:
        log.warning("%d rows have no country; they are looked up as if the sheet had no country column", empty)


def check(path, column, country_column, sheet_name, header_row, mapping_countries, log):
    """Rulebook 11.2: every check on the client's file. Raises Stop for a problem that prevents coding; logs a
    warning for one that only affects some rows."""
    sheet = open_sheet(path, sheet_name, header_row, log)
    a = sheet.column(column, "institution")
    c = sheet.column(country_column, "country") if country_column else None
    cell = lambda row, i: text(row[i]) if i is not None and i < len(row) else ""  # noqa: E731
    values = [(n, cell(row, a), cell(row, c)) for n, row in sheet.data_rows()]
    n_answers = sum(1 for _, answer, _ in values if answer)
    if not n_answers:
        raise Stop(f"the institution column {column!r} has no answers below row {header_row}")
    log.info(
        "institution column: %r | answers: %d | rows without an answer: %d", column, n_answers, len(values) - n_answers
    )
    job = Job(sheet)
    if c is None:
        log.warning(
            "no country column was given: an answer is coded only where it has the same code in every "
            "country of the mapping, otherwise its status is %r",
            COUNTRY_NEEDED,
        )
        job.rows = [(n, answer, "") for n, answer, _ in values]
    else:
        log.info("country column: %r", country_column)
        resolve_countries(job, values, mapping_countries, log)
    patterns = json.loads((CODING / "coding_rules.json").read_text(encoding="utf-8"))["personal_data"]
    job.personal = {n for n, answer, _ in job.rows if answer and personal_data(answer, patterns)}
    if job.personal:
        log.warning(
            "%d answers are personal data (an e-mail address or an ID or phone number): they are not coded "
            "and not listed",
            len(job.personal),
        )
    again = [name for name in ADDED if find_header(sheet.header, name) is not None]
    if again:
        log.warning("the sheet already has the columns %s (an earlier run?): they are overwritten in the copy", again)
    return job


def code(job, mapping, session=False):
    """Rulebook 11.3-11.5: the four values per row, and the answers not in the mapping. With a session's mapping
    (session), an answer it does not hold is one the client took off the list (a person's name): LEFT_OFF."""
    codes, missing = {}, []
    for n, answer, country in job.rows:
        if not answer:
            codes[n] = ("", "", "", NO_ANSWER)
        elif n in job.personal:
            codes[n] = ("", "", "", PERSONAL)
        else:
            codes[n] = mapping.lookup(answer, country)
            if codes[n][3] == NOT_IN_MAPPING and session:
                codes[n] = ("", "", "", LEFT_OFF)
            elif codes[n][3] == NOT_IN_MAPPING:
                missing.append((answer, country))
    return codes, missing


def unmapped_table(missing):
    """Rulebook 11.6: one row per pipeline key and country; the most frequent spelling; learners = rows."""
    groups = defaultdict(Counter)
    for answer, country in missing:
        groups[(pipeline_key(answer), country)][answer] += 1
    rows = [
        {"raw institution": c.most_common(1)[0][0], "country": country, "learners": sum(c.values())}
        for (_, country), c in groups.items()
    ]
    t = pd.DataFrame(rows, columns=["raw institution", "country", "learners"])
    return t.sort_values(["learners", "raw institution"], ascending=[False, True], ignore_index=True)


def write_outputs(job, codes, missing, out, stem, log, session=False):
    """The coded copy of the sheet, and the list of answers not in the mapping (if any; never with a session's
    mapping, whose list was written before)."""
    coded = out / f"{stem}_coded{job.sheet.path.suffix.lower()}"
    try:
        job.sheet.write(coded, codes)
    except PermissionError as e:
        raise Stop(f"{coded.name} cannot be written: close it in Excel and run again") from e
    log.info("coded copy: %s", coded)
    if session:
        log.info("coded with the session's mapping: the list of new answers is not written again")
        return
    if not missing:
        log.info("every answer was found in the mapping: there is no list to send back")
        return
    t = unmapped_table(missing)
    path = out / f"unmapped_institutions_{datetime.date.today().isoformat()}_{safe_stem(stem)}.xlsx"
    t.to_excel(path, sheet_name="unmapped", index=False)
    log.info(
        "answers not in the mapping: %d rows, %d different answers, listed in %s (send this file to the "
        "maintainer of the mapping)",
        len(missing),
        len(t),
        path,
    )


class _Counter(logging.Handler):
    """Counts the log lines per level, for the summary printed at the end."""

    def __init__(self):
        super().__init__()
        self.n = Counter()

    def emit(self, record):
        """Count one log line."""
        self.n[record.levelname] += 1


def safe_stem(stem):
    """A file name part with letters, digits, '_' and '-' only: names the list (11.6) and the log (11.2)."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", stem)


def log_path(folder, stem):
    """The log beside the outputs: <file>_coding_log.txt. The submit command adds to the same log."""
    return Path(folder) / f"{safe_stem(stem)}_coding_log.txt"


def open_log(path, mode="w"):
    """The log for the AI assistant: one line per finding, 'LEVEL message'. Written anew by each coding run
    (mode 'w'); the submit command adds to it (mode 'a')."""
    log = logging.getLogger(LOGGER)
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    handler = logging.FileHandler(path, mode=mode, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    counter = _Counter()
    log.addHandler(handler)
    log.addHandler(counter)
    return log, counter


def close_log(log):
    """Close the log's file, so that the next command can open it again."""
    for h in list(log.handlers):
        h.close()
        log.removeHandler(h)


def run(file, column, country_column=None, sheet=None, header_row=1, out_dir=None, check_only=False, mapping=None):
    """Check the file and, unless check_only, code it with the published mapping (or the mapping workbook
    `mapping`). Returns 0, or 1 if a check stopped it (see the log)."""
    path = Path(file).resolve()
    out = Path(out_dir).resolve() if out_dir else path.parent
    out.mkdir(parents=True, exist_ok=True)
    log_file = log_path(out, path.stem)
    log, counter = open_log(log_file)
    status = 0
    try:
        log.info("file: %s | %s", path, "checks only" if check_only else "checks and coding")
        m, name = published_mapping(mapping)
        log.info("%s mapping: %s (%d answers)", "session" if mapping else "published", name, len(m))
        job = check(path, column, country_column, sheet, header_row, set(m.country), log)
        if not check_only:
            codes, missing = code(job, Mapping(m), session=mapping is not None)
            for s, k in Counter(v[3] for v in codes.values()).most_common():
                log.info("coding_status %r: %d rows", s, k)
            write_outputs(job, codes, missing, out, path.stem, log, session=mapping is not None)
        log.info("done")
    except Stop as e:
        log.error("%s", e)
        status = 1
    finally:
        close_log(log)
    print(
        f"{'stopped' if status else 'done'}: {counter.n['ERROR']} errors, {counter.n['WARNING']} warnings. "
        f"Log: {log_file}"
    )
    return status
