import unittest

from external_services.bible import BibleVerse


class BibleVerseParsingTest(unittest.TestCase):
    def test_default_translation(self):
        self.assertEqual(
            BibleVerse.parse("Exodus 14:14"),
            ([BibleVerse("Exodus", 14, 14, "NLT")], ""),
        )

    def test_explicit_translation(self):
        self.assertEqual(
            BibleVerse.parse("Exodus 14:14 NLT"),
            ([BibleVerse("Exodus", 14, 14, "NLT")], ""),
        )
        self.assertEqual(
            BibleVerse.parse("Exodus 14:14 (KJV)"),
            ([BibleVerse("Exodus", 14, 14, "KJV")], ""),
        )
        self.assertEqual(
            BibleVerse.parse("John 3:16 (NIV)"),
            ([BibleVerse("John", 3, 16, "NIV")], ""),
        )

    def test_psalm_119_176(self):
        expected = ([BibleVerse("Psalm", 119, 176, "NLT")], "")
        self.assertEqual(BibleVerse.parse("Psalm 119:176 (NLT)"), expected)
        self.assertEqual(BibleVerse.parse("Psalms 119:176 NLT"), expected)

    def test_song_of_solomon_1_1(self):
        self.assertEqual(
            BibleVerse.parse("Song of Solomon 1:1 (NLT)"),
            ([BibleVerse("Song of Solomon", 1, 1, "NLT")], ""),
        )
        self.assertEqual(
            BibleVerse.parse("Song of Songs 1:1 (NIV)"),
            ([BibleVerse("Song of Solomon", 1, 1, "NIV")], ""),
        )

    def test_2kings_2_23(self):
        self.assertEqual(
            BibleVerse.parse("2 kings 2:23 (kjv)"),
            ([BibleVerse("2 Kings", 2, 23, "KJV")], ""),
        )

    def test_deuteronomy_11_31(self):
        expected = ([BibleVerse("Deuteronomy", 11, 31, "NLT")], "")
        self.assertEqual(BibleVerse.parse("Deuteronomy 11:31 (NLT)"), expected)
        self.assertEqual(BibleVerse.parse("Deut 11:31 NLT"), expected)
        self.assertEqual(BibleVerse.parse("deut. 11:31 NLT"), expected)

    def test_no_colon(self) -> None:
        # Example from 2024-05-12 service
        expected = ([BibleVerse("Proverbs", 31, 10, "NLT")], "")
        self.assertEqual(BibleVerse.parse("Proverbs 31 10 NLT"), expected)

    def test_consecutive_verses(self):
        self.assertEqual(
            BibleVerse.parse("Numbers 11:11-15 (NLT)"),
            (
                [
                    BibleVerse("Numbers", 11, 11, "NLT"),
                    BibleVerse("Numbers", 11, 12, "NLT"),
                    BibleVerse("Numbers", 11, 13, "NLT"),
                    BibleVerse("Numbers", 11, 14, "NLT"),
                    BibleVerse("Numbers", 11, 15, "NLT"),
                ],
                "",
            ),
        )

    def test_nonconsecutive_verses(self):
        self.assertEqual(
            BibleVerse.parse("Jeremiah 20:14,18 NIV"),
            (
                [
                    BibleVerse("Jeremiah", 20, 14, "NIV"),
                    BibleVerse("Jeremiah", 20, 18, "NIV"),
                ],
                "",
            ),
        )

    def test_multiple_ranges(self):
        self.assertEqual(
            BibleVerse.parse("Psalm 13:1-2,5-6,9 (KJV)"),
            (
                [
                    BibleVerse("Psalm", 13, 1, "KJV"),
                    BibleVerse("Psalm", 13, 2, "KJV"),
                    BibleVerse("Psalm", 13, 5, "KJV"),
                    BibleVerse("Psalm", 13, 6, "KJV"),
                    BibleVerse("Psalm", 13, 9, "KJV"),
                ],
                "",
            ),
        )

    def test_starts_with_verse(self):
        self.assertEqual(
            BibleVerse.parse(
                "John 3:16 (NLT) is a Bible verse. This whole text is not a Bible verse, but for simplicity we'll still parse the reference to John 3:16."
            ),
            (
                [BibleVerse("John", 3, 16, "NLT")],
                " is a Bible verse. This whole text is not a Bible verse, but for simplicity we'll still parse the reference to John 3:16.",
            ),
        )

    def test_not_a_verse(self):
        self.assertIsNone(
            BibleVerse.parse(
                "This string is not a Bible verse, even if it mentions John 3:16 (NIV)"
            )
        )

    def test_unicode(self):
        self.assertIsNone(BibleVerse.parse("éà\u00a0🤠"))

    def test_invalid_chapter(self):
        self.assertIsNone(BibleVerse.parse("Genesis A:1 (NLT)"))

    def test_invalid_verse(self):
        self.assertIsNone(BibleVerse.parse("Genesis 1:A (NLT)"))
