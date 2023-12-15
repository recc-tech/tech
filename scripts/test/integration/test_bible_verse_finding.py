import unittest
import unittest.mock as mock

from autochecklist import ProblemLevel
from common import ReccWebDriver
from slides import BibleVerse, BibleVerseFinder


class BibleVerseFindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._messenger = mock.Mock()
        # Save this in its own variable to get Pylance to stop complaining that the type is unknown
        cls._log_problem_mock = mock.Mock()
        cls._messenger.log_problem = cls._log_problem_mock
        # Create the driver once and reuse it for all tests because
        #  (1) creating a new WebDriver is slow
        #  (2) having a bunch of Firefox windows open is massively memory-intensive
        cls._driver = ReccWebDriver(
            messenger=cls._messenger, headless=True, log_file=None
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._driver.close()

    def setUp(self):
        self.finder = BibleVerseFinder(
            driver=self._driver, messenger=self._messenger, cancellation_token=None
        )

    def tearDown(self) -> None:
        # Prevent errors logged by one test from carrying over to other tests
        self._log_problem_mock.reset_mock()

    def test_genesis_1_1_nlt(self):
        # Beginning of a chapter (so BibleGateway shows a large chapter number)
        # Footnote at the end
        self.assertEqual(
            self.finder.find(BibleVerse("Genesis", 1, 1, "NLT")),
            "In the beginning God created the heavens and the earth.",
        )
        self._log_problem_mock.assert_not_called()

    def test_john_3_16_nlt(self):
        # Footnote in the middle of the verse
        self.assertEqual(
            self.finder.find(BibleVerse("John", 3, 16, "NLT")),
            "“For this is how God loved the world: He gave his one and only Son, so that everyone who believes in him will not perish but have eternal life.",
        )
        self._log_problem_mock.assert_not_called()

    def test_2kings_9_20_niv(self):
        # Book name starting with a number
        # Unicode output
        self.assertEqual(
            self.finder.find(BibleVerse("2 Kings", 9, 20, "NIV")),
            "The lookout reported, “He has reached them, but he isn’t coming back either. The driving is like that of Jehu son of Nimshi—he drives like a maniac.”",
        )
        self._log_problem_mock.assert_not_called()

    def test_2kings_9_20_kjv(self):
        # Lowercase input
        self.assertEqual(
            self.finder.find(BibleVerse("2 kings", 9, 20, "kjv")),
            "And the watchman told, saying, He came even unto them, and cometh not again: and the driving is like the driving of Jehu the son of Nimshi; for he driveth furiously.",
        )
        self._log_problem_mock.assert_not_called()

    def test_psalm_119_176_nlt(self):
        # Psalms are often displayed on multiple lines in NLT
        self.assertEqual(
            self.finder.find(BibleVerse("Psalm", 119, 176, "NLT")),
            "I have wandered away like a lost sheep; come and find me, for I have not forgotten your commands.",
        )
        self._log_problem_mock.assert_not_called()

    def test_matthew_14_16_niv(self):
        # The words of Jesus are often shown with red text
        self.assertEqual(
            self.finder.find(BibleVerse("Matthew", 14, 16, "NIV")),
            "Jesus replied, “They do not need to go away. You give them something to eat.”",
        )
        self._log_problem_mock.assert_not_called()

    def test_hebrews_13_5_nlt(self):
        # The text is shown in two separate paragraphs on BibleGateway
        self.assertEqual(
            self.finder.find(BibleVerse("Hebrews", 13, 5, "NLT")),
            "Don’t love money; be satisfied with what you have. For God has said, “I will never fail you. I will never abandon you.”",
        )
        self._log_problem_mock.assert_not_called()

    def test_exodus_14_14_invalid_translation(self):
        self.assertIsNone(self.finder.find(BibleVerse("Exodus", 14, 14, "INVALID")))
        self._log_problem_mock.assert_called_once()
        call_args = self._log_problem_mock.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args.args[0], ProblemLevel.WARN)
        self.assertEqual(
            call_args.args[1],
            "Failed to fetch text for Bible verse Exodus 14:14 (INVALID).",
        )
        self.assertTrue(
            "stacktrace" in call_args.kwargs,
            f"Expected error log to contain a stack trace, but received call args {call_args}.",
        )

    def test_invalid_chapter(self):
        self.assertIsNone(self.finder.find(BibleVerse("Psalm", 151, 1, "NLT")))
        self._log_problem_mock.assert_called_once()
        call_args = self._log_problem_mock.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args.args[0], ProblemLevel.WARN)
        self.assertEqual(
            call_args.args[1],
            "Failed to fetch text for Bible verse Psalm 151:1 (NLT).",
        )
        self.assertTrue(
            "stacktrace" in call_args.kwargs,
            f"Expected error log to contain a stack trace, but received call args {call_args}.",
        )
