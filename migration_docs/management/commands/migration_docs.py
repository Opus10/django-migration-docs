import sys

from django.core.management.base import BaseCommand

import migration_docs


class SubCommands(BaseCommand):
    '''
    Subcommand class vendored in from
    https://github.com/andrewp-as-is/django-subcommands.py
    because of installation issues
    '''

    argv = []
    subcommands = {}

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest='subcommand', title='subcommands', description=''
        )
        subparsers.required = True

        for command_name, command_class in self.subcommands.items():
            command = command_class()

            subparser = subparsers.add_parser(
                command_name, help=command_class.help
            )
            command.add_arguments(subparser)
            prog_name = subcommand = ''
            if self.argv:
                prog_name = self.argv[0]
                subcommand = self.argv[1]

            command_parser = command.create_parser(prog_name, subcommand)
            subparser._actions = command_parser._actions

    def run_from_argv(self, argv):
        self.argv = argv
        return super().run_from_argv(argv)

    def handle(self, *args, **options):
        command_name = options['subcommand']
        self.subcommands.get(command_name)
        command_class = self.subcommands[command_name]

        if self.argv:
            args = [self.argv[0]] + self.argv[2:]
            return command_class().run_from_argv(args)
        else:
            return command_class().execute(*args, **options)


class BootstrapCommand(BaseCommand):
    help = 'Bootstraps initial empty migration docs for a project.'

    def handle(self, *args, **options):
        migration_docs.bootstrap()


class SyncCommand(BaseCommand):
    help = 'Adds, updates, and removes migration docs for a project.'

    def handle(self, *args, **options):
        migration_docs.sync()


class CheckCommand(BaseCommand):
    help = 'Checks that the migration docs are in sync.'

    def handle(self, *args, **options):
        if not migration_docs.check():
            sys.exit(1)
        else:
            sys.exit(0)


class ShowCommand(BaseCommand):
    help = 'Renders the migration docs.'

    def add_arguments(self, parser):
        parser.add_argument(
            'app_label',
            nargs='*',
            help='App labels of applications to limit the output to.',
        )
        parser.add_argument(
            '--style',
            default='default',
            help=(
                'Rendering style, which corresponds to a'
                ' .migration-docs/{style}_show.tpl Jinja template. If not'
                ' specified, the default template is used.'
            ),
        )
        parser.add_argument(
            '--unapplied',
            action='store_true',
            help='Only show unapplied migrations.',
        )

    def handle(self, *args, **options):
        rendered = migration_docs.show(
            app_labels=options['app_label'],
            unapplied=options['unapplied'],
            style=options['style'],
        )
        print(rendered, end='')


class UpdateCommand(BaseCommand):
    help = 'Update migration docs for individual migrations.'

    def add_arguments(self, parser):
        parser.add_argument(
            'migration',
            nargs='+',
            help='Migrations (e.g. "users.0001_initial") to update.',
        )

    def handle(self, *args, **options):
        migration_docs.update(options['migration'])


class Command(SubCommands):
    help = """
     migration_docs must be followed by a subcommand to:\n
     - 'bootstrap' the project with initial migration docs\n
     - 'check' the status of the migration docs\n
     - 'sync' the docs\n
     - 'show' the migration docs.\n
     - 'update' docs for individual migrations.
    """
    subcommands = {
        'bootstrap': BootstrapCommand,
        'sync': SyncCommand,
        'check': CheckCommand,
        'show': ShowCommand,
        'update': UpdateCommand,
    }
