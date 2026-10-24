"""Unit tests for the shared ER schema module. No PrairieLearn runtime required."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.er_schema import (  # noqa: E402
    compute_rubric_marks,
    format_marks_feedback,
    normalize_semantic,
    schema_mismatch_feedback,
    strip_layout,
    validate,
)


def load_example(name: str) -> dict:
    doc = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if not k.startswith("_")}


class ValidateTests(unittest.TestCase):
    def test_student_course_valid(self):
        self.assertIsNone(validate(load_example("student-course.json")))

    def test_books_authors_valid(self):
        self.assertIsNone(validate(load_example("books-authors.json")))

    def test_employee_pay_valid(self):
        self.assertIsNone(validate(load_example("employee-pay.json")))

    def test_rejects_empty_attribute(self):
        doc = load_example("student-course.json")
        doc["entities"][0]["attributes"].append("")
        err = validate(doc)
        self.assertIsNotNone(err)
        self.assertIn("empty", err.lower())

    def test_rejects_duplicate_entity_names(self):
        doc = load_example("student-course.json")
        doc["entities"].append(
            {
                "name": "Student",
                "key_attributes": ["x"],
                "attributes": [],
            }
        )
        self.assertEqual(validate(doc), "Entity names must be unique.")

    def test_rejects_unknown_participant(self):
        doc = load_example("student-course.json")
        doc["relationships"][0]["participants"][0]["entity"] = "Person"
        err = validate(doc)
        self.assertIn("unknown", err.lower())
        self.assertIn("Person", err)

    def test_escapes_html_in_entity_name(self):
        doc = {
            "entities": [
                {
                    "name": "<script>x</script>",
                    "key_attributes": ["id"],
                    "attributes": [""],
                }
            ],
            "relationships": [],
        }
        err = validate(doc)
        self.assertIsNotNone(err)
        self.assertNotIn("<script>", err)
        self.assertIn("&lt;script&gt;", err)

    def test_rejects_bad_cardinality(self):
        doc = load_example("student-course.json")
        doc["relationships"][0]["participants"][0]["cardinality"] = "n"
        err = validate(doc)
        self.assertIn("Invalid cardinality", err)

    def test_rejects_single_participant(self):
        doc = load_example("student-course.json")
        doc["relationships"][0]["participants"] = [
            doc["relationships"][0]["participants"][0]
        ]
        err = validate(doc)
        self.assertIn("at least", err.lower())


class NormalizeTests(unittest.TestCase):
    def test_strips_layout(self):
        doc = load_example("student-course.json")
        doc["layout"] = {"entities": {"Student": {"x": 1, "y": 2}}}
        self.assertNotIn("layout", strip_layout(doc))

    def test_order_independent(self):
        a = load_example("student-course.json")
        b = {
            "entities": list(reversed(a["entities"])),
            "relationships": [
                {
                    **a["relationships"][0],
                    "participants": list(reversed(a["relationships"][0]["participants"])),
                    "attributes": list(reversed(a["relationships"][0]["attributes"])),
                }
            ],
        }
        self.assertEqual(
            normalize_semantic(strip_layout(a)),
            normalize_semantic(strip_layout(b)),
        )


class GradeTests(unittest.TestCase):
    def _expected(self):
        return normalize_semantic(strip_layout(load_example("student-course.json")))

    def test_perfect_score(self):
        exp = self._expected()
        marks = compute_rubric_marks(exp, exp)
        self.assertAlmostEqual(marks["score_fraction"], 1.0)
        self.assertAlmostEqual(marks["total_scaled_marks"], 10.0)

    def test_wrong_cardinality_is_partial(self):
        exp = self._expected()
        sub = json.loads(json.dumps(exp))
        for p in sub["relationships"][0]["participants"]:
            if p["entity"] == "Student":
                p["cardinality"] = "one"
        marks = compute_rubric_marks(sub, exp)
        self.assertGreater(marks["score_fraction"], 0.0)
        self.assertLess(marks["score_fraction"], 1.0)
        html = schema_mismatch_feedback(sub, exp)
        self.assertIn("Student", html)
        self.assertIn("cardinality", html.lower())

    def test_missing_entity(self):
        exp = self._expected()
        sub = {
            "entities": [e for e in exp["entities"] if e["name"] != "Course"],
            "relationships": [],
        }
        html = schema_mismatch_feedback(sub, exp)
        self.assertIn("Missing entity", html)
        self.assertIn("Course", html)
        marks = compute_rubric_marks(sub, exp)
        self.assertLess(marks["score_fraction"], 1.0)

    def test_extra_entity_penalty(self):
        exp = self._expected()
        sub = json.loads(json.dumps(exp))
        sub["entities"].append(
            {
                "name": "Department",
                "key_attributes": [],
                "attributes": [],
                "weak": False,
            }
        )
        marks = compute_rubric_marks(sub, exp)
        self.assertEqual(marks["extra_entities_penalty"], -0.25)
        self.assertLess(marks["score_fraction"], 1.0)

    def test_feedback_lists_rubric_lines(self):
        exp = self._expected()
        marks = compute_rubric_marks(exp, exp)
        html = format_marks_feedback(marks)
        self.assertIn("Rubric breakdown", html)
        self.assertIn("Total scaled marks: 10/10", html)


if __name__ == "__main__":
    unittest.main()
