from django.test import SimpleTestCase
from core.localization import system_tree

class SavedNonvariantLocalizationTests(SimpleTestCase):
    def test_null_variants_in_saved_nonvariant_snapshot_do_not_crash(self):
        source={'variants':None,'materials':[]}
        self.assertEqual(system_tree(source),source)
