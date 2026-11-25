"""Read text only from bounded PDF/DOCX containers, without OCR, media or network."""
import io
import re
import unicodedata
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 22000
PAGES = 15
NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class ContractFileError(ValueError):
    pass


def tidy(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFC', text)
                           if c.isspace() or unicodedata.category(c) not in ('Cc', 'Cf', 'Cs')).split())


def read_source(upload):
    if not upload or not 0 < upload.size <= MAX_BYTES:
        raise ContractFileError('file_size')
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ContractFileError('file_size')
    extension = upload.name.rsplit('.', 1)[-1].lower()
    try:
        if extension == 'pdf' and raw.startswith(b'%PDF-'):
            doc = PdfReader(io.BytesIO(raw), strict=True)
            if doc.is_encrypted or not 1 <= len(doc.pages) <= PAGES:
                raise ContractFileError('file_pages')
            rows = []
            for i, page in enumerate(doc.pages, 1):
                text = page.extract_text() or ''
                # A partial scan must not silently omit clauses.
                if len(re.findall(r'[^\W\d_]', text)) < 24:
                    raise ContractFileError('scan')
                blocks = re.split(r'\n(?=\s*(?:\d{1,2}[.)]|§|\d{1,2}\.\d{1,2}\b|Приложение|Қосымша))|\n\s*\n', text)
                rows.extend((i, line) for line in (tidy(block) for block in blocks) if line)
        elif extension == 'docx' and raw.startswith(b'PK\x03\x04'):
            with ZipFile(io.BytesIO(raw)) as z:
                members = z.infolist()
                if len(members) > 128 or sum(x.file_size for x in members) > 20 * MAX_BYTES:
                    raise ContractFileError('file_size')
                if any(x.filename.casefold().endswith(('vbaproject.bin', '.exe', '.dll')) for x in members):
                    raise ContractFileError('file_type')
                info = z.getinfo('word/document.xml')
                if info.file_size > 1024 * 1024:
                    raise ContractFileError('file_size')
                xml = z.read(info)
                # DOCX uses UTF-8 XML; declarations/entities are not needed.
                xml.decode('utf-8', errors='strict')
                if b'<!' in xml:
                    raise ContractFileError('file_type')
                root = ElementTree.fromstring(xml)
                rows = []
                for paragraph in root.iter(NS + 'p'):
                    # Preserve run boundaries and table paragraphs, avoiding duplicated nested text.
                    line = tidy(''.join(elem.text or '' for elem in paragraph.iter(NS + 't')))
                    if line:
                        rows.append((None, line))
        else:
            raise ContractFileError('file_type')
    except ContractFileError:
        raise
    except (PyPdfError, BadZipFile, KeyError, RuntimeError, ValueError, TypeError, ElementTree.ParseError, OSError, RecursionError) as exc:
        raise ContractFileError('file_type') from exc
    if not rows or sum(len(line) for _, line in rows) < 80:
        raise ContractFileError('scan')
    grouped = []
    for page, line in rows:
        # Retain stable paragraph IDs; a PDF paragraph can be a long continuous text block.
        grouped.extend((page, line[i:i + 2200]) for i in range(0, len(line), 2200))
    if sum(len(line) for _, line in grouped) > MAX_CHARS or len(grouped) > 160:
        raise ContractFileError('file_size')
    return extension, raw, [{'id': i, 'page': page, 'text': line}
                             for i, (page, line) in enumerate(grouped, 1)]
