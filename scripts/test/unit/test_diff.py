import unittest

from lib.diff import Deletion, Insertion, NoOp, find_diff


class DiffTestCase(unittest.TestCase):
    def test_know_vs_known(self) -> None:
        actual = find_diff(list("know"), list("known"))
        expected = [NoOp("k"), NoOp("n"), NoOp("o"), NoOp("w"), Insertion("n")]
        self.assertEqual(actual, expected)

    def test_known_vs_know(self) -> None:
        actual = find_diff(list("known"), list("know"))
        expected = [NoOp("k"), NoOp("n"), NoOp("o"), NoOp("w"), Deletion("n")]
        self.assertEqual(actual, expected)

    def test_crown_vs_clown(self) -> None:
        actual = find_diff(list("crown"), list("clown"))
        expected = [
            NoOp("c"),
            Deletion("r"),
            Insertion("l"),
            NoOp("o"),
            NoOp("w"),
            NoOp("n"),
        ]
        self.assertEqual(actual, expected)

    def test_clown_vs_crown(self) -> None:
        actual = find_diff(list("clown"), list("crown"))
        expected = [
            NoOp("c"),
            Deletion("l"),
            Insertion("r"),
            NoOp("o"),
            NoOp("w"),
            NoOp("n"),
        ]
        self.assertEqual(actual, expected)

    def test_saturday_vs_sunday(self) -> None:
        actual = find_diff(list("Saturday"), list("Sunday"))
        expected = [
            NoOp("S"),
            Deletion("a"),
            Deletion("t"),
            NoOp("u"),
            Deletion("r"),
            Insertion("n"),
            NoOp("d"),
            NoOp("a"),
            NoOp("y"),
        ]
        self.assertEqual(actual, expected)

    def test_sunday_vs_saturday(self) -> None:
        actual = find_diff(list("Sunday"), list("Saturday"))
        expected = [
            NoOp("S"),
            Insertion("a"),
            Insertion("t"),
            NoOp("u"),
            Deletion("n"),
            Insertion("r"),
            NoOp("d"),
            NoOp("a"),
            NoOp("y"),
        ]
        self.assertEqual(actual, expected)

    def test_empty_vs_foo(self) -> None:
        actual = find_diff(list(""), list("foo"))
        expected = [Insertion(c) for c in "foo"]
        self.assertEqual(actual, expected)

    def test_foo_vs_empty(self) -> None:
        actual = find_diff(list("foo"), list(""))
        expected = [Deletion(c) for c in "foo"]
        self.assertEqual(actual, expected)

    def test_20250420_message(self) -> None:
        original = [
            "Name Change to RIVERS - Show New Banner.",
            "Isaiah 43:18-19 NLT",
            "John 7:38 NLT",
            "Prayer",
            "Stones Are Rolled Away",
            "Mark 16:1-7 NLT",
            "Stones Keep Things In",
            "Stones Keep Things Out",
            "Stones Separate Us From Living A Full Life",
            "Stones Placed Are Placed, Protected & Padlocked By Our Enemies",
            "Call Out The Stone By Name",
            "Move Towards The Stone Prepared",
            "Keep Moving Towards The Stone",
            "Keep Moving Towards The Stone Looking Up",
            "Keep Moving Towards The Stone Knowing You Can’t Move It Alone",
            "Keep Moving Towards The Stone Believing That The Stone Will Be Rolled Away",
            "Matthew 28:2 NLT",
            "We Become The First Witnesses",
            "God Still Rolls Away Stones",
            "Don’t Let Any Stone Separate You From Jesus Today",
        ]
        edited = [
            "Name Change to RIVERS - Show New Banner.",
            "Isaiah 43:18-19 NLT",
            "John 7:38 NLT",
            "Prayer",
            "Stones Are Rolled Away",
            "Mark 16:1-7 NLT",
            "Stones keep things in or out",
            "Stones Separate Us From Living A Full Life",
            "Stones Placed Are Placed, Protected & Padlocked By Our Enemies",
            "Call Out The Stone By Name",
            "Move Towards The Stone Prepared",
            "Keep Moving Towards The Stone",
            "Keep Moving Towards The Stone Looking Up",
            "Keep Moving Towards The Stone Knowing You Can't Move It Alone",
            "Keep Moving Towards The Stone Believing That The Stone Will Be Rolled Away",
            "Matthew 28:2 NLT",
            "We Become The First Witnesses",
            "God Still Rolls Away Stones",
            "Don't Let Any Stone Separate You From Jesus Today",
            "New line",
            "Newest line",
        ]
        actual = find_diff(original, edited)
        expected = [
            NoOp("Name Change to RIVERS - Show New Banner."),
            NoOp("Isaiah 43:18-19 NLT"),
            NoOp("John 7:38 NLT"),
            NoOp("Prayer"),
            NoOp("Stones Are Rolled Away"),
            NoOp("Mark 16:1-7 NLT"),
            Deletion("Stones Keep Things In"),
            Deletion("Stones Keep Things Out"),
            Insertion("Stones keep things in or out"),
            NoOp("Stones Separate Us From Living A Full Life"),
            NoOp("Stones Placed Are Placed, Protected & Padlocked By Our Enemies"),
            NoOp("Call Out The Stone By Name"),
            NoOp("Move Towards The Stone Prepared"),
            NoOp("Keep Moving Towards The Stone"),
            NoOp("Keep Moving Towards The Stone Looking Up"),
            Deletion("Keep Moving Towards The Stone Knowing You Can’t Move It Alone"),
            Insertion("Keep Moving Towards The Stone Knowing You Can't Move It Alone"),
            NoOp(
                "Keep Moving Towards The Stone Believing That The Stone Will Be Rolled Away"
            ),
            NoOp("Matthew 28:2 NLT"),
            NoOp("We Become The First Witnesses"),
            NoOp("God Still Rolls Away Stones"),
            Deletion("Don’t Let Any Stone Separate You From Jesus Today"),
            Insertion("Don't Let Any Stone Separate You From Jesus Today"),
            Insertion("New line"),
            Insertion("Newest line"),
        ]
        self.assertEqual(actual, expected)

    def test_noop_repr(self) -> None:
        x = NoOp("abc")
        self.assertEqual(eval(repr(x)), x)

    def test_deletion_repr(self) -> None:
        x = Deletion("abc")
        self.assertEqual(eval(repr(x)), x)

    def test_insertion_repr(self) -> None:
        x = Insertion("abc")
        self.assertEqual(eval(repr(x)), x)
