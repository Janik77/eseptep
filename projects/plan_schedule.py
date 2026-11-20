"""Conservative room-area join for a text PDF with a separate schedule.

Data in unverified/scanned schedules cannot override measurements or establish
that a document is a floor plan. Text-layer line numbers are not printed row
numbers; they let readers locate the exact verified text in the right PDF page.
"""
import re
import unicodedata
from collections import Counter, defaultdict


def _fold(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


_SCHEDULE = {
    'room schedule', 'schedule of rooms',
    'экспликация помещений', 'экспликация',
    'бөлмелер экспликациясы', 'үй-жайлар экспликациясы', 'бөлмелер тізімі',
}
_UNIT = re.compile(
    r'^(?:apartment|unit|квартира|пәтер)\s*(?:[№#:]\s*|\s+)'
    r'([a-zа-яғқңөұүһі0-9][a-zа-яғқңөұүһі0-9-]{0,23})$'
)
_ROOM = re.compile(r'^([0-9]{1,3}[a-zа-я]?)\s+([^\d\s].{0,98})$')
_ROW = re.compile(r'^([0-9]{1,3}[a-zа-я]?)\s+([^\d\s].{0,98}?)\s+([0-9]{1,5}(?:[.,][0-9]{1,2})?)\s*(?:m2|м2)$')
_POSSIBLE_ROW = re.compile(r'^([0-9]{1,3}[a-zа-я]?)\s+')
_FLOOR_TITLE = re.compile(r'^(?:floor plan|план (?:квартиры|этажа|помещений)|планировка|қабат жоспары|пәтер жоспары)(?:$|:)')
_METRIC_END = re.compile(r'(?:m2|м2)$')
_TOTAL = re.compile(r'^(?:total|subtotal|итого|всего|общая площадь|жиыны|барлығы|жалпы аудан)(?:$|\s)')


def _lines(text):
    return [(i, raw.strip(), _fold(raw)) for i, raw in enumerate(text.splitlines(), 1) if raw.strip()]


def _unit(lines):
    labels = [_UNIT.fullmatch(value) for _, _, value in lines]
    scopes = {match[1] for match in labels if match is not None}
    return next(iter(scopes)) if len(scopes) == 1 else None


def _is_schedule(lines):
    return bool(lines and lines[0][2].rstrip(':') in _SCHEDULE
                and not any(_FLOOR_TITLE.match(value) for _, _, value in lines))


def is_separate_schedule(text):
    """Never accept a page with only an explicit schedule heading as geometry."""
    return _is_schedule(_lines(text))


def add_schedule_areas(rooms, proposed_rows, frames, floor_pages, parse_area):
    """Fill unknown rooms only, requiring an exact unique same-unit/text join."""
    schedules = defaultdict(list)
    for page, (image, text) in enumerate(frames, 1):
        if not image or page in floor_pages:
            continue
        lines = _lines(text)
        if not _is_schedule(lines) or (unit := _unit(lines)) is None:
            continue
        for line, evidence, value in lines:
            # Malformed candidate rows also count as conflicts. Do not quietly
            # choose a formatted row over a second same-reference row.
            potential = _POSSIBLE_ROW.match(value)
            if not potential:
                continue
            match = _ROW.fullmatch(value)
            schedules[unit, potential[1]].append((page, line, evidence, match))

    anchors = {}
    counts = Counter()
    for page in floor_pages:
        lines = _lines(frames[page - 1][1])
        unit = _unit(lines)
        if unit is None:
            continue
        rows = defaultdict(list)
        for _, _, value in lines:
            match = _ROOM.fullmatch(value)
            if match and not _METRIC_END.search(match[2]):
                rows[match[2]].append(match[1])
                counts[unit, match[1]] += 1
        anchors[page] = (unit, rows)

    assignments = []
    for room, proposal in zip(rooms, proposed_rows, strict=True):
        seen = proposal.get('schedule_evidence')
        if not isinstance(seen, str) or not 1 <= len(seen) <= 240 or len(seen.splitlines()) != 1:
            continue
        if room['source'] != 'unknown' or room['page'] not in anchors:
            continue
        page = room['page']
        unit, rows = anchors[page]
        name = _fold(room['name'])
        if _TOTAL.match(name):
            continue
        refs = rows.get(name, [])
        if len(refs) != 1 or counts[unit, refs[0]] != 1:
            continue
        candidates = schedules.get((unit, refs[0]), [])
        if len(candidates) != 1:
            continue
        source_page, line, evidence, match = candidates[0]
        if match is None or match[2] != name or _fold(evidence) != _fold(seen):
            continue
        area = parse_area(match[3])
        if area:
            assignments.append((unit, refs[0], room, area, page, source_page, line, evidence))

    assigned = Counter((unit, ref) for unit, ref, *_ in assignments)
    for unit, ref, room, area, page, source_page, line, evidence in assignments:
        if assigned[unit, ref] == 1:
            room.update(area=area, source='stated', page=source_page, line=line,
                        evidence=evidence, visual_evidence='', schedule_floor_page=page)
