# Changelog

What changed between versions of the mapping and of the code. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): newest first; each version says what was added, changed or
removed. Rule numbers refer to `RULEBOOK.md`; ledger IDs (`Dnnnnn`) to `coding/decisions.csv`. Paths in older entries are those of their day.

Version numbers: every release in which a row of the mapping is added or changes its coding gets the next whole
number (v24, v25, …). `output/` holds only the latest workbook, named with the date of its run; earlier versions are
in the git history.

## Unreleased

The published mapping is unchanged.

Added
- The client path (rulebook section 11): `python -m institution_mapping code-sheet FILE --column ...` checks a
  spreadsheet, then adds `canonical_name`, `institution_id`, `norhed` and `coding_status` to a copy of it from the
  published mapping, and lists the answers the mapping does not know in the format of the pipeline's batches, to go
  into `input/`. It makes no new code. A log beside the outputs tells the AI assistant what the checks found.
- Rule 11.5: NORHED is `yes` when the ID is on the NORHED partner list (`core/norhed.py`).
- `AGENTS.md`: the client path's instructions for an AI assistant, written for a client who knows nothing about
  the repository (the assistant downloads, installs and runs everything, and is brief with returning clients);
  `README.md`: the person's guide ("Two ways of working", "Coding your own spreadsheet"), and for the maintainer the
  email to a client.
- Rule 11.7: `submit` sends the list of new answers as a pull request that adds it to `input/`, with a key of the
  maintainer's limited to this repository; `save-key` saves the key once in the person's user folder. The client
  needs no GitHub account.
- `worklist OUT_DIR`: after a run, what became of the answers of the lists in `input/` (coded by rules, by a
  decision, searched before, left to search), and the answers to search with ROR candidates and groups, in one file
  that `tools/add_decisions.py` reads (it chains the three search tools).
- Rule 9.5: `judgement-calls OUT_DIR` drafts the list of judgement calls (acronyms, organisations abroad, organisations
  run by a church or an NGO, two organisations named). The operator AI goes through it with the person in the loop in
  the chat (`CLAUDE.md`, `HIL.md` step 4).
- `release` compares the new workbook with the published one: it stops if the version number does not fit what
  changed, writes `docs/releases/changes_log_vNN.csv` and moves the previous version's files to `archive/`.

- The client's whole session (rules 11.1, 11.8): in one session of the AI assistant the client chooses, the lookup codes
  what the mapping knows, the same session codes the rest with this repository's process (the run, `worklist`, web
  searches recorded with `tools/add_decisions.py --to`, the judgement calls decided by the client), codes the sheet
  again with its own run's mapping (`code-sheet --mapping`), and sends what it added. `AGENTS.md`, README and the email
  to clients describe it.
- Rule 9.6: a client session's decisions file, `input/decisions_<date>_<file>.csv`. A run applies the decisions files
  after the ledger; `take-in` moves them into `coding/decisions.csv` with the next D-numbers before a release, and
  `release` stops while one is waiting.
- Rule 11.7: `submit --run OUT_DIR` sends the list, the decisions file and the LOCAL IDs the session's run issued (added
  to the register), in one pull request. It sends nothing if the session issued LOCAL IDs and the published register
  changed since the session's copy was downloaded; two pull requests adding LOCAL IDs to the same register conflict.
- `tools/add_decisions.py`: `--to` (a session's decisions file), `override` as a ninth worksheet field, and the
  rationale types `client decision` and `human-review decision`. The judgement-call draft numbers its rows (`gid`), so
  the tool records the answers from it.
- Rule 9.5: judgement calls are put one answer per message, as a closed question: the code the rulebook gives, the
  rule it follows, how similar answers were coded before, and why consistency matters. A correction meant for every
  answer of its kind is a rule change, not a one-row decision. The draft gains the columns `rules` and `precedent`;
  `precedents OUT_DIR "answer" CC` shows the organisations an answer may name (with the answers coded to each), how
  answers sharing its words were coded, a person's earlier decisions on them, and the ROR links between them.
  `submit --note` passes a client's point on a rule to the maintainer.
- Rule 5.5: a university and its teaching hospital named together are coded as the teaching hospital (6.3): its own
  ROR record if it has one ("UoN / KNH" → Kenyatta National Hospital).
- `LICENSE` (MIT, the code) and README "Licence" (CC BY 4.0, the mapping data; ROR's data is CC0).
- `docs/trial_data.xlsx`: 20 made-up answers with the flaws of a real export, for trying the client path.

Changed
- The repository is public: `Walrus4990/institutions_mapping_public`, starting at v26 without the earlier history.
  Not published: the Moodle exports and the pipeline batch of 22 Oct (their answers are in the published mapping),
  and the v25 archive (QA report, notes to the pipeline team, judgement-call answers).
- Rule 1.4: the exports in `input/historical_exports/` are optional; without them, the published mapping carries
  every earlier answer, with its learners. A run without them gives the same mapping.
- The search tools' logic is in `search.py` (used by `worklist`); `tools/check_against_ledger.py`,
  `tools/ror_candidates.py` and `tools/group_uncoded.py` run it from the command line. Every tool has a `main()`,
  and `tools/reduce_ror_dump.py` takes the dump and the snapshot's name as arguments. Candidates with equal scores
  are listed in the order of their ROR IDs, so the list no longer changes between runs.

Removed
- Unused code (`table.read_mapping`, `table.ID_COLUMNS`, the snapshot tool's unused size options), the column
  `norhed_partner` from `tools/compare_workbooks.py` (dropped from the output in v23) and `requirements.txt` (the
  dependencies are in `pyproject.toml`).

Fixed
- `run --from-stage` kept the run's earlier copy of the decisions, so decisions recorded since the full run were not
  applied; every run now re-reads them.
- The command line writes UTF-8 on every system: on Windows, output captured by an AI assistant stopped at the first
  character the local encoding could not write.
- `tools/check_against_ledger.py` never marked an answer as needing a search: it looked for the old status label
  "uncoded".

## v26 – ROR and LOCAL used together; folders by role (26 Oct 2026)

6 rows differ from v25 (`docs/releases/changes_log_v26.csv`): 4 change their code, 2 only their rule code or
evidence text.

Added
- Rule 7.6: the ROR snapshot and the LOCAL register are used together. An answer that no rule and no person has
  decided, and that is the name of exactly one LOCAL ID in the learner's country, gets that ID. A LOCAL ID in use
  whose name is the name of exactly one ROR record in its country (the organisation has joined ROR) moves to that
  record and is retired, automatically. The run stops if the name fits several ROR records, or if a not-identified
  answer is the name of a LOCAL ID in its country (unless a person decided it is ambiguous).
- Rule 7.4: a LOCAL name never equals a ROR name in its country; the town is added when they share a name.
- `docs/TODO.md` item 3: the learner's city from the M&E pipeline, as evidence between same-name organisations.
- Rule 1.4: the published mapping is the record of every answer coded so far. The input of a run carries forward
  every answer of the published mapping that is no longer in the exports, so answers no longer drop out. An answer
  leaves the mapping only by a decision with the new target `REMOVE`.
- `python -m institution_mapping run OUT_DIR` builds the input and unzips ROR itself.

Fixed (found by rule 7.6)
- "Mater Misericordiae Hospital" (KE): LOCAL-0610, the hospital's ID in Kenya (it was left uncoded because ROR has
  the name only abroad).
- "Pharmacie Le Bon Samaritain" (RW): LOCAL-0884, like its two other spellings (ledger `D05638`).
- LOCAL-0859 and LOCAL-0868 were organisations in ROR: their rows go to Baba Saheb Ambedkar Education University
  (`03bw6pv11`) and WageIndicator Foundation (`02xs9jt02`), and the two IDs are retired (`D05640`, `D05641`).
- "St. Joseph's Institute of Management" (IN) stays not identified, now as ambiguous: two institutes share the name
  (`D05639`).

Changed: folders by role
- `input/`: the M&E pipeline's newest batch at the root; the Moodle exports in `input/historical_exports/`.
  `release` removes older batches (their answers are in the published mapping).
- `coding/`: `RULEBOOK.md`, `coding_rules.json` (was `data/rules/settings.json`), `decisions.csv` (was
  `data/rules/ledger.csv`) and `registries/`: the ROR snapshot (`ror/ror_v2.14_2026-10-06.zip`, was
  `data/external/ror/ror_small.zip`), the LOCAL register and the two tables that link codes.
- `docs/`: people only (TODO, code quality, `reference/norhed_partners_ror_matching.xlsx`, `releases/`).
- `archive/`: the previous version only (`v25/`); `data/`, `reports/` and `archive/v23/` are gone (in the git
  history). `extra_rows_v23.csv` retired: its 5 answers are carried forward by the published mapping.

## v25 – client review and rulebook (25 Oct 2026)

9 rows differ from v24 (`reports/changes_log_v25.csv`): 7 change their coding, 2 only their evidence text.

Changed
- `RULEBOOK.md` holds the rules only, each with the code that applies it (**Code:** lines; `tests/test_rulebook.py`
  checks the references both ways). The dated notes, version figures and the list of decisions it held are below,
  under the version they belong to.
- "United Methodist Church Sierra Leone" (SL): its own LOCAL ID instead of the US denomination's ROR record
  (client, ledger `D05637`).
- LOCAL-0494 ActionAid International is listed without a country in the register (an international organisation,
  rule 6.4); its rows are unchanged.

Fixed: the code now follows rules 4.1-4.2 itself, as the rulebook says
- Stage 4 typed roles, kinds and junk ("student", "other", "yes", "institution", "-", "test" …) NOT_APPLICABLE; the
  16 Oct re-check then made them NOT_SPECIFIED. Stage 4 now types them NOT_SPECIFIED (rule 4.2); bare country names
  too ("Cambodia" (KH) was NOT_APPLICABLE).
- A no-organisation sentence with a keyword ("I have no organization") was typed COMPANY_OR_NGO from the keyword;
  it is NOT_APPLICABLE (rule 4.1; 3 rows).
- "College of agriculture" is NOT_SPECIFIED by rule (4.2) instead of being left uncoded for a decision
  (`settings.json` `uncoded_no_search` removed).

Confirmed, unchanged: Caritas Kotido stays on the Catholic Diocese of Kotido (Caritas is a confederation; a
diocese's Caritas office is part of the diocese, 6.1); programmes run by a university or contractor abroad (e.g. the
Stellenbosch student network) stay on its record (6.1).

## Repository restructure (25 Oct 2026)

The code was reorganised to be easier to read and navigate. **The mapping is unchanged**: a run of the new code on
the v24 input reproduces every intermediate file and the delivered workbook of the old code cell for cell (the
workbook title now reads v24, as in the copy delivered by hand).

Changed
- Code: the `scripts/` folder (31 numbered scripts called by `run_all.sh`) became the package
  `src/institution_mapping/`: `core/` (text keys, ROR snapshot, ledger, LOCAL register, mapping helpers),
  `stages/` (one module per stage, named by what it does) and `stages/replay/` (the 16-17 Oct passes).
  `pipeline.py` lists the stages in order; `python -m institution_mapping run` runs them in one process.
- Duplicated code is shared: one function each for cleaning keys (`core/text.py`), the org_type of a ROR record
  (`core/org_types.py`), the ID columns of a row (`core/table.py`), reading a ledger batch (`core/ledger.py`) and
  reading the ROR snapshot (`core/ror.py`, read once per run instead of once per script). The three review passes
  share one function (`stages/replay/review.py`).
- Long scripts are split into functions and classes: the rules engine is a list of rules tried in order
  (`stages/rules_engine.py`); the decision applier, the finalise stage and the workbook are split into one function
  per rule (rule codes in `stages/rule_codes.py`).
- Data and documents by kind: `data/rules/` (ledger, LOCAL register, settings, networks, NGO parents),
  `data/raw/` (client exports with plain file names, pipeline feedback, extra rows), `data/external/ror/`,
  `docs/` (QA reports, the pipeline's notes), `reports/` (outcome lists), `tests/reference/`.
  `RULEBOOK_v24.md` is `RULEBOOK.md`; the version history is in this file instead of the README.
- Intermediate files: in `OUT_DIR/work/`, mappings named after the stage that wrote them
  (`mapping_08_typo_pass.csv` … `mapping_27_finalise.csv`); one `OUT_DIR/new_local_ids.csv` lists every LOCAL ID a
  run issued (was one file per stage).
- `tools/build_raw.py` is `python -m institution_mapping build-input`; copying the register, workbook and reference
  back after a run is `python -m institution_mapping release` (was by hand).
- Tests run with pytest (`tests/`); the workbook comparison is `tools/compare_workbooks.py`.
- Tools named by what they do: `tools/ror_candidates.py` (was `step17_candidates.py`), `tools/find_ror.py`
  (`rorfind.py`), `tools/reduce_ror_dump.py` (`ROR/ror_asia_africa.py`).

Fixed
- `tools/group_uncoded.py` found no rows in a final mapping: it looked for status `uncoded`, which the final
  mapping writes as `not identified` since v23.
- `tools/ror_candidates.py` needed the columns `row` and `priority` of an old worklist; they are now optional, so the
  not-identified rows of `mapping_final.csv` can be passed directly.

Quality: lint findings 672 → 0, docstring coverage 40 % → 100 %, the largest function from complexity 169 to 32
(`docs/qa/code_quality.md`).

Removed (unused; kept in the git history)
- The draft workbook written after assembly (`institution_mapping.xlsx`); the typo pass reads the same table from CSV.
- `step9_review_sheet.py` (review sheet of 15 Oct, no longer read), `step26_unmatched_list.py` (needed the client's
  list `ret.xlsx`, not in the repository), `tools/step6.py` (needed a file no step writes),
  `tools/step14_clusters.py` (replaced by `tools/group_uncoded.py`), `tools/report_coverage.py` (compared with v22).

## v24 – 25 Oct 2026

Added
- Input: `raw.csv` is built from the three client exports, every pipeline unmapped list and
  `data/raw/extra_rows_v23.csv` (the input of v23 was not in the repository). From the pipeline's lists only the
  answers that are new under the pipeline key are added: the pipeline normalises spellings when it looks them up,
  so other spellings need no row (and would count learners twice).
- Rule 6.7: an organisation run by an NGO keeps its own LOCAL ID; the NGO's ROR ID goes in `ror_parent_ids`
  (`data/rules/local_parents.csv`).
- Decisions of 25 Oct (ledger `D05005`-`D05636`): the 4 clashes the pipeline reported, the pipeline's new answers,
  QA corrections and the web searches of the whole search backlog (listed under v24 below).

Changed
- Rule 3.6 widened: answers are the same answer if they clean alike (step 1) OR have the same pipeline key
  (capitals, accents and punctuation ignored). The open spelling takes the code of its decided twin; the final
  check stops the run on a clash and lists the rows.
- A recorded decision for an answer that is not in the input is skipped and counted; v23 stopped the run.
- A decision recorded on a spelling that is not in the input applies to the same answer under the pipeline key.
- Rules 5.1/5.2: one-word and generic NGO/company names are not coded abroad unless the record is in
  `settings.json` `abroad_checked`; a spelling with learners in several countries is coded per country; a unique
  contained ROR name codes learners without a country.

Rulebook notes of v24 (moved from the rulebook)
- Figures: 11,163 rows (one per user-entered name and learner country), 22,086 learners, 167 learner countries;
  7 answers (7 learners) removed as personal data. Coded with a ROR ID 6,784 rows (16,665 learners), with a LOCAL ID
  1,692 (2,081), NOT_APPLICABLE 475 (920), NOT_SPECIFIED 487 (549), type only 81 (97), not identified 1,644
  (1,774). 2,512 ROR IDs and 1,280 LOCAL IDs in use; 219 ROR IDs (468 rows) have a parent, 4 LOCAL IDs (7 rows) carry
  their NGO's ID (6.7). All 11,041 v23 rows are in v24; 244 changed ID or status (`reports/changes_log_v24.csv`). Of
  the pipeline's 922 answers, 122 are new texts and 800 other spellings of answers in the exports; 888 are coding
  complete and 34 not identified (`reports/pipeline_unmapped_2026-10-22_outcome.csv`).
- `raw_institution`: spaces at the start and end are trimmed (the pipeline's lookup). The input adds only the
  pipeline answers that are new under the pipeline key (client, 25 Oct 2026).
- The rules engine checks rule 5.2: v23 had coded acronyms such as CHAM, TRA and IMDC to unrelated records abroad;
  they are recoded to the organisation in the learner's country or left uncoded. National ministries and agencies
  named without a country, which v23 left as "abroad", get the learner's own country's body (6.5). Four rows that
  the stricter check uncodes are kept by hand decision (EngenderHealth (ET), University of Medical Sciences and
  Technology (SA), International University of Africa (YE), University for Development Studies (GB)); "CSRS" (SN)
  is now uncoded. UNDP is an international organisation, like WHO and UNICEF.
- Rule 6.7 (client): Bharatpur, Mechi and Himalaya Eye Hospitals (Nepal Netra Jyoti Sangh, `00ck9qk95`) and
  Mildmay Uganda Hospital (Mildmay Uganda, `00xas1432`) keep their own LOCAL IDs, with the NGO in `ror_parent_ids`.
- The four clashes the pipeline reported: "St Anne's Community Hospital" (MW) is St. Anne's Community Hospital,
  Chilumba (LOCAL-0876; v23 had LOCAL-0238, another hospital); "Bharatpur Eye Hospital" (NP) keeps LOCAL-0833;
  "St. Xavier's College" (NP) and "Geospatial Research Forum (GRF)" (UG) follow their decided spellings.
- Other corrections: Bowen University Teaching Hospital has its own ROR record (6.3); SIDRA Institute is in ROR
  (`04trsx227`, LOCAL-1022 retired); TVET → NOT_SPECIFIED; Independent Electoral and Boundaries Commission (KE) →
  LOCAL ID; African Institute for Mathematical Sciences (GH) → AIMS Ghana; IITA without a country → the
  headquarters record; "Jimma" → NOT_SPECIFIED (a bare town name, as "Jigjiga"); a church ministry typed GOVERNMENT
  → COMPANY_OR_NGO. Departments named without a university stay NOT_SPECIFIED (client: merged with the NORHED row
  after the mapping).
- Search backlog: all 464 answers decided (ledger `D05166`–`D05393`, `D05398`, `D05402`–`D05636`): 152 LOCAL IDs,
  32 ROR IDs, 3 NOT_SPECIFIED, 277 not identified with the search result as evidence. Company groups and
  international churches and NGOs without an in-country record got the whole organisation's record (Samsung,
  Coca-Cola, BRAC, ByteDance for TikTok, CNOOC, the United Methodist Church). RP-Gishari (RW) → Rwanda Polytechnic –
  Gishari College; MoH Somaliland → one LOCAL ID (Somaliland like a state); Ligula Regional Referral Hospital (TZ)
  → LOCAL ID; "federal Teaching Hospital" (NG) → uncoded.

## v23 – 22 Oct 2026

Added
- Step 0: answers that are personal data (e-mail address, phone/ID/student number, document number) are removed in
  memory before any file is written; patterns in `settings.json` (`personal_data`); the run stops if any output cell
  matches. The 7 such answers and the 12 ledger rows about them were deleted from every file.
- Rule 3.6: answers that clean to the same text in the same country get the same code; rule 6.4: international
  organisations follow `international_networks.csv` (built by `tools/make_networks.py`).

Changed
- Input: all free-text sources in one `raw.csv` (column `source`; learners summed per name and country).
- Output columns: `ror_parent_ids` (ROR's own parent chains) instead of `norhed_partner`; status labels
  `coding complete` / `not identified`.
- Final check: the run stops if two answers with the same cleaned text and country have different codes.

Rulebook notes of v23 (moved from the rulebook)
- Step 0 (22 Oct 2026): on the exports of 21 Oct the three patterns caught exactly 7 answers (3 e-mails, 4 numbers),
  all in the custom profile field, and no organisation name. In v22 two of the e-mails had been coded from their
  domain (Universidad Nacional de Loja; an autism organisation in Nepal), 1 learner each; these codes were given up
  (removing is simpler and safer than keeping part of the address). The 7 answers were deleted from the mapping,
  `ledger.csv` (12 decision rows), the research log and every log, archive and test file. The pipeline applies the
  same patterns before it matches answers and before it writes its unmapped list (ADR institution_coding,
  decision 9).
- Status labels `coding complete` / `not identified` replace the v22 labels `final` / `uncoded` (pipeline note of
  22 Oct 2026); the code keeps the old labels inside. The column `norhed_partner` was dropped (ADR decision 3): the
  pipeline sets the NORHED flag from `institution_id` and `ror_parent_ids` (ADR decision 4); no parent is added to
  `ror_parent_ids` (decided 22 Oct 2026).
- Rule 6.4 rewritten (client, 22 Oct 2026): in-country record, else the record for the whole organisation, no added
  parents; CGIAR centres and company groups included; FAO is a UN body. National Red Cross and Red Crescent societies
  are independent organisations.
- Decisions of 21-22 Oct 2026: GIZ → GOVERNMENT, like USAID and Enabel; Consortium for Economic and Social Research,
  Museum and Institute of Zoology, KIT Royal Tropical Institute → RESEARCH; British Red Cross, Rotary International,
  Aga Khan Development Network → COMPANY_OR_NGO. Eight LOCAL IDs that had two org_types follow rule 3.3 point 4
  (`archive/v23/org_type_conflicts_v23.csv`); LOCAL-0207, LOCAL-0579 and LOCAL-0585 changed from RESEARCH to
  COMPANY_OR_NGO. Rows with only a fuzzy candidate on which a decision was recorded are left for client review
  (`archive/v23/review_suggested_rows_v23.csv`). "USAID Quality Healthcare Activity" (ET) → JSI. "National school of
  commerce and management" (MA, no city) → one LOCAL ID "Écoles Nationales de Commerce et de Gestion (ENCG),
  Morocco", a deliberate exception to rule 7.1 (12 separate schools; Settat and Tanger keep their own records when
  the city is named). Duplicate IDs merged: DI Skin Health and Referral Centre (NP) → LOCAL-0264; Asia Pacific
  Institute of Information Technology (LK) → LOCAL-0061; KAAF University (GH) → `03ykqg675`.

## v22 and earlier (13-21 Oct 2026)

The rules engine (13-15 Oct), the typo pass and the decision passes of 16-17 Oct, rule 3a (17 Oct) and the
decision applier (18 Oct). Their files are not in this repository, which starts at v26.

Rulebook notes (moved from the rulebook)
- Rule 3a (owner, not organisation) and the present rule 5.5 (two organisations named) were added on 17 Oct 2026 and
  apply from v21; 5.5 replaced the earlier employer and ministry exceptions. "MINISTRY OF HEALTH- Addis Ababa
  University" (ET), earlier coded to the Federal Ministry of Health, follows rules 3a and 5.5 → Addis Ababa
  University `038b8e254`.
- Human-review case decisions of 17 Oct 2026: "Broward County" (US) → NOT_SPECIFIED; "Mechi Eye Hospital" (NP) → its
  own LOCAL ID; "Northeastern University" (CA) → Northeastern University in the United States (`04t5xt781`).
- Client decisions for named organisations (14-19 Oct 2026; ledger, or `settings.json` where they apply to a whole
  country or everywhere): UNISA also for learners in Eswatini; USIU-Africa (RW) → `05qj64q37`; Vietnam National
  University (VN) → `02jmfj006`; Aga Khan University: Uganda → uncoded, Kenya → "Aga Khan University Nairobi";
  Jhpiego (NG) → `038wq4t12`; HealthNet TPO (AF) → `0088fqs38`, COMPANY_OR_NGO; Ministry of Health Sri Lanka →
  `054pkye94`; Colegio Médico de Honduras → LOCAL ID, COMPANY_OR_NGO; WorldQuant University → WorldQuant
  Foundation's `057ftxp55`, named "WorldQuant University"; NHS bodies (GB) → National Health Service `02wnqcb97`;
  APHRC (KE) `032ztsj35` → RESEARCH (19 Oct; its ROR type healthcare would give HOSPITAL).
- A close spelling on which a decision was recorded is left for client review (decided 21 Oct 2026).
