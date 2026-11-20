"""Replay of the 16 Oct review of uncoded spellings (ledger batch review_16oct). See review.py."""

from .review import apply_review


def run(ctx):
    apply_review(ctx, __name__, "review_16oct")
