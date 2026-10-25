# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
"""Re-export the element grader for local tests and scripts."""

from __future__ import annotations

import sys
from pathlib import Path

_ELEMENT = Path(__file__).resolve().parents[1] / "elements" / "pl-er-diagram-builder"
if str(_ELEMENT) not in sys.path:
    sys.path.insert(0, str(_ELEMENT))

from er_schema import (  # noqa: E402
    CARDINALITY_ALLOWED,
    PARTICIPATION_ALLOWED,
    compute_rubric_marks,
    format_marks_feedback,
    jaccard,
    normalize_semantic,
    safe_ratio,
    schema_mismatch_feedback,
    strip_layout,
    validate,
)

__all__ = [
    "CARDINALITY_ALLOWED",
    "PARTICIPATION_ALLOWED",
    "compute_rubric_marks",
    "format_marks_feedback",
    "jaccard",
    "normalize_semantic",
    "safe_ratio",
    "schema_mismatch_feedback",
    "strip_layout",
    "validate",
]
