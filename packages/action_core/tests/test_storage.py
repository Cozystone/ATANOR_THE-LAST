from collections import namedtuple
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from packages.action_core.storage import require_space


class StorageTests(unittest.TestCase):
    def test_checks_output_and_temp_without_creating_output(self):
        usage = namedtuple('Usage', 'total used free')(1000, 100, 900)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'not-created'
            with patch('packages.action_core.storage.shutil.disk_usage', return_value=usage) as call:
                result = require_space(path, minimum_bytes=800)
            self.assertEqual(len(result), 2)
            self.assertEqual(call.call_count, 2)
            self.assertFalse(path.exists())

    def test_low_temp_space_refuses_without_cleanup(self):
        Usage = namedtuple('Usage', 'total used free')
        with patch('packages.action_core.storage.shutil.disk_usage',
                   side_effect=[Usage(1000, 100, 900), Usage(1000, 999, 1)]):
            with self.assertRaises(OSError):
                require_space(Path.cwd(), minimum_bytes=800)

    def test_invalid_minimum_rejected(self):
        with self.assertRaises(ValueError):
            require_space(Path.cwd(), minimum_bytes=-1)


if __name__ == '__main__':
    unittest.main()
