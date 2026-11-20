# Institution name mapping – rulebook

This rulebook states the rules that turn each user-entered institution name into one row of the mapping. It holds
rules only: what changed when, and the figures of each version, are in `CHANGELOG.md`.

Every rule names the code that applies it (**Code:**, a module of `src/institution_mapping/`). Some rules need a
person's judgement, such as a web search or a choice between candidates. For those, the person records the decision
in `coding/decisions.csv` with its rationale, and the code applies the recorded decision (**Decided by:** a
person, step 7). `tests/test_rulebook.py` checks that every **Code:** reference exists and that every rulebook
section the code cites exists here.

## 1. Purpose and principle

1.1 Every answer from the free-text sources gets one row per user-entered name and learner country, with exactly one
outcome: a ROR ID, a LOCAL ID, NOT_APPLICABLE, NOT_SPECIFIED, type only, or not identified.

1.2 A wrong ID is worse than no ID. IF no rule identifies the organisation safely THEN the row is not identified,
with the reason in `evidence`.

1.3 The same input and the same files in `coding/` always give the same output. Code: `pipeline.py`.

1.4 **The published mapping is the record of every answer coded so far.** The input of a run is: the exports in
`input/historical_exports/`, if any (all three, or none); every answer of the published mapping in `output/` that is
not in them (with its
learners), so that no answer drops out when an export no longer holds it; and the batches at the root of `input/`
(the M&E pipeline's, and the lists of the client path, 11.6), of which only the answers new under the pipeline key
(3.6) are added. An answer leaves the mapping
only by a recorded decision with target `REMOVE` (9.2). Code: `build_input.py`.

## 2. Terms

| Term | Meaning |
| --- | --- |
| user-entered name | The answer as the learner typed it (column `raw_institution`). |
| learner's country | The country the learner gave (column `country`, ISO 2-letter code). Empty if not given. |
| ROR | Research Organization Registry, the reference database of organisations. The snapshot used is `coding/registries/ror/ror_v2.14_2026-10-06.zip`. |
| ROR record | One organisation in ROR. Only active records are coded. |
| ROR ID | The 9-character identifier of a ROR record (e.g. `01r22mr83`). |
| ROR name | The display name of a ROR record. ROR also stores labels (other languages), aliases and acronyms. |
| LOCAL ID | An identifier `LOCAL-nnnn` for an organisation that exists but has no ROR record (section 7). |
| coded name | The name written in column `canonical_name`. |
| parent | The organisation a unit belongs to (the university of a faculty, the ministry of a department). |
| cleaned text | The answer after step 1. |
| pipeline key | The answer after the pipeline's lookup normalisation (3.6). |
| international organisation | An organisation with ROR records in several countries: an international NGO network, a UN or other intergovernmental body, a CGIAR research centre or a company group (6.4). |
| personal data | An e-mail address, or a phone, ID, passport or student number, given as the answer (step 0). |
| ledger | `coding/decisions.csv`: every decision taken by a person, each with its rationale (section 9). |

## 3. Output

### 3.1 File and sheets
The deliverable is `institution_mapping_YYYY-MM-DD.xlsx`. The pipeline reads its `mapping` sheet. Code:
`stages/workbook.py`.

| Sheet | Content |
| --- | --- |
| read me | Outcome counts (formulas over the `mapping` sheet), what each column means (marking the columns the pipeline reads), the org_type and rule-code lists. |
| mapping | One row per user-entered name and learner's country; columns in 3.2. |
| organisations | One row per ROR ID or LOCAL ID used: the shortest coded name, the other coded names on the ID, org_type, learners, number of user-entered names, learners' countries, ROR parent IDs. |
| local IDs | Every LOCAL ID in use: name, organisation's country (empty for an international organisation or where not recorded), the source that confirms it exists. |
| retired local IDs | LOCAL IDs no longer used, what replaced them and why. |
| research log | Every ledger decision, one row each, with what it rests on (`rationale_type`). |

### 3.2 Columns of the `mapping` sheet
Column names do not change. Columns marked **P** are read by the pipeline. Code: `stages/finalise.py`.

| Column | P | Content |
| --- | --- | --- |
| `raw_institution` | P | The user-entered name as typed, with spaces at the start and end trimmed; answers that differ only by those spaces are one row. Capitals, inner spaces and punctuation are kept. Each `raw_institution` + `country` pair appears once. |
| `country` | P | The learner's country as given; empty if not given. Never changed. |
| `learners` | | Number of learners who typed this user-entered name in this country (summed over all sources). |
| `canonical_name` | P | The coded name (section 8). Empty for NOT_APPLICABLE, NOT_SPECIFIED and type-only rows. |
| `institution_id` | P | ROR ID or LOCAL ID. Empty for every other outcome. |
| `id_kind` | | `ROR`, `LOCAL`, or empty. |
| `ror_url` | | `https://ror.org/<ROR ID>` for a ROR ID, otherwise empty. |
| `ror_parent_ids` | P | Every ROR parent of the row's ROR record as recorded in ROR, followed upwards: each chain from the nearest parent to the top, IDs separated by `/`; one chain per parent, chains separated by `\|`. Empty IF the row has no ROR ID or ROR lists no parent. No parent is added, with one exception: an organisation run by an NGO (6.7). |
| `org_type` | P | Kind of organisation (3.3). |
| `status` | P | `coding complete` or `not identified` (3.4). |
| `rule` | | Rule code (3.5). |
| `rule_description` | | The rule code in words. |
| `evidence` | | What the decision rests on: the match found, the source, or the reason the row is not identified. |

### 3.3 org_type
| Label | Used for |
| --- | --- |
| EDUCATION | University, college, polytechnic, school or other teaching institution. |
| TEACHING_HOSPITAL | Teaching hospital of a university or medical college (6.3). |
| HOSPITAL | Hospital, clinic or health centre that is not a teaching hospital. |
| RESEARCH | Research institute or centre that is not part of a university. |
| GOVERNMENT | Ministry, government agency, regulator, statutory board or commission, local government, intergovernmental body. |
| COMPANY_OR_NGO | Company, NGO, foundation, association, professional society, church or other non-governmental organisation. |
| NOT_APPLICABLE | The person has no organisation (4.1). |
| NOT_SPECIFIED | The person has an organisation, but the answer does not name it (4.2). |
| (empty) | Only on a not-identified row whose name does not show the kind of organisation. |

How org_type is set, first match wins:
1. A teaching-hospital row (6.3) → TEACHING_HOSPITAL.
2. An org_type recorded by a person for the ID (ledger batches `org_type` and `org_type_17oct`, or `coding_rules.json`
   `org_type_overrides`) → that type.
3. A ROR ID → the first type on the ROR record that maps: education → EDUCATION; healthcare → HOSPITAL; government
   → GOVERNMENT; facility → RESEARCH; nonprofit or company → COMPANY_OR_NGO. IF none maps (only other, funder,
   archive) THEN from the name by the keyword list of point 5. A hospital record coded under a name that says
   "teaching hospital" → TEACHING_HOSPITAL.
4. A LOCAL ID without a recorded type → from its name, first match: university, université, universidad, college,
   polytechnic, institute of technology, school, academy, lycée, liceo, pesantren → EDUCATION; hospital, hôpital,
   rumah sakit, clinic, medical centre, eye centre, treatment centre, ear care, fistula → HOSPITAL; ministry,
   ministère, department, government, commission, authority, agency, board, badan, direction, judicial,
   coordinating mechanism → GOVERNMENT; research, recherche, investigación → RESEARCH; otherwise COMPANY_OR_NGO.
5. A not-identified row → from the name by the keyword list in `coding_rules.json` (`name_keywords`, first match:
   teaching hospital; management board, health service commission, ministry; hospital, clinic, medical centre,
   health centre, cancer centre; ministry, authority, agency, council, commission, government, board, bureau,
   department, directorate, district health, health office, county, municipal, local government; university,
   college, polytechnic, school, academy, faculty, seminary; research, institute, laboratory, observatory, centre
   for; ltd, limited, foundation, association, ngo, society, trust, network, initiative, consult, company,
   corporation, innovations, systems, group, colegio); otherwise empty.
6. One organisation, one org_type: every row of an ID carries the same org_type, except teaching-hospital rows.
   IF two rows of one ID still differ, or a coded row has no org_type, THEN the run stops.

Code: `core/org_types.py` (points 3-4), `stages/common_rules.py` (point 5), `stages/finalise.py` (points 2 and 6).

### 3.4 status
Exactly two values. Code: `stages/finalise.py`.

| Value | Meaning |
| --- | --- |
| `coding complete` | The row is decided: a ROR ID or LOCAL ID, or NOT_APPLICABLE, NOT_SPECIFIED or type only. |
| `not identified` | The answer names an organisation, but no rule identifies it safely. No ID; the coded name is the tidied answer (8.3); the reason is in `evidence`. |

IF any other value would be written THEN the run stops.

### 3.5 Rule codes
Each row gets one code. A code recorded with a decision (or by rule 3a) is used as recorded; otherwise the code is
derived from how the row was decided. Code: `stages/rule_codes.py`.

| Code | status | Meaning |
| --- | --- | --- |
| ROR-EXACT | coding complete | The answer equals a ROR name, label or alias (step 2). |
| ROR-CONTAINED | coding complete | A ROR name is contained in the answer (step 3, step 5 B-C). |
| ROR-ACRONYM | coding complete | The answer is the ROR acronym of a record in the learner's country (step 3). |
| ROR-TYPO | coding complete | A typo or close spelling of a ROR name in the learner's country (step 5 A, D). |
| ROR-UNIQUE | coding complete | The only ROR record worldwide with this name (step 6), or the words of one ROR name in another order (step 5 E). |
| ROR-ROLLUP | coding complete | The ROR ID of the parent or of the organisation as a whole: unit, campus, teaching hospital, country office, ministry department (section 6). |
| ROR-SEARCH | coding complete | A ROR ID found by review or web search (step 7). |
| ROR-CLIENT | coding complete | A ROR ID set by a client or reviewer decision, or by a setting (section 10). |
| LOCAL | coding complete | A LOCAL ID (section 7). |
| LOCAL-ROLLUP | coding complete | The LOCAL ID of the parent (section 6). |
| NA | coding complete | NOT_APPLICABLE (4.1). |
| NS | coding complete | NOT_SPECIFIED (4.2). |
| TYPE | coding complete | Type only (4.3). |
| UNC-ABROAD | not identified | The name matches a ROR record only in another country, and section 5 does not allow it. |
| UNC-AMBIGUOUS | not identified | Several organisations fit, the acronym is shared, or two organisations are named and none can be chosen (5.5). |
| UNC-NOTFOUND | not identified | The organisation could not be found or its existence could not be confirmed. |

### 3.6 Same answer, same code
Two answers with the same learner's country are the same answer IF
- their cleaned text (step 1) is the same; OR
- their pipeline key is the same. The pipeline key: (1) lower case; (2) accents removed; (3) these characters
  removed, not replaced by a space: `. , ; : ' " ! ? ( ) [ ] { } / \ - _ @ # $ % ^ & * + = < > | ~` and the backtick;
  (4) spaces trimmed and runs of spaces cut to one. "St. Xavier's College" and "st xaviers college" have the key
  `st xaviers college`.

A chain of such pairs is one group. The answers stay separate rows and carry the same code:
- IF the decided rows of a group agree on one ID (or, without an ID, on one org_type) AND other rows of the group
  are still open (not identified, or only a suggestion) THEN the open rows take the outcome of the decided row with
  the most learners; the evidence names the answer they follow.
- A decision recorded for a spelling that is not in the input applies to the row with the same pipeline key and
  country, IF that row is still open (9.3).
- IF two answers of one group end with a different ID or status, or (when decided) a different org_type, THEN the
  run stops and lists them; a recorded decision resolves them. The org_type of a not-identified row is not compared.

Code: `core/text.py` (`pipeline_key`, `same_answer_groups`), `stages/apply_decisions.py` (`code_same_answers`),
`stages/finalise.py` (the check).

## 4. How a user-entered name is decided

The steps run in this order; the first step that decides a row ends it. Steps 2-6 decide by rule. Step 7 is a
person's decision, applied by the code.

**Step 0 – Remove personal data.** Runs on the answers as read, before any other step and before anything is
written. The answer is removed IF
- it contains an e-mail address (`text@domain.tld`); OR
- it consists only of digits and separators (space, `+`, `-`, `.`, `/`, brackets) AND has 6 or more digits; OR
- it is 1-3 letters followed by 6 or more digits (a passport or document number).

A removed answer gets no row and appears in no file; the run reports only how many were removed. It is not coded,
even when an e-mail's domain would identify the organisation. Numbers inside a name are not affected, because the
whole answer must match ("21 September University", "461 NAF Hospital" stay). People's names are not removed: they
cannot be told apart from organisations named after people. The patterns are `coding_rules.json` `personal_data`, the
same as the pipeline's. Code: `stages/prepare.py`, `core/personal_data.py`.

**Step 1 – Clean.** HTML decoded, `&` → "and", spaces collapsed, dots, commas and spaces at the end dropped, lower
case, accents removed. Punctuation inside the text is kept. The cleaned text is used for matching only;
`raw_institution` keeps the answer as typed. Code: `core/text.py` (`clean`), `stages/prepare.py`.

**Step 2 – Exact ROR name.** IF the cleaned text equals an official name (display name or label) of a ROR record,
or, when no official name matches, an alias, THEN that record. An inactive record with exactly one active successor
is replaced by the successor; otherwise an inactive record is not used.
- One record has the name: IF the record is in the learner's country, or the learner gave no country, THEN that
  record. Learners in other countries get it only IF the name is specific (5.2); otherwise their rows go on to the
  next steps.
- Several records have the name: each learner country gets the one record in that country; a country with none
  or several goes on to the next steps (5.1, 5.4).

Code: `stages/exact_names.py`.

**Step 3 – Contained name or acronym.**
- Contained name. IF a ROR name (display name or label) of 2 or more words stands in the cleaned text as words of
  its own (not joined to other name words) THEN the longest such name decides: the record with that name in the
  learner's country; for a learner without a country, the only record in the world with that name. A name made only
  of generic words counts only when it stands apart from the rest by punctuation. The row goes on to the next steps
  (to be decided by a later rule or a person) IF the text names more than one institution, OR the name has several
  records in the country, OR the name belongs to records that differ only by their city and the text names none of
  these cities, OR the text says "hospital" and the record is not a healthcare record (6.3), OR the learners are in
  several countries and the name exists elsewhere too.
- A unit and its parent. IF the record found by step 2 or 3 is a unit (not itself a university or hospital record)
  whose one active parent is a university THEN the parent university (6.1). IF the text names a unit and its parent
  university as two names THEN it names one institution, the parent.
- Acronym. IF the whole answer (letters and digits, up to 8 characters when it has spaces) is the ROR acronym of
  exactly one record in the learner's country THEN that record; per country when the learners are in several.
- A contained match is rejected (the row is not identified) IF the ROR name is only part of another proper name in
  the text, or the text names an affiliated college.

Code: `stages/contained_names.py`, `stages/assemble.py` (the rejection).

**Rule 3a – Owner, not organisation.** IF a row is coded to a government body (org_type GOVERNMENT, its coded name
naming a ministry, a government, a state, county or local government, or a district council) AND the rest of the
answer, without that body's name, country names and linking words, names an institution (university, college,
polytechnic, academy, school, institute, hospital, clinic) THEN the government body is the institution's owner and
is not used:
- IF the rest of the answer equals, or contains as words of its own, the name (2+ words) of exactly one ROR record
  in the learner's country (not a government record) THEN that record (rule code ROR-EXACT or ROR-CONTAINED);
- OTHERWISE the row is released (not identified, UNC-NOTFOUND) and is decided by step 7.

Departments, directorates, divisions, units, programmes, services and laboratories of a ministry are not
institutions: they still roll up to the ministry (6.5). Code: `stages/owner_rule.py`.

**Step 4 – No organisation, unnamed organisation, type only.**

4.1 **NOT_APPLICABLE.** IF the answer says the person has no organisation THEN org_type NOT_APPLICABLE, no ID, no
coded name. These are: the listed phrases (none, n/a, nil, no, nothing, no affiliation, not affiliated,
self-employed, freelance, independent researcher or consultant, consultant, private practice, petty business,
unemployed, retired, job seeker and the like, in several languages: `stages/non_institutions.py` `NA_EXACT`,
`NA_PATTERNS`); the answers a person judged so (ledger batch `na_judged_13oct`); sentences such as "I am not in an
institution" or "I have no organisation" (`coding_rules.json` `not_applicable_patterns`); and an answer without an ID
that contains "not affiliated", "no affiliation" or "unaffiliated". A keyword in such an answer ("organization")
does not give it a type. A real organisation is never NOT_APPLICABLE. Code: `stages/non_institutions.py`
(`classify`), `stages/rules_engine.py` (`generic_answers`, `decide_all`), `stages/finalise.py` (`open_rows`).

4.2 **NOT_SPECIFIED.** IF the answer implies an organisation but does not name it THEN org_type NOT_SPECIFIED, no
ID, no coded name. These are: the listed answers (roles such as student and scholar; kinds such as institution,
organization, research, public, private, academic; "other", "yes", "unsure", "confidential", "not available"; codes
and junk such as "x", "test", "gg": `stages/non_institutions.py` `NS_EXACT`, and `coding_rules.json` `generic_exact`:
university, education, school, faculty of science and the like, TVET, college of agriculture …); an answer of
punctuation or digits only (`NS_PATTERNS`); a bare country name. A person decides the same for other roles,
sectors, bare place names, people's names, and faculty or department names without their university (step 7).
Code: `stages/non_institutions.py` (`classify`), `stages/rules_engine.py` (`generic_exact`).

4.3 **Type only.** IF the answer is only a kind of organisation (hospital, private, public, government or general
hospital, teaching hospital, government, gov, govt, NGO, pharmacy, consultancy: `coding_rules.json`
`generic_keep_type_no_name`) THEN no ID, no coded name, org_type = that kind, rule TYPE. A named organisation that
is not an academic institution gets its type from the keyword list (3.3 point 5) and goes on to step 5, unless ROR
may hold it (its acronym, or all its distinctive words in a ROR name of the learner's country); IF no later step
identifies it THEN it is not identified with that type. Code: `stages/non_institutions.py` (`classify`,
`RorGuard`), `stages/rules_engine.py` (`generic_answers`, `decide_all`), `stages/assemble.py`.

**Step 5 – Rules for the remaining spellings (rules engine and typo pass).** Applied to rows not yet decided, in this
order. Code: `stages/rules_engine.py` (`Engine.RULES`, in this order), `stages/typo_pass.py`,
`stages/replay/word_order.py`.
1. Named organisation clusters: the spellings of one organisation listed in `coding_rules.json` `name_clusters` get its
   ROR record, or its LOCAL ID (section 7).
2. A ministry of health named without its country → the learner's country's ministry (6.5).
3. An NHS body named by a learner in the United Kingdom → National Health Service (10.1).
4. A teaching hospital → its own ROR record, else its university's record (6.3).
5. The research recorded for the spelling on 14-15 Oct 2026 (ledger batches `research_14oct`, `deepdive_15oct`): a
   ROR record (used IF 5.2 allows it in the learner's country, else the in-country alternative of 5.1, else not
   identified); a confirmed organisation not in ROR (a LOCAL ID, section 7); a type or a name only; a candidate
   (a suggestion, point 9).
6. A unit of a university ("<unit>, <university>"): one part of the answer is exactly one university in the
   learner's country and the other parts are unit words or countries → the university (6.1).
7. The cleaned text (or, for one word of 2-8 letters, the acronym) is a ROR name: decided by the country rules
   (5.1-5.2, 5.4). IF the only records are government records abroad THEN the learner's own country's body (6.5).
8. A branch: "<shared name> <place>" names one of several in-country records with that name by its city (5.1).
9. Word coverage and close spelling: exactly one in-country fuzzy candidate holds every word of the answer, or a clear
   fuzzy candidate (score ≥ 90, 5 points ahead) holds a close match of every distinctive word → a suggestion only
   (status not identified; the candidate is kept in the evidence for step 7).
10. Typo pass, learner's country only, on rows still open (not on rows left uncoded on purpose by 5.1-5.2):
   - A: after removing punctuation and correcting misspelt generic words (univeristy, collage, institue …) the text
     equals a ROR name (display, label, alias or the part before the first comma) or an answer already coded; also
     compared with spaces removed ("Leadcity" = "Lead City").
   - B: one part of the text (split at , ; / ( ) | - "at") is such a name, and the other parts are only unit words,
     the record's own city or the country.
   - C: a ROR name of 2+ words sits inside the text, preceded only by unit words and followed only by places or unit
     words.
   - D: close spelling with a score ≥ 92, at least 5 points ahead of the next record, every distinctive word matched
     both ways; not IF the text names a place that is not the record's own.
   - A suggestion (point 9) is confirmed only when the typo pass lands on the suggested record. A hospital or clinic
     answer is never coded to a non-hospital record. An NHS body becomes the National Health Service (10.1).
11. Word order (E): the words of the answer, typos corrected and small words ignored, are exactly the words of one
    ROR name in the learner's country ("Bonn University" = "University of Bonn").

A suggestion that no rule confirms is not a decision: the row is not identified, the candidate in its evidence.

**Step 6 – Unique name anywhere in the world.** IF the answer (typos of generic words corrected; also without
brackets, or without a trailing country or city) equals the display name, a label, or the part before a comma of
exactly one active ROR record worldwide, OR (for a university or college) has exactly the words of one record's
display name, AND the name has 2 or more words and is specific (5.2), THEN that record, wherever it is. Not used for
records in the learner's own country (steps 2-5 decide those), for government bodies (6.5), or for names a person
recorded as not unique in the country (ledger batch `not_unique_16oct`). The same test codes a not-identified answer
to a LOCAL ID whose name it is, when that name belongs to one LOCAL ID only. Code: `stages/replay/unique_names.py`.

**Step 7 – Review and web search (decided by a person).** A row not decided by steps 0-6, and not left uncoded on
purpose by a rule (5.1-5.2), is searched on the web as "learner's country + user-entered name", after checking the
decisions already recorded for the same answer (3.6), so that no search is repeated. The result is recorded in the
ledger (section 9) and applied by the code:
- IF the organisation is in ROR (also under a former name, a typo, or as a unit of a ROR record) THEN its ROR ID, or
  its parent's (section 6).
- ELSE IF the organisation is confirmed to exist (its own website, an official register, a reliable news or
  reference page) THEN a LOCAL ID (section 7).
- ELSE IF the answer is only a type, a role or a sector THEN step 4.
- OTHERWISE not identified, with the reason: not found; not confirmed; several candidates; acronym shared by several
  bodies; two organisations named and none chosen (5.5); a project rather than an organisation; a name that does not
  exist as given.

Code: `stages/apply_decisions.py`; the decision passes of 16-17 Oct 2026 are applied by `stages/replay/`.
Helpers for the search: `tools/check_against_ledger.py`, `tools/ror_candidates.py`, `tools/group_uncoded.py`.

**Step 8 – Final rules and checks.** Run on the whole mapping. Code: `stages/finalise.py`, `stages/workbook.py`.
1. One org_type per organisation (3.3 point 6).
2. Coded names (section 8).
3. ROR parents (3.2, 6.7).
4. Rule codes and evidence (3.5).
5. The run stops IF a row breaks one of: a rule code outside 3.5; a not-identified row without an UNC code, or an
   UNC code on a decided row; an ID without a ROR or LOCAL code, or such a code without an ID; a ROR code on a LOCAL
   ID or the reverse; `id_kind` or `ror_url` not matching the ID; a coded name on a NOT_APPLICABLE, NOT_SPECIFIED or
   type-only row; two answers of one group (3.6) with different codes; a LOCAL ID whose name is the name of a
   ROR record in its country, or a not-identified answer that is the name of a LOCAL ID in its country (7.6).
6. Personal data: the step 0 patterns run again on every text cell of the mapping and of every sheet (ROR IDs,
   LOCAL IDs and dates excepted); IF any matches THEN the run stops.

## 5. Country rules: which record, and when an answer is coded abroad

5.1 **Default.** Matching looks for the record in the learner's country first.
- IF exactly one matching record is in the learner's country THEN that record.
- ELSE IF several are: IF the answer names the branch's city THEN that record; ELSE IF one of them is the parent of
  the others (the headquarters) THEN the headquarters; OTHERWISE not identified.
- ELSE (no matching record in the learner's country) a record abroad is used only IF 5.2 allows it; OTHERWISE the
  best fuzzy candidate in the learner's country scoring 85 or more, if any; OTHERWISE not identified (UNC-ABROAD).
- A learner without a country: a name held by exactly one record in the world codes the row. An international
  organisation (6.4) named without a country gets the record for the whole organisation.
- A spelling with learners in several countries is decided per country.

Code: `stages/exact_names.py`, `stages/contained_names.py`, `stages/rules_engine.py` (`exact_name`,
`headquarters`, `branch`, `in_country_alt`).

5.2 **When a record abroad is used.** IF one of these holds:
- **Specific unique name:** the name belongs to exactly one active ROR record worldwide (step 6) AND it is specific:
  it has a word that is not generic or descriptive (a place, a person, a coined name). NOT specific: one-word
  answers; names made only of generic and descriptive words ("College of Agriculture", "European University",
  "Southwest University"). The word lists are `core/text.py` `SPECIFIC_GENERIC`, `SPECIFIC_DESCRIPTIVE`, and
  `NGO_GENERIC` for NGO and company names (association, foundation, society, network, services, company …).
- **International organisation:** a record listed in `coding_rules.json` `international` (intergovernmental bodies,
  online universities, named NGOs), or a ROR nonprofit or company record that is not also an education or
  healthcare record, followed by 6.4.
- **Country exception:** a record that `coding_rules.json` `country_exceptions` allows for the learner's country (10.1).
- **Recorded decision:** a decision whose rationale cites rule 5.2 (step 7).

Never abroad, whatever the name: a close spelling (step 5 is in-country only); a one-word answer (acronym, short
name) or a generic name coded to an NGO or company record, unless that record was checked by a person
(`coding_rules.json` `abroad_checked`); a government body (an answer naming a ministry or agency without a country
means the learner's own country's body, 6.5). Code: `core/text.py` (`specific`), `stages/rules_engine.py`
(`allowed`, `checked_abroad`, `exact_name`), `stages/apply_decisions.py` (`ror_outcome`).

5.3 **Same-name institution in the learner's country (decided by a person).** IF the answer matches a ROR record
abroad AND an institution of that name exists in the learner's country THEN the in-country institution (its ROR
ID, or its LOCAL ID). IF several institutions of that name exist there THEN not identified. Code:
`stages/replay/review_17oct.py`, `stages/apply_decisions.py`.

5.4 **Shared ROR name.** A name held by 2 or more ROR records (Aga Khan University, "National University"): the
record in the learner's country (5.1); OTHERWISE not identified. International organisations follow 6.4. Code:
`stages/exact_names.py`, `stages/rules_engine.py` (`exact_name`).

5.5 **Two or more organisations named (decided by a person).** "X / Y", "X and Y", "X, Y": the code sends such an
answer to step 7 (step 3). Not covered, because it is one organisation: one name is a unit, campus or programme of
the other (6.1-6.2), its teaching hospital (6.3), or a country office of its network (6.4). Otherwise each named
organisation is identified on its own; the candidates are those that get an ID. These tests run in order; each
keeps the candidates that pass it, and IF none pass, all go on to the next test; the row is decided as soon as one
candidate is left:
1. IF no candidate THEN not identified (UNC-AMBIGUOUS); IF one THEN that one.
2. NORHED partners (the partner list in `core/norhed.py`).
3. org_type EDUCATION.
4. In the learner's country (a learner without a country: all pass).
5. With a ROR ID.
6. The one named first.

Evidence: "two organisations named; coded X (<the test that decided>); not coded: Y". Code:
`stages/contained_names.py` (sends the answer to step 7), `stages/apply_decisions.py`.

## 6. Parents and units

6.1 **Units roll up.** Departments, faculties, schools, institutes, centres, research groups, laboratories, student
clubs and associations of an organisation get the parent's ID and the parent's coded name. A ROR record that is a
unit of one university (its one active parent) rolls up to the university (step 3). Programmes, journals,
centres and hubs are coded to the organisation that runs them, also when it is in another country. Code:
`stages/contained_names.py` (`parent_uni`), `stages/rules_engine.py` (`unit_of_university`),
`stages/assemble.py`; other units are decided by a person (step 7).

6.2 **Campuses and colleges in another town** keep their name on the parent's ID: "<ROR name> – <Town>
College/Campus" (e.g. "Rwanda Polytechnic – Musanze College"). The town is a city of a ROR record in the country, or
one of `coding_rules.json` `known_places`, and not the parent's own city; a campus in the parent's own town rolls up
(6.1). A university's branch campus in another country is its own institution (its own ROR record or LOCAL ID).
Code: `stages/assemble.py` (`unit_name`).

6.3 **Teaching hospitals.**
- IF the teaching hospital has its own ROR record (a healthcare record with its name in the learner's country, or
  one a person recorded: ledger batch `own_teaching_hospital_17oct`) THEN that record and its ROR name.
- ELSE IF it is named after a university or medical college of the learner's country THEN the university's ID,
  coded name "<ROR name of the university> Teaching Hospital" (with the university's city when the name is shared),
  org_type TEACHING_HOSPITAL.
- ELSE its own LOCAL ID (section 7), decided by a person.

Code: `stages/rules_engine.py` (`teaching_hospital`), `stages/finalise.py` (`teaching_hospitals`).

6.4 **International organisations.** An international NGO network, UN or other intergovernmental body, CGIAR
research centre or company group with ROR records in several countries. For an answer naming the organisation, one
of its country offices or one of its programmes:
- IF ROR has a record of it in the learner's country THEN that record; IF several there THEN 5.1 decides; the record
  already chosen stays when it is in the learner's country.
- OTHERWISE the record that stands for the whole organisation: its headquarters' record; IF the headquarters has no
  ROR record THEN the record of its main member; a record that carries the organisation's global website counts as
  the headquarters' record.
- IF ROR has no record for the organisation at all THEN one LOCAL ID for the whole organisation, in every country
  (7.3).
- No parent is added (3.2).
- The records of each organisation and the record that stands for it are listed, with the reason, in
  `coding/registries/international_networks.csv` (built by `tools/make_networks.py`); an organisation not in the list is
  decided the same way by a person (step 7).
- Not one organisation, so not covered: national Red Cross and Red Crescent societies (each its own ID); a
  separately registered national affiliate without its own ROR record (its own LOCAL ID).

Code: `stages/apply_decisions.py` (`roll_up_networks`).

6.5 **Ministries and government.**
- One ID per ministry per country: its ROR record in that country, else one LOCAL ID ("Ministry of <portfolio>,
  <country>"). A ministry of health named without its country gets the learner's country's ministry by rule; other
  ministries are decided by a person. The ROR name is kept when the ministry has been renamed.
- Same ministry = same country and same main portfolio; spelling, language, additions, renaming, merging or splitting
  do not make a new ministry.
- Departments, directorates, programmes and laboratories of a ministry roll up to it (6.1, rule 3a).
- State and provincial ministries are separate organisations, one ID each; Somaliland is treated as a state.
- Statutory agencies, regulators, commissions, boards, councils and local governments are organisations in their own
  right, one ID each. Central banks follow the ministry rules.
- A government body named without a country is the learner's own country's body (5.2).
- Church "ministries" are COMPANY_OR_NGO.

Code: `stages/rules_engine.py` (`ministry_per_country`, `exact_name`), `stages/replay/ministries.py`,
`stages/apply_decisions.py`.

6.6 **Institutions in their own right (decided by a person)**, not rolled up: nursing, health and teacher-training
colleges (unless named as part of a university); colleges run by a hospital or a company; affiliated colleges;
research institutes of a national research council that have their own ROR record. A research-council institute
without its own ROR record carries the council's ROR ID with its own name, like a campus. Code:
`stages/apply_decisions.py`.

6.7 **Organisations run by an NGO.** IF an organisation (a hospital or clinic) is run by an NGO AND has no ROR record
of its own THEN it keeps its own LOCAL ID; IF the NGO has a ROR record THEN the NGO's ROR ID, followed by the NGO's
own ROR parents, goes in `ror_parent_ids` of its rows. The pairs are listed in `coding/registries/local_parents.csv` (name,
country, the NGO's ROR ID, reason). Code: `stages/finalise.py` (`parent_ids`).

## 7. LOCAL IDs

7.1 **When issued.** IF an organisation is confirmed to exist (its own website, an official register, or a reliable
news or reference page) AND it has no ROR record THEN it gets a LOCAL ID, whatever its type and the number of
learners. The source goes in the register and the `local IDs` sheet. Code: `core/register.py`,
`stages/replay/known_organisations.py`, `stages/apply_decisions.py`.

7.2 **Before issuing**, the name is looked up in the register among the LOCAL IDs of the same country, by current and
former names (an international organisation in any country, 7.3). IF it is there THEN that ID is used; a retired ID
leads to the ID that replaced it. The lookup ignores capitals, punctuation and a leading "the" but needs the same
words, so a decision uses the existing ID's name exactly. Code: `core/register.py` (`find`, `issue`).

7.3 **One organisation, one LOCAL ID.** All answers naming the same organisation get its LOCAL ID. An organisation
active in several countries keeps one LOCAL ID in every country (ledger `org_country` `*`; its register country is
empty). Code: `core/register.py`, `stages/apply_decisions.py`.

7.4 **Name.** The organisation's own current name from its website or the official source: the full name, not an
acronym. A LOCAL name never equals the name of a ROR record in the same country: IF the organisation shares its name
with one THEN its town is added ("St. Mary's Hospital, Mumias").

7.6 **ROR and LOCAL IDs are used together.** The two registries are searched together, so that an organisation
gets the same ID however it is reached:
- IF an answer that no rule and no person has decided is the current or former name of exactly one active LOCAL ID
  in the learner's country (or of an international one, 7.3) THEN that LOCAL ID (rule code LOCAL).
- IF a LOCAL ID in use has the current or former name of exactly one active ROR record in its country THEN the
  organisation is in ROR (7.4): its rows move to that ROR record and the LOCAL ID is retired (7.5), automatically.
  This happens when ROR adds an organisation that had a LOCAL ID.
- The run stops IF a LOCAL ID in use has the name of several ROR records in its country, or IF a not-identified
  answer is the name of a LOCAL ID in its country, unless a person decided it is ambiguous (UNC-AMBIGUOUS). A person
  then compares the LOCAL ID's source with the ROR records (city, website) and records which it is; IF the evidence
  does not tell THEN the answer is not identified as ambiguous (5.4).

Code: `core/register.py` (`names_in`), `stages/apply_decisions.py` (`retire_locals_in_ror`, `code_local_names`),
`stages/finalise.py` (`registry_conflicts`).

7.5 **Numbering and retirement.** LOCAL IDs are numbered from LOCAL-0001 and are permanent. The register
`coding/registries/local_ids.csv` holds the ID, name, former names, the organisation's country, status (active or
retired), what replaced a retired ID and why, and the source. A new ID is the highest number ever issued + 1. A LOCAL
ID is retired (decided by a person) when the organisation turns out to have a ROR record, or when it duplicates an
older LOCAL ID (same organisation, whatever the spelling, word order, renaming, or acronym versus full name). Its
rows move to the ROR ID or the older LOCAL ID; the number is never reused. Each run copies the register and writes
the IDs it issued to `OUT_DIR/new_local_ids.csv`; a release copies the register back. Code: `core/register.py`,
`stages/replay/review_17oct.py`, `pipeline.py`, `__main__.py` (`release`).

## 8. Coded names

8.1 **With a ROR ID:** the ROR name, with these additions:
- a teaching hospital or a campus on its parent's ID: 6.2-6.3;
- IF two or more ROR IDs in the output have the same ROR name (ignoring accents and capitals) THEN the country is
  added in brackets, or the city and country IF two of them are in the same country: "Ministry of Health (Ghana)",
  "Federal Medical Centre (Owo, Nigeria)". A row whose coded name already ends in brackets keeps it.

Code: `stages/finalise.py` (`shared_ror_names`); earlier passes: `stages/assemble.py`,
`stages/replay/client_check.py`, `core/table.py` (`add_place_suffix`).

8.2 **With a LOCAL ID:** 7.4.

8.3 **Not identified:** a tidied version of the answer: spaces collapsed; dots, commas, semicolons and dashes at the
ends dropped; an answer all in capitals or all in lower case is written in title case, except acronyms: a one-word
answer of up to 6 letters, words in brackets, all-capital words in a mixed-case answer, and words that ROR writes in
capitals keep (or get) their capitals (aiims → AIIMS); small words inside a name are lower case (of, for, and);
"Children's", not "Children'S"; HTML entities are decoded. Code: `core/text.py` (`tidy_answer`),
`stages/replay/client_check.py` (`AcronymCase`), `stages/finalise.py`.

## 9. Decisions taken by a person

9.1 **The ledger.** Every decision taken by a person (web search results with their sources, reviewer, client and
human-review decisions) is a row of `coding/decisions.csv`, keyed by user-entered name and learner's country, with
its rationale. Each row belongs to a batch: batch `decisions` holds every new decision; the other batches are the
decision passes of 13-17 Oct 2026, applied by `stages/replay/` with the conventions of their day. The workbook's
research log lists every row. Code: `core/ledger.py`.

9.2 **A decision** (batch `decisions`): `raw_institution`, `country`, `target`, `name`, `org_type`, `org_country`,
`source`, `note`, `rationale_type`, `rationale`, `extra`, and optionally `rule_code` and `evidence_text`.
- `target`: a ROR ID; `TH:<ROR ID>` (teaching hospital on its university's record, `name` required); `LOCAL`
  (`name` required, `org_country` = the organisation's country, `*` for an international organisation); `NS`; `NA`;
  `TYPE:<org_type>`; `UNC` (stays not identified, the reason in `note`); `REMOVE` (the answer leaves the mapping,
  1.4).
- An org_type for every row of an ID is batch `org_type` (`target` = the ID).

9.3 **How decisions are applied**, in ledger order, then rules 7.6, 3.6 and 6.4:
- A decision is refused and reported (`OUT_DIR/decisions_report.csv`), never half-applied, IF it has no rationale;
  OR the row is already decided and `extra` does not say `override`; OR it names a ROR record abroad that 5.2 does
  not allow; OR it is `LOCAL` or `TH:` without a name; OR the ROR record is not active.
- A decision for a spelling that is not in the input applies to the row with the same pipeline key and country (3.6),
  IF that row is still open. A decision whose answer is not in the input at all is skipped and counted.
- Rule code and evidence: as recorded; otherwise the code that fits the target (3.5) and the note.

Code: `stages/apply_decisions.py`.

9.4 **Human-review case decisions** apply only to the named rows; they are not rules and are never applied to other
answers.

9.5 **Judgement calls.** After the decisions are applied, code drafts the list of judgement calls
(`OUT_DIR/judgement_calls.csv`): the coded rows of this round (new, or with another ID or status than in the
published mapping) that have more than one reasonable reading. Each row gets the first flag that applies, in this
order, with the reason and the alternative:
1. `acronym`: coded from an acronym (rule code ROR-ACRONYM, a decision whose evidence names an acronym, or an answer
   of 2-5 capitals): other organisations may share it.
2. `abroad`: the row was rolled up, found by a search or given a LOCAL ID (rule codes ROR-ROLLUP, LOCAL-ROLLUP,
   ROR-SEARCH, LOCAL), the organisation's country (in ROR, or in the LOCAL register) is not the learner's, and the ID
   is not one that is used for learners in any country by rule (5.2, 6.4, 10.1): a programme, network, country office
   or branch? An answer that is the name of an organisation abroad (ROR-EXACT and the like) is not flagged.
3. `owner`: an organisation run by an NGO (6.7), or a hospital, clinic, college, school or institute whose answer
   names a church, a mission or an NGO: part of its owner, or its own organisation?
4. `two organisations`: rule 5.5 chose one of two organisations named.

Rows a person has decided already (a client or human-review decision) are left out. The person in the loop answers
each row (HIL.md step 4), in the chat with the operator AI or in the spreadsheet; the answer is recorded as a client
decision (9.2), with the person's words as the rationale. Code: `judgement_calls.py` (`draft`, `this_round`).

## 10. Rule settings for named organisations

10.1 **Settings.** These rules name organisations and are set in `coding/coding_rules.json`:
- `international`: records used for learners in any country (5.2, 6.4): WHO, Africa CDC, UNICEF, UNDP, HealthNet
  TPO, University of the People, WorldQuant (University) and International Open University.
- `country_exceptions`: UNISA (University of South Africa) is also used for learners in Eswatini.
- `nhs`: every NHS body named by a learner in the United Kingdom → National Health Service (`02wnqcb97`).
- `org_type_overrides`: HealthNet TPO → COMPANY_OR_NGO.
- `abroad_checked`: NGO and company records checked by a person, which one-word or generic answers may use abroad
  (5.2).
- `per_country_generic`: "Ministry of Health" → the learner's country's ministry (6.5).
- `name_clusters`: the spellings of the International Youth Neuroscience Association.

Other decisions about named organisations are ledger decisions (section 9), listed in the workbook's research log.

Code: `stages/rules_engine.py`, `stages/typo_pass.py`, `stages/apply_decisions.py`.

## 11. Coding a sheet (client path)

11.1 **Two ways of working.** On the pipeline path (sections 1-10) the M&E pipeline matches its answers to the
published mapping itself and sends the answers it did not find as a batch to `input/`; a run codes them and a release
publishes the new mapping. On the client path (this section) anyone with a copy of the repository codes the
institution column of their own spreadsheet from the published mapping, with one command, on their own computer. The
client path makes no code: an answer that is not in the mapping is listed (11.6) and stays uncoded in the sheet until
a release has coded it and the sheet is coded again. The AI assistant that runs the command follows `AGENTS.md`; the
person's guide is `README.md`. Code: `code_sheet.py`, `__main__.py`.

11.2 **Checks first.** The file is checked before anything is coded. The command stops, and writes only the log, IF
the file does not exist; OR it is not `.xlsx` or `.csv` (an `.xls` file is saved as `.xlsx` first); OR it cannot be
opened (open in another program, password, damaged); OR the named sheet does not exist; OR the institution column, or
the country column when one is named, is not in the header row (IF it is in another of the first 20 rows, the
message names that row); OR the institution column has no answers. Problems that affect only some rows are warnings:
several sheets (the first is used), no country column, country values not recognised, rows without a country,
personal data (step 0), and the columns of 11.3 already in the sheet (they are overwritten in the copy). Every
finding is one line of the log `<file>_coding_log.txt` beside the outputs (`ERROR`, `WARNING` or `INFO`), written for
the AI assistant; the log holds no answer text; sending the list (11.7) adds to it. `--check-only` runs the checks alone. Code: `code_sheet.py`
(`check`, `open_sheet`, `resolve_countries`).

11.3 **Lookup.** A copy of the sheet, `<file>_coded.xlsx` (or `.csv`), gets four columns: `canonical_name`,
`institution_id`, `norhed` and `coding_status`. The client's own cells are not changed. An answer is found IF the
mapping has the same answer (3.6: the same pipeline key or the same cleaned text) in the same country (11.4); it
takes that row's outcome. The mapping has one outcome per answer and country (3.6), so the row chosen does not matter.

| `coding_status` | When | Added values |
| --- | --- | --- |
| `coded` | the mapping row is coding complete, with an ID | coded name, ID, norhed |
| `no organisation (NOT_APPLICABLE)` | the mapping row is NOT_APPLICABLE | none |
| `organisation not named (NOT_SPECIFIED)` | the mapping row is NOT_SPECIFIED | none |
| `type only (<org_type>)` | the mapping row is coding complete without an ID | none |
| `not identified` | the mapping row is not identified | none |
| `not in mapping` | no mapping row: the answer is listed (11.6) | none |
| `country needed` | no country, and the answer has different outcomes in different countries (11.4) | none |
| `personal data, not coded` | the answer is personal data (step 0) | none |
| `no answer` | the cell is empty | none |

Code: `code_sheet.py` (`Mapping`, `code`).

11.4 **Country.** The country is a two-letter code, or a country name as ROR writes it or as listed in
`code_sheet.py` (`COUNTRY_ALIASES`) and `build_input.py` (`COUNTRY_SPELLINGS`), in any capitals. A row with no
country, or with a country that is not recognised, takes the mapping's row for the answer without a country; IF
there is none, the outcome the answer has in every country of the mapping; IF its outcomes differ between countries
THEN `country needed`. When the row's country is known, an answer coded only in other countries is `not in mapping`
(5.1). Code: `code_sheet.py` (`country_codes`, `Mapping.lookup`).

11.5 **NORHED.** `norhed` is `yes` IF the row's ID is on the NORHED partner list (`core/norhed.py`), `no` for any
other ID, and empty for a row without an ID. Only the ID counts: an organisation coded to its own ROR record is not
NORHED because its ROR parent is a partner. The pipeline path does not set NORHED (3.2). Code: `code_sheet.py`
(`Mapping.norhed`).

11.6 **The list of answers not in the mapping.** `unmapped_institutions_<date>_<file>.xlsx`, beside the outputs, in
the format of the pipeline's batches (columns `raw institution`, `country`, `learners`), so that it goes into
`input/` as it is (1.4). One row per pipeline key and country, with the most frequent spelling; `learners` is the
number of rows of the sheet; a row without a recognised country has an empty country. Not listed: personal data,
`country needed` rows, and answers already in the mapping (not identified ones included). Step 0 removes e-mail
addresses and numbers only: the person looks the list over for people's names before sending it. Code:
`code_sheet.py` (`unmapped_table`, `write_outputs`).

11.7 **Sending the list.** The list goes to the repository as a pull request that adds it to `input/`; the
maintainer merges it, and the client needs no GitHub account. First the list is checked: its name
(`unmapped_institutions_<date>_<file>.xlsx`), its three columns, every row in their form (an answer; a two-letter code
or nothing; a whole number of learners), and no personal data (step 0). A list that fails is not sent. Then the key is
checked, and that no list of the same name is in `input/` already (it was sent before). A branch
`client-list/<list name>` (numbered IF it exists) gets the list, and the pull request is opened; its description holds
counts only, no answer text. The key is a GitHub access key of the maintainer's, limited to this repository (README,
"Setting up the submit key"). It is saved once on the person's computer, in their own user folder, never in the
repository folder, and it is never printed or written to the log. `--check-only` checks the list and the key and sends
nothing. Code: `submit.py` (`check_list`, `send`, `save_key`).
