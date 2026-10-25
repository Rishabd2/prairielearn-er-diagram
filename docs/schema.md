# Schemas in this repository

All three schemas are original to this repository.

## Cardinality convention

A participant's `cardinality` describes **that entity's own side** of the relationship: the
maximum number of instances of this entity that can be related to one instance (or one combination
of instances) of the other participant(s). It is drawn as `1` or `N` on the line next to the entity,
as in Chen notation. `participation` is `total` when every instance of the entity must take part in
the relationship, and is drawn as a double line.

Example: in `paid_by`, Pay is `many` (one employee has many pay records) and Employee is `one`
(each pay record belongs to one employee).

## Student / Course (graded sample)

Source: `questions/element/erDiagram/` and `examples/student-course.json`.

| Kind | Name | Keys | Other attributes | Notes |
| --- | --- | --- | --- | --- |
| Entity | Student | student_id | name, email | |
| Entity | Course | course_id | title | |
| Relationship | Enrolls | | semester, grade | Student many / total. Course many / partial. |

A course has many students and a student takes many courses. Every student is enrolled in at least
one course (total); a course may have no enrollments yet (partial).

Chen drawing: `docs/figures/student-course.{svg,png}`. Crow's-foot Mermaid: `docs/figures/student-course.mmd`.

## Departments and professors (reference)

Source: `examples/department-professor.json`.

| Kind | Name | Keys | Other attributes | Notes |
| --- | --- | --- | --- | --- |
| Entity | Department | dept_code | dept_name, building | |
| Entity | Professor | prof_id | name, office | |
| Relationship | works_in | | start_date | Professor many / total. Department one / partial. |
| Relationship | chairs | | | Professor one / partial. Department one / total. |

`works_in`: each professor works in exactly one department (Department `one`, Professor total); a
department has many professors and a new department may have none yet (Professor `many`,
Department partial). `chairs`: every department has exactly one chair (Professor `one`, Department
total); a professor chairs at most one department and most chair none (Department `one`, Professor
partial).

Chen drawing: `docs/figures/department-professor.{svg,png}`. Crow's-foot Mermaid: `docs/figures/department-professor.mmd`.

## Employee / Pay (weak entity, starter sample)

Source: `questions/element/erDiagramStarter/` and `examples/employee-pay.json`.

| Kind | Name | Keys | Other attributes | Notes |
| --- | --- | --- | --- | --- |
| Entity | Employee | emp_id | name | |
| Entity (weak) | Pay | pay_no (partial key) | hours | |
| Relationship (identifying) | paid_by | | | Employee one / partial. Pay many / total. |

Pay is weak: `pay_no` is only unique within one employee, so a pay record is identified by
(`emp_id`, `pay_no`). A weak entity always participates totally in its identifying relationship, so
Pay is total. An employee can have many pay records (Pay `many`); a newly hired employee may have
none (Employee partial). Each pay record belongs to one employee (Employee `one`).

Chen drawing: `docs/figures/employee-pay.{svg,png}`.
