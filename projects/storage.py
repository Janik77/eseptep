from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateFileStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return str(Path(settings.PRIVATE_MEDIA_ROOT).resolve())


def private_storage():
    return PrivateFileStorage()
