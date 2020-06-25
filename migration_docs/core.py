import collections
import hashlib
import inspect
import os
import pathlib

import click
from django.conf import settings
from django.db import connections
from django.db.migrations import executor as django_migration_executor
from django.db.migrations import loader as django_migration_loader
from django.utils.functional import cached_property
import formaldict
import jinja2
import yaml

from migration_docs import utils


# The default Jinja template for showing migrations
DEFAULT_MIGRATION_TEMPLATE = """
{% for migration in migrations %}
[{% if migration.applied %}X{% else %} {% endif %}] {{ migration.label }}
{% endfor %}
""".strip()


def _get_migration_docs_file_root():
    """
    Get the root path to migration docs configuration files.
    """
    return os.path.join(os.getcwd(), '.migration-docs')


def _get_migration_docs_file_path(file_name):
    """
    Get the path to a migration docs file.
    """
    return os.path.join(_get_migration_docs_file_root(), file_name)


def _no_msg(msg, fg='green'):
    """A message printer that does nothing"""
    pass


def _pretty_msg(msg, fg='green'):
    """A pretty message printer"""
    click.secho(msg, fg=fg)


class Migration:
    """A migration and its associated docs.

    Migrations are typically loaded and accessed via the parent `Migrations`
    object. When loaded, the Migration has access to core migration
    attributes (e.g. ``atomic``, ``sql``, etc) and also has attributes
    for every attribute collected in the documentation schema. For example,
    if the user configured a ``type`` attribute to be collected
    in ``.migration-docs/migration.yaml``, it would be accessible as
    a ``type`` attribute on this object.
    """

    def __init__(self, node, *, executor, loader, docs):
        self._node = node
        self._executor = executor
        self._loader = loader
        self._docs = docs

    @property
    def applied(self):
        """True if the migration has been applied"""
        return (self.app_label, self.name) in self._loader.applied_migrations

    @cached_property
    def hash(self):
        """The MD5 hash of the migration file"""
        return hashlib.md5(
            inspect.getsource(inspect.getmodule(self._node)).encode()
        ).hexdigest()

    @property
    def atomic(self):
        """True if the migration is executed in a transaction"""
        return self._node.atomic

    @property
    def app_label(self):
        """The Django app label of the migration"""
        return self._node.app_label

    @property
    def name(self):
        """The name of the migration (e.g. 0001_initial)"""
        return self._node.name

    @property
    def operations(self):
        """The raw list of migration operation objects"""
        return self._node.operations

    @property
    def operations_str(self):
        """String representations of the migration operations"""
        return [str(operation) for operation in self.operations]

    @cached_property
    def sql(self):
        """The raw SQL for the migration"""
        try:
            sql_statements = self._executor.collect_sql([(self._node, False)])
            return '\n'.join(sql_statements)
        except Exception as exc:
            return f'Error obtaining SQL - "{exc}"'

    @property
    def label(self):
        """The unique identifying label of the migration"""
        return str(self._node)

    def __str__(self):
        return self.label

    def __getattribute__(self, attr):
        """
        Allows migration docs to be accessed as attributes on the Migration
        or the migration docs.

        Doing this provides the ability for users to filter Migrations
        by any documented attribute.
        """
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            if self._docs.get(self.label) and attr in self._docs[self.label]:
                return self._docs[self.label][attr]
            elif attr in self._docs.schema:
                return None
            else:
                raise

    def set_docs(self, prompt=True, defaults=None):
        """Set docs about a migration

        Args:
            prompt (boolean, default=False): True if collecting data from
                a user.
            defaults (dict, default=None): When prompting, use these values
                as defaults.
        """
        if self.label not in self._docs:
            self._docs[self.label] = {}
        self._docs[self.label]['_hash'] = self.hash
        self._docs[self.label]['atomic'] = self.atomic
        self._docs[self.label]['sql'] = self.sql

        if prompt:
            self._docs[self.label].update(
                self._docs.schema.prompt(defaults=defaults)
            )

        self._docs.save()


class Migrations(utils.FilterableUserList):
    """
    A filterable and groupable list of migrations and their associated
    migration docs.
    """

    def __init__(self, using='default', loader=None, executor=None):
        connection = connections[using]
        self._loader = loader or django_migration_loader.MigrationLoader(
            connection, ignore_no_migrations=True
        )
        self._graph = self._loader.graph
        self._executor = django_migration_executor.MigrationExecutor(
            connection
        )
        self._docs = MigrationDocs()

        self._migrations = {
            str(node): Migration(
                node,
                executor=self._executor,
                loader=self._loader,
                docs=self._docs,
            )
            for node in self._graph.nodes.values()
        }

        # Construct a plan of migrations. Set the ``data`` as the plan so
        # that this datastructure is a list
        targets = self._graph.leaf_nodes()
        self.data = []
        seen = set()
        for target in targets:
            for migration in self._graph.forwards_plan(target):
                if migration not in seen:  # pragma: no branch
                    # We don't cover the "else" branch of this statement since
                    # our test models dont have complex enough migrations
                    self.data.append(
                        self._migrations[str(self._graph.nodes[migration])]
                    )
                    seen.add(migration)

    def __getitem__(self, i):
        """Allow accessing by list index or migration label"""
        if isinstance(i, int):
            return self.data[i]
        else:
            return self._migrations[i]

    def filter_by_missing_docs(self):
        return self.intersect('label', set(self._migrations) - set(self._docs))

    def filter_by_stale_docs(self):
        labels = [
            migration
            for migration, docs in self._docs.items()
            if docs is not None
            and migration in self._migrations
            and docs['_hash'] != self._migrations[migration].hash
        ]
        return self.intersect('label', labels)

    @property
    def excess_docs(self):
        return set(self._docs) - set(self._migrations)

    def prune_excess_docs(self):
        for label in self.excess_docs:
            del self._docs[label]

        self._docs.save()

    def bootstrap_docs(self):
        """Bootstraps all migration docs to empty values."""
        self._docs = MigrationDocs(data={str(node): None for node in self})
        self._docs.save()


class MigrationDocs(collections.UserDict):
    def __init__(self, data=None, msg=_pretty_msg):
        """
        Represents migration docs as a dictionary. Reads and persists docs as
        YAML.

        Args:
            msg (func): Function for printing messages to the user.
            data (dict, default=None): Data to use as migration docs. If None,
                load migration docs from the docs.yaml file.
        """
        self._msg = msg

        if not data:
            docs_file = _get_migration_docs_file_path('docs.yaml')
            try:
                with open(docs_file, 'r') as f:
                    self.data = yaml.safe_load(f)
            except IOError:
                self.data = {}
            except Exception as exc:
                raise RuntimeError(
                    'django-migration-docs: docs.yaml is corrupt and cannot'
                    ' be parsed as YAML. Please fix the'
                    ' .migration-docs/docs.yaml file.'
                ) from exc
        else:
            self.data = data

    @cached_property
    def schema(self):
        """Loads the migration doc schema

        If not configured, returns a schema with a point of contact and
        description for the migration.
        """
        try:
            with open(
                _get_migration_docs_file_path('migration.yaml'), 'r'
            ) as f:
                schema = yaml.safe_load(f)
        except IOError:
            schema = [
                {
                    'label': 'point_of_contact',
                    'help': 'The point of contact for this migration.',
                },
                {
                    'label': 'description',
                    'help': 'An in-depth description of the migration.',
                    'multiline': True,
                },
            ]
        except Exception as exc:
            raise RuntimeError(
                'django-migration-docs: migration.yaml is corrupt and cannot'
                ' be parsed as YAML. Please fix the'
                ' .migration-docs/migration.yaml file.'
            ) from exc

        return formaldict.Schema(schema)

    def save(self):
        """Save all migration docs

        Ensure docs are ordered when persisted to keep YAML consistently
        ordered
        """
        docs_file = _get_migration_docs_file_path('docs.yaml')

        yaml.Dumper.add_representer(
            collections.OrderedDict,
            lambda dumper, data: dumper.represent_mapping(
                'tag:yaml.org,2002:map', data.items()
            ),
        )
        ordered_docs = collections.OrderedDict(
            (label, docs) for label, docs in sorted(self.data.items())
        )
        yaml_str = yaml.dump(ordered_docs, Dumper=yaml.Dumper)
        pathlib.Path(docs_file).parent.mkdir(parents=True, exist_ok=True)
        with open(docs_file, 'w+') as f:
            f.write(yaml_str)


def bootstrap(msg=_pretty_msg):
    """
    Bootstrap migration docs with filler values when integrating docs
    with a project for the first time.

    Args:
        msg (func): A message printer for showing messages to the user.

    Raises:
        RuntimeError: When migration docs have already been synced
    """
    if MigrationDocs():
        raise RuntimeError(
            'Cannot bootstrap when migration docs have already been synced.'
        )

    Migrations().bootstrap_docs()

    msg('django-migration-docs: Docs successfully bootstrapped.')


def sync(msg=_pretty_msg):
    """
    Sync new migrations with the migration docs and prune migrations that
    no longer exist.

    Args:
        msg (func): A message printer for showing messages to the user.
    """
    # Run any configured pre-sync hooks
    pre_sync_hooks = getattr(settings, 'MIGRATION_DOCS_PRE_SYNC_HOOKS', [])
    if pre_sync_hooks:
        msg(f'django-migration-docs: Running pre-sync hooks...')
        for pre_sync_hook in pre_sync_hooks:
            msg(pre_sync_hook, fg='yellow')
            utils.shell(pre_sync_hook)

    migrations = Migrations()
    missing_docs = migrations.filter_by_missing_docs()
    stale_docs = migrations.filter_by_stale_docs()
    excess_docs = migrations.excess_docs

    # Collect information for new migrations
    if missing_docs:
        msg(
            'django-migration-docs: Found no docs for'
            f' {len(missing_docs)} migration(s). Please enter'
            ' more information.'
        )
        for migration in missing_docs:
            msg(f'{migration.label}:', fg='yellow')
            migration.set_docs()

    # Update any stale documentation
    if stale_docs:
        msg(
            f'django-migration-docs: Found {len(stale_docs)} stale'
            ' migration doc(s). Docs updated automatically.'
        )
        for migration in stale_docs:
            migration.set_docs(prompt=False)

    # Delete old migrations
    if excess_docs:
        msg(
            f'django-migration-docs: Found docs for {len(excess_docs)}'
            ' deleted migration(s). Docs were removed.'
        )
        migrations.prune_excess_docs()

    msg('django-migration-docs: Successfully synced migration docs.')


def update(migrations, msg=_pretty_msg):
    """
    Update migration docs for specific migrations.

    Args:
        migrations (List[str]): A list of migration labels to update
            (e.g. users.0001_initial).
        msg (func): A message printer for showing messages to the user.
    """
    migration_objs = Migrations()
    for migration in migrations:
        msg(f'{migration}:', fg='yellow')
        try:
            migration_objs[migration].set_docs()
        except KeyError:
            msg(
                f'Migration with label "{migration}" does not exist.', fg='red'
            )


def check(msg=_pretty_msg):
    """
    Check migration notes. Return False if any of the conditions hold true:
    - There are migrations without docs.
    - There are documented migrations that no longer exist.
    - There are stale migration docs.

    Args:
        msg (func): A message printer for showing messages to the user.

    Raises:
        bool: True when the migration docs are up to date, False otherwise.
    """
    migrations = Migrations()
    missing_docs = migrations.filter_by_missing_docs()
    stale_docs = migrations.filter_by_stale_docs()
    excess_docs = migrations.excess_docs

    if missing_docs:
        msg(
            f'django-migration-docs: Found no docs for {len(missing_docs)}'
            ' migration(s).',
            fg='red',
        )

    if stale_docs:
        msg(
            f'django-migration-docs: Found {len(stale_docs)} stale'
            ' migration doc(s).',
            fg='red',
        )

    if excess_docs:
        msg(
            f'django-migration-docs: Found docs for {len(excess_docs)}'
            ' deleted migration(s).',
            fg='red',
        )

    if missing_docs or stale_docs or excess_docs:
        msg(
            'django-migration-docs: Run "manage.py migration_docs sync" to'
            ' fix errors.',
            fg='red',
        )
        return False
    else:
        msg('django-migration-docs: Migration docs are up to date.')
        return True


def show(app_labels=None, unapplied=False, style='default'):
    """Shows migration docs to the user

    Args:
        app_labels (List[str]): App labels to limit the shown migrations to.
        unapplied (bool, default=False): Only show unapplied migrations.
        style (str, default='default'): The style to use when rendering.
            Corresponds to a Jinja template stored in
            ``.migration-docs/{style}_show.tpl``.

    Returns:
        str: The rendered migration list.
    """
    migrations = Migrations()

    if app_labels:
        migrations = migrations.intersect('app_label', app_labels)

    if unapplied:
        migrations = migrations.filter('applied', False)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(_get_migration_docs_file_root()),
        trim_blocks=True,
    )
    template_file = 'show.tpl' if style == 'default' else f'show_{style}.tpl'
    try:
        template = env.get_template(template_file)
    except jinja2.exceptions.TemplateNotFound:
        if style == 'default':
            # Use the default migration template if the user didn't provide one
            template = jinja2.Template(
                DEFAULT_MIGRATION_TEMPLATE, trim_blocks=True
            )
        else:
            raise

    rendered = template.render(
        migrations=migrations, app_labels=app_labels, unapplied=unapplied
    )

    return rendered
