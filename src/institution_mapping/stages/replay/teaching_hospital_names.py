"""Replay of the 16 Oct name fixes (rulebook 6.3): teaching hospitals carry "<university> Teaching Hospital"
(ledger batch name_fixes_16oct_b)."""

from ...core.ledger import present
from ...core.table import row_of


def run(ctx):
    m = ctx.read_previous(__name__)
    for _, r in present(ctx.ledger.batch("name_fixes_16oct_b"), m, "name_fixes_16oct_b").iterrows():
        m.at[row_of(m, r.raw_institution, r.country), "canonical_name"] = r["name"]
    ctx.write(__name__, m)
