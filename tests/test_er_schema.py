# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
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

    def test_department_professor_valid(self):
        self.assertIsNone(validate(load_example("department-professor.json")))

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


def _norm(doc):
    return normalize_semantic(strip_layout(doc))


class GamingTests(unittest.TestCase):
    """Padding lists with extra items must not earn full credit."""

    def setUp(self):
        self.exp = _norm(load_example("student-course.json"))

    def test_every_attribute_as_key_and_descriptive_loses_credit(self):
        sub = json.loads(json.dumps(self.exp))
        for e in sub["entities"]:
            everything = sorted(set(e["key_attributes"]) | set(e["attributes"]))
            e["key_attributes"] = everything
            e["attributes"] = everything
        marks = compute_rubric_marks(sub, self.exp)
        self.assertLess(marks["entity_pk_marks"], 0.6)
        self.assertLess(marks["entity_attr_marks"], 0.3)
        self.assertLess(marks["score_fraction"], 1.0)

    def test_extra_key_attribute_scored_by_jaccard(self):
        sub = json.loads(json.dumps(self.exp))
        for e in sub["entities"]:
            if e["name"] == "Student":
                e["key_attributes"] = ["email", "student_id"]
        marks = compute_rubric_marks(sub, self.exp)
        # Student keys: 1/2; Course keys: 1/1; mean 0.75 of 0.6.
        self.assertAlmostEqual(marks["entity_pk_marks"], 0.6 * 0.75)

    def test_third_participant_on_binary_relationship_loses_credit(self):
        exp = _norm(load_example("department-professor.json"))
        sub = json.loads(json.dumps(load_example("department-professor.json")))
        sub["entities"].append({"name": "Room", "key_attributes": ["room_no"], "attributes": []})
        sub["relationships"][0]["participants"].append(
            {"entity": "Room", "cardinality": "many", "participation": "partial"}
        )
        sub = _norm(sub)
        marks = compute_rubric_marks(sub, exp)
        # works_in: 2 matching of 3 entities; chairs: 2 of 2; mean 5/6.
        self.assertAlmostEqual(marks["relationship_card_marks"], 5 / 6)
        self.assertLess(marks["score_fraction"], 1.0)

    def test_missing_participant_still_partial(self):
        sub = json.loads(json.dumps(self.exp))
        sub["relationships"][0]["participants"][0]["cardinality"] = "one"
        marks = compute_rubric_marks(sub, self.exp)
        self.assertAlmostEqual(marks["relationship_card_marks"], 0.5)


class NameAndFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.exp = _norm(load_example("student-course.json"))

    def test_whitespace_in_names_is_ignored(self):
        sub = load_example("student-course.json")
        sub["entities"][0]["name"] = "  " + sub["entities"][0]["name"] + " "
        sub["entities"][0]["attributes"] = [a + " " for a in sub["entities"][0]["attributes"]]
        for p in sub["relationships"][0]["participants"]:
            p["entity"] = " " + p["entity"]
        self.assertIsNone(validate(sub))
        self.assertEqual(_norm(sub), self.exp)

    def test_feedback_hides_expected_by_default(self):
        sub = json.loads(json.dumps(self.exp))
        sub["entities"][0]["attributes"] = ["wrong"]
        sub["relationships"][0]["participants"][0]["cardinality"] = "one"
        hidden = schema_mismatch_feedback(sub, self.exp)
        self.assertNotIn("(expected", hidden)
        self.assertNotIn(", expected", hidden)
        self.assertNotIn("title", hidden)
        self.assertIn("1 missing, 1 unexpected", hidden)
        self.assertIn("cardinality incorrect", hidden)
        shown = schema_mismatch_feedback(sub, self.exp, show_expected=True)
        self.assertIn("(expected [&#x27;title&#x27;])", shown)
        self.assertIn(", expected <code>many</code>", shown)


class ExampleConventionTests(unittest.TestCase):
    """Weak entities participate totally in their identifying relationship."""

    def test_weak_entities_total_in_identifying_relationships(self):
        for name in ("student-course.json", "department-professor.json", "employee-pay.json"):
            doc = load_example(name)
            weak = {e["name"] for e in doc["entities"] if e.get("weak")}
            for r in doc["relationships"]:
                if not r.get("weak"):
                    continue
                for p in r["participants"]:
                    if p["entity"] in weak:
                        self.assertEqual(p["participation"], "total", f"{name}: {r['name']}")

    def test_entities_have_keys(self):
        for name in ("student-course.json", "department-professor.json", "employee-pay.json"):
            for e in load_example(name)["entities"]:
                self.assertTrue(e["key_attributes"], f"{name}: {e['name']}")



class GradeWeakTests(unittest.TestCase):
    def setUp(self):
        self.exp = normalize_semantic(strip_layout(load_example("employee-pay.json")))

    def _unflagged(self):
        sub = json.loads(json.dumps(self.exp))
        for item in sub["entities"] + sub["relationships"]:
            item["weak"] = False
        return sub

    def test_default_rubric_ignores_weak_flags(self):
        marks = compute_rubric_marks(self._unflagged(), self.exp)
        self.assertEqual(marks["score_fraction"], 1.0)
        self.assertEqual(marks["maxima"]["total"], 3.5)
        self.assertNotIn("Weak entity marks", format_marks_feedback(marks))

    def test_grade_weak_scores_flags(self):
        full = compute_rubric_marks(self.exp, self.exp, grade_weak=True)
        self.assertEqual(full["score_fraction"], 1.0)
        self.assertEqual(full["maxima"]["total"], 4.0)
        # Employee is not weak in the answer, so 1 of 2 entity flags still match.
        partial = compute_rubric_marks(self._unflagged(), self.exp, grade_weak=True)
        self.assertAlmostEqual(partial["total_marks"], 3.5 + 0.125)
        self.assertIn("Identifying relationship marks", format_marks_feedback(partial))


if __name__ == "__main__":
    unittest.main()
