#!/usr/bin/env python
"""VECTIS V2 — Liguria wildfire end-to-end demo (console entry point).

Run from the ``backend/`` directory:

    python scripts/run_demo_liguria.py

Thin wrapper so the documented command works whether or not the package is
pip-installed; the demo itself lives in ``vectis.scripts.demo_v2`` (importable
and tested). We add the backend root to ``sys.path`` so a bare ``python
scripts/...`` run finds ``vectis`` even before ``pip install -e .``.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from vectis.scripts.demo_v2 import main  # noqa: E402  (after sys.path setup)

if __name__ == "__main__":
    main()
