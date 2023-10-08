import django

from migration_docs.core import Migration, Migrations, bootstrap, check, show, sync, update
from migration_docs.version import __version__

__all__ = [
    "bootstrap",
    "check",
    "show",
    "sync",
    "update",
    "Migration",
    "Migrations",
    "__version__",
]

if django.VERSION < (3, 2):  # pragma: no cover
    default_app_config = "migration_docs.apps.MigrationDocsConfig"

del django
