import unittest
from pathlib import Path
from typing import Dict, List

import config
import manage_config
from config import Colour, ConfigReader, StringTemplate


class ConfigTestCase(unittest.TestCase):
    def test_load_all(self) -> None:
        for p in config.list_profiles():
            manage_config.test_load_one_config(p)

    def test_resolve_simple(self) -> None:
        reader = ConfigReader({"foo": "A %{bar}%", "bar": "B"}, strict=True)
        self.assertEqual({"foo": "A B", "bar": "B"}, reader.dump())

    def test_resolve_multiple(self) -> None:
        reader = ConfigReader(
            {
                "foo": "%{bar}% %{baz}%",
                "bar": "B %{baz}%",
                "baz": "C %{waldo}%",
                "waldo": "Waldo",
            },
            strict=True,
        )
        expected_data = {
            "foo": "B C Waldo C Waldo",
            "bar": "B C Waldo",
            "baz": "C Waldo",
            "waldo": "Waldo",
        }
        self.assertEqual(expected_data, reader.dump())

    def test_resolve_circular_reference_0(self) -> None:
        data: Dict[str, object] = {"foo": "%{bar}%", "bar": "%{bar}%"}
        with self.assertRaises(ValueError) as cm:
            ConfigReader(data, strict=False)
        e = cm.exception
        messages: List[str] = []
        while e != None:
            messages.append(str(e))
            e = e.__cause__
        self.assertIn(
            "Failed to fill placeholders in configuration value foo.",
            messages,
        )
        self.assertIn(
            "Circular reference in configuration: bar --> bar.",
            messages,
        )

    def test_resolve_circular_reference_2(self) -> None:
        data: Dict[str, object] = {"foo": "%{bar}%", "bar": "%{baz}%", "baz": "%{foo}%"}
        with self.assertRaises(ValueError) as cm:
            ConfigReader(data, strict=False)
        e = cm.exception
        messages: List[str] = []
        while e != None:
            messages.append(str(e))
            e = e.__cause__
        self.assertIn(
            "Failed to fill placeholders in configuration value foo.",
            messages,
        )
        self.assertIn(
            "Circular reference in configuration: foo --> bar --> baz --> foo.",
            messages,
        )

    def test_read_valid(self) -> None:
        reader = ConfigReader(
            {
                "foo": "%{bar}%/%{baz}%",
                # It's fine to have config values that aren't used directly by
                # the app, as long as they're used in at least one other value
                "bar": "BAR",
                "baz": "BAZ",
                # Unused args are fine; they're always there just in case
                "args.root_repo": "root",
                "int": -5,
                "positive_int": 42,
                "zero": 0,
                "true": True,
                "false": False,
                "direction": "north",
                "strings": ["a", "b"],
                "pi": 3.14159,
                "fs.docs": "~/Documents",
                "fs.file": "%{fs.docs}%/hello.txt",
                "fs.missing": "%{fs.docs}%/!{missing}!",
                "red": "red",
                "blue": "#0000ff",
            },
            strict=True,
        )
        with reader:
            self.assertEqual("BAR/BAZ", reader.get_str("foo"))
            self.assertEqual(-5, reader.get_int("int"))
            self.assertEqual(42, reader.get_positive_int("positive_int"))
            self.assertEqual(0, reader.get_nonneg_int("zero"))
            self.assertEqual(True, reader.get_bool("true"))
            self.assertEqual(False, reader.get_bool("false"))
            self.assertEqual(
                "north",
                reader.get_enum("direction", {"north", "south", "east", "west"}),
            )
            self.assertEqual(["a", "b"], reader.get_str_list("strings"))
            self.assertEqual(3.14159, reader.get_float("pi"))
            # Ints can be used in place of floats
            self.assertEqual(0.0, reader.get_float("zero"))
            self.assertEqual(3.14159, reader.get_positive_float("pi"))
            self.assertEqual(42.0, reader.get_positive_float("positive_int"))
            self.assertEqual(
                Path.home().joinpath("Documents"),
                reader.get_directory("fs.docs"),
            )
            self.assertEqual(
                Path.home().joinpath("Documents", "hello.txt"),
                reader.get_file("fs.file"),
            )
            self.assertEqual(
                StringTemplate("~/Documents/!{missing}!"),
                reader.get_template("fs.missing"),
            )
            self.assertEqual(Colour(r=255, g=0, b=0, a=255), reader.get_colour("red"))
            self.assertEqual(Colour(r=0, g=0, b=255, a=255), reader.get_colour("blue"))

    def test_read_with_unused_keys(self) -> None:
        reader = ConfigReader({"foo": 1, "bar": 2.5}, strict=True)
        with self.assertRaises(ValueError) as cm:
            with reader:
                reader.get_int("foo")
        self.assertEqual(
            "The following configuration values are unrecognized: {'bar'}.",
            str(cm.exception),
        )
