# Changelog
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

