"""Development-only serving for the two public profile-image namespaces."""
from pathlib import Path
from django.conf import settings
from django.http import Http404
from django.views.static import serve


def public_development_media(request, path):
    # Never delegate arbitrary media paths to Django's normalizing static helper.
    # Django has decoded URL escapes before dispatch; reject ambiguous separators
    # and encoded leftovers as well as literal dot segments.
    parts = path.split('/')
    if (not settings.DEBUG or not parts or parts[0] not in {'avatars', 'masters'}
            or any(part in {'', '.', '..'} for part in parts)
            or '\\' in path or '%' in path):
        raise Http404
    root = Path(settings.MEDIA_ROOT).resolve()
    public_root = root / parts[0]
    target = (root / path).resolve()
    if public_root.resolve() != public_root or public_root not in target.parents:
        raise Http404
    return serve(request, path, document_root=root)
