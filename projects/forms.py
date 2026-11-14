from decimal import Decimal
from io import BytesIO
from pathlib import Path
import warnings

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from .models import ProjectUpload


class ProjectUploadForm(forms.Form):
    file = forms.FileField()
    comment = forms.CharField(required=False, max_length=4000, widget=forms.Textarea)

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        if not uploaded.size or uploaded.size > settings.PROJECT_UPLOAD_MAX_BYTES:
            raise forms.ValidationError('Выберите непустой файл размером до 10 МБ.')
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}:
            raise forms.ValidationError('Поддерживаются PDF, JPG, PNG и WEBP. DWG пока не принимается: безопасная проверка недоступна.')
        data = uploaded.read()
        uploaded.seek(0)
        if suffix != '.pdf':
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(BytesIO(data)) as picture:
                        expected = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}[suffix]
                        if picture.format != expected or picture.width * picture.height > 20_000_000:
                            raise ValueError('Unsupported image')
                        picture.load()
                        result = BytesIO()
                        picture.convert('RGB' if expected == 'JPEG' else 'RGBA').save(result, format=expected)
                # Re-encode image pixels; do not retain executable trailers or metadata.
                if result.tell() > settings.PROJECT_UPLOAD_MAX_BYTES:
                    raise ValueError('Re-encoded image exceeds size limit')
                return ContentFile(result.getvalue(), name=Path(uploaded.name).name)
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise forms.ValidationError('Изображение повреждено, слишком большое или не соответствует расширению.')
        try:
            if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
                raise ValueError('Invalid PDF')
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
                raise ValueError('Unsupported PDF')
            # Reject active/embedded content, including escaped PDF names resolved by parser.
            forbidden = {'/JS', '/JavaScript', '/OpenAction', '/AA', '/Launch', '/EmbeddedFiles', '/RichMedia', '/XFA', '/EF', '/FS', '/AF'}
            forbidden_values = {'/EmbeddedFile', '/FileAttachment', '/Filespec', '/JavaScript',
                                '/Launch', '/GoToR', '/GoToE', '/SubmitForm', '/ImportData',
                                '/Rendition', '/Movie', '/Sound', '/RichMedia', '/URI'}
            visited = set()
            def inspect(obj, depth=0):
                if depth > 100:
                    raise ValueError('PDF nesting too deep')
                if hasattr(obj, 'get_object'):
                    obj = obj.get_object()
                marker = id(obj)
                if marker in visited:
                    return
                visited.add(marker)
                if isinstance(obj, dict):
                    if forbidden.intersection(obj):
                        raise ValueError('Active PDF')
                    for value in obj.values():
                        inspect(value, depth + 1)
                elif isinstance(obj, str) and obj in forbidden_values:
                    raise ValueError('Embedded file or active PDF action')
                elif isinstance(obj, (list, tuple)):
                    for value in obj:
                        inspect(value, depth + 1)
            inspect(reader.trailer)
        except Exception:
            raise forms.ValidationError('Нужен корректный PDF до 100 страниц, без пароля, скриптов и вложений.')
        return uploaded


class ProjectEstimateForm(forms.Form):
    area = forms.DecimalField(label='Площадь квартиры', min_value=Decimal('0.01'), max_value=Decimal('999999.99'),
                              max_digits=8, decimal_places=2, localize=True)
    repair_level = forms.ChoiceField(label='Уровень ремонта', choices=ProjectUpload.RepairLevel.choices)

