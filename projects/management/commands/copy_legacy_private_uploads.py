"""Copy only database-referenced legacy files. Never delete or infer ownership."""
from pathlib import Path
import shutil
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from projects.models import ProjectUpload


class Command(BaseCommand):
    help = 'Dry-run legacy media migration; --apply copies files into private storage. Does not delete originals.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        source_root = Path(settings.MEDIA_ROOT).resolve()
        target_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        if source_root == target_root or source_root in target_root.parents:
            raise CommandError('Private root must be outside the public media directory')
        for item in ProjectUpload.objects.exclude(file='').iterator():
            source = (source_root / item.file.name).resolve()
            target = (target_root / item.file.name).resolve()
            if source_root not in source.parents or target_root not in target.parents:
                raise CommandError(f'Unsafe path on record {item.pk}')
            if target.exists():
                if source.is_file() and source.read_bytes() != target.read_bytes():
                    raise CommandError(f'Conflicting target for record {item.pk}; inspect manually')
                self.stdout.write(f'{item.pk}: private copy already present')
            elif source.is_file():
                if options['apply']:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Exclusive create: never overwrite another upload.
                    with source.open('rb') as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
                self.stdout.write(f'{item.pk}: {"copied" if options["apply"] else "would copy"}')
            else:
                self.stdout.write(f'{item.pk}: source missing; review required')
            if not item.user_id:
                self.stdout.write(f'{item.pk}: legacy guest remains inaccessible; ownership requires manual verification')
