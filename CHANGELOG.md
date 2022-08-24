# Changelog
## 1.0.5 (2022-08-24)
### Trivial
  - Fix ReadTheDocs builds [Wes Kendall, 08d08f2]

## 1.0.4 (2022-08-20)
### Trivial
  - Fix release note rendering and code formatting changes [Wes Kendall, 215910b]

## 1.0.3 (2022-07-31)
### Trivial
  - Updated with the latest Django template, fixing doc builds [Wes Kendall, cfbe987]

## 1.0.2 (2022-03-13)
### Trivial
  - Updated with the latest template, dropping py3.6 support and adding Django 4 support [Wes Kendall, fa37002]
  - Updated to the latest Django template [Wes Kendall, dec0d8e]

## 1.0.1 (2020-06-29)
### Trivial
  - Added more docs to the README [Wes Kendall, 6b0fe2d]

## 1.0.0 (2020-06-25)
### Api-Break
  - Initial release of django-migration-docs [Wes Kendall, 24a8798]

    The first version of django-migration-docs provides the following
    commands for maintaining additional documentation about migrations
    in a Django project:
    1. ``migration_docs bootstrap`` - To bootstrap migration docs for the first time.
    2. ``migration_docs sync`` - To keep migration docs in sync by adding, updating
       and removing docs for migrations.
    3. ``migration_docs update`` - For updating docs about specific migrations.
    4. ``migration_docs show`` - For rendering migration docs using a configurable
       jinja template.
    5. ``migration_docs check`` - For checking that the docs are in sync.

