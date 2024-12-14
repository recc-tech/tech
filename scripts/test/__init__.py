import unittest

# Don't show test docstrings when unittest is run with --verbose
unittest.TestCase.shortDescription = lambda self: None
