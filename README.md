# Institution mapping

Learners type the name of their institution in free text ("Univ. of Nairobi", "KNH", "self employed"). This
repository turns every such answer, per learner country, into one coded row: a **ROR ID** (from the
[Research Organization Registry](https://ror.org)) or a **LOCAL ID** for a confirmed organisation that is not in ROR,
a coded name and an org_type. Answers that name no organisation get NOT_APPLICABLE or NOT_SPECIFIED. An answer that
cannot be identified safely stays "not identified", with the reason recorded.

The result is the workbook `output/institution_mapping_YYYY-MM-DD.xlsx`; the M&E pipeline reads its `mapping` sheet.
The rules are in [`coding/RULEBOOK.md`](coding/RULEBOOK.md), what changed between versions in [`CHANGELOG.md`](CHANGELOG.md).
For the person who looks after the mapping without running code: [`HIL.md`](HIL.md) (human in the loop).
Current version: v26 (26 Oct 2026): 11,163 answers, 22,086 learners.

## Two ways of working

- **Pipeline path.** The M&E pipeline looks up its learners' answers in the published mapping itself, and sends the
  answers it did not find to `input/`. An operator codes them and publishes a new version of the mapping. The person
  in the loop's guide is [`HIL.md`](HIL.md); the operator's steps are below, from "Quick start".
- **Client path.** You code the institution column of your own spreadsheet with the published mapping, with an AI
  assistant on your computer. Your file stays on your computer. Answers the mapping does not know yet are listed in a
  separate file, which the assistant sends to the maintainer of the mapping; they are coded in its next version.

## Coding your own spreadsheet

You need an AI assistant that can run programs on your computer, and Python on that computer. You do not need to
download anything yourself, know this website, or have a GitHub account: the assistant does the technical part.

**Each time**
1. Open your AI assistant, paste the email you received from the maintainer of the mapping, and attach your file.
2. Answer its questions. It checks your file first and tells you if anything needs fixing.
3. You get back a copy of your file with four columns added.
4. If some answers are new to the mapping, the assistant shows you the list. Tell it if any of them is a person's
   name; it removes those and sends the rest to the maintainer. They are coded in the next version of the mapping:
   code your file again then.

The first time, the assistant also saves a key that lets it send that list. The maintainer sends you the key
separately, as a small file. Keep it to yourself.

**Your file**
- An Excel workbook (`.xlsx`) or a CSV file. An old `.xls` file: open it in Excel and save it as "Excel Workbook".
- One row per answer (for example, one per learner), with the column headers in one row, normally the first.
- A column with the institution exactly as people typed it.
- Best also a column with the learner's country, as a two-letter code (`KE`) or a name (`Kenya`). Without a country,
  an answer is coded only when it means the same organisation in every country.
- Close the file in Excel before you start.

**What you get back**, beside your file (your file itself is not changed):
- `<file>_coded.xlsx`: a copy with four columns added: `canonical_name` (the organisation's name), `institution_id`
  (a ROR ID such as `02y9nww90`, which you can look up at `https://ror.org/02y9nww90`, or a LOCAL ID such as
  `LOCAL-0494` for an organisation that is not in ROR), `norhed` (`yes` if the organisation is a NORHED partner) and
  `coding_status`.
- `unmapped_institutions_<date>_<file>.xlsx`, only if some answers are new to the mapping: the list that is sent to
  the maintainer.
- `<file>_coding_log.txt`: what the checks found, for the assistant.

**What `coding_status` means**

| coding_status | Meaning |
| --- | --- |
| `coded` | The organisation is identified: name, ID and NORHED are filled in. |
| `no organisation (NOT_APPLICABLE)` | The person has no organisation ("retired", "self-employed"). |
| `organisation not named (NOT_SPECIFIED)` | The answer names no organisation ("student", "university"). |
| `type only (...)` | Only the kind of organisation is known, for example `type only (HOSPITAL)`. |
| `not identified` | The mapping knows this answer but could not identify it safely. |
| `not in mapping` | The answer is new to the mapping: it is on the list to send back. |
| `country needed` | The answer means different organisations in different countries: add the country. |
| `personal data, not coded` | The answer is an e-mail address or an ID or phone number. |
| `no answer` | The cell is empty. |

The rules of the client path are section 11 of [`coding/RULEBOOK.md`](coding/RULEBOOK.md).

## For the maintainer: setting up a client

**The email to the client.** The client pastes it into their AI assistant each time, so it is written for both:

> Subject: Coding the institution names in your spreadsheets
>
> Dear …,
>
> You can now code the institution names in your own spreadsheets yourself: for each answer, the organisation's
> name, its ID and whether it is a NORHED partner.
>
> Each time: open your AI assistant (one that can run programs on your computer), paste this whole email into the
> chat and attach your Excel file. Then answer its questions. It checks your file first and tells you if anything
> needs fixing; you get back a copy of your file with four columns added.
>
> Answers we do not know yet are collected in a short list. The assistant shows it to you and, once you have
> confirmed that it holds no names of people, sends it to us. We add them to the next version: code your file
> again then.
>
> The first time, the assistant asks for a small key file that lets it send the list to us. We send it to you
> separately. Please keep it to yourself.
>
> For the AI assistant: follow `AGENTS.md` in the public repository https://github.com/Walrus4990/institutions_mapping_public.
> It tells you how to download the latest version, check and code the file, and send the list. The person does not
> need to know anything about the repository.

## Quick start

```
make install                  # pip install -e ".[dev]": the package, pandas, openpyxl, pytest, ruff, radon, interrogate
make run OUT=/tmp/im/out      # build the input, unzip ROR, run all stages (about 25 minutes)
make test OUT=/tmp/im/out     # unit tests, and the run compared with tests/reference/
```

`make run` is `python -m institution_mapping run OUT_DIR`. Keep `OUT_DIR` **outside the repository**: its
`work/input/raw.csv` holds what the learners typed, personal data included, until stage 1 removes it.

A run reads `input/`, `coding/` and the published mapping in `output/`, and writes only into `OUT_DIR`. The same
files always give the same output.

| Output | What it is |
|---|---|
| `OUT_DIR/institution_mapping_final.xlsx` | the deliverable: read me, mapping, organisations, local IDs, retired local IDs, research log |
| `OUT_DIR/mapping_final.csv` | the mapping sheet as CSV |
| `OUT_DIR/decisions_report.csv` | each recorded decision: applied, refused (and why) or not in this input |
| `OUT_DIR/new_local_ids.csv` | LOCAL IDs this run issued |
| `OUT_DIR/work/` | intermediate files: `mapping_NN_<stage>.csv` after each stage, for tracing a row |

## Repository map

```
input/                        new answers (HIL.md, step 1)
  unmapped_institutions_*.xlsx  the newest batch, at the root: from the M&E pipeline, or a client's list
  historical_exports/         optional: exports of every answer (rule 1.4); without them, the published mapping
                              carries every earlier answer
coding/                       what the code codes with
  RULEBOOK.md                 the rules, each with the code that applies it
  coding_rules.json           the rule parameters: word lists, thresholds, international bodies, step 0 patterns
  decisions.csv               every decision taken by a person, each with its rationale (the ledger)
  registries/                 which organisations and codes exist; read together (rule 7.6)
    ror/                      the ROR snapshot, named after its ROR release (made by tools/reduce_ror_dump.py)
    local_ids.csv             the LOCAL ID register: grows, never renumbered (7.5)
    international_networks.csv  which ROR record stands for an international organisation (6.4)
    local_parents.csv         the ROR parent of organisations run by an NGO (6.7)
output/                       the published mapping: one workbook, replaced at each release
docs/                         for people only, never read by the code: TODO, code quality, reference material,
                              the current release's changed rows (releases/), trial_data.xlsx (made-up answers
                              with the flaws of a real export, for trying the client path)
archive/                      the previous version's release files (archive/README.md)
src/institution_mapping/      the code (a Python package)
  pipeline.py                 the list of stages, in order, and where each reads and writes
  __main__.py                 command line: run, build-input, release, worklist, judgement-calls (the operator);
                              code-sheet, submit, save-key (the client path)
  code_sheet.py               the client path: a spreadsheet coded from the published mapping (rulebook 11)
  submit.py                   the client path: the list of new answers sent as a pull request (11.7)
  worklist.py                 after a run: what became of each list's answers, and what is left to search
  search.py                   the search's preparation: decided before?, ROR candidates, groups (used by worklist)
  judgement_calls.py          the draft list of judgement calls (rule 9.5)
  changes.py                  the release's changes log and version check
  build_input.py              the input of a run, from input/ and the published mapping (rule 1.4)
  core/                       shared building blocks
    text.py                   text keys: cleaning (step 1), pipeline key (3.6), word lists
    ror.py                    the ROR snapshot: records, names, parents, successors
    ledger.py                 decisions.csv: the recorded decisions, by batch
    register.py               local_ids.csv: issuing, finding and retiring LOCAL IDs (7.2-7.6)
    table.py                  the mapping table: ID columns, row lookup, shared-name suffixes
    org_types.py              org_type from a ROR record or from a name (3.3)
    personal_data.py          step 0 patterns (step 0, step 8)
    fuzzy.py                  the fuzzy spelling score
    norhed.py                 the NORHED partner list (source: docs/reference/)
  stages/                     one module per stage, run in the order of pipeline.STAGES
    replay/                   the recorded decision passes of 16-17 Oct 2026, replayed with their conventions
tests/                        pytest tests; reference/ holds the workbook the code must reproduce
tools/                        command-line helpers, not part of a run: the web search (check_against_ledger,
                              ror_candidates, group_uncoded, find_ror, add_decisions), comparing workbooks, and
                              upkeep (reduce_ror_dump: a new ROR snapshot; make_networks; purge_personal)
README.md, LICENSE           this file; the code's licence (data: see "Licence")
HIL.md                        the guide for the person in the loop
AGENTS.md                     the client path's instructions for an AI assistant
CLAUDE.md                     the operator AI's notes and procedures
CHANGELOG.md                  what changed in each version
```

## How a run works

`pipeline.STAGES` lists the 28 stages; each is a module in `stages/` with a function `run(ctx)`. `ctx`
(`pipeline.Run`) knows the run's folders: a stage reads the mapping of the stage before it
(`ctx.read_previous`) and writes its own (`ctx.write`). The numbers in brackets are rulebook sections.

| Stages | Modules | What they do |
|---|---|---|
| 1-5 | `prepare`, `exact_names`, `contained_names`, `non_institutions`, `fuzzy_candidates` | remove personal data and clean (0-1); exact ROR name (2); ROR name or acronym inside the answer (3); no organisation and type-only answers (4); close ROR spellings as candidates |
| 6 | `rules_engine` | the rules on every open spelling and country, tried in order (`Engine.RULES`): research, units, teaching hospitals, ministries, branches, word coverage, fuzzy |
| 7-8 | `assemble`, `typo_pass` | one outcome per answer and country; typos and close spellings in the learner's country |
| 9-24 | `replay.*` | the decision passes of 16-17 Oct 2026; each applies the ledger batches named after it |
| 25 | `owner_rule` | rule 3a: a ministry named with its institution is the owner, not the organisation |
| 26 | `apply_decisions` | every decision since 18 Oct (batch `decisions`); LOCAL names (7.6); same answer, same code (3.6); international organisations (6.4) |
| 27-28 | `finalise`, `workbook` | one org_type per ID, coded-name conventions, rule codes (`rule_codes.py`), ROR parents, the checks that stop the run; the workbook |

The run stops, and lists the rows, if the output breaks a consistency rule or holds personal data (rulebook step 8).
`python -m institution_mapping run OUT_DIR --from-stage apply_decisions` re-runs the last stages on an earlier
run's `OUT_DIR/work`, which is quicker when only decisions changed.

## Coding new answers

1. New answers arrive at the root of `input/`: a batch from the M&E pipeline (HIL.md step 1), or a client's list
   when you merge its pull request. Run the mapping. Earlier answers come out as before: the published mapping
   carries every earlier answer, the decisions and the register every earlier decision and ID.
2. See what became of the new answers, and prepare the search for what is left:
   ```
   python -m institution_mapping worklist OUT_DIR
   ```
   It prints, per list in `input/`, how many answers were coded by rules, by a recorded decision, searched before,
   or are left to search, and writes `OUT_DIR/worklist.csv`: the answers to search, with ROR candidates in the
   learner's country, similar answers grouped so that one search decides them all (`cluster`), whether a decision
   exists for a learner in another country (`ledger_status` `other_country`: read it first), and a row number `gid`.
   Its three steps are in `search.py`; the scripts `tools/check_against_ledger.py`, `tools/ror_candidates.py` and
   `tools/group_uncoded.py` run each step on its own. During the search, `tools/find_ror.py` looks up ROR records by
   words.
3. Search the web for each group: "learner's country + answer".
4. Record each result as a row of `coding/decisions.csv` with `batch` = `decisions` (by hand, or from a short
   worksheet with `tools/add_decisions.py`):

   | column | content |
   |---|---|
   | `id`, `date` | a new ID (`Dnnnnn`) and the date |
   | `raw_institution`, `country` | the answer, exactly as in the input |
   | `target` | a ROR ID; `TH:<ROR ID>` (teaching hospital on its university's record); `LOCAL` (confirmed, not in ROR); `NS`; `NA`; `TYPE:<org_type>`; `UNC` (stays not identified); `REMOVE` (the answer leaves the mapping) |
   | `name` | coded name (required for `LOCAL` and `TH:`) |
   | `org_type`, `org_country` | optional; `org_country` = the organisation's own country for `LOCAL` |
   | `source`, `note` | the web source and what it shows |
   | `rationale_type`, `rationale` | **required**: `source` / `rule` / `client decision` / `human-review decision` / `searched, not found`, and the text |
   | `extra` | `override` to correct a row that is already decided |
   | `rule_code`, `evidence_text` | optional: as they should appear in the output |

   An org_type for all rows of an ID goes in batch `org_type` (`target` = the ID, `org_type`, rationale).
   `tools/add_decisions.py OUT_DIR/worklist.csv WORKSHEET ...` reads the worklist's `gid` and `cluster` as they are.
5. Run again (`--from-stage apply_decisions`) and read `OUT_DIR/decisions_report.csv`. A decision is refused without
   a rationale, on a decided row without `override`, for a ROR record abroad that rule 5.2 does not allow, or for
   `LOCAL` without a name. `worklist` again shows what is left.
6. Draft the judgement calls (rulebook 9.5) and go through them with the person in the loop (`CLAUDE.md`):
   ```
   python -m institution_mapping judgement-calls OUT_DIR
   ```

## Releasing

```
make run OUT=/tmp/im/out && make test OUT=/tmp/im/out   # the reference test fails where the output changed
python tools/compare_workbooks.py /tmp/im/out/institution_mapping_final.xlsx tests/reference/reference_output.xlsx
python -m institution_mapping release /tmp/im/out      # register -> coding/registries/, workbook -> output/ and tests/reference/
```

`release` first compares the new workbook with the published one. IF a row was added, removed or coded
differently THEN the release needs the next version number: set `VERSION` in `src/institution_mapping/__init__.py`
before the run (it is the workbook's title); `release` stops if the number does not fit what changed. It then
writes the changed rows to `docs/releases/changes_log_vNN.csv`, moves the previous version's changes log and
judgement-call list to `archive/vNN-1/` and older archive folders to `archive/old/` (git-ignored). `output/` holds one
workbook only: `release` replaces the previous one, and removes the older batches from `input/` (their answers are in
the published mapping; both stay in the git history). Add the version to `CHANGELOG.md`, update `archive/README.md`,
and commit.

## Testing and code quality

`pytest` runs the unit tests. With `IM_RUN_DIR` set to a run's `OUT_DIR` (as `make test` does) it
also checks that the run reproduces `tests/reference/reference_output.xlsx` cell for cell, and runs the decision
applier on 12 made-up decisions. `make lint` runs ruff; `make quality` prints the measures recorded in
[`docs/qa/code_quality.md`](docs/qa/code_quality.md) (complexity, maintainability, docstring coverage).

Personal data in stored files (step 0 clean-up): `python tools/purge_personal.py coding/coding_rules.json FOLDER...`.

## Licence

- The code (`src/`, `tools/`, `tests/`) is under the MIT licence: [`LICENSE`](LICENSE).
- The mapping data (`output/`, `coding/`, `docs/`) is under the Creative Commons Attribution 4.0 International
  licence ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)): use it freely, naming this repository as the
  source.
- ROR IDs and the ROR snapshot in `coding/registries/ror/` come from the [Research Organization
  Registry](https://ror.org), released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
