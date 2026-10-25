# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
"""Run the element JS in headless Chrome (skipped when Chrome is not installed)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from render_element import find_chrome

    find_chrome()
    HAVE_CHROME = True
except (ImportError, SystemExit):
    HAVE_CHROME = False


@unittest.skipUnless(HAVE_CHROME, "Chrome or Chromium not available")
class BrowserSmokeTest(unittest.TestCase):
    def test_smoke(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_element.py"), "smoke"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
