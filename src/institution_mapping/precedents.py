"""How similar answers were coded before (rulebook 9.5): the evidence for a consistent proposal in a judgement call.

For an answer and its learner's country:
- the organisations it may name: the proposed ID, and the ROR records found by an acronym or a name in the answer
  (search.RorIndex, score 80 or more), each with the number of answers the published mapping codes to it;
- for each distinctive word of the answer (search.distinct), how the published mapping coded the answers that contain
  it: the most frequent outcomes, in the learner's country if any answer there has the word, else in any country;
- the decisions a person took on such answers (client, human-review and reviewer decisions in the ledger and in the
  decisions files of input/);
- the ROR links (parent and child) between the organisations found.
Used by judgement_calls.py (column `precedent`) and on its own by
`python -m institution_mapping precedents OUT_DIR "answer" CC`.
"""

from collections import defaultdict
from pathlib import Path

import pandas as pd

from .core.ledger import decision_files, read_decision_file
from .pipeline import CODING, INPUT, OUTPUT
from .search import RorIndex, distinct

PERSON = {"client decision", "human-review decision", "reviewer decision"}


def outcome_label(institution_id, name, status, org_type):
    """An outcome in words: 'ID name', 'not identified', or the type of a row without an ID."""
    if status != "coding complete":
        return "not identified"
    return f"{institution_id} {name}" if institution_id else (org_type or "no ID")


class Precedents:
    """The published mapping, the person's decisions and the ROR links, indexed by distinctive word."""

    def __init__(self, mapping, ledger, orgs=None, ror_index=None):
        self.m = mapping.reset_index(drop=True)
        self.m["label"] = [
            outcome_label(*r) for r in zip(self.m.institution_id, self.m.canonical_name, self.m.status, self.m.org_type)
        ]
        self.index = defaultdict(set)  # distinctive word -> rows of the mapping
        for i, a in enumerate(self.m.raw_institution):
            for w in distinct(a):
                self.index[w].add(i)
        led = ledger[ledger.rationale_type.isin(PERSON)].reset_index(drop=True)
        self.person = led
        self.person_index = defaultdict(set)
        for i, a in enumerate(led.raw_institution):
            for w in distinct(a):
                self.person_index[w].add(i)
        self.ror = ror_index
        self.parents = {}
        if orgs is not None:
            self.parents = {r: set(p.split(";")) - {""} for r, p in zip(orgs.ror_id, orgs.parent_ids)}

    def organisations(self, answer, country, proposed=""):
        """[(ID, name, how found, answers coded to it in the learner's country, in any country)]: the proposed ID
        and the ROR records an acronym or a name in the answer points to."""
        found = {proposed: "proposed"} if proposed else {}
        if self.ror is not None:
            best = sorted(self.ror.candidates(answer, country).items(), key=lambda x: (-x[1][0], x[0]))
            for rid, (score, how) in best[:3]:
                if score >= 80:
                    found.setdefault(rid, how)
        out = []
        for i, how in found.items():
            coded = self.m[self.m.institution_id == i]
            names = coded.canonical_name.value_counts()
            name = names.index[0] if len(names) else (self.ror.orgs.at[i, "display_name"] if self.ror else "")
            out.append((i, name, how, int((coded.country == country).sum()), len(coded)))
        return out

    def by_word(self, answer, country, top=3):
        """[(word, where, number of answers, [(outcome, count)])] for each distinctive word of the answer."""
        out = []
        for w in sorted(distinct(answer)):
            rows = self.m.loc[sorted(self.index.get(w, ()))]
            here = rows[rows.country == country] if country else rows.iloc[0:0]
            rows, where = (here, country) if len(here) else (rows, "any country")
            counts = rows.label.value_counts().head(top)
            out.append((w, where, len(rows), list(counts.items())))
        return out

    def decisions(self, answer, top=5):
        """The person's decisions on answers that share a distinctive word with this one."""
        rows = set().union(*[self.person_index.get(w, set()) for w in distinct(answer)] or [set()])
        d = self.person.loc[sorted(rows)].head(top)
        return [(r.raw_institution, r.country, r.target, r.rationale_type, r.rationale) for r in d.itertuples()]

    def links(self, ids):
        """'A is a ROR parent of B' for every pair of these ROR IDs that ROR links."""
        ids = [i for i in dict.fromkeys(ids) if i and not i.startswith("LOCAL-")]
        return [f"{p} is a ROR parent of {c}" for c in ids for p in ids if p in self.parents.get(c, set())]

    def summary(self, answer, country, proposed=""):
        """One line for the judgement-call draft."""
        orgs = self.organisations(answer, country, proposed)
        parts = [
            f"{i} {n} ({how}): {k} answers coded to it in {country or 'no country'}, {t} in all"
            for i, n, how, k, t in orgs
        ]
        for w, where, n, counts in self.by_word(answer, country):
            if n:
                coded = "; ".join(f"{label} ({k})" for label, k in counts)
                parts.append(f"'{w}' in {where}: {n} answers -> {coded}")
            else:
                parts.append(f"'{w}': no earlier answer")
        ids = [i for i, *_ in orgs]
        ids += [label.split(" ")[0] for _, _, _, counts in self.by_word(answer, country) for label, _ in counts]
        parts += self.links(ids) or ["no ROR link between these organisations"]
        return " | ".join(parts)

    def report(self, answer, country, proposed=""):
        """The whole precedent of an answer, as lines of text."""
        lines = [f"# {answer} ({country or 'no country'})"]
        orgs = self.organisations(answer, country, proposed)
        for i, n, how, k, t in orgs:
            lines.append(f"may name {i} {n} ({how}): {k} answers coded to it in {country or 'no country'}, {t} in all")
        for w, where, n, counts in self.by_word(answer, country, top=6):
            lines.append(f"'{w}' in {where}: {n} answers")
            lines += [f"   {label}: {k}" for label, k in counts]
        ids = [i for i, *_ in orgs]
        ids += [label.split(" ")[0] for _, _, _, counts in self.by_word(answer, country, top=6) for label, _ in counts]
        lines += [f"ROR link: {x}" for x in self.links(ids)] or ["no ROR link between these organisations"]
        for raw, cc, target, rtype, why in self.decisions(answer):
            lines.append(f"decided by a person: '{raw}' ({cc}) -> {target} [{rtype}] {why}")
        return lines


def load(out_dir=None):
    """Precedents from the published mapping, the ledger with the decisions files of input/, and (with OUT_DIR, a
    run's folder) the run's ROR snapshot."""
    files = sorted(OUTPUT.glob("institution_mapping_*.xlsx"))
    m = pd.read_excel(files[-1], sheet_name="mapping", dtype=str, keep_default_na=False)
    led = pd.read_csv(CODING / "decisions.csv", dtype=str, keep_default_na=False)
    led = pd.concat([led] + [read_decision_file(f, list(led.columns)) for f in decision_files(INPUT)])
    orgs = index = None
    ror = Path(out_dir) / "work" / "ror" if out_dir is not None else None
    if ror is not None and (ror / "ror_orgs.csv").exists():
        orgs = pd.read_csv(ror / "ror_orgs.csv", dtype=str, keep_default_na=False)
        index = RorIndex(ror)
    return Precedents(m, led, orgs, index)


def run(out_dir, answer, country="", proposed=""):
    """Print the precedent of one answer."""
    print("\n".join(load(out_dir).report(answer, country, proposed)))
