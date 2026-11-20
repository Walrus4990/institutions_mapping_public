# Notes for a coding session

Start with `README.md` (repository map, how a run works), `coding/RULEBOOK.md` (the rules, each naming its code),
`HIL.md` (what the person in the loop does) and `docs/TODO.md` (the next steps). To code a client's spreadsheet
(the client path, rulebook section 11), follow `AGENTS.md` instead.

## Running
- `pip install -e ".[dev]"`, then `python -m institution_mapping run OUT_DIR`. A full run takes about 25 minutes:
  run it in the background with a time limit of at least an hour, or it is cut off.
- Keep `OUT_DIR` outside the repository (a scratch folder): `OUT_DIR/work/input/raw.csv` holds personal data.
- `--from-stage apply_decisions` re-runs only the last stages on an earlier run, in a few minutes; enough when only
  `coding/decisions.csv` or those stages changed.
- Tests: `IM_RUN_DIR=OUT_DIR python -m pytest -q`; with `IM_RUN_DIR` they also compare the run with
  `tests/reference/reference_output.xlsx`. Lint: `ruff format` and `ruff check src tests tools`.
- `python tools/compare_workbooks.py OUT_DIR/institution_mapping_final.xlsx tests/reference/reference_output.xlsx`
  lists every changed cell.

## Conventions
- The output must not change unless a rule or decision is meant to change it. Check with the reference workbook.
- Any added or changed row is a new version, numbered in sequence (v26, v27; no v26.1): set `VERSION` in
  `src/institution_mapping/__init__.py` before the run; `release` checks the number, writes
  `docs/releases/changes_log_vNN.csv` and archives the previous one (see "Releasing" below).
- `output/` holds one workbook. `archive/` holds only the previous version; older material leaves the repository
  (it stays in the git history).
- No accumulation of small files: every answer lives in the published mapping (rule 1.4), every person's decision
  in `coding/decisions.csv`, every LOCAL ID in `coding/registries/local_ids.csv`.
- ROR always comes first; a LOCAL ID only stands in for an organisation that has no ROR record (rule 7).
- Every change of rule goes into `coding/RULEBOOK.md` with its `Code:` line; `tests/test_rulebook.py` checks the
  references both ways.
- The person in the loop does not run code. Write to them in plain language, with no code terms.

## Procedures

### A new list in `input/` (a client list merged, or a pipeline batch)
1. Run the mapping (in the background), then `python -m institution_mapping worklist OUT_DIR`.
2. Search what `OUT_DIR/worklist.csv` lists, one search per cluster; record the results with
   `tools/add_decisions.py` (README, "Coding new answers"); run again from `apply_decisions`; repeat `worklist`.

### A client's pull request (rulebook 11.7)
It adds a list and a decisions file to `input/` and, if the client's session issued any, LOCAL IDs to the register.
1. Check the files: the list holds answers, countries and counts only; every decision has a target, a source or note
   and a rationale; the new register rows have names and countries. Merge it. (GitHub shows a pull request whose LOCAL
   IDs clash with an earlier one as conflicting: ask that client to run the session's last part again.)
2. Before the next release: `python -m institution_mapping take-in` (the decisions files into `coding/decisions.csv`,
   numbered on), then the final run; the client's answers come out as in their session.

### Judgement calls, in the chat (HIL.md step 4)
1. `python -m institution_mapping judgement-calls OUT_DIR` drafts `OUT_DIR/judgement_calls.csv` (rule 9.5). Read
   it first: drop a flag that is plainly not a judgement call, and add one the code missed.
2. Go through it with the person in the loop **in the chat**, one answer per message, never two. Before each, read the
   rules the row names (`rules`) and its precedent (`precedent`; in full: `precedents OUT_DIR "answer" CC
   --proposed ID`), and propose the code the rulebook gives (it may differ from the run's code: say so). The message
   gives, in plain language with no code terms: what the learner typed and their country, the proposal and the rule it
   follows (with its number), how similar answers were coded before, why consistency matters, and one closed question
   ("Shall I code it so?"), never an open one.
3. A question from them is answered (search if needed) before anything is recorded. A correction that departs from
   the rule or the precedent: say so, and ask whether it is about this answer only or about every answer of this kind;
   for every answer of this kind it is a rule change, agreed with them and made in the rulebook, not a one-row
   decision.
4. Record each answer as a decision in `coding/decisions.csv`, batch `decisions`, `rationale_type`
   `client decision`, the person's words as `rationale` (`extra` `override` where it changes a decided row). Then
   run again from `apply_decisions`.
5. If they prefer a spreadsheet, copy the draft to `docs/qa/codes_to_check_vNN.csv`; their answers come back in its
   `answer` column.

### Releasing (step 7)
The operator AI does all of it; the maintainer only merges the pull request.
1. `python -m institution_mapping take-in` if decisions files are waiting in `input/`. IF `worklist`, the decisions or
   a client's pull request changed a row THEN set `VERSION` to the next number before the final run.
2. Final run; tests with `IM_RUN_DIR`; `tools/compare_workbooks.py` shows every changed cell: check that each change
   is meant (a decision or a rule change).
3. `python -m institution_mapping release OUT_DIR`. It stops on a version number that does not fit, and writes the
   changes log and the archive moves itself.
4. Add the `CHANGELOG.md` entry (what changed and why, the number of rows) and update `archive/README.md`.
5. Commit, push, and open a pull request for the maintainer to merge; merging publishes the new mapping. Clients
   get it the next time they code a file.
