# Contributing

This repo is a PrairieLearn course element plus the sample question that uses it. Keep that split.

## Layout

- Element code lives in `elements/pl-er-diagram-builder/`. Instructors copy that folder into a course.
- Shared validation and grading live in `er_schema.py` in that same folder. The PrairieLearn controller and `tests/test_er_schema.py` both import it. Do not fork a second copy.
- Do not add entities, attributes, or relationships that are not already in a source question or README snippet.

## Checks

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/render_element.py screenshot
python3 scripts/render_er.py
```

New source files start with `SPDX-License-Identifier: AGPL-3.0-or-later` in a comment. Contributions are accepted under that license.

`render_element.py screenshot` refreshes `docs/figures/element-editor.png` from the live element. The schema renderer reads `examples/*.json` and overwrites `docs/figures/*.png` and `*.svg`. If you change a schema, rerun it and commit the figures.

## Local PrairieLearn

Install PrairieLearn, point it at this directory (it is a complete course: `infoCourse.json`, `elements/`, `questions/`, `courseInstances/demo/`), then Load from disk. The sample question is `element/erDiagram`.

## Pull requests

Say what you changed and how you tested it (pytest, local PrairieLearn, or both). Match the existing JSON shape (`entities`, `relationships`, optional `layout`).
