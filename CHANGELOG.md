# Changelog

## 1.3.0 (2024-08-24)

### Feature

  - Added Django 5.1 support.
  - Dropped Django 3.2 support.

## 1.2.1 (2024-04-06)

### Trivial

  - Fix ReadTheDocs builds. [Wesley Kendall, 72e66f9]

## 1.2.0 (2023-11-26)

### Feature

  - Django 5.0 compatibility [Wesley Kendall, 952becf]

    Support and test against Django 5 with psycopg2 and psycopg3.

## 1.1.1 (2023-10-09)

### Trivial

  - Added Opus10 branding to docs [Wesley Kendall, 3bd7da8]

## 1.1.0 (2023-10-08)

### Feature

  - Add Python 3.12 support and use Mkdocs for documentation [Wesley Kendall, cf2b2aa]

    Python 3.12 and Postgres 16 are supported now, along with having revamped docs using Mkdocs and the Material theme.

    Python 3.7 support was dropped.
  - Added Python 3.11, Django 4.2, and Psycopg 3 support [Wesley Kendall, d8cac40]

    Adds Python 3.11, Django 4.2, and Psycopg 3 support along with tests for multiple Postgres versions. Drops support for Django 2.2.

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
