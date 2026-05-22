"""UI integration smoke tests for the library browser page (PR 11 Agent C).

Per ``docs/pr11_prep/pr11_spec.md`` §9 final paragraph: "gated on PR 10
landing a test harness. PR 11 ships the file as a stub with
``pytest.skip('requires PR 10 UI harness')`` at the top until then."

PR 10a landed a NiceGUI testing harness via ``nicegui.testing.User`` —
``tests/test_ui_smoke.py`` is the home of those tests. The harness is
currently not fully wired (``ui/app.py`` registers ``@ui.page("/")``
only inside ``launch()``, so ``User.open("/")`` fails with "You must
call ui.run()..." at runtime). Until that harness gap is closed, this
file ships as a stub-with-plan.

Planned tests (PR 11.5; spec §4):
- Library browser page mounts without error after PR 11's stub →
  real wiring of ``ui/views/library_browser.py``.
- Filter form updates the table on change (matching street + label
  patterns through ``Library.list``).
- "Load" button populates the solve panel via ``Library.get``
  routed through ``asyncio.to_thread``.
- "Export" button writes a JSON file via ``Library.export``.
- "Save to library" button on the spot-input panel appears after a
  solve completes; clicking it calls ``Library.put`` and toasts.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "requires PR 10 UI harness (ui/app.py registers @ui.page('/') only "
    "inside launch(); follow-up in PR 11.5 wires test-mode registration)",
    allow_module_level=True,
)
