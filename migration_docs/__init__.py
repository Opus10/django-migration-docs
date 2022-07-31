import django

from migration_docs.core import bootstrap
from migration_docs.core import check
from migration_docs.core import Migration
from migration_docs.core import Migrations
from migration_docs.core import show
from migration_docs.core import sync
from migration_docs.core import update
from migration_docs.version import __version__


__all__ = [
    'bootstrap',
    'check',
    'show',
    'sync',
    'update',
    'Migration',
    'Migrations',
    '__version__',
]

if django.VERSION < (3, 2):
    default_app_config = 'migration_docs.apps.MigrationDocsConfig'

del django
