from decimal import Decimal
from unittest.mock import patch
from django.test import SimpleTestCase
from tools import qa_whole_plan_live_once as live


class LiveOnceGuardTests(SimpleTestCase):
    def test_full_context_bound_with_cache_write_and_region_is_below_partition(self):
        self.assertEqual(live.cost_bound(),Decimal('5.80470'))
        self.assertLess(live.cost_bound(),Decimal('6'))
        self.assertLess(Decimal('2')+Decimal('6'),Decimal('10'))

    def test_existing_marker_refuses_before_database_or_provider(self):
        with patch('pathlib.Path.exists',return_value=True), patch('sqlite3.connect') as connect:
            with self.assertRaisesRegex(SystemExit,'already reserved'):
                live.main(['--confirm-one-live-synthetic'])
            connect.assert_not_called()

    def test_default_is_preflight_only_no_database(self):
        with patch('sqlite3.connect') as connect,patch('builtins.print'):
            live.main([])
            connect.assert_not_called()
