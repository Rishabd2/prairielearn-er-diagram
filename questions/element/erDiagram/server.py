def generate(data):
    data["correct_answers"]["er"] = {
        "entities": [
            {
                "name": "Student",
                "key_attributes": ["student_id"],
                "attributes": ["name", "email"],
            },
            {
                "name": "Course",
                "key_attributes": ["course_id"],
                "attributes": ["title"],
            },
        ],
        "relationships": [
            {
                "name": "Enrolls",
                "participants": [
                    {
                        "entity": "Student",
                        "cardinality": "many",
                        "participation": "total",
                    },
                    {
                        "entity": "Course",
                        "cardinality": "many",
                        "participation": "partial",
                    },
                ],
                "attributes": ["semester", "grade"],
            }
        ],
    }
