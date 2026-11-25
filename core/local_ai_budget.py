"""Auditable local pilot allowance, not an OpenAI organisation billing limit.
Historic cap stays reserved; ambiguous new calls retain the entire context hold.
"""
from contextlib import contextmanager, closing
import hashlib
import json
import sqlite3
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

HOLD = 600
CEILING = 1000

class BudgetError(Exception):
    pass


def usage_bound(data):
    if data.get('status') != 'completed' or not str(data.get('id', '')).startswith('resp_'):
        raise BudgetError('unverified_usage')
    usage = data.get('usage', {})
    i, o, total = (usage.get(k) for k in ('input_tokens', 'output_tokens', 'total_tokens'))
    if any(type(v) is not int for v in (i, o, total)) or not 0 <= i <= 1050000 or not 0 <= o <= 1800 or total != i + o:
        raise BudgetError('unverified_usage')
    # Every input at long-context cache WRITE rate, every output at long-context
    # output rate, plus regional10%; round UP, minimum3c. Not an invoice.
    cents = ((Decimal(i)*5 + Decimal(o)*15)*Decimal('1.10')/10000).to_integral_value(rounding=ROUND_CEILING)
    return max(3, int(cents))


@contextmanager
def connect(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise BudgetError('budget_missing')
    c = sqlite3.connect(p, timeout=10)
    c.execute('PRAGMA synchronous=FULL')
    try:
        with c:yield c
    finally:c.close()


def initialize(path, historical, evidence):
    p=Path(path)
    if p.exists():
        return status(p)
    # Exclusive creation: never reconstruct a missing budget from an empty app DB.
    with p.open('xb'):
        pass
    with closing(sqlite3.connect(p)) as c, c:
        c.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, identity TEXT NOT NULL, cents INTEGER NOT NULL, evidence TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE UNIQUE INDEX unique_event ON events(kind,identity)')
        c.execute('INSERT INTO events(kind,identity,cents,evidence) VALUES(?,?,?,?)', ('historic_cap','original-pilot',200,'Original full cap remains reserved; old approval unchanged'))
        c.execute('INSERT INTO events(kind,identity,cents,evidence) VALUES(?,?,?,?)', ('reserve','historical-whole',HOLD,json.dumps(evidence,sort_keys=True)))
        c.execute('INSERT INTO events(kind,identity,cents,evidence) VALUES(?,?,?,?)', ('reconcile','historical-whole',historical-HOLD,'Completed single response; conservative usage bound, not billed spend'))
    return status(p)


def status(path):
    with connect(path) as c:
        used=c.execute('SELECT SUM(cents) FROM events').fetchone()[0]
        reserves=c.execute("SELECT COUNT(*) FROM events WHERE kind='reserve'").fetchone()[0]
        reconciles=c.execute("SELECT COUNT(*) FROM events WHERE kind='reconcile'").fetchone()[0]
        valid=c.execute("SELECT COUNT(*) FROM events WHERE kind='historic_cap' AND identity='original-pilot' AND cents=200").fetchone()[0]
        if not valid or used is None or not 200 <= used <= CEILING:
            raise BudgetError('budget_invalid')
        return {'ceiling_cents':CEILING,'accounted_cents':used,'remaining_cents':CEILING-used,'next_hold_cents':HOLD,'next_call_available':used+HOLD<=CEILING,
                'known_completed_calls':reconciles,'open_holds':reserves-reconciles}


def reserve(path, payload, *, scope=None):
    if payload.get('model') != 'gpt-6.1-sol' or payload.get('service_tier') != 'default' or payload.get('max_output_tokens') != 1800 or payload.get('tools') or payload.get('previous_response_id'):
        raise BudgetError('budget_configuration')
    status(path)
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    # A private scope belongs only to the ledger, never to provider request data.
    identity=hashlib.sha256(payload_bytes if scope is None else scope.encode()+b'\0'+payload_bytes).hexdigest()
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM events WHERE kind='reserve' AND identity=?",(identity,)).fetchone():
            raise BudgetError('duplicate_call')
        used=c.execute('SELECT SUM(cents) FROM events').fetchone()[0]
        if used is None or used+HOLD>CEILING:
            raise BudgetError('budget_limit')
        c.execute('INSERT INTO events(kind,identity,cents,evidence) VALUES(?,?,?,?)',('reserve',identity,HOLD,'gpt-6.1-sol/default; full context1050000; output1800; worst rates+10%; no retry'))
    return identity


def reconcile(path, identity, data):
    bound=usage_bound(data)
    if bound>HOLD:
        raise BudgetError('unverified_usage')
    evidence=json.dumps({'request_id':data['id'],'usage':data['usage'],'model':'gpt-6.1-sol','service_tier':'default','bound_cents':bound},sort_keys=True)
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute("SELECT 1 FROM events WHERE kind='reserve' AND identity=? AND cents=?",(identity,HOLD)).fetchone():
            raise BudgetError('budget_invalid')
        prior=c.execute("SELECT evidence FROM events WHERE kind='reconcile' AND identity=?",(identity,)).fetchone()
        if prior:
            if prior[0]!=evidence:raise BudgetError('unverified_usage')
            return
        c.execute('INSERT INTO events(kind,identity,cents,evidence) VALUES(?,?,?,?)',('reconcile',identity,bound-HOLD,evidence))
