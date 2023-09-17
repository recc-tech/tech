import unittest
from pathlib import Path
from unittest.mock import Mock, create_autospec

from autochecklist.messenger import Messenger, ProblemLevel
from common import ReccWebDriver
from slides.read import BibleVerseFinder, SlideBlueprintReader


class SlideBlueprintReaderTestCase(unittest.TestCase):
    RAW_NOTES_DIR = Path(__file__).parent.joinpath("raw_message_notes")
    EXPECTED_BLUEPRINTS_DIR = Path(__file__).parent.joinpath(
        "expected_message_blueprints"
    )
    ACTUAL_BLUEPRINTS_DIR = Path(__file__).parent.joinpath("actual_message_blueprints")
    MESSAGE_NOTES_WITH_DUPLICATES = {
        RAW_NOTES_DIR.joinpath("2023-09-03.txt"),
        RAW_NOTES_DIR.joinpath("2023-09-10.txt"),
    }

    @classmethod
    def setUpClass(cls):
        # Create the driver once and reuse it for all tests because
        #  (1) creating a new WebDriver is slow
        #  (2) having a bunch of Firefox windows open is massively memory-intensive
        cls._driver = ReccWebDriver(headless=True, log_file=None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._driver.close()

    def test_load_message_notes(self):
        # NOTE: The expected outputs sometimes reflect what is realistic, not
        # what is ideal.
        #  - 2023-09-03: The text of Exodus 33:14 is copied incorrectly (e.g.,
        #    the message notes say "[...] go with you, and [...]" instead of
        #    "[...] go with you, Moses, and [...]").
        #  - 2023-09-03: The Paul Heintzman quote spans multiple lines.
        #  - 2023-09-10: The notes incorrectly cite Genesis 24:4 NLT twice but
        #    include the text for Genesis 24:7-8 the second time.
        log_problem_mock = Mock()
        messenger = create_autospec(Messenger)
        messenger.log_problem = log_problem_mock
        finder = BibleVerseFinder(
            driver=self._driver, messenger=messenger, cancellation_token=None
        )
        reader = SlideBlueprintReader(messenger=messenger, bible_verse_finder=finder)
        raw_notes_paths = [
            x
            for x in self.RAW_NOTES_DIR.iterdir()
            if x.is_file() and x not in self.MESSAGE_NOTES_WITH_DUPLICATES
        ]
        self.assertGreater(len(raw_notes_paths), 0)
        for p in raw_notes_paths:
            log_problem_mock.reset_mock()
            with self.subTest(msg=p.relative_to(self.RAW_NOTES_DIR).as_posix()):
                expected_blueprints_path = self.EXPECTED_BLUEPRINTS_DIR.joinpath(
                    p.stem + ".json"
                )
                actual_blueprints_path = self.ACTUAL_BLUEPRINTS_DIR.joinpath(
                    p.stem + ".json"
                )
                if not expected_blueprints_path.is_file():
                    raise ValueError(
                        f"Failed to find expected blueprints for '{p.as_posix()}'."
                    )
                actual_blueprints = reader.load_message_notes(p)
                reader.save_json(actual_blueprints_path, actual_blueprints)
                actual_blueprints = reader.load_json(actual_blueprints_path)
                expected_blueprints = reader.load_json(expected_blueprints_path)
                self.assertEqual(expected_blueprints, actual_blueprints)
                log_problem_mock.assert_not_called()

    def test_load_message_notes_with_duplicates(self):
        warn_msg_by_file = {
            "2023-09-03": 'The message notes ask for multiple slides with body "“Be still, and know that I am God! I will be honored by every nation. I will be honored throughout the world.”", name "Psalm 46 10 NLT", and footer "Psalm 46:10 (NLT)". Is there a typo?',
            "2023-09-10": 'The message notes ask for multiple slides with body "Go instead to my homeland, to my relatives, and find a wife there for my son Isaac.”", name "Genesis 24 4 NLT", and footer "Genesis 24:4 (NLT)". Is there a typo?',
        }
        log_problem_mock = Mock()
        messenger = create_autospec(Messenger)
        messenger.log_problem = log_problem_mock
        finder = BibleVerseFinder(
            driver=self._driver, messenger=messenger, cancellation_token=None
        )
        reader = SlideBlueprintReader(messenger=messenger, bible_verse_finder=finder)
        raw_notes_paths = [
            x
            for x in self.RAW_NOTES_DIR.iterdir()
            if x.is_file() and x in self.MESSAGE_NOTES_WITH_DUPLICATES
        ]
        self.assertGreater(len(raw_notes_paths), 0)
        for p in raw_notes_paths:
            log_problem_mock.reset_mock()
            with self.subTest(msg=p.relative_to(self.RAW_NOTES_DIR).as_posix()):
                expected_blueprints_path = self.EXPECTED_BLUEPRINTS_DIR.joinpath(
                    p.stem + ".json"
                )
                actual_blueprints_path = self.ACTUAL_BLUEPRINTS_DIR.joinpath(
                    p.stem + ".json"
                )
                if not expected_blueprints_path.is_file():
                    raise ValueError(
                        f"Failed to find expected blueprints for '{p.as_posix()}'."
                    )
                actual_blueprints = reader.load_message_notes(p)
                reader.save_json(actual_blueprints_path, actual_blueprints)
                actual_blueprints = reader.load_json(actual_blueprints_path)
                expected_blueprints = reader.load_json(expected_blueprints_path)
                self.assertEqual(expected_blueprints, actual_blueprints)
                log_problem_mock.assert_called_once_with(
                    level=ProblemLevel.WARN, message=warn_msg_by_file[p.stem]
                )
