# Schemas in this repository

Nothing here adds entities that were not already in the source files.

## Student / Course (graded sample)

Source: `questions/element/erDiagram/` and `examples/student-course.json`.

| Kind | Name | Keys | Other attributes | Notes |
| --- | --- | --- | --- | --- |
| Entity | Student | student_id | name, email | |
| Entity | Course | course_id | title | |
| Relationship | Enrolls | | semester, grade | Student many / total. Course many / partial. |

Student participation in Enrolls is total. Course participation is partial. The relationship is many-to-many.

Chen drawing: `docs/figures/student-course.svg` (and `.png`). Crow's-foot mermaid: `docs/figures/student-course.mmd`.

## Books / Authors / Categories (reference only)

Source: `498erd-example/questions/erd_e3_books/question.html`, a `pl-uml-element` question. The UML answer listed three classes and two unlabeled associations:

```
[Books|isbn {PK}; title; pubYear; genre]
[Authors|authorId {PK}; name]
[Categories|name {PK}; displayOrder]
[Books] 0..* - 1..* [Authors]
[Books] 0..* - 0..1 [Categories]
```

JSON translation: `examples/books-authors.json`. Relationship names `written_by` and `categorized` are the verbs from that question text. They are not a second graded PrairieLearn question.

Cardinalities follow the UML ranges and the prose: authors are kept even if they have not published; a book that is categorized sits in one category.

## Weak entity snippet

Source: `elements/pl-er-diagram-builder/README.md`.

`Pay` is weak with key `pay_no` and attribute `hours`. `paid_by` is an identifying relationship to `Employee` (Employee one / total, Pay many / partial). The README does not define Employee attributes, so `examples/employee-pay.json` leaves them empty.
