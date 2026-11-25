import sqlite3
import tempfile
from pathlib import Path
from contextlib import closing

from django.test import SimpleTestCase

from tools.closed_pilot_db import inspect_db, mark_prepared


class ClosedPilotDatabaseGuardTests(SimpleTestCase):
    def test_marked_demo_database_resumes_after_a_local_test_signup(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp,'pilot.sqlite3')
            self.assertFalse(inspect_db(database))
            with closing(sqlite3.connect(database)) as con, con:
                con.execute('create table auth_user(username text)')
                con.execute("insert into auth_user values ('demo-client@example.test')")
            self.assertFalse(inspect_db(database))
            mark_prepared(database)
            with closing(sqlite3.connect(database)) as con, con:
                con.execute("insert into auth_user values ('new-local-test@example.test')")
            self.assertTrue(inspect_db(database))

    def test_existing_unmarked_non_demo_database_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp,'unmarked.sqlite3')
            with closing(sqlite3.connect(database)) as con, con:
                con.execute('create table auth_user(username text)')
                con.execute("insert into auth_user values ('unrelated@example.test')")
            with self.assertRaises(SystemExit):
                inspect_db(database)
