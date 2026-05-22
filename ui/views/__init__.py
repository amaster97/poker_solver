"""View modules for the poker-solver NiceGUI UI.

Each view exports a ``render(state: AppState, ...) -> None`` function that
draws itself into the current NiceGUI slot. The top-level
``ui.app.build_page`` composes them inside a two-pane layout per the
``pr10a_spec.md`` §0.1 Q1 lock.
"""

from __future__ import annotations
