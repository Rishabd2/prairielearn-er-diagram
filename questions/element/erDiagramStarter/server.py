# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
def generate(data):
    # Shown on the canvas before the student's first save. Layout is optional.
    data["params"]["er_starter"] = {
        "entities": [
            {"name": "Employee", "key_attributes": [], "attributes": []},
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

    data["correct_answers"]["er"] = {
        "entities": [
            {"name": "Employee", "key_attributes": [], "attributes": []},
            {
                "name": "Pay",
                "key_attributes": ["pay_no"],
                "attributes": ["hours"],
                "weak": True,
            },
        ],
        "relationships": [
            {
                "name": "paid_by",
                "weak": True,
                "participants": [
                    {"entity": "Employee", "cardinality": "one", "participation": "total"},
                    {"entity": "Pay", "cardinality": "many", "participation": "partial"},
                ],
                "attributes": [],
            }
        ],
    }
