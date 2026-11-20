# Next steps

## 1. Use LOCAL names inside longer answers

Rule 7.6 matches an answer to a LOCAL ID when the answer is exactly the ID's name. ROR names are also found inside
longer answers ("Department of X, <university>", step 3). Doing the same for LOCAL names would treat the two
registries fully alike. In v26 no not-identified answer contains a LOCAL name of three or more words, so this is
for future batches.

## 2. The learner's city in the input

Ask the M&E pipeline for one complete list of every free-text institution answer from all sources, with the
learner's country and, where available, the learner's city. Feed it back as the next batch in `input/`.

What it is for:
- Choosing between organisations with the same name in one country (5.4, 7.6). The learner's city is evidence
  for which one is meant, though not proof: it is where the learner is, not necessarily where the organisation is.
- Naming LOCAL IDs that share a name with a ROR record ("St. Mary's Hospital, Mumias", rule 7.4), and an optional
  `city` column in the LOCAL register, so that rule 8.1 can name LOCAL IDs as it names ROR IDs.

Needed in the code: a `city` column carried from the input through the mapping's working files (not the delivered
`mapping` sheet, whose columns the pipeline reads), and used by the rules above.
