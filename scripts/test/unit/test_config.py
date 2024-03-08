import unittest

import config
import manage_config


class ConfigTestCase(unittest.TestCase):
    def test_load_all(self) -> None:
        for p in config.list_profiles():
            manage_config.test_load_one_config(p)
