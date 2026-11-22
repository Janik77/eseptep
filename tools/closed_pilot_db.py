"""Provenance guard for the offline PyCharm demonstration database only."""
import json
import sqlite3

DEMO_NAMES = ('demo-client@example.test', 'demo-supplier@example.test', 'demo-master@example.test')
APPLICATION_ID = 0x45535141  # ESQA; private isolated review database marker.


def inspect_db(path):
    """Return whether this file was already prepared and can resume without seeding."""
    if path.is_symlink():
        raise SystemExit('Refusing symlink DB.')
    if not path.exists():
        return False
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as con:
        identifier = con.execute('PRAGMA application_id').fetchone()[0]
        if identifier == APPLICATION_ID:
            return True
        if identifier != 0:
            raise SystemExit('Unrelated SQLite application; refusing.')
        tables = {row[0] for row in con.execute("select name from sqlite_master where type='table'")}
        if 'auth_user' in tables:
            marks = ','.join('?' for _ in DEMO_NAMES)
            if con.execute(f'SELECT 1 FROM auth_user WHERE username NOT IN ({marks}) LIMIT 1', DEMO_NAMES).fetchone():
                raise SystemExit('Unmarked database contains non-demo users; refusing.')
        if 'calculators_pricebook' in tables and con.execute(
            "SELECT 1 FROM calculators_pricebook WHERE version NOT LIKE 'meeting-demo-%' LIMIT 1").fetchone():
            raise SystemExit('Unmarked database contains non-demo prices; refusing.')
    return False


def mark_prepared(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=rw',uri=True) as con:
        con.execute(f'PRAGMA application_id={APPLICATION_ID}')

def read_two_room_fixture(root):
    directory = root / 'tests' / 'fixtures' / 'plans'
    catalog = json.loads((directory / 'typical-manifest.json').read_text(encoding='utf-8'))
    plan = next(item for item in catalog if item['key'] == 'two-room')
    rooms = []
    for row in plan['ground_truth']:
        area = f"{row['area']:.2f}"
        evidence = f"{row['name']} {area} м²"
        rooms.append(dict(name=row['name'], kind=row['kind'], area=area, source='stated',
                          page=row['page'], evidence=evidence, visual_evidence=evidence, finish=None))
    return (directory / plan['pdf']).read_bytes(), rooms
