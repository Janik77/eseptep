from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from calculators.price_import import MAX_BYTES, import_floor_prices


class Command(BaseCommand):
    help = 'Validate the pilot floor-price CSV. Use --write-draft to save it without publishing.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--store', required=True)
        parser.add_argument('--version', required=True)
        parser.add_argument('--source', required=True)
        parser.add_argument('--date', required=True)
        parser.add_argument('--write-draft', action='store_true')

    def handle(self, *args, **opts):
        try:
            with open(opts['csv_path'], 'rb') as source:
                data = source.read(MAX_BYTES + 1)
            book, count = import_floor_prices(
                data, store=opts['store'], version=opts['version'], source=opts['source'],
                date_text=opts['date'], write=opts['write_draft'])
        except (OSError, ValueError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        if book:
            self.stdout.write(f'Inactive draft {book.version} created: {count} rows; no publication.')
        else:
            self.stdout.write(f'Dry run: {count} rows validated; no writes.')
