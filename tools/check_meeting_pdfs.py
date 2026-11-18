"""Inspect actual browser-downloaded PDFs, not just generator unit tests."""
from pathlib import Path
from pypdf import PdfReader
paths=list(Path('meeting-evidence').glob('*.pdf'))
assert len(paths)==8, len(paths)
for path in paths:
    text='\n'.join(page.extract_text() for page in PdfReader(path).pages)
    if 'precision' in path.name:assert '36,5' in text, path
    else:assert '4,8' in text, path
    if '-kk-' in path.name:assert 'Сақталған смета' in text, path
    assert 'meeting-demo-v' in text, path
print(f'{len(paths)} browser-downloaded PDFs preserve decimal area, Cyrillic/Kazakh and price version.')
