# `pl-er-diagram-builder` element

Interactive ER (entity-relationship) diagram editor for PrairieLearn. Students can build diagrams either with the **canvas + selection inspector** or by editing **JSON** directly. The element supports entities, weak entities, relationships, weak/identifying relationships, attributes, and relationship participants with cardinality and participation. Optional `layout` data stores positions and is ignored during grading.

Validation, normalization, and the rubric live in `er_schema.py` in this folder so the PrairieLearn controller and the repo tests share one implementation. Copy this whole directory into a course `elements/` folder.

## Overview

- **Canvas editing**: Add, move, select, rename, and delete entities and relationships.
- **Selection inspector**: Edit names, weak flags, attributes, and relationship participants; **Apply** / **Discard** control when changes are written to the submitted payload (clicking elsewhere on the canvas commits pending edits).
- **Undo / Redo**: Toolbar buttons and keyboard shortcuts (Ctrl+Z / Ctrl+Shift+Z when the canvas is focused) revert recent edits.
- **JSON view**: Edit the raw submission directly if preferred.
- **Submission panel**: Shows a **read-only diagram** (zoomable) plus **pretty-printed** submitted JSON (parsed from the stored raw string when needed) for instructor review.
- **Grading**: Compares the submitted semantic ER schema against the correct answer after normalizing order and stripping layout.

---

## Sample question

An example question that uses this element lives at [questions/element/erDiagram/question.html](../../questions/element/erDiagram/question.html). It asks students to model a Student/Course enrollment schema and uses [questions/element/erDiagram/server.py](../../questions/element/erDiagram/server.py) for the reference answer.

**question.html**

```html
<pl-question-panel>
  <p>Build an ER diagram with entities <strong>Student</strong> and <strong>Course</strong>, and a many-to-many relationship <strong>Enrolls</strong> with attributes <code>semester</code> and <code>grade</code>. Use <code>student_id</code> and <code>course_id</code> as keys; include attributes <code>name</code> and <code>email</code> on Student and <code>title</code> on Course. Student participation in Enrolls is total; Course participation is partial.</p>
</pl-question-panel>

<pl-er-diagram-builder answers-name="er" height="520"></pl-er-diagram-builder>
```

Set the correct answer in `server.py` as `data["correct_answers"]["er"]` using the semantic schema shape (`entities` + `relationships`). Do not include `layout`; it is ignored for grading.

**server.py**

```python
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
```

Grading compares the normalized ER schema from the submission to `correct_answers`.

---

## Submitted JSON shape

The submitted JSON should have this shape:

- `entities[]`: `name`, `key_attributes[]`, `attributes[]`, optional `weak` (boolean)
- `relationships[]`: `name`, `participants[]` (at least two, unique `entity`; each participant has `cardinality` and `participation`), `attributes[]`, optional `weak` (boolean)
- `layout` (optional): `{ "entities": { "EntityName": { "x", "y", "width", "height" } }, "relationships": { "RelName": { "x", "y" } } }`

The `layout` field is preserved for the editor but stripped before grading.

### Weak entities and identifying relationships

- **Weak entity**: set `"weak": true` on an entity. The canvas draws a double rectangle.
- **Identifying (weak) relationship**: set `"weak": true` on a relationship. The canvas draws a double diamond.

Example snippet:

```json
"entities": [
  { "name": "Pay", "key_attributes": ["pay_no"], "attributes": ["hours"], "weak": true }
],
"relationships": [
  {
    "name": "paid_by",
    "weak": true,
    "participants": [
      { "entity": "Employee", "cardinality": "one", "participation": "total" },
      { "entity": "Pay", "cardinality": "many", "participation": "partial" }
    ],
    "attributes": []
  }
]
```

### Cardinality and participation

Each participant must include:

- `"cardinality"`: `"one"` or `"many"`
- `"participation"`: `"total"` or `"partial"`

Use the inspector dropdowns when a relationship is selected, or set these fields in JSON.

### Ternary (and higher) relationships

Create a relationship with **at least two** participants (binary by default). To model a relationship among three or more entities, select the relationship and use **Add participant** in the inspector until every connected entity appears once. Cardinality and participation are configured per participant.

---

## Customizations

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `answers-name` | string | required | Unique identifier for this element instance. |
| `weight` | integer | `1` | Weight of the element in scoring. |
| `height` | integer | `600` | Canvas height in pixels. |
| `disable-grading` | boolean | `false` | If `true`, the element stores submissions but does not grade them. |
| `hide-instructions` | boolean | `false` | If `true`, the collapsible help block at the top of the element is hidden. |
| `grade-weak` | boolean | `false` | If `true`, weak-entity and identifying-relationship flags are scored (0.25 each, rubric total 4.0 instead of 3.5). Off by default, so existing questions keep their scores. |
| `starter-params-name` | string | none | Key in `data["params"]` holding a starter diagram (dict or JSON string, same shape as a submission, `layout` optional). Shown until the student saves their first answer. Validated in `prepare`. |

## How to use

1. **Entities**: Use **Add entity** or double-click empty canvas. Select an entity to rename it, toggle **Weak entity**, and edit key or descriptive attributes in the inspector.
2. **Relationships**: Click **Add relationship**, then click two entities for a binary link. Select the relationship to rename it, toggle **Weak / identifying**, edit relationship attributes, and set each participant's **cardinality** and **participation** with the dropdowns.
3. **Ternary+**: With a relationship selected, use **Add participant** (and remove with **×**) so each participating entity appears exactly once.
4. **Delete**: Select an item on the canvas (click the canvas first so it has keyboard focus), press **Delete** or **Backspace**, or use **Delete selection** in the inspector.
5. **JSON**: Expand **JSON view** to edit the submission directly; valid JSON updates the diagram after a short delay; leaving the field reformats and syncs the hidden submitted payload.
6. **Zoom**: Use **+** / **−** on the canvas; scroll the canvas area if the diagram extends past the visible region when zoomed.
7. **Inspector Apply / Discard**: After editing fields in the inspector, use **Apply** to sync the submission JSON or **Discard** to revert this selection's fields to when you opened it; selecting another entity on the canvas saves pending edits automatically.
8. **Undo / Redo**: Use the toolbar buttons or Ctrl+Z / Ctrl+Shift+Z (canvas focused) to step through recent changes.

### Starter / pre-filled diagrams

Set a starter in `server.py` and name it with `starter-params-name`:

```python
def generate(data):
    data["params"]["er_starter"] = {
        "entities": [
            {"name": "Employee", "key_attributes": [], "attributes": []},
            {"name": "Pay", "key_attributes": ["pay_no"], "attributes": ["hours"]},
        ],
        "relationships": [],
    }
```

```html
<pl-er-diagram-builder answers-name="er" starter-params-name="er_starter"></pl-er-diagram-builder>
```

The starter appears on the canvas until the student saves; after that the saved answer is shown. The starter is not graded on its own: a student who submits it unchanged is scored against `correct_answers` like any other submission. Full example: `questions/element/erDiagramStarter/`.
