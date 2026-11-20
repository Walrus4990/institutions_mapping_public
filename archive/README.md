# archive/

Kept for history only. Nothing here is read by the code.

Rule: the repository keeps the current version and the one before it. At each release, `release` moves the previous
version's changes log (`docs/releases/changes_log_vNN.csv`) and judgement-call list (`docs/qa/codes_to_check_vNN.csv`)
to `archive/vNN/`, and older archive folders to `archive/old/`, which is git-ignored.

| Folder | What it holds |
|---|---|
| `vNN/` | the release files of the previous version (none yet: the first release after v26 fills it) |
