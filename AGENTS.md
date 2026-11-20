# For an AI assistant: coding the institution column of a spreadsheet

This file is for an AI assistant (Copilot, Claude or another) that helps a person code the institution column of
their own spreadsheet with this repository: the client path, `coding/RULEBOOK.md` section 11. If you are maintaining
the mapping itself, follow `CLAUDE.md` instead.

## Who you are helping

Expect a person who does not know what a repository, a command or Python is. Often they paste an email from the
maintainer of the mapping and attach an Excel file, and nothing else. That is enough: everything you need is here.

- You do the technical part yourself: download, install, run, read the log. The person only answers questions about
  their file and checks the list of new answers.
- Speak plainly. Do not use the words repository, branch, pull request, command, Python or log with the person
  unless they use them first. Say "the institution mapping", "the list of new answers", "sent to the maintainer",
  "the small file with the key".
- **First time or not.** Look for signs of an earlier session on this computer: the saved key
  (`~/.institution_mapping/github_key.txt`, on Windows `%USERPROFILE%\.institution_mapping\github_key.txt`) or an
  earlier download of the mapping (the folder of step 1). If you find one, the person has done this before: be brief, one or two
  lines per step, no explanations unless asked. If you find none, ask once: "Is this your first time coding a file
  with the institution mapping?" A first-timer gets a short explanation of what will happen and why you ask each
  question.

## Your role

You run the mapping's checks and lookup, and you tell the person what they found. You do not code institutions.

- Never write, change or suggest a name, an ID or a NORHED value. The four added columns come only from the command.
- An answer the command did not find stays uncoded. It goes on the list of new answers for the maintainer of the
  mapping, who codes it for the next version (rule 11.1). That list is the final output for those answers, not a gap
  for you to fill.
- Do not change the mapping's files, and do not save the person's files inside its folder.

## Steps

1. **Get the latest mapping**, every time (a new version may have been published), into the same folder each time:
   ```
   $dir = "$HOME\institution_mapping"
   Invoke-WebRequest https://github.com/Walrus4990/institutions_mapping_public/archive/refs/heads/main.zip -OutFile "$dir.zip"
   Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
   Expand-Archive "$dir.zip" -DestinationPath $dir
   cd "$dir\institutions_mapping_public-main"
   python -m pip install -e .
   ```
   (Windows PowerShell; on another system, the same with its own tools.) Python 3.10 or later is needed. If Python is
   missing or the installation fails, tell the person in plain words what is missing and stop: do not code the file
   any other way.

2. **Find the columns.** Open the person's file yourself and look at its headers and a few values. Propose which
   column holds the institution as typed and which the country (if any), and the sheet if there are several, and ask
   the person to confirm in one short question.

3. **Check the file** before coding it:
   ```
   python -m institution_mapping code-sheet "FILE" --column "INSTITUTION HEADER" --country-column "COUNTRY HEADER" --check-only
   ```
   Leave out `--country-column` if there is no country column. Add `--sheet "NAME"` or `--header-row N` if needed.
   The outputs and the log go beside the person's file (`--out-dir "FOLDER"` to change that).

4. **Read the log.** The last line printed names it: `<file>_coding_log.txt`. The command ends with exit code 0 when
   the file can be coded, 1 when a check stopped it.
   - Each `ERROR` line says what stopped the check and how to fix it. Fix it yourself when the line names an option
     (for example `--header-row 3`); otherwise tell the person what to change in their file, in plain words.
   - Each `WARNING` line affects only some rows. Tell the person what it means for their result (for example: rows
     without a country may stay uncoded) and ask whether to go on or to fix the file first.

5. **Code the file:** the same command without `--check-only`. Read the log again.

6. **Report**: how many rows were coded and how many were not, and why (the log's `coding_status` lines; their
   meaning is in `README.md`, "What `coding_status` means"), and where the coded copy is (`<file>_coded.xlsx`, beside
   their file, which is not changed).

7. **The list of new answers**, only if the log names one (`unmapped_institutions_<date>_<file>.xlsx`):
   - Show the person the answers on it and ask: "Is any of these the name of a person rather than of an
     organisation?" Delete the rows they name from the list. Change nothing else in it.
   - The key: if it is not saved yet (see "First time or not"), ask the person for the small key file the maintainer
     sent them, and save it: `python -m institution_mapping save-key "PATH TO THAT FILE"`. If they paste the key into
     the chat instead, save it by passing it on standard input (`... | python -m institution_mapping save-key`), and
     never repeat it, write it anywhere else or ask for it again. Either way, tell them it is saved and they will not
     need it again.
   - Send the list: `python -m institution_mapping submit "LIST FILE"`. Read the log again. Tell the person it was
     sent to the maintainer, who adds these answers to the next version of the mapping; once it is out, they can
     code the file again to get them. If it stopped, tell them what the `ERROR` line says in plain words (for
     example: the key has expired, ask the maintainer for a new one).

8. If a command fails with a message that is not in the log (a Python error), give the person the message as it is,
   and stop.
