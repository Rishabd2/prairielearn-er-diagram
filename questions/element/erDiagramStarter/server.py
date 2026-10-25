# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
import json

# The reference answer is the repository example examples/employee-pay.json,
# copied here so the question folder works on its own.
CORRECT = {
    "entities": [
        {"name": "Employee", "key_attributes": ["emp_id"], "attributes": ["name"]},
        {"name": "Pay", "key_attributes": ["pay_no"], "attributes": ["hours"], "weak": True},
    ],
    "relationships": [
        {
            "name": "paid_by",
            "weak": True,
            "participants": [
                # Cardinality describes the entity's own side: one Employee per Pay,
                # many Pay records per Employee.
                {"entity": "Employee", "cardinality": "one", "participation": "partial"},
                # A weak entity always participates totally in its identifying relationship.
                {"entity": "Pay", "cardinality": "many", "participation": "total"},
            ],
            "attributes": [],
        }
    ],
}


def generate(data):
    # Shown on the canvas before the student's first save. Layout is optional.
    data["params"]["er_starter"] = {
        "entities": [
            {"name": "Employee", "key_attributes": ["emp_id"], "attributes": ["name"]},
            {"name": "Pay", "key_attributes": ["pay_no"], "attributes": ["hours"]},
        ],
        "relationships": [],
        "layout": {
            "entities": {
                "Employee": {"x": 60, "y": 120},
                "Pay": {"x": 460, "y": 120},
            },
            "relationships": {},
        },
    }
    data["correct_answers"]["er"] = json.loads(json.dumps(CORRECT))
