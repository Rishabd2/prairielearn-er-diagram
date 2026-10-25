# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
"""Run the element controller (prepare, render, parse, grade) outside PrairieLearn.

PrairieLearn's ``prairielearn`` Python package is replaced by a small stub that
implements only the attribute helpers the controller calls. ``chevron`` and
``lxml`` must be installed (see requirements-dev.txt).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELEMENT = ROOT / "elements" / "pl-er-diagram-builder"

HAVE_DEPS = all(importlib.util.find_spec(m) for m in ("chevron", "lxml"))

_MISSING = object()


def _install_prairielearn_stub() -> None:
    if "prairielearn" in sys.modules and getattr(sys.modules["prairielearn"], "_is_stub", False):
        return
    pl = types.ModuleType("prairielearn")
    pl._is_stub = True
    pl.QuestionData = dict

    def check_attribs(element, required_attribs, optional_attribs):
        allowed = set(required_attribs) | set(optional_attribs)
        for a in required_attribs:
            if a not in element.attrib:
                raise ValueError(f'Required attribute "{a}" missing')
        for a in element.attrib:
            if a not in allowed:
                raise ValueError(f'Attribute "{a}" not allowed')

    def get_string_attrib(element, name, default=_MISSING):
        if name in element.attrib:
            return element.attrib[name]
        if default is _MISSING:
            raise ValueError(f'Attribute "{name}" missing')
        return default

    def get_boolean_attrib(element, name, default=_MISSING):
        if name not in element.attrib:
            if default is _MISSING:
                raise ValueError(f'Attribute "{name}" missing')
            return default
        return element.attrib[name].strip().lower() in ("true", "t", "1", "yes", "y")

    def get_integer_attrib(element, name, default=_MISSING):
        if name not in element.attrib:
            if default is _MISSING:
                raise ValueError(f'Attribute "{name}" missing')
            return default
        return int(element.attrib[name])

    pl.check_attribs = check_attribs
    pl.get_string_attrib = get_string_attrib
    pl.get_boolean_attrib = get_boolean_attrib
    pl.get_integer_attrib = get_integer_attrib
    sys.modules["prairielearn"] = pl


@contextmanager
def in_element_dir():
    # PrairieLearn runs element controllers with the element folder as cwd.
    old = os.getcwd()
    os.chdir(ELEMENT)
    try:
        yield
    finally:
        os.chdir(old)


def load_controller():
    _install_prairielearn_stub()
    if str(ELEMENT) not in sys.path:
        sys.path.insert(0, str(ELEMENT))
    return importlib.import_module("pl_er_diagram_builder")


def load_server(question: str):
    path = ROOT / "questions" / "element" / question / "server.py"
    spec = importlib.util.spec_from_file_location(f"server_{question}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def new_data() -> dict:
    return {
        "params": {},
        "correct_answers": {},
        "submitted_answers": {},
        "raw_submitted_answers": {},
        "format_errors": {},
        "partial_scores": {},
        "panel": "question",
        "editable": True,
    }


def embedded_backup(html: str, name: str = "er") -> object:
    marker = f'id="{name}-er-backup-json">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    text = html[start:end].strip()
    return json.loads(text) if text else None


SIMPLE = '<pl-er-diagram-builder answers-name="er"></pl-er-diagram-builder>'


@unittest.skipUnless(HAVE_DEPS, "chevron and lxml are required")
class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctl = load_controller()

    def _student_course(self):
        data = new_data()
        load_server("erDiagram").generate(data)
        self.ctl.prepare(SIMPLE, data)
        return data

    def test_prepare_rejects_unknown_attribute(self):
        with self.assertRaises(ValueError):
            self.ctl.prepare('<pl-er-diagram-builder answers-name="er" colour="red"></pl-er-diagram-builder>', new_data())

    def test_prepare_rejects_invalid_correct_answer(self):
        data = new_data()
        data["correct_answers"]["er"] = {"entities": [{"name": "A"}], "relationships": []}
        with self.assertRaises(ValueError):
            self.ctl.prepare(SIMPLE, data)

    def test_show_expected_controls_feedback(self):
        for tag, leaks in (
            (SIMPLE, False),
            ('<pl-er-diagram-builder answers-name="er" show-expected="true"></pl-er-diagram-builder>', True),
        ):
            data = new_data()
            load_server("erDiagram").generate(data)
            self.ctl.prepare(tag, data)
            answer = json.loads(json.dumps(data["correct_answers"]["er"]))
            answer["entities"][0]["attributes"] = []
            data["raw_submitted_answers"]["er-raw"] = json.dumps(answer)
            self.ctl.parse(tag, data)
            self.ctl.grade(tag, data)
            self.assertEqual("(expected" in data["partial_scores"]["er"]["feedback"], leaks)

    def test_render_question_panel_empty(self):
        data = self._student_course()
        with in_element_dir():
            html = self.ctl.render(SIMPLE, data)
        self.assertIn('name="er-raw"', html)
        self.assertIn("new ERDiagramBuilder", html)
        self.assertIsNone(embedded_backup(html))
        self.assertNotIn("SPDX", html)

    def test_correct_submission_scores_full(self):
        data = self._student_course()
        answer = json.loads(json.dumps(data["correct_answers"]["er"]))
        answer["entities"].reverse()
        answer["layout"] = {"entities": {"Student": {"x": 5, "y": 5}}, "relationships": {}}
        data["raw_submitted_answers"]["er-raw"] = json.dumps(answer)
        self.ctl.parse(SIMPLE, data)
        self.assertEqual(data["format_errors"], {})
        self.assertNotIn("layout", data["submitted_answers"]["er"])
        self.ctl.grade(SIMPLE, data)
        self.assertEqual(data["partial_scores"]["er"]["score"], 1.0)

    def test_partial_submission_scores_below_one(self):
        data = self._student_course()
        answer = json.loads(json.dumps(data["correct_answers"]["er"]))
        answer["relationships"][0]["participants"][0]["participation"] = "partial"
        data["raw_submitted_answers"]["er-raw"] = json.dumps(answer)
        self.ctl.parse(SIMPLE, data)
        self.ctl.grade(SIMPLE, data)
        score = data["partial_scores"]["er"]["score"]
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_parse_reports_bad_json(self):
        data = self._student_course()
        data["raw_submitted_answers"]["er-raw"] = "{not json"
        self.ctl.parse(SIMPLE, data)
        self.assertIn("er", data["format_errors"])

    def test_disable_grading(self):
        tag = '<pl-er-diagram-builder answers-name="er" disable-grading="true"></pl-er-diagram-builder>'
        data = new_data()
        load_server("erDiagram").generate(data)
        self.ctl.prepare(tag, data)
        data["raw_submitted_answers"]["er-raw"] = json.dumps({"entities": [], "relationships": []})
        self.ctl.parse(tag, data)
        self.ctl.grade(tag, data)
        self.assertIsNone(data["partial_scores"]["er"]["score"])

    def test_submission_panel_renders_pretty_json(self):
        data = self._student_course()
        data["raw_submitted_answers"]["er-raw"] = json.dumps(data["correct_answers"]["er"])
        self.ctl.parse(SIMPLE, data)
        self.ctl.grade(SIMPLE, data)
        data["panel"] = "submission"
        with in_element_dir():
            html = self.ctl.render(SIMPLE, data)
        self.assertIn("Submitted diagram", html)
        self.assertIn("&quot;Enrolls&quot;", html)


@unittest.skipUnless(HAVE_DEPS, "chevron and lxml are required")
class StarterTests(unittest.TestCase):
    TAG = (
        '<pl-er-diagram-builder answers-name="er" height="420" '
        'starter-params-name="er_starter" grade-weak="true"></pl-er-diagram-builder>'
    )

    @classmethod
    def setUpClass(cls):
        cls.ctl = load_controller()

    def _data(self):
        data = new_data()
        load_server("erDiagramStarter").generate(data)
        self.ctl.prepare(self.TAG, data)
        return data

    def test_starter_is_embedded_before_first_save(self):
        data = self._data()
        with in_element_dir():
            html = self.ctl.render(self.TAG, data)
        backup = embedded_backup(html)
        self.assertEqual([e["name"] for e in backup["entities"]], ["Employee", "Pay"])
        self.assertEqual(backup["relationships"], [])

    def test_saved_answer_wins_over_starter(self):
        data = self._data()
        saved = {"entities": [{"name": "X", "key_attributes": [], "attributes": []}], "relationships": []}
        data["raw_submitted_answers"]["er-raw"] = json.dumps(saved)
        with in_element_dir():
            html = self.ctl.render(self.TAG, data)
        self.assertEqual(json.loads(embedded_backup(html)), saved)

    def test_starter_alone_does_not_score_full(self):
        data = self._data()
        data["raw_submitted_answers"]["er-raw"] = json.dumps(data["params"]["er_starter"])
        self.ctl.parse(self.TAG, data)
        self.ctl.grade(self.TAG, data)
        # Entities 1.5 + Employee weak flag 0.125, no relationship marks: 1.625 / 4.0.
        self.assertAlmostEqual(data["partial_scores"]["er"]["score"], 1.625 / 4.0)

    def test_reference_answer_scores_full(self):
        data = self._data()
        data["raw_submitted_answers"]["er-raw"] = json.dumps(data["correct_answers"]["er"])
        self.ctl.parse(self.TAG, data)
        self.ctl.grade(self.TAG, data)
        self.assertEqual(data["partial_scores"]["er"]["score"], 1.0)

    def test_missing_weak_flags_lose_credit_when_graded(self):
        data = self._data()
        answer = json.loads(json.dumps(data["correct_answers"]["er"]))
        answer["entities"][1]["weak"] = False
        answer["relationships"][0]["weak"] = False
        data["raw_submitted_answers"]["er-raw"] = json.dumps(answer)
        self.ctl.parse(self.TAG, data)
        self.ctl.grade(self.TAG, data)
        self.assertAlmostEqual(data["partial_scores"]["er"]["score"], (3.5 + 0.125) / 4.0)
        self.assertIn("Weak entity marks", data["partial_scores"]["er"]["feedback"])

    def test_missing_starter_param_raises(self):
        with self.assertRaises(ValueError):
            self.ctl.prepare(self.TAG, new_data())

    def test_invalid_starter_raises(self):
        data = new_data()
        data["params"]["er_starter"] = {"entities": [{"name": ""}], "relationships": []}
        with self.assertRaises(ValueError):
            self.ctl.prepare(self.TAG, data)

    def test_starter_as_json_string(self):
        data = new_data()
        data["params"]["er_starter"] = json.dumps({"entities": [], "relationships": []})
        self.ctl.prepare(self.TAG, data)


if __name__ == "__main__":
    unittest.main()
