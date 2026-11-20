"""Command line: python -m institution_mapping COMMAND (see README.md).

The operator's commands: build-input, run, worklist, judgement-calls, precedents, take-in, release; the client path's
(rulebook 11): code-sheet, submit, save-key.
"""

import argparse
import datetime
import shutil
import sys
import tempfile
from pathlib import Path

from . import build_input, changes, code_sheet, judgement_calls, pipeline, precedents, submit, worklist
from .core.ledger import decision_files, take_in


def release(out_dir, date):
    """Copy a run's results into the repository: the LOCAL register (IDs issued by the run become permanent,
    rulebook 7.5), the workbook (output/ holds only the latest one) and the regression reference (tests/reference/).
    First the changed rows are compared with the published workbook and listed (changes.py), and the version
    number is checked.
    Older pipeline batches leave input/: their answers are carried forward by the published mapping."""
    out = pipeline.Run(None, None, Path(out_dir).resolve())
    waiting = decision_files(pipeline.INPUT)
    if waiting:
        raise SystemExit(
            f"decisions files are waiting in input/ ({', '.join(f.name for f in waiting)}): take them in first "
            "(python -m institution_mapping take-in), run again, then release (rulebook 9.6)"
        )
    published = sorted((pipeline.REPO / "output").glob("institution_mapping_*.xlsx"))
    if published:  # the changes log and the version check, before anything is copied
        changes.check_and_log(out.o("institution_mapping_final.xlsx"), published[-1])
    for old in published:
        old.unlink()  # one deliverable: the previous version is in the git history
    for old in sorted(pipeline.INPUT.glob("unmapped_institutions_*.xlsx"))[:-1]:
        old.unlink()  # its answers are in the published mapping now; the file is in the git history
        print("removed", old.relative_to(pipeline.REPO))
    workbook = out.o("institution_mapping_final.xlsx")
    targets = [
        (out.registry("local_ids.csv"), pipeline.REGISTRIES / "local_ids.csv"),
        (workbook, pipeline.REPO / "output" / f"institution_mapping_{date}.xlsx"),
        (workbook, pipeline.REPO / "tests" / "reference" / "reference_output.xlsx"),
    ]
    for src, dst in targets:
        shutil.copyfile(src, dst)
        print("copied", src, "->", dst.relative_to(pipeline.REPO))


def operator_commands(sub):
    """The operator's commands: build-input, run, release, worklist."""
    b = sub.add_parser(
        "build-input", help="only build raw.csv from input/ and output/ (keep it outside the repository)"
    )
    b.add_argument("out_csv")
    b.add_argument(
        "--ror", help="unzipped ROR snapshot (default: unzip coding/registries/ror/ into a temporary folder)"
    )
    r = sub.add_parser("run", help="run the mapping into OUT_DIR (input built from input/ and output/)")
    r.add_argument("out_dir")
    r.add_argument("--input", help="a folder holding raw.csv to use instead of building it")
    r.add_argument("--ror", help="an unzipped ROR snapshot to use instead of coding/registries/ror/")
    r.add_argument("--from-stage", help="re-run from this stage on, reusing OUT_DIR/work (e.g. apply_decisions)")
    s = sub.add_parser("release", help="copy a run's register, workbook and reference into the repository")
    s.add_argument("out_dir")
    s.add_argument("--date", default=datetime.date.today().isoformat())
    w = sub.add_parser(
        "worklist",
        help="after a run: what became of the answers of the lists in input/, and what is left to search (step 7)",
    )
    w.add_argument("out_dir")
    sub.add_parser(
        "take-in", help="move the decisions files of input/ into coding/decisions.csv, before a release (rule 9.6)"
    )
    j = sub.add_parser(
        "judgement-calls", help="after the decisions are applied: the draft list of judgement calls (rulebook 9.5)"
    )
    j.add_argument("out_dir")
    j.add_argument("--all", action="store_true", help="every row, not only the new or changed ones")
    q = sub.add_parser("precedents", help="how similar answers were coded before, for a judgement call (rule 9.5)")
    q.add_argument("out_dir", help="a run's folder (for the ROR links), or - for none")
    q.add_argument("answer")
    q.add_argument("country", nargs="?", default="")
    q.add_argument("--proposed", default="", help="the ID proposed for the answer")


def client_commands(sub):
    """The client path's commands (rulebook 11): code-sheet, submit, save-key."""
    c = sub.add_parser(
        "code-sheet",
        help="client path (rulebook 11): check a spreadsheet and add canonical_name, institution_id, norhed and "
        "coding_status from the published mapping; the log beside the outputs says what was found",
    )
    c.add_argument("file", help="the client's .xlsx or .csv file")
    c.add_argument("--column", required=True, help="header of the column with the institution as typed")
    c.add_argument("--country-column", help="header of the column with the country (two-letter code or name)")
    c.add_argument("--sheet", help="sheet name (default: the first sheet)")
    c.add_argument("--header-row", type=int, default=1, help="row that holds the headers (default 1)")
    c.add_argument("--out-dir", help="folder for the outputs and the log (default: the file's folder)")
    c.add_argument("--check-only", action="store_true", help="only check the file and write the log")
    c.add_argument(
        "--mapping", help="a mapping workbook to use instead of the published one (a session's run: rule 11.3)"
    )
    u = sub.add_parser(
        "submit",
        help="client path (rulebook 11.7): send the list of answers not in the mapping as a pull request to input/",
    )
    u.add_argument("list_file", help="the list written by code-sheet: unmapped_institutions_<date>_<file>.xlsx")
    u.add_argument("--run", help="the folder the session ran the mapping into: its new LOCAL IDs go with the list")
    u.add_argument("--check-only", action="store_true", help="only check the list and the key; send nothing")
    u.add_argument("--note", default="", help="a note to the maintainer for the description (no person's name)")
    u.add_argument("--key-file", default=submit.KEY_FILE, help=f"where the key is saved (default {submit.KEY_FILE})")
    u.add_argument("--repo", default=submit.GITHUB_REPO, help=f"owner/name (default {submit.GITHUB_REPO})")
    k = sub.add_parser("save-key", help="save the key for submit once: from the maintainer's file, or from stdin")
    k.add_argument("file", nargs="?", help="the key file from the maintainer (omit to read a pasted key from stdin)")
    k.add_argument("--key-file", default=submit.KEY_FILE, help=f"where to save it (default {submit.KEY_FILE})")
    k.add_argument("--repo", default=submit.GITHUB_REPO, help=f"owner/name (default {submit.GITHUB_REPO})")


def build_input_only(a):
    """build-input: raw.csv only."""
    with tempfile.TemporaryDirectory() as tmp:
        ror = a.ror or tmp
        if not a.ror:
            pipeline.unzip_ror(ror)
        build_input.build(ror, a.out_csv)


def run_mapping(a):
    """run: every stage, or the stages from --from-stage on."""
    stages = pipeline.STAGES[pipeline.STAGES.index(a.from_stage) :] if a.from_stage else None
    pipeline.run(a.out_dir, in_dir=a.input, ror_dir=a.ror, stages=stages)


def take_in_decisions(a):
    """take-in: the decisions files of input/ into the ledger (rule 9.6)."""
    taken = take_in(pipeline.CODING / "decisions.csv", pipeline.INPUT)
    for name, n in taken.items():
        print(f"{name}: {n} decisions taken into coding/decisions.csv")
    print("" if taken else "no decisions files in input/")


def code_a_sheet(a):
    """code-sheet: the client path's lookup (rule 11.3); its exit code."""
    return code_sheet.run(
        a.file, a.column, a.country_column, a.sheet, a.header_row, a.out_dir, check_only=a.check_only, mapping=a.mapping
    )


COMMANDS = {  # command -> function of the parsed arguments; a returned number is the exit code
    "build-input": build_input_only,
    "run": run_mapping,
    "release": lambda a: release(a.out_dir, a.date),
    "worklist": lambda a: worklist.run(a.out_dir),
    "take-in": take_in_decisions,
    "judgement-calls": lambda a: judgement_calls.run(a.out_dir, every_row=a.all),
    "precedents": lambda a: precedents.run(None if a.out_dir == "-" else a.out_dir, a.answer, a.country, a.proposed),
    "code-sheet": code_a_sheet,
    "submit": lambda a: submit.submit(a.list_file, a.run, a.key_file, a.repo, check_only=a.check_only, note=a.note),
    "save-key": lambda a: submit.save_key(a.file, a.key_file, a.repo),
}


def main(argv=None):
    """Parse the command line and run the command. Output is UTF-8 everywhere: on Windows, output captured by an AI
    assistant would otherwise use the local encoding and stop at the first character it cannot write."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m institution_mapping", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    operator_commands(sub)
    client_commands(sub)
    a = p.parse_args(argv)
    status = COMMANDS[a.command](a)
    if isinstance(status, int):
        raise SystemExit(status)


if __name__ == "__main__":
    main()
