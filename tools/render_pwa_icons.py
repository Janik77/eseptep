"""Generate the official blue ESEPTEP E-mark in each platform's required crop."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'static' / 'pwa'
BLUE = '#315f9a'


def icon(size, maskable=False, apple=False):
    canvas = Image.new('RGBA', (1024, 1024), BLUE if maskable or apple else (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    if not (maskable or apple):
        draw.rounded_rectangle((44, 44, 980, 980), radius=212, fill=BLUE)
    # Geometric form of the site's white E mark. All corners are inside the
    # 40%-radius maskable safe area, including Android circle crops.
    mark = [(354, 299), (690, 299), (690, 378), (449, 378), (449, 468),
            (668, 468), (668, 546), (449, 546), (449, 646), (690, 646),
            (690, 725), (354, 725)]
    draw.polygon(mark, fill='#ffffff')
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == '__main__':
    for name, size, maskable, apple in [
        ('icon-192.png', 192, False, False), ('icon-512.png', 512, False, False),
        ('icon-maskable-512.png', 512, True, False), ('icon-apple-180.png', 180, False, True),
    ]:
        icon(size, maskable, apple).save(ROOT / name, optimize=True)
