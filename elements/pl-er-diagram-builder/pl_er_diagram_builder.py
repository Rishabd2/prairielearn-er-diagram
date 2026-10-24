import json

import chevron
import lxml.html
import prairielearn as pl

from er_schema import (
    compute_rubric_marks,
    format_marks_feedback,
    normalize_semantic,
    schema_mismatch_feedback,
    strip_layout,
    validate,
)

WEIGHT_DEFAULT = 1
HEIGHT_DEFAULT = 600

ER_DIAGRAM_MUSTACHE = "pl-er-diagram-builder.mustache"


def _json_embed_safe(obj) -> str:
    """Embed JSON inside HTML; escape </ to avoid closing tags."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _pretty_json_for_display(value) -> str:
    """Pretty-print submitted JSON for the submission panel."""
    if value is None:
        return ""
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return ""
        try:
            parsed = json.loads(s)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return s
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return json.dumps(value, indent=2, ensure_ascii=False)


def prepare(element_html: str, data: pl.QuestionData) -> None:
    element = lxml.html.fragment_fromstring(element_html)
    pl.check_attribs(
        element,
        required_attribs=["answers-name"],
        optional_attribs=["weight", "height", "disable-grading", "hide-instructions"],
    )
    name = pl.get_string_attrib(element, "answers-name")
    data["params"][name] = {
        "disable_grading": pl.get_boolean_attrib(element, "disable-grading", False),
        "hide_instructions": pl.get_boolean_attrib(element, "hide-instructions", False),
    }


def render(element_html: str, data: pl.QuestionData) -> str:
    element = lxml.html.fragment_fromstring(element_html)
    name = pl.get_string_attrib(element, "answers-name")
    editable = data["editable"]
    display_dict_name = f"{name}-raw"
    display_json = data["raw_submitted_answers"].get(display_dict_name, None)
    if display_json is None:
        submitted_doc = data.get("submitted_answers", {}).get(display_dict_name)
        if submitted_doc is not None:
            display_json = submitted_doc
    if display_json is None:
        submitted_doc = data.get("submitted_answers", {}).get(name)
        if submitted_doc is not None:
            display_json = submitted_doc
    feedback = None
    if name in data["partial_scores"]:
        feedback = data["partial_scores"][name].get("feedback", None)

    fmt_err = data["format_errors"].get(name)

    if data["panel"] == "question":
        html_params = {
            "question": True,
            "answers_name": name,
            "display_json": _json_embed_safe(display_json),
            "format_errors_json": _json_embed_safe(fmt_err),
            "editable": editable,
            "height": pl.get_integer_attrib(element, "height", HEIGHT_DEFAULT),
            "hide_instructions": pl.get_boolean_attrib(
                element, "hide-instructions", False
            ),
        }
        with open(ER_DIAGRAM_MUSTACHE) as f:
            return chevron.render(f, html_params).strip()

    if data["panel"] == "submission":
        display_pretty = _pretty_json_for_display(display_json)
        html_params = {
            "submission": True,
            "answers_name": name,
            "display_json": display_pretty,
            "submission_json_embed": _json_embed_safe(display_json),
            "format_errors_json": _json_embed_safe(fmt_err),
            "editable": False,
            "feedback": feedback,
            "height": pl.get_integer_attrib(element, "height", HEIGHT_DEFAULT),
            "show_submission_diagram": display_json is not None,
        }
        if fmt_err is not None:
            html_params["parse_errors"] = fmt_err
        with open(ER_DIAGRAM_MUSTACHE) as f:
            return chevron.render(f, html_params).strip()

    return ""


def parse(element_html: str, data: pl.QuestionData) -> None:
    element = lxml.html.fragment_fromstring(element_html)
    name = pl.get_string_attrib(element, "answers-name")
    raw_key = f"{name}-raw"
    try:
        raw = data["raw_submitted_answers"][raw_key]
        doc = json.loads(raw)
    except json.JSONDecodeError:
        data["format_errors"][name] = {"message": "Could not parse submission."}
        return
    except KeyError:
        data["format_errors"][name] = {"message": "Missing submission."}
        return

    err = validate(doc)
    if err is not None:
        data["format_errors"][name] = {"message": err}
        return

    normalized = normalize_semantic(strip_layout(doc))
    data["submitted_answers"][name] = normalized


def grade(element_html: str, data: pl.QuestionData) -> None:
    element = lxml.html.fragment_fromstring(element_html)
    name = pl.get_string_attrib(element, "answers-name")
    weight = pl.get_integer_attrib(element, "weight", WEIGHT_DEFAULT)

    if data["params"][name].get("disable_grading"):
        data["partial_scores"][name] = {
            "score": None,
            "weight": weight,
            "feedback": "Grading disabled for this element.",
        }
        return

    if name not in data["submitted_answers"]:
        return

    sub = data["submitted_answers"][name]
    if name not in data.get("correct_answers", {}):
        data["partial_scores"][name] = {
            "score": 0,
            "weight": weight,
            "feedback": "No correct answer configured for this question.",
        }
        return

    correct_doc = data["correct_answers"][name]
    if not isinstance(correct_doc, dict):
        data["partial_scores"][name] = {
            "score": 0,
            "weight": weight,
            "feedback": "Correct answer has invalid format.",
        }
        return

    key_err = validate(correct_doc)
    if key_err is not None:
        data["partial_scores"][name] = {
            "score": 0,
            "weight": weight,
            "feedback": (
                "<p>Correct answer has invalid format:</p>"
                f"<p>{key_err}</p>"
            ),
        }
        return

    expected = normalize_semantic(strip_layout(correct_doc))

    marks = compute_rubric_marks(sub, expected)
    mismatch_feedback = None if sub == expected else schema_mismatch_feedback(sub, expected)
    data["partial_scores"][name] = {
        "score": marks["score_fraction"],
        "weight": weight,
        "feedback": format_marks_feedback(marks, mismatch_feedback),
    }
