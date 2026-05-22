"""poker-solver NiceGUI UI package (PR 10a — scaffolds against ui.mock_solver).

The UI is the **same artifact** PR 10b will ship; only the contents of
``ui/mock_solver.py`` change between PRs. The single import line in
``ui/state.py``'s ``SolveRunner._worker`` is the swap point (see
``docs/pr10_prep/pr10b_spec.md``).

Per ``pr10a_spec.md`` §0.1, seven UX decisions are LOCKED (Q1-Q7):

- **Q1**: Two-pane layout (matrix center + collapsible right sidebar).
- **Q2**: Hand-class labels visible in cells (numeric freqs on hover).
- **Q3**: Default iterations = 1000 (target-expl mode opt-in).
- **Q4**: Bet sizes default = 4 of 6 checked (33 / 75 / 100 / all-in).
- **Q5**: Combo inspector below matrix (full-width strip).
- **Q6**: Tree reach filter default = 0.01.
- **Q7**: Yellow "Mock mode" banner, dismissible.
"""

from __future__ import annotations

__version__: str = "0.1.0"

__all__ = ["__version__"]
