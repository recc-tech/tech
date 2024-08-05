import unittest

from external_services import BibleVerse, BibleVerseFinder


class BibleVerseFindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.finder = BibleVerseFinder()

    def test_genesis_1_1_nlt(self):
        # Beginning of a chapter (so BibleGateway shows a large chapter number)
        # Footnote at the end
        self.assertEqual(
            self.finder.find(BibleVerse("Genesis", 1, 1, "NLT")),
            "In the beginning God created the heavens and the earth.",
        )

    def test_john_3_16_nlt(self):
        # Footnote in the middle of the verse
        self.assertEqual(
            self.finder.find(BibleVerse("John", 3, 16, "NLT")),
            "“For this is how God loved the world: He gave his one and only Son, so that everyone who believes in him will not perish but have eternal life.",
        )

    def test_2kings_9_20_niv(self):
        # Book name starting with a number
        # Unicode output
        self.assertEqual(
            self.finder.find(BibleVerse("2 Kings", 9, 20, "NIV")),
            "The lookout reported, “He has reached them, but he isn’t coming back either. The driving is like that of Jehu son of Nimshi—he drives like a maniac.”",
        )

    def test_2kings_9_20_kjv(self):
        # Lowercase input
        self.assertEqual(
            self.finder.find(BibleVerse("2 kings", 9, 20, "kjv")),
            "And the watchman told, saying, He came even unto them, and cometh not again: and the driving is like the driving of Jehu the son of Nimshi; for he driveth furiously.",
        )

    def test_psalm_119_176_nlt(self):
        # Psalms are often displayed on multiple lines in NLT
        self.assertEqual(
            self.finder.find(BibleVerse("Psalm", 119, 176, "NLT")),
            "I have wandered away like a lost sheep; come and find me, for I have not forgotten your commands.",
        )

    def test_matthew_14_16_niv(self):
        # The words of Jesus are often shown with red text
        self.assertEqual(
            self.finder.find(BibleVerse("Matthew", 14, 16, "NIV")),
            "Jesus replied, “They do not need to go away. You give them something to eat.”",
        )

    def test_hebrews_13_5_nlt(self):
        # The text is shown in two separate paragraphs on BibleGateway
        self.assertEqual(
            self.finder.find(BibleVerse("Hebrews", 13, 5, "NLT")),
            "Don’t love money; be satisfied with what you have. For God has said, “I will never fail you. I will never abandon you.”",
        )

    def test_exodus_14_14_invalid_translation(self):
        with self.assertRaises(ValueError) as cm:
            self.finder.find(BibleVerse("Exodus", 14, 14, "INVALID"))
        self.assertEqual(str(cm.exception), "Invalid translation 'INVALID'.")

    def test_invalid_chapter(self):
        with self.assertRaises(ValueError) as cm:
            self.finder.find(BibleVerse("Psalm", 151, 1, "NLT"))
        self.assertEqual(str(cm.exception), "Invalid chapter.")
