# Human in the loop: how the institution mapping works and what you do

This guide is for the person who looks after the institution mapping without running code. You need a web browser
and access to this repository on GitHub. Someone else, the **operator**, runs the code: a colleague who can run
Python, or a Claude Code session. You hand them the inputs, answer their questions, and pass the result on.

## What the institution mapping does

Learners type the name of their institution in their own words: "Univ. of Nairobi", "KNH", "UoN", "self
employed". The M&E pipeline needs one standard code per organisation. For each answer and the learner's country,
the institution mapping decides:

- **which organisation it is**, as a code from **ROR**, the Research Organization Registry: a free, worldwide list
  of universities, hospitals, research institutes, ministries and NGOs. Each has a code such as `02y9nww90`
  (University of Nairobi);
- or, when the organisation exists but is not in ROR, a **LOCAL** code that this project gives it, such as
  `LOCAL-0494`;
- or that the person **has no organisation** ("retired", "self-employed": NOT_APPLICABLE), or **did not name one**
  ("student", "university": NOT_SPECIFIED);
- or that the answer **could not be identified safely**. A wrong code is worse than no code, so doubtful answers
  are left uncoded, with the reason written down.

Most answers are decided by fixed rules: the same answer always gets the same code. The rules are in
`coding/RULEBOOK.md`. The rest need a person: a web search, or a judgement where reasonable people could disagree. Every
such decision is written down with its reason and source, so it is never asked twice.

## The cycle, step by step

### 1. You deposit the new answers

When the M&E pipeline produces a list of institution answers it could not find in the mapping, save it in this
folder of the repository, directly in the folder (not in a subfolder):

**`input/`**

- Name it `unmapped_institutions_YYYY-MM-DD.xlsx`, with the date it was produced (e.g.
  `unmapped_institutions_2026-11-02.xlsx`). The name must start exactly like this, or it will not be read.
- It needs three columns, as in the earlier file: `raw institution`, `country` (two-letter code such as `KE`),
  `learners`.
- An earlier batch may still be there: leave it. The operator's release removes it once its answers are in the
  published mapping, which keeps every answer ever coded. Answers already seen are recognised and not counted
  twice.

Clients who code their own spreadsheets send their new answers, already coded, to the same folder: their AI
assistant does the searches and the client decides the judgement calls. The operator adds them. You do nothing for
those.

Complete exports of every answer (for example from Moodle) are optional; if you have them, they go in
`input/historical_exports/`, replacing the old file of the same name.

On GitHub: open the folder, choose **Add file → Upload files**, drag the file in, and choose **Commit changes**.

Then tell the operator that new answers have arrived.

### 2. The operator runs the mapping

You do not need to do anything here. The run takes about 25 minutes and:

1. removes answers that are personal data (an e-mail address, a phone or ID number) before anything is saved;
2. compares every answer with ROR: exact names, names inside the answer, acronyms, typos, the same words in
   another order;
3. applies the rules for special cases: no organisation, units of a university, teaching hospitals, ministries,
   international organisations, campuses;
4. reuses every decision already taken by a person;
5. checks the result and stops if anything contradicts the rules, for example two spellings of the same answer
   with different codes.

### 3. The operator searches what the rules could not decide

For each answer the rules leave open, the operator searches the web for "learner's country + answer" and writes
the result down with its source: in ROR, confirmed to exist but not in ROR (a LOCAL code), or not found.

### 4. You make the judgement calls

Some answers have more than one reasonable reading. The operator does not guess: the code drafts a list of these
judgement calls, and the operator goes through it **with you in the chat**, one at a time. For each, you see what
the learner typed and their country, the code proposed, and why it is a judgement call, with the alternative.

Typical judgement calls:

- an acronym that fits several organisations ("MIT" from a learner in Ethiopia);
- a country office of an international NGO, or a programme or student network run by a university in another
  country: code it to that organisation, or not?
- a hospital or college run by a church, an NGO or a ministry: part of its owner, or an organisation in its own
  right?
- an answer naming two organisations.

**How to answer**, in your own words:

- "yes" if the proposal is right;
- what to do instead ("use local", "leave it uncoded", "code it to X");
- or a question ("is this the same as the NGO Caritas?"). The operator looks into it and comes back to you before
  anything is recorded.

Your answers are recorded as **client decisions**, with your wording as the reason, and the mapping is run again.

If you prefer a spreadsheet, ask for one: the same list as **`docs/qa/codes_to_check_vNN.csv`** (NN is the version
number), which opens in Excel. Write your answer in its first column, `answer`, and upload it to the same place
(step 1 explains how) or send it to the operator.

The operator may also ask about a **rule** rather than a single answer, for example "should every faculty named
without its university be NOT_SPECIFIED?". A rule change applies to all answers, old and new; it is written into
`coding/RULEBOOK.md` and listed in `CHANGELOG.md`.

### 5. You collect the final file and share it

The finished mapping is in the folder **`output/`**. It is the only file there, named
`institution_mapping_YYYY-MM-DD.xlsx`. Each release replaces the previous file; earlier versions stay in the
repository's history.

On GitHub: open `output/`, click the file, and choose **Download** (the download icon).

Share this file with the M&E pipeline. The pipeline reads its **`mapping`** sheet; do not rename the sheets or the
columns, or edit the file by hand. Corrections go through step 4, so they are kept for the next run.

The **read me** sheet explains every column and code. The version number is its first line (e.g. "Institution
mapping – v26"). A new version number means that at least one answer was added or coded differently. What changed
is in `CHANGELOG.md`, and the changed rows are listed in `docs/releases/changes_log_vNN.csv`.

## Where everything is

| What | Where |
|---|---|
| New answers from the M&E pipeline (you put them here) | `input/` |
| Complete exports of every answer, if any (you put them here) | `input/historical_exports/` |
| Judgement calls for you to answer | in the chat with the operator, or `docs/qa/codes_to_check_vNN.csv` |
| The final mapping to share with the M&E pipeline | `output/institution_mapping_YYYY-MM-DD.xlsx` |
| What changed in each version | `CHANGELOG.md`, `docs/releases/changes_log_vNN.csv` |
| The rules | `coding/RULEBOOK.md` |
| Every decision taken by a person, with its reason | `coding/decisions.csv` (also the **research log** sheet of the final file) |
| The lists of organisations and codes: ROR and the LOCAL IDs | `coding/registries/` |

## What you never need to do

- Run code or install anything.
- Edit `coding/` or the code: the operator records your decisions there.
- Remove personal data from the pipeline's file: the mapping does this before anything is saved.
- Check that ROR codes exist: the code accepts only active ROR records and refuses a decision without a reason.
