# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
"""Semantic ER schema: validate, normalize, and grade.

PrairieLearn's element controller and the standalone tests both import this
module. Layout coordinates are stored for the canvas and ignored here.
"""

from __future__ import annotations

import html

CARDINALITY_ALLOWED = frozenset({"one", "many"})
PARTICIPATION_ALLOWED = frozenset({"total", "partial"})

# Default rubric: entity 1.5 + relationship 2.0 = 3.5, reported out of 10.
ENTITY_NAME_WEIGHT = 0.6
ENTITY_ATTR_WEIGHT = 0.3
ENTITY_PK_WEIGHT = 0.6
ENTITY_WEAK_WEIGHT = 0.0
# Used instead of 0.0 for entities and relationships when grade_weak=True.
WEAK_FLAG_WEIGHT = 0.25
ENTITY_EXTRA_PENALTY = 0.25
ENTITY_TOTAL_MAX = 1.5

REL_NAME_WEIGHT = 1.0
REL_CARD_WEIGHT = 1.0
REL_EXTRA_PENALTY = 0.25
REL_TOTAL_MAX = 2.0

TOTAL_MAX = 3.5
SCALED_MAX = 10.0


def strip_layout(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "layout"}


def normalize_semantic(doc: dict) -> dict:
    """Canonical form for grading: sorted names and attribute lists."""
    entities = []
    for e in doc.get("entities", []):
        entities.append(
            {
                "name": str(e["name"]).strip(),
                "key_attributes": sorted({str(a).strip() for a in e.get("key_attributes", [])}),
                "attributes": sorted({str(a).strip() for a in e.get("attributes", [])}),
                "weak": bool(e.get("weak", False)),
            }
        )
    entities.sort(key=lambda x: x["name"])

    relationships = []
    for r in doc.get("relationships", []):
        participants = []
        for p in r.get("participants", []):
            participants.append(
                {
                    "entity": str(p["entity"]).strip(),
                    "cardinality": str(p["cardinality"]),
                    "participation": str(p["participation"]),
                }
            )
        participants.sort(key=lambda x: x["entity"])
        relationships.append(
            {
                "name": str(r["name"]).strip(),
                "participants": participants,
                "attributes": sorted({str(a).strip() for a in r.get("attributes", [])}),
                "weak": bool(r.get("weak", False)),
            }
        )
    relationships.sort(key=lambda x: x["name"])

    return {"entities": entities, "relationships": relationships}


def validate(doc: dict) -> str | None:
    """Return an HTML error message, or None if the document is valid."""
    if not isinstance(doc, dict):
        return "Submission must be a JSON object."
    if "entities" not in doc or not isinstance(doc["entities"], list):
        return "Missing or invalid <code>entities</code> array."
    if "relationships" not in doc or not isinstance(doc["relationships"], list):
        return "Missing or invalid <code>relationships</code> array."

    names = []
    for i, e in enumerate(doc["entities"]):
        if not isinstance(e, dict):
            return f"Entity at index {i} is not an object."
        if "name" not in e or not isinstance(e["name"], str) or not e["name"].strip():
            return f"Entity at index {i} needs a non-empty <code>name</code>."
        en = html.escape(e["name"])
        for key in ("key_attributes", "attributes"):
            if key not in e or not isinstance(e[key], list):
                return f"Entity <code>{en}</code> needs a <code>{key}</code> array."
            for a in e[key]:
                if not isinstance(a, str):
                    return f"Entity <code>{en}</code> has non-string attribute."
                if not a.strip():
                    return (
                        f"Entity <code>{en}</code> has an empty "
                        f"<code>{key}</code> entry (remove blank attributes)."
                    )
        if "weak" in e and not isinstance(e["weak"], bool):
            return f"Entity <code>{en}</code> <code>weak</code> must be a boolean."
        names.append(e["name"].strip())

    if len(names) != len(set(names)):
        return "Entity names must be unique."

    entity_set = set(names)

    for i, r in enumerate(doc["relationships"]):
        if not isinstance(r, dict):
            return f"Relationship at index {i} is not an object."
        if "name" not in r or not isinstance(r["name"], str) or not r["name"].strip():
            return f"Relationship at index {i} needs a non-empty <code>name</code>."
        rn = html.escape(r["name"])
        parts = r.get("participants")
        if not isinstance(parts, list) or len(parts) < 2:
            return (
                f"Relationship <code>{rn}</code> must have at least "
                f"two participants."
            )
        if "attributes" not in r or not isinstance(r["attributes"], list):
            return f"Relationship <code>{rn}</code> needs an <code>attributes</code> array."
        for a in r["attributes"]:
            if not isinstance(a, str):
                return f"Relationship <code>{rn}</code> has non-string attribute."
            if not a.strip():
                return (
                    f"Relationship <code>{rn}</code> has an empty attribute "
                    f"(remove blank attributes)."
                )
        if "weak" in r and not isinstance(r["weak"], bool):
            return f"Relationship <code>{rn}</code> <code>weak</code> must be a boolean."
        seen_ent = set()
        for p in parts:
            if not isinstance(p, dict):
                return f"Relationship <code>{rn}</code> has invalid participant."
            ent = p.get("entity")
            ent_esc = html.escape(str(ent)) if ent is not None else ""
            if isinstance(ent, str):
                ent = ent.strip()
            if not isinstance(ent, str) or ent not in entity_set:
                return (
                    f"Relationship <code>{rn}</code> references unknown "
                    f"entity <code>{ent_esc}</code>."
                )
            if ent in seen_ent:
                ent_rep = html.escape(ent)
                return (
                    f"Relationship <code>{rn}</code> lists entity "
                    f"<code>{ent_rep}</code> more than once."
                )
            seen_ent.add(ent)
            c = p.get("cardinality")
            part = p.get("participation")
            c_esc = html.escape(str(c))
            part_esc = html.escape(str(part))
            if c not in CARDINALITY_ALLOWED:
                return (
                    f"Invalid cardinality <code>{c_esc}</code> for "
                    f"<code>{rn}</code> / <code>{html.escape(ent)}</code>."
                )
            if part not in PARTICIPATION_ALLOWED:
                return (
                    f"Invalid participation <code>{part_esc}</code> for "
                    f"<code>{rn}</code> / <code>{html.escape(ent)}</code>."
                )

    rel_names = [r["name"].strip() for r in doc["relationships"]]
    if len(rel_names) != len(set(rel_names)):
        return "Relationship names must be unique."

    if "layout" in doc and doc["layout"] is not None and not isinstance(doc["layout"], dict):
        return "<code>layout</code> must be an object when present."

    return None


def _fmt_list(items) -> str:
    return html.escape(repr(list(items)))


def _list_diff(label: str, sub_items, exp_items, show_expected: bool) -> str:
    """Describe a list mismatch. Without show_expected, give counts only."""
    if show_expected:
        return f"{label} differ (expected {_fmt_list(exp_items)})."
    missing = len(set(exp_items) - set(sub_items))
    extra = len(set(sub_items) - set(exp_items))
    return f"{label} differ ({missing} missing, {extra} unexpected)."


def schema_mismatch_feedback(
    sub: dict, exp: dict, max_items: int = 12, show_expected: bool = False
) -> str:
    """HTML list of differences between two already-normalized schemas.

    Entity and relationship names are reported (questions state them). Expected
    attribute lists, weak flags, and cardinality/participation values are only
    revealed when ``show_expected`` is true.
    """
    issues: list[str] = []

    def push(msg: str) -> None:
        if len(issues) < max_items:
            issues.append(f"<li>{msg}</li>")

    sub_ent = {e["name"]: e for e in sub["entities"]}
    exp_ent = {e["name"]: e for e in exp["entities"]}

    for name in sorted(set(exp_ent) - set(sub_ent)):
        push(f"Missing entity <code>{html.escape(name)}</code>.")
    for name in sorted(set(sub_ent) - set(exp_ent)):
        push(f"Unexpected entity <code>{html.escape(name)}</code>.")

    for name in sorted(set(sub_ent) & set(exp_ent)):
        se, ee = sub_ent[name], exp_ent[name]
        ne = html.escape(name)
        if se["weak"] != ee["weak"]:
            if show_expected:
                push(
                    f"Entity <code>{ne}</code>: weak flag is "
                    f"<code>{str(se['weak']).lower()}</code>, "
                    f"expected <code>{str(ee['weak']).lower()}</code>."
                )
            else:
                push(f"Entity <code>{ne}</code>: weak flag is incorrect.")
        if se["key_attributes"] != ee["key_attributes"]:
            push(
                f"Entity <code>{ne}</code>: "
                + _list_diff("key attributes", se["key_attributes"], ee["key_attributes"], show_expected)
            )
        if se["attributes"] != ee["attributes"]:
            push(
                f"Entity <code>{ne}</code>: "
                + _list_diff("attributes", se["attributes"], ee["attributes"], show_expected)
            )

    sub_rel = {r["name"]: r for r in sub["relationships"]}
    exp_rel = {r["name"]: r for r in exp["relationships"]}

    for name in sorted(set(exp_rel) - set(sub_rel)):
        push(f"Missing relationship <code>{html.escape(name)}</code>.")
    for name in sorted(set(sub_rel) - set(exp_rel)):
        push(f"Unexpected relationship <code>{html.escape(name)}</code>.")

    for name in sorted(set(sub_rel) & set(exp_rel)):
        sr, er = sub_rel[name], exp_rel[name]
        nr = html.escape(name)
        if sr["weak"] != er["weak"]:
            if show_expected:
                push(
                    f"Relationship <code>{nr}</code>: identifying (weak) flag is "
                    f"<code>{str(sr['weak']).lower()}</code>, "
                    f"expected <code>{str(er['weak']).lower()}</code>."
                )
            else:
                push(f"Relationship <code>{nr}</code>: identifying (weak) flag is incorrect.")
        if sr["attributes"] != er["attributes"]:
            push(
                f"Relationship <code>{nr}</code>: "
                + _list_diff("attributes", sr["attributes"], er["attributes"], show_expected)
            )
        sub_map = {p["entity"]: (p["cardinality"], p["participation"]) for p in sr["participants"]}
        exp_map = {p["entity"]: (p["cardinality"], p["participation"]) for p in er["participants"]}
        if sr["participants"] != er["participants"]:
            for ent in sorted(set(exp_map) - set(sub_map)):
                push(
                    f"Relationship <code>{nr}</code>: missing participant "
                    f"<code>{html.escape(ent)}</code>."
                )
            for ent in sorted(set(sub_map) - set(exp_map)):
                push(
                    f"Relationship <code>{nr}</code>: unexpected participant "
                    f"<code>{html.escape(ent)}</code>."
                )
            for ent in sorted(set(sub_map) & set(exp_map)):
                sc, sp = sub_map[ent]
                ec, ep = exp_map[ent]
                if (sc, sp) == (ec, ep):
                    continue
                if show_expected:
                    push(
                        f"Relationship <code>{nr}</code>, entity "
                        f"<code>{html.escape(ent)}</code>: cardinality/participation are "
                        f"<code>{html.escape(sc)}</code>/<code>{html.escape(sp)}</code>, "
                        f"expected <code>{html.escape(ec)}</code>/<code>{html.escape(ep)}</code>."
                    )
                else:
                    wrong = [w for w, bad in (("cardinality", sc != ec), ("participation", sp != ep)) if bad]
                    push(
                        f"Relationship <code>{nr}</code>, entity "
                        f"<code>{html.escape(ent)}</code>: {' and '.join(wrong)} incorrect."
                    )

    body = "".join(issues)
    if not body.strip():
        return "<p>Your ER diagram does not match the expected schema.</p>"
    return (
        "<p>Your ER diagram does not match the expected schema.</p>"
        "<ul>" + body + "</ul>"
    )


def safe_ratio(numer: float, denom: float) -> float:
    if denom <= 0:
        return 1.0
    return numer / denom


def jaccard(sub_items, exp_items) -> float:
    """|sub & exp| / |sub | exp|; 1.0 when both are empty. Extras lower the score."""
    a, b = set(sub_items), set(exp_items)
    return safe_ratio(len(a & b), len(a | b))


def _weak_ratio(sub_items: dict, exp_items: dict) -> float:
    """Share of expected items present in the submission with the same weak flag."""
    hits = sum(
        1 for n, e in exp_items.items() if n in sub_items and sub_items[n]["weak"] == e["weak"]
    )
    return safe_ratio(hits, len(exp_items))


def compute_rubric_marks(sub: dict, exp: dict, grade_weak: bool = False) -> dict:
    """Partial credit for a normalized submission against a normalized answer.

    Attribute, key, and participant lists are scored with Jaccard similarity,
    so extra items cost credit just like missing ones. With ``grade_weak`` the
    weak-entity and identifying-relationship flags each add WEAK_FLAG_WEIGHT to
    the rubric (total 4.0 instead of 3.5).
    """
    ent_weak_max = WEAK_FLAG_WEIGHT if grade_weak else ENTITY_WEAK_WEIGHT
    rel_weak_max = WEAK_FLAG_WEIGHT if grade_weak else 0.0

    sub_ent = {e["name"]: e for e in sub["entities"]}
    exp_ent = {e["name"]: e for e in exp["entities"]}
    exp_ent_names = set(exp_ent)
    matched_ent_names = set(sub_ent) & exp_ent_names
    extra_ent_count = len(set(sub_ent) - exp_ent_names)

    ent_name_marks = ENTITY_NAME_WEIGHT * safe_ratio(len(matched_ent_names), len(exp_ent_names))

    attr_sum = 0.0
    pk_sum = 0.0
    for en in exp_ent_names:
        se = sub_ent.get(en)
        if se is None:
            continue
        ee = exp_ent[en]
        attr_sum += jaccard(se["attributes"], ee["attributes"])
        pk_sum += jaccard(se["key_attributes"], ee["key_attributes"])

    ent_attr_marks = ENTITY_ATTR_WEIGHT * safe_ratio(attr_sum, len(exp_ent_names))
    ent_pk_marks = ENTITY_PK_WEIGHT * safe_ratio(pk_sum, len(exp_ent_names))
    ent_weak_marks = ent_weak_max * _weak_ratio(sub_ent, exp_ent) if ent_weak_max else 0.0
    ent_extra_penalty = -ENTITY_EXTRA_PENALTY * extra_ent_count

    ent_total_marks = (
        ent_name_marks + ent_attr_marks + ent_pk_marks + ent_weak_marks + ent_extra_penalty
    )

    sub_rel = {r["name"]: r for r in sub["relationships"]}
    exp_rel = {r["name"]: r for r in exp["relationships"]}
    exp_rel_names = set(exp_rel)
    matched_rel_names = set(sub_rel) & exp_rel_names
    extra_rel_count = len(set(sub_rel) - exp_rel_names)

    rel_name_marks = REL_NAME_WEIGHT * safe_ratio(len(matched_rel_names), len(exp_rel_names))

    rel_card_sum = 0.0
    for rn in exp_rel_names:
        sr = sub_rel.get(rn)
        if sr is None:
            continue
        sub_parts = {(p["entity"], p["cardinality"], p["participation"]) for p in sr["participants"]}
        exp_parts = {(p["entity"], p["cardinality"], p["participation"]) for p in exp_rel[rn]["participants"]}
        # Denominator is the union of participating entities, so an extra
        # participant lowers the score even if every expected one matches.
        sub_ents = {p[0] for p in sub_parts}
        exp_ents = {p[0] for p in exp_parts}
        rel_card_sum += safe_ratio(len(sub_parts & exp_parts), len(sub_ents | exp_ents))

    rel_card_marks = REL_CARD_WEIGHT * safe_ratio(rel_card_sum, len(exp_rel_names))
    rel_weak_marks = rel_weak_max * _weak_ratio(sub_rel, exp_rel) if rel_weak_max else 0.0
    rel_extra_penalty = -REL_EXTRA_PENALTY * extra_rel_count
    rel_total_marks = rel_name_marks + rel_card_marks + rel_weak_marks + rel_extra_penalty

    entity_total_max = ENTITY_TOTAL_MAX + ent_weak_max
    rel_total_max = REL_TOTAL_MAX + rel_weak_max
    total_max = entity_total_max + rel_total_max
    total_marks = max(0.0, ent_total_marks + rel_total_marks)
    score_fraction = max(0.0, min(1.0, safe_ratio(total_marks, total_max)))
    scaled_marks = score_fraction * SCALED_MAX

    return {
        "entity_name_marks": ent_name_marks,
        "entity_attr_marks": ent_attr_marks,
        "entity_pk_marks": ent_pk_marks,
        "entity_weak_marks": ent_weak_marks,
        "extra_entities_penalty": ent_extra_penalty,
        "total_entity_marks": ent_total_marks,
        "relationship_marks": rel_name_marks,
        "relationship_card_marks": rel_card_marks,
        "relationship_weak_marks": rel_weak_marks,
        "extra_relationships_penalty": rel_extra_penalty,
        "total_relationship_marks": rel_total_marks,
        "total_marks": total_marks,
        "total_scaled_marks": scaled_marks,
        "score_fraction": score_fraction,
        "maxima": {
            "entity_name": ENTITY_NAME_WEIGHT,
            "entity_attr": ENTITY_ATTR_WEIGHT,
            "entity_pk": ENTITY_PK_WEIGHT,
            "entity_weak": ent_weak_max,
            "entity_total": entity_total_max,
            "relationship_name": REL_NAME_WEIGHT,
            "relationship_card": REL_CARD_WEIGHT,
            "relationship_weak": rel_weak_max,
            "relationship_total": rel_total_max,
            "total": total_max,
            "scaled_total": SCALED_MAX,
        },
    }


def format_marks_feedback(marks: dict, include_mismatch_html: str | None = None) -> str:
    def fmt(v: float) -> str:
        return f"{v:.2f}".rstrip("0").rstrip(".")

    m = marks
    mx = m["maxima"]
    lines = [
        f"Entity name marks: {fmt(m['entity_name_marks'])}/{fmt(mx['entity_name'])}",
        f"Entity attribute marks: {fmt(m['entity_attr_marks'])}/{fmt(mx['entity_attr'])}",
        f"Entity primary key marks: {fmt(m['entity_pk_marks'])}/{fmt(mx['entity_pk'])}",
        f"Extra entities: {fmt(m['extra_entities_penalty'])}",
        f"Total entity marks: {fmt(m['total_entity_marks'])}/{fmt(mx['entity_total'])}",
        f"Relationship marks: {fmt(m['relationship_marks'])}/{fmt(mx['relationship_name'])}",
        (
            "Relationship cardinalities marks: "
            f"{fmt(m['relationship_card_marks'])}/{fmt(mx['relationship_card'])}"
        ),
        f"Extra relationships: {fmt(m['extra_relationships_penalty'])}",
        (
            "Total relationship marks: "
            f"{fmt(m['total_relationship_marks'])}/{fmt(mx['relationship_total'])}"
        ),
        f"Total marks: {fmt(m['total_marks'])}/{fmt(mx['total'])}",
        f"Total scaled marks: {fmt(m['total_scaled_marks'])}/{fmt(mx['scaled_total'])}",
    ]

    if mx.get("entity_weak"):
        lines.insert(
            3, f"Weak entity marks: {fmt(m['entity_weak_marks'])}/{fmt(mx['entity_weak'])}"
        )
    if mx.get("relationship_weak"):
        at = next(i for i, ln in enumerate(lines) if ln.startswith("Extra relationships"))
        lines.insert(
            at,
            "Identifying relationship marks: "
            f"{fmt(m['relationship_weak_marks'])}/{fmt(mx['relationship_weak'])}",
        )

    feedback = "<p><strong>Rubric breakdown</strong></p><pre>" + "\n".join(lines) + "</pre>"
    if include_mismatch_html:
        feedback += include_mismatch_html
    return feedback
