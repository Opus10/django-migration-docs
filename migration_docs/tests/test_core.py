"""Unit tests for the core migration_docs module"""
from contextlib import ExitStack as does_not_raise

from django.db.migrations.executor import MigrationExecutor
import pytest

from migration_docs import core


@pytest.mark.django_db
@pytest.mark.parametrize(
    'migration_name, attribute, expected_exception, expected_value',
    [
        ('tests.0001_initial', 'applied', does_not_raise(), True),
        (
            'tests.0001_initial',
            'hash',
            does_not_raise(),
            'd1468bb233398bcc089bd33151f51cd3',
        ),
        ('tests.0002_testmodel_field2', 'atomic', does_not_raise(), True),
        (
            'tests.0002_testmodel_field2',
            'app_label',
            does_not_raise(),
            'tests',
        ),
        (
            'tests.0002_testmodel_field2',
            'name',
            does_not_raise(),
            '0002_testmodel_field2',
        ),
        (
            'tests.0002_testmodel_field2',
            'operations_str',
            does_not_raise(),
            [
                "<AddField  model_name='testmodel', name='field2', "
                "field=<django.db.models.fields.CharField>, "
                "preserve_default=False>"
            ],
        ),
        (
            'tests.0002_testmodel_field2',
            'sql',
            does_not_raise(),
            '--\n-- Add field field2 to testmodel\n--\nALTER TABLE '
            '"tests_testmodel" ADD COLUMN "field2" varchar(100) DEFAULT '
            '\'test\' NOT NULL;\nALTER TABLE "tests_testmodel" ALTER COLUMN '
            '"field2" DROP DEFAULT;',
        ),
        (
            'tests.0002_testmodel_field2',
            'label',
            does_not_raise(),
            'tests.0002_testmodel_field2',
        ),
        (
            'tests.0002_testmodel_field2',
            'invalid',
            pytest.raises(AttributeError),
            None,
        ),
    ],
)
def test_migration_properties(
    migration_name, attribute, expected_exception, expected_value
):
    """Asserts various properties of migrations from the test models"""

    migrations = core.Migrations()
    migration = migrations._migrations[migration_name]
    with expected_exception:
        assert getattr(migration, attribute) == expected_value


@pytest.mark.django_db
def test_bad_migration_sql_collection(mocker):
    mocker.patch.object(
        MigrationExecutor,
        'collect_sql',
        autospec=True,
        side_effect=RuntimeError('Cannot collect.'),
    )

    migrations = core.Migrations()

    assert len(migrations) == 3
    for migration in migrations:
        assert migration.sql == 'Error obtaining SQL - "Cannot collect."'


def test_migration_docs_no_files():
    """
    Verify the MigrationDocs object loads no docs when the
    .migration-docs/docs.yaml file doesnt exist. Also verifies the
    default schema is present when .migration-docs/migration.yaml does
    not exist
    """
    docs = core.MigrationDocs()
    assert docs.data == {}
    assert docs.schema._raw_schema == [
        {
            'help': 'The point of contact for this migration.',
            'label': 'point_of_contact',
        },
        {
            'help': 'An in-depth description of the migration.',
            'label': 'description',
            'multiline': True,
        },
    ]


def test_migration_docs_invalid_yaml(mocker, tmp_path):
    """Checks the error that is raised when the docs file is invalid yaml"""
    migration_docs_root = tmp_path / '.migration-docs'
    migration_docs_root.mkdir()

    migration_schema = migration_docs_root / 'docs.yaml'
    migration_schema.write_text('[invalid yaml')

    mocker.patch(
        'migration_docs.core._get_migration_docs_file_root',
        return_value=str(migration_docs_root),
        autospec=True,
    )

    with pytest.raises(RuntimeError, match='docs.yaml is corrupt'):
        core.MigrationDocs()


def test_migration_schema_invalid_yaml(mocker, tmp_path):
    """Checks the error that is raised when the schema file is invalid yaml"""
    migration_docs_root = tmp_path / '.migration-docs'
    migration_docs_root.mkdir()

    migration_schema = migration_docs_root / 'migration.yaml'
    migration_schema.write_text('[invalid yaml')

    mocker.patch(
        'migration_docs.core._get_migration_docs_file_root',
        return_value=str(migration_docs_root),
        autospec=True,
    )

    with pytest.raises(RuntimeError, match='migration.yaml is corrupt'):
        core.MigrationDocs().schema
