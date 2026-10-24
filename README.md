# pl-er-diagram-builder

PrairieLearn element for building and grading Chen-style entity-relationship diagrams. Students draw on a canvas (or edit JSON). The server scores the semantic schema and ignores layout.

This is course work from UIUC CS 498 (Designing Software for Education), not an official [PrairieLearn](https://github.com/PrairieLearn/PrairieLearn) project.

## What the sample models

The shipped question is a Student / Course enrollment schema:

- **Student** — key `student_id`; attributes `name`, `email`
- **Course** — key `course_id`; attribute `title`
- **Enrolls** — many-to-many; attributes `semester`, `grade`. Student participation is total. Course participation is partial.

![Chen ER diagram of Student, Course, and Enrolls](docs/figures/student-course.png)

JSON for that diagram: [`examples/student-course.json`](examples/student-course.json). Field-level notes: [`docs/schema.md`](docs/schema.md).

A second diagram, Books / Authors / Categories, comes from a `pl-uml-element` question in `498erd-example`. It is documentation only (see `examples/books-authors.json`).

## Setup

Python 3.10+ is enough for tests. The PrairieLearn container already has `prairielearn`, `chevron`, and `lxml`.

```bash
python3 -m unittest tests/test_er_schema.py
```

To redraw the figures:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/render_er.py
```

To run the sample question, install [PrairieLearn](https://prairielearn.readthedocs.io/en/latest/installing/) (Docker is the usual path), point it at this repo root, and Load from disk.

## Use it in a PrairieLearn course

Copy `elements/pl-er-diagram-builder/` into your course `elements/` directory. Copy `questions/element/erDiagram/` if you want the sample. Sync the course.

```html
<pl-question-panel>
  <p>Build an ER diagram with entities <strong>Student</strong> and <strong>Course</strong>,
  and a many–many relationship <strong>Enrolls</strong> with attributes
  <code>semester</code> and <code>grade</code>. Use <code>student_id</code> and
  <code>course_id</code> as keys; include attributes <code>name</code> and
  <code>email</code> on Student and <code>title</code> on Course. Student
  participation in Enrolls is total; Course participation is partial.</p>
</pl-question-panel>

<pl-er-diagram-builder answers-name="er" height="520"></pl-er-diagram-builder>
```

Set the answer in `server.py` as `data["correct_answers"]["er"]` using `entities` and `relationships`. Leave `layout` out; grading drops it.

This repository is also a loadable PrairieLearn course (`infoCourse.json` + `courseInstances/demo`). Point a local PrairieLearn at the repo root, Load from disk, and open Homework 1.

Element attributes, inspector behavior, and the JSON shape are in [`elements/pl-er-diagram-builder/README.md`](elements/pl-er-diagram-builder/README.md).

## How grading works

`elements/pl-er-diagram-builder/er_schema.py` validates the submission, sorts names and attributes, then compares it to the configured answer. Order does not matter. Extra entities and relationships cost 0.25 each. The displayed score is scaled to 10.

```bash
python3 -m unittest tests/test_er_schema.py
```

## How to draw the figures

```bash
python3 scripts/render_er.py
```

Writes `docs/figures/*.png` and `*.svg` from `examples/*.json`. Mermaid crow's-foot sources sit next to them (`*.mmd`) if you want that view instead of Chen.

## Layout

```
elements/pl-er-diagram-builder/   drop this folder into a course
questions/element/erDiagram/      Student / Course sample
examples/                         schema JSON used by tests and the renderer
docs/figures/                     rendered diagrams
courseInstances/demo/             local PrairieLearn assessment
```

## License

MIT. See [LICENSE](LICENSE).

PrairieLearn is a separate project (AGPL-3.0) at [PrairieLearn/PrairieLearn](https://github.com/PrairieLearn/PrairieLearn). The element talks to its Python API (`import prairielearn`). The Books schema is from the CS 498 / IS 206 ERD example course (`498erd-example`), not from PrairieLearn itself.
