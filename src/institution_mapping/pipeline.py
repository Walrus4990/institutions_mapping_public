"""Runs the whole mapping, stage by stage, and defines where every stage reads and writes.

A run reads three folders of the repository and writes only into OUT_DIR:
  input/    the answers to code (build_input.py turns them, and the published mapping, into work/input/raw.csv)
  coding/   what the code codes with: registries/ (the ROR snapshot, the LOCAL register and the tables that link
            codes), coding_rules.json and decisions.csv
  output/   the published mapping, read as the record of every answer coded so far
coding/ is copied to OUT_DIR/work/coding first: stages that issue LOCAL IDs update that copy, never the repository.
`python -m institution_mapping release OUT_DIR` copies the result back (see README, "Releasing").
"""

import importlib
import json
import shutil
import time
import zipfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pandas as pd

from .core.ledger import Ledger
from .core.register import Register

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "input"
CODING = REPO / "coding"
REGISTRIES = CODING / "registries"
OUTPUT = REPO / "output"

# The stages in the order they run. Each is a module of institution_mapping.stages with a function run(ctx).
# Stages 1-8 decide every answer by rule; stages 9-24 replay the recorded decision passes of 16-17 Oct 2026
# (stages/replay/); stages 25-28 apply the later rules and decisions and write the deliverable.
STAGES = [
    "prepare",  # 1  step 0 (personal data) and step 1 (cleaning); ROR names cleaned the same way
    "exact_names",  # 2  user-entered name = a ROR name
    "contained_names",  # 3  a ROR name or acronym inside the user-entered name
    "non_institutions",  # 4  no organisation (NOT_APPLICABLE) and type-only answers
    "fuzzy_candidates",  # 5  up to three close ROR candidates per open spelling
    "rules_engine",  # 6  the rulebook's rules on every open spelling and country
    "assemble",  # 7  one outcome per user-entered name and country
    "typo_pass",  # 8  typos and close spellings in the learner's country
    "replay.client_check",  # 9  client check of the suggested rows (16 Oct)
    "replay.spelling_groups",  # 10 similar uncoded spellings searched as one organisation (16 Oct)
    "replay.word_order",  # 11 the words of one ROR name in another order
    "replay.review_16oct",  # 12 review of uncoded spellings
    "replay.na_check",  # 13 NOT_APPLICABLE re-checked
    "replay.ministries",  # 14 ministries and central banks: one ID per ministry and country
    "replay.review_universities",  # 15 review of uncoded universities
    "replay.teaching_hospital_names",  # 16 teaching hospitals named after their university
    "replay.review_16oct_b",  # 17 second review of uncoded spellings
    "replay.unique_names",  # 18 the only ROR record worldwide with this name
    "replay.client_universities",  # 19 client review of the unmatched-universities list
    "replay.search_universities",  # 20 web search of the remaining universities and colleges
    "replay.verified_universities",  # 21 universities confirmed by a website get a LOCAL ID
    "replay.known_organisations",  # 22 NGO/company rule; confirmed organisations get an ID
    "replay.search_all",  # 23 web search of every remaining entry
    "replay.review_17oct",  # 24 duplicate LOCAL IDs merged; human-review case decisions (17 Oct)
    "owner_rule",  # 25 rule 3a: a ministry named with its institution is the owner, not the organisation
    "apply_decisions",  # 26 ledger batch `decisions`; same answer, same code (3.6); international bodies (6.4)
    "finalise",  # 27 org_type per ID, coded-name conventions, rule codes, parents, checks
    "workbook",  # 28 the delivered workbook
]


def stage_name(module_or_stage):
    """'replay.word_order' for the module institution_mapping.stages.replay.word_order (or the name itself)."""
    return module_or_stage.split(".stages.")[-1]


@dataclass
class Run:
    """Paths and shared inputs of one run, passed to every stage."""

    in_dir: Path
    ror_dir: Path
    out_dir: Path

    @property
    def work(self):
        """OUT_DIR/work: every intermediate file of the run."""
        return self.out_dir / "work"

    @property
    def coding(self):
        """This run's copy of coding/ (stages that issue LOCAL IDs update its LOCAL register)."""
        return self.work / "coding"

    def w(self, name):
        """Path of an intermediate file (OUT_DIR/work/<name>)."""
        return str(self.work / name)

    def c(self, name):
        """Path of a file in this run's copy of coding/ (coding_rules.json, decisions.csv)."""
        return str(self.coding / name)

    def registry(self, name):
        """Path of a registry in this run's copy of coding/registries/ (local_ids.csv, local_parents.csv, ...)."""
        return str(self.coding / "registries" / name)

    def o(self, name):
        """Path of a deliverable (OUT_DIR/<name>)."""
        return str(self.out_dir / name)

    def mapping(self, stage):
        """Path of the mapping written by a stage (work/mapping_NN_<stage>.csv)."""
        stage = stage_name(stage)
        n = STAGES.index(stage) + 1
        return self.w(f"mapping_{n:02d}_{stage.split('.')[-1]}.csv")

    def previous_mapping(self, stage):
        """Path of the mapping written by the stage before this one."""
        return self.mapping(STAGES[STAGES.index(stage_name(stage)) - 1])

    def read_previous(self, stage, **read_args):
        """The mapping written by the stage before this one (institution_id read as text)."""
        read_args.setdefault("dtype", {"institution_id": str})
        return pd.read_csv(self.previous_mapping(stage), keep_default_na=False, **read_args)

    def write(self, stage, m):
        """Save this stage's mapping."""
        m.to_csv(self.mapping(stage), index=False)

    @cached_property
    def settings(self):
        """coding_rules.json: the rule parameters."""
        with open(self.c("coding_rules.json"), encoding="utf-8") as f:
            return json.load(f)

    @cached_property
    def ledger(self):
        """decisions.csv: every decision taken by a person."""
        return Ledger(self.c("decisions.csv"))

    def register(self):
        """The LOCAL register of this run (re-read: earlier stages may have issued IDs)."""
        return Register(self.registry("local_ids.csv"))


def unzip_ror(ror_dir):
    """Unzip the ROR snapshot of coding/registries/ror/ (one zip file) into ror_dir."""
    (snapshot,) = (REGISTRIES / "ror").glob("*.zip")
    with zipfile.ZipFile(snapshot) as z:
        z.extractall(ror_dir)
    print("ROR snapshot:", snapshot.name)


def run(out_dir, in_dir=None, ror_dir=None, coding=CODING, stages=None):
    """Run the stages (all by default) into a fresh OUT_DIR/work. Without in_dir the input is built from input/ and
    output/ (work/input/raw.csv); without ror_dir the ROR snapshot is unzipped into work/ror."""
    out = Path(out_dir).resolve()
    ror = Path(ror_dir).resolve() if ror_dir else out / "work" / "ror"
    inp = Path(in_dir).resolve() if in_dir else out / "work" / "input"
    ctx = Run(inp, ror, out)
    if stages is None:
        if ctx.work.exists():
            shutil.rmtree(ctx.work)
        shutil.copytree(coding, ctx.coding)
        if not ror_dir:
            unzip_ror(ror)
        if not in_dir:
            from .build_input import build  # build_input imports this module

            build(ror, inp / "raw.csv")
        stages = STAGES
    start_register = pd.read_csv(ctx.registry("local_ids.csv"), dtype=str, keep_default_na=False)
    for name in stages:
        t0 = time.time()
        print(f"== stage {STAGES.index(name) + 1}: {name}", flush=True)
        importlib.import_module(f"institution_mapping.stages.{name}").run(ctx)
        print(f"   ({time.time() - t0:.0f} s)", flush=True)
    end_register = pd.read_csv(ctx.registry("local_ids.csv"), dtype=str, keep_default_na=False)
    new = end_register[~end_register.local_id.isin(start_register.local_id)]
    new[["local_id", "name", "country", "source"]].to_csv(ctx.o("new_local_ids.csv"), index=False)
    print(f"run complete: {ctx.o('institution_mapping_final.xlsx')} | new LOCAL IDs: {len(new)}")
    return ctx
