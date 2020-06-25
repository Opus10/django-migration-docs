"""Integration tests for django-migration-docs"""
from contextlib import ExitStack as does_not_raise
import subprocess
from unittest import mock

from django.core.management import call_command
import formaldict
import jinja2.exceptions
import pytest
import yaml

from migration_docs import core
from migration_docs import utils


@pytest.fixture()
def migration_docs_config(tmp_path, mocker):
    """Creates an example migration docs configuration for integration tests"""
    migration_docs_root = tmp_path / '.migration-docs'
    migration_docs_root.mkdir()

    migration_schema = migration_docs_root / 'migration.yaml'
    migration_schema.write_text(
        '- label: point_of_contact\n'
        '  help: The person responsible for the migration.\n'
        '  matches: .*@gmail.com\n'
        '\n'
        '- label: type\n'
        '  help: The type of migration.\n'
        '  choices:\n'
        '      - before\n'
        '      - after\n'
        '\n'
        '- label: description\n'
        '  help: An in-depth description of the migration.\n'
        '  multiline: True\n'
        '\n'
        '- label: jira\n'
        '  name: Jira\n'
        '  help: Jira Ticket ID.\n'
        '  type: string\n'
        '  condition: ["!=", "type", "trivial"]\n'
        '  matches: WEB-[\\d]+\n'
    )

    show_template = migration_docs_root / 'show.tpl'
    show_template.write_text(
        '{% for type, by_type in migrations.group("type").items() %}\n'
        '# Deployment order: {{ type|default("unknown", True) }}\n'
        '{% for migration in by_type %}\n'
        '[{% if migration.applied %}X{% else %} {% endif %}]'
        ' {{ migration.label }}\n'
        '{% endfor %}\n'
        '{% endfor %}\n'
    )

    mocker.patch(
        'migration_docs.core._get_migration_docs_file_root',
        return_value=str(migration_docs_root),
        autospec=True,
    )

    yield migration_docs_root


@pytest.mark.django_db
@pytest.mark.parametrize(
    'management_args, docs, expected_exception, expected_output',
    [
        (
            [],
            {},
            does_not_raise(),
            (
                '# Deployment order: unknown\n'
                '[X] tests.0001_initial\n'
                '[X] tests.0002_testmodel_field2\n'
                '[X] tests.0003_testmodel_field3\n'
            ),
        ),
        (['--unapplied'], {}, does_not_raise(), ''),
        (
            ['tests'],
            {},
            does_not_raise(),
            (
                '# Deployment order: unknown\n'
                '[X] tests.0001_initial\n'
                '[X] tests.0002_testmodel_field2\n'
                '[X] tests.0003_testmodel_field3\n'
            ),
        ),
        (
            ['tests'],
            {
                'tests.0001_initial': {'type': 'before'},
                'tests.0002_testmodel_field2': {'type': 'before'},
                'tests.0003_testmodel_field3': {'type': 'after'},
            },
            does_not_raise(),
            (
                '# Deployment order: before\n'
                '[X] tests.0001_initial\n'
                '[X] tests.0002_testmodel_field2\n'
                '# Deployment order: after\n'
                '[X] tests.0003_testmodel_field3\n'
            ),
        ),
        (['app_with_no_migrations'], {}, does_not_raise(), ''),
        (  # Try to show docs with an invalid template
            ['--style=invalid'],
            {},
            pytest.raises(jinja2.exceptions.TemplateNotFound),
            '',
        ),
    ],
)
def test_migration_docs_show(
    capsys,
    migration_docs_config,
    management_args,
    docs,
    expected_exception,
    expected_output,
):
    """
    Integration test for manage.py migration_docs show
    """
    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(yaml.safe_dump(docs))

    with expected_exception:
        call_command('migration_docs', 'show', *management_args)
        captured = capsys.readouterr()
        assert captured.out == expected_output


@pytest.mark.django_db
@pytest.mark.parametrize(
    'initial_docs, pre_sync_hooks, user_input, expected_output, expected_docs',
    [
        (
            # Tests the scenario where there are no initial docs. 3 docs
            # should be added.
            {},
            [],
            [{'type': 'before'}, {'type': 'after'}, {'type': 'before'}],
            (
                'django-migration-docs: Found no docs for 3 migration(s).'
                ' Please enter more information.\n'
                'tests.0001_initial:\n'
                'tests.0002_testmodel_field2:\n'
                'tests.0003_testmodel_field3:\n'
                'django-migration-docs: Successfully synced migration docs.\n'
            ),
            {
                # Check the full SQL here, but dont do it for any other
                # scenarios for the sake of verbosity
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                    'atomic': True,
                    'type': 'before',
                    'sql': '--\n'
                    '-- Create model TestModel\n'
                    '--\n'
                    'CREATE TABLE "tests_testmodel" ("id" serial '
                    'NOT NULL PRIMARY KEY, "field1" varchar(100) '
                    'NOT NULL);',
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c',
                    'atomic': True,
                    'type': 'after',
                    'sql': (
                        '--\n'
                        '-- Add field field2 to testmodel\n'
                        '--\n'
                        'ALTER TABLE "tests_testmodel" ADD '
                        'COLUMN "field2" varchar(100) DEFAULT '
                        "'test' NOT NULL;\n"
                        'ALTER TABLE "tests_testmodel" ALTER '
                        'COLUMN "field2" DROP DEFAULT;'
                    ),
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f',
                    'atomic': True,
                    'type': 'before',
                    'sql': (
                        '--\n'
                        '-- Add field field3 to testmodel\n'
                        '--\n'
                        'ALTER TABLE "tests_testmodel" ADD '
                        'COLUMN "field3" varchar(100) DEFAULT '
                        "'test' NOT NULL;\n"
                        'ALTER TABLE "tests_testmodel" ALTER '
                        'COLUMN "field3" DROP DEFAULT;'
                    ),
                },
            },
        ),
        (
            # Test the scenario where one migration has been updated since
            # docs were last synced
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                    'description': 'This is a description.',
                },
                'tests.0002_testmodel_field2': {
                    '_hash': 'outdated_hash',
                    'description': 'This is another description.',
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f',
                    'description': 'And description number 3.',
                },
            },
            [],
            [],
            (
                'django-migration-docs: Found 1 stale migration doc(s).'
                ' Docs updated automatically.\n'
                'django-migration-docs: Successfully synced migration docs.\n'
            ),
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                    'description': 'This is a description.',
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c',
                    'description': 'This is another description.',
                    'atomic': True,
                    'sql': mock.ANY,
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f',
                    'description': 'And description number 3.',
                },
            },
        ),
        (
            # Test the scenario where there are extra migration docs that
            # should be deleted
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
                'deleted_migration': {'_hash': 'deleted_hash_value'},
            },
            [],
            [],
            (
                'django-migration-docs: Found docs for 1 deleted migration(s).'
                ' Docs were removed.\n'
                'django-migration-docs: Successfully synced migration docs.\n'
            ),
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
        ),
        (
            # Test the scenario where all docs are up to date
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
            [],
            [],
            ('django-migration-docs: Successfully synced migration docs.\n'),
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
        ),
        (
            # Test the scenario where all docs are up to date and some
            # were bootstrapped
            {
                'tests.0001_initial': None,
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
            [],
            [],
            ('django-migration-docs: Successfully synced migration docs.\n'),
            {
                'tests.0001_initial': None,
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
        ),
        (
            # Test the scenario where all docs are up to date and some
            # were bootstrapped. Configures pre-sync hooks
            {
                'tests.0001_initial': None,
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
            ['black .'],
            [],
            (
                'django-migration-docs: Running pre-sync hooks...\n'
                'black .\n'
                'django-migration-docs: Successfully synced migration docs.\n'
            ),
            {
                'tests.0001_initial': None,
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
        ),
    ],
)
def test_migration_docs_sync(
    capsys,
    mocker,
    settings,
    migration_docs_config,
    initial_docs,
    pre_sync_hooks,
    user_input,
    expected_output,
    expected_docs,
):
    """
    Integration test for manage.py migration_docs sync
    """
    settings.MIGRATION_DOCS_PRE_SYNC_HOOKS = pre_sync_hooks

    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(yaml.safe_dump(initial_docs))

    mocker.patch.object(formaldict.Schema, 'prompt', side_effect=user_input)

    call_command('migration_docs', 'sync')
    captured = capsys.readouterr()
    assert captured.out == expected_output
    with open(docs_file, 'r') as f:
        assert yaml.safe_load(f) == expected_docs


@pytest.mark.django_db
@pytest.mark.parametrize(
    'initial_docs, management_args, user_input, expected_output, expected_docs',
    [
        (
            # Tests successfully updating docs
            {},
            ['tests.0001_initial', 'tests.0002_testmodel_field2'],
            [{'type': 'before'}, {'type': 'after'}],
            ('tests.0001_initial:\n' 'tests.0002_testmodel_field2:\n'),
            {
                # Check the full SQL here, but dont do it for any other
                # scenarios for the sake of verbosity
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                    'atomic': True,
                    'type': 'before',
                    'sql': '--\n'
                    '-- Create model TestModel\n'
                    '--\n'
                    'CREATE TABLE "tests_testmodel" ("id" serial '
                    'NOT NULL PRIMARY KEY, "field1" varchar(100) '
                    'NOT NULL);',
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c',
                    'atomic': True,
                    'type': 'after',
                    'sql': (
                        '--\n'
                        '-- Add field field2 to testmodel\n'
                        '--\n'
                        'ALTER TABLE "tests_testmodel" ADD '
                        'COLUMN "field2" varchar(100) DEFAULT '
                        "'test' NOT NULL;\n"
                        'ALTER TABLE "tests_testmodel" ALTER '
                        'COLUMN "field2" DROP DEFAULT;'
                    ),
                },
            },
        ),
        (
            # Test the scenario where migrations dont exist
            # Tests successfully updating docs
            {},
            ['invalid', 'tests.0001_initial'],
            [{'type': 'before'}],
            (
                'invalid:\n'
                'Migration with label "invalid" does not exist.\n'
                'tests.0001_initial:\n'
            ),
            {
                # Check the full SQL here, but dont do it for any other
                # scenarios for the sake of verbosity
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                    'atomic': True,
                    'type': 'before',
                    'sql': '--\n'
                    '-- Create model TestModel\n'
                    '--\n'
                    'CREATE TABLE "tests_testmodel" ("id" serial '
                    'NOT NULL PRIMARY KEY, "field1" varchar(100) '
                    'NOT NULL);',
                }
            },
        ),
    ],
)
def test_migration_docs_update(
    capsys,
    mocker,
    migration_docs_config,
    management_args,
    initial_docs,
    user_input,
    expected_output,
    expected_docs,
):
    """
    Integration test for manage.py migration_docs update
    """
    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(yaml.safe_dump(initial_docs))

    mocker.patch.object(formaldict.Schema, 'prompt', side_effect=user_input)

    call_command('migration_docs', 'update', *management_args)
    captured = capsys.readouterr()
    assert captured.out == expected_output
    with open(docs_file, 'r') as f:
        assert yaml.safe_load(f) == expected_docs


@pytest.mark.django_db
@pytest.mark.parametrize(
    'initial_docs, expected_output, expected_exit_code',
    [
        (
            # Tests the scenario where there are no initial docs.
            {},
            (
                'django-migration-docs: Found no docs for 3 migration(s).\n'
                'django-migration-docs: Run "manage.py migration_docs sync"'
                ' to fix errors.\n'
            ),
            1,
        ),
        (
            # Test the scenario where one migration has been updated since
            # docs were last synced
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {'_hash': 'outdated_hash'},
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
            (
                'django-migration-docs: Found 1 stale migration doc(s).\n'
                'django-migration-docs: Run "manage.py migration_docs sync"'
                ' to fix errors.\n'
            ),
            1,
        ),
        (
            # Test the scenario where there are extra migration docs that
            # should be deleted
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
                'deleted_migration': None,
            },
            (
                'django-migration-docs: Found docs for 1 deleted migration(s).'
                '\n'
                'django-migration-docs: Run "manage.py migration_docs sync"'
                ' to fix errors.\n'
            ),
            1,
        ),
        (
            # Test the scenario where all docs are up to date
            {
                'tests.0001_initial': {
                    '_hash': 'd1468bb233398bcc089bd33151f51cd3'
                },
                'tests.0002_testmodel_field2': {
                    '_hash': '8cb7f6747d4ef78074521309d5d05a2c'
                },
                'tests.0003_testmodel_field3': {
                    '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f'
                },
            },
            ('django-migration-docs: Migration docs are up to date.\n'),
            0,
        ),
    ],
)
def test_migration_docs_check(
    capsys,
    mocker,
    migration_docs_config,
    initial_docs,
    expected_output,
    expected_exit_code,
):
    """
    Integration test for manage.py migration_docs check
    """
    patched_exit = mocker.patch('sys.exit', autospec=True)
    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(yaml.safe_dump(initial_docs))

    call_command('migration_docs', 'check')
    captured = capsys.readouterr()
    assert captured.out == expected_output
    patched_exit.assert_called_once_with(expected_exit_code)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'initial_docs, expected_exception, expected_output, expected_docs',
    [
        (  # Tests the scenario where there were previously docs
            {'tests.0001_initial': None},
            pytest.raises(RuntimeError),
            None,
            None,
        ),
        (  # Test the scenario where there were no previous docs
            {},
            does_not_raise(),
            'django-migration-docs: Docs successfully bootstrapped.\n',
            {
                'tests.0001_initial': None,
                'tests.0002_testmodel_field2': None,
                'tests.0003_testmodel_field3': None,
            },
        ),
    ],
)
def test_migration_docs_bootstrap(
    capsys,
    mocker,
    migration_docs_config,
    initial_docs,
    expected_exception,
    expected_output,
    expected_docs,
):
    """
    Integration test for manage.py migration_docs sync
    """
    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(yaml.safe_dump(initial_docs))

    with expected_exception:
        call_command('migration_docs', 'bootstrap')
        captured = capsys.readouterr()
        assert captured.out == expected_output
        with open(docs_file, 'r') as f:
            assert yaml.safe_load(f) == expected_docs


@pytest.mark.django_db
def test_migration_filtering(migration_docs_config):
    """Tests various filtering methods of the core Migrations object"""
    docs_file = migration_docs_config / 'docs.yaml'
    with open(docs_file, 'w+') as f:
        f.write(
            yaml.safe_dump(
                {
                    'tests.0001_initial': {
                        '_hash': 'd1468bb233398bcc089bd33151f51cd3',
                        'type': 'before',
                        'point_of_contact': 'john',
                    },
                    'tests.0002_testmodel_field2': {
                        '_hash': '8cb7f6747d4ef78074521309d5d05a2c',
                        'type': 'after',
                        'point_of_contact': 'john',
                    },
                    'tests.0003_testmodel_field3': {
                        '_hash': 'e53ffdcc6e8b9cc7f8a960e49968040f',
                        'type': 'before',
                    },
                }
            )
        )

    migrations = core.Migrations()

    # Check various migration properties
    after_migration = list(migrations.filter('type', 'after'))[0]
    assert str(after_migration.hash) == '8cb7f6747d4ef78074521309d5d05a2c'

    # Check various filterings
    assert len(migrations.filter('type', 'before')) == 2
    assert len(migrations.exclude('type', 'before')) == 1
    assert len(migrations.filter('type', 'after')) == 1
    assert (
        len(
            migrations.filter('type', 'before').filter(
                'point_of_contact', '.*jo.*', match=True
            )
        )
        == 1
    )

    # Check groupings
    type_groups = migrations.group('type')
    assert len(type_groups) == 2
    assert len(type_groups['before']) == 2
    assert len(type_groups['after']) == 1
    poc_groups = migrations.group('point_of_contact')
    assert len(poc_groups[None]) == 1
    assert len(poc_groups['john']) == 2

    # Check group sorting
    assert list(migrations.group('type', ascending_keys=True)) == [
        'after',
        'before',
    ]
    assert list(migrations.group('point_of_contact', ascending_keys=True)) == [
        'john',
        None,
    ]
    assert list(migrations.group('type', descending_keys=True)) == [
        'before',
        'after',
    ]
    assert list(
        migrations.group(
            'point_of_contact', ascending_keys=True, none_key_first=True
        )
    ) == [None, 'john']

    # Verify filtering on applied migrations
    assert len(migrations.filter('applied', True)) == 3
    call_command('migrate', 'tests', '0001')

    migrations = core.Migrations()
    assert len(migrations.filter('applied', True)) == 1
    call_command('migrate', 'tests')

    migrations = core.Migrations()
    assert len(migrations.filter('applied', True)) == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    'pre_migrate_sync, expected_sync_call_count', [(True, 1), (False, 0)]
)
def test_pre_migrate_sync(
    mocker, settings, pre_migrate_sync, expected_sync_call_count
):
    settings.MIGRATION_DOCS_PRE_MIGRATE_SYNC = pre_migrate_sync
    patched_sync = mocker.patch('migration_docs.sync', autospec=True)

    call_command('migrate')

    assert len(patched_sync.call_args_list) == expected_sync_call_count


@pytest.mark.parametrize(
    'subcommand, expected_exception',
    [
        ('show', does_not_raise()),
        ('invalid', pytest.raises(subprocess.CalledProcessError)),
    ],
)
def test_call_management_command(subcommand, expected_exception):
    """Verifies the management command can be called from the shell"""
    with expected_exception:
        utils.shell(f'python manage.py migration_docs {subcommand}')
