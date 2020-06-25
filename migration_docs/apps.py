from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command
from django.db.models.signals import pre_migrate


_current_migration_run = None


def sync_docs_on_pre_migrate(plan, interactive, **kwargs):
    """
    Sync docs on pre_migrate.

    pre_migrate is called for every django app. We only want to sync
    docs before all migrations begin. We achieve this by keeping
    track of the ID of the migration plan and only running sync
    when the plan changes
    """
    global _current_migration_run

    if (
        _current_migration_run != id(plan)
        and getattr(settings, 'MIGRATION_DOCS_PRE_MIGRATE_SYNC', False)
        and interactive
    ):
        call_command('migration_docs', 'sync')

    _current_migration_run = id(plan)


class MigrationDocsConfig(AppConfig):
    name = 'migration_docs'
    verbose_name = 'Migration Docs'

    def ready(self):
        """
        Listen for pre-migrate signals and prompt for migration docs.
        """
        pre_migrate.connect(
            sync_docs_on_pre_migrate, dispatch_uid='sync_docs_on_pre_migrate'
        )
