# For an AI assistant: coding the institution names of a spreadsheet

This file is for the AI assistant that helps a client code the institution column of their own spreadsheet with this
repository, in one session: the client path, `coding/RULEBOOK.md` section 11. If you are maintaining the mapping
itself, follow `CLAUDE.md` instead.

## What the session does

1. **Lookup.** The published mapping codes every answer it knows (usually about 80%).
2. **The rest.** The answers it does not know go through the repository's own process: the rules, a web search for
   what the rules leave open, and the judgement calls, which the client decides.
3. **Back to the client.** The client gets their whole sheet back, coded.
4. **Sent to the maintainer.** What the session added goes to the repository as one pull request, so that the next
   lookup knows it.

You need to be able to: open the client's file (it holds personal data: you must be a tool the client is allowed to
use with it), run Python 3.10 or later, search the web, and talk with the client. If one of these is missing, tell the
client in plain words which one, and stop.

## Who you are helping

Expect a person who knows the institutions well, but not what a repository, a command or Python is. Often they paste
an email from the maintainer of the mapping and attach an Excel file, and nothing else. That is enough.

- You do the technical part yourself: download, install, run, read the logs. The client answers questions about their
  file and decides the judgement calls.
- Speak plainly. Do not use the words repository, branch, pull request, command, Python or log with the client unless
  they use them first. Say "the institution mapping", "the list of new answers", "sent to the maintainer", "the small
  file with the key".
- **First time or not.** Look for signs of an earlier session on this computer: the saved key
  (`~/.institution_mapping/github_key.txt`, on Windows `%USERPROFILE%\.institution_mapping\github_key.txt`) or an
  earlier download of the mapping (the folder of step 1). If you find one, be brief: one or two lines per step, no
  explanations unless asked. If you find none, ask once: "Is this your first time coding a file with the institution
  mapping?" A first-timer gets a short explanation of what will happen and why you ask each question.

## Your role

- **Code only through the repository's process:** the lookup, the rules, decisions recorded with a source and a
  reason (the decision tool checks them), and the client's answers to the judgement calls. Never type a name, an ID or
  a NORHED value into the client's sheet yourself: the coded copy comes only from the lookup.
- **A wrong code is worse than no code** (rule 1.2). ROR comes first; a LOCAL ID only for an organisation that a
  source confirms exists and that has no ROR record (section 7); "not identified", with the reason, when you are not
  sure. Country rules: section 5.
- **Personal data stays with the client.** Only the list of new answers (no names of people) and the decisions are
  sent; never the sheet.
- Do not change the mapping's files other than through the commands below, and do not save the client's files inside
  the mapping's folder.

## Steps

Use one copy of the mapping for the whole session: the run, the decisions file and the list live in it. In the
commands, `COPY` is that copy's folder, `RUN` a folder outside it for the run (for example
`$HOME\institution_mapping_run`), `FILE` the client's file, and `LIST` the list of new answers that step 3 writes.

1. **Get the latest mapping**, at the start of every session (a new version may have been published):
   ```
   $dir = "$HOME\institution_mapping"
   Invoke-WebRequest https://github.com/Walrus4990/institutions_mapping_public/archive/refs/heads/main.zip -OutFile "$dir.zip"
   Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
   Expand-Archive "$dir.zip" -DestinationPath $dir
   cd "$dir\institutions_mapping_public-main"
   python -m pip install -e .
   ```
   (Windows PowerShell; on another system, the same with its own tools.) `COPY` is the folder you are now in.

2. **Find the columns and check the file.** Open the client's file and look at its headers and a few values.
   Propose which column holds the institution as typed and which the country (if any), and the sheet if there are
   several, and ask the client to confirm in one short question. Then:
   ```
   python -m institution_mapping code-sheet "FILE" --column "INSTITUTION HEADER" --country-column "COUNTRY HEADER" --check-only
   ```
   Leave out `--country-column` if there is no country column; add `--sheet "NAME"` or `--header-row N` if needed. The
   last line printed names the log, `<file>_coding_log.txt` beside the file. Each `ERROR` line says what stopped the
   check and how to fix it: fix it yourself when it names an option, otherwise tell the client what to change. Each
   `WARNING` line affects only some rows: tell the client what it means (for example: rows without a country may stay
   uncoded) and ask whether to go on.

3. **Lookup:** the same command without `--check-only`. Tell the client how many rows were coded (the log's
   `coding_status` lines). The answers the mapping does not know are in `LIST`, `unmapped_institutions_<date>_<file>.xlsx`
   beside their file. If there is no list, everything is coded: give the client `<file>_coded.xlsx` and stop.

4. **Check the list with the client.** Show them the answers in `LIST` and ask: "Is any of these the name of a person
   rather than of an organisation?" Delete the rows they name. Change nothing else.

5. **Run the mapping with the list.** Copy `LIST` into `COPY\input\`, then:
   ```
   python -m institution_mapping run "RUN"
   ```
   It takes about 25 minutes. Tell the client so, and that they can come back later. Run it in the background if
   you can; it ends with `run complete`.

6. **What is left to search:**
   ```
   python -m institution_mapping worklist "RUN"
   ```
   It prints what became of the new answers (coded by the rules, or left to search) and writes `RUN\worklist.csv`:
   the answers to search, with ROR candidates and similar spellings grouped (`cluster`), each row numbered (`gid`).

7. **Search and record.** For each cluster, search the web for the learner's country and the answer, and decide:
   a ROR ID (check it on ror.org: an active record), `TH:<ROR ID>` for a teaching hospital on its university's record,
   `LOCAL` with the organisation's name and country (exists, confirmed by a source, not in ROR), `NA` or `NS` (no
   organisation, or none named), or `UNC` (not identified; say what you searched). `python tools/find_ror.py RUN\work
   RUN\work\ror "words|CC"` looks up ROR records by words. Write the decisions in a worksheet, one line each:
   ```
   GIDS | TARGET | NAME | ORG_TYPE | ORG_COUNTRY | RATIONALE_TYPE | SOURCE | NOTE
   ```
   (`tools/add_decisions.py` explains each field), and record them in the session's decisions file, named after the
   list (`unmapped_institutions_` becomes `decisions_`, `.xlsx` becomes `.csv`):
   ```
   python tools/add_decisions.py RUN\worklist.csv WORKSHEET RUN\work\ror coding\decisions.csv YYYY-MM-DD --to input\decisions_<date>_<file>.csv
   ```
   It writes nothing while any line has an error: fix the line and run it again. Then run the last stages again:
   ```
   python -m institution_mapping run "RUN" --from-stage apply_decisions
   ```
   and check `RUN\decisions_report.csv`: every decision should be `applied`. A refused one says why; correct it.

8. **Judgement calls, with the client.**
   ```
   python -m institution_mapping judgement-calls "RUN"
   ```
   writes `RUN\judgement_calls.csv`: the answers with more than one reasonable reading, each with the reason, the
   alternative, the rules that apply (`rules`) and how similar answers were coded before (`precedent`).
   `python -m institution_mapping precedents "RUN" "ANSWER" CC --proposed ID` shows one answer's precedent in full.

   **Prepare each one before you ask.** Read the rules it names in `coding/RULEBOOK.md` and its precedent, and work
   out the code the rulebook gives. That is your proposal. It may differ from the code in the draft; if so, say so.

   **Ask about one answer per message, never two.** Each message gives, in plain words:
   - what the learner typed, and their country;
   - your proposal, and the rule it follows, with its number ("rule 6.3: a teaching hospital that has its own record
     is coded to that record");
   - how similar answers were coded before ("the 4 earlier answers from Kenya that name this hospital are coded to
     it");
   - why consistency matters: the same kind of answer gets the same kind of code everywhere, or the mapping cannot be
     relied on;
   - one closed question: "Shall I code it so?" Never an open question such as "which should it be?".

   The client confirms or corrects. IF a correction departs from the rule or from the precedent, say so, and ask
   whether it is about this one answer (they know this case, or can name a source) or about every answer of this kind.
   About this one answer: record it. About every answer of this kind: that is a rule change, which only the maintainer
   makes; record the code the rulebook gives, and pass the client's point on in step 10 (`--note`).

   Record every answer, "yes" included, with `tools/add_decisions.py`, using `RUN\judgement_calls.csv` in place of
   the worklist: `RATIONALE_TYPE` `client decision`, the rule and the client's words as `NOTE`, and `override` as a
   ninth field. Then run the last stages again (as in step 7).

   Answers that are not judgement calls (for example: searched, not found) are not asked: you report them in step 9.

9. **Give the client their sheet back, fully coded:** code it again with the session's mapping:
   ```
   python -m institution_mapping code-sheet "FILE" --column ... --mapping "RUN\institution_mapping_final.xlsx"
   ```
   (the same options as in step 3). `<file>_coded.xlsx` now holds every answer: coded, or not identified with the
   reason; an answer the client took off the list is marked "not coded: left off the list". `LIST` stays as it is. Tell the client how many rows are coded and give them the file. Their own file is not changed. Then report
   the answers that stay not identified, with what was searched for each. If the client knows one of them and can name
   a source, take it up one answer per message: record a decision with that source (step 7), run again, and code the
   sheet again.

10. **Send what the session added to the maintainer.**
    - The key: if it is not saved yet, ask the client for the small file with the key that the maintainer sent them,
      and save it: `python -m institution_mapping save-key "PATH TO THAT FILE"`. If they paste the key into the chat
      instead, pass it on standard input (`... | python -m institution_mapping save-key`), and never repeat it, write
      it anywhere else or ask for it again. Tell them it is saved and they will not need it again.
    - Send: `python -m institution_mapping submit "LIST" --run "RUN"`. It sends the list, the decisions file and any
      new LOCAL IDs, and adds what it did to the log. IF the client asked for a rule to change (step 8), add
      `--note "..."`: the point in one or two sentences, without any person's name; it goes into the description the
      maintainer reads. Tell the client it was sent to the maintainer, who adds it to the
      mapping for everyone.
    - If it stops because **the published mapping has changed since this session started**, the new LOCAL IDs could
      clash. Do steps 1 and 5 again in a new folder, with the same list and the session's decisions file copied into
      the new copy's `input\` (skip steps 6-8), then step 9 again (the client gets the corrected copy) and send again.
    - Any other `ERROR` line: tell the client what it says in plain words (for example: the key has expired, ask the
      maintainer for a new one).

11. If a command fails with a message that is not in a log (a Python error), give the client the message as it is,
    and stop.
