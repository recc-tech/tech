from typing import List

from autochecklist import BaseConfig, DependencyProvider


class MyList:
    def __init__(self):
        self.the_list: List[str] = []


class TestConfig(BaseConfig):
    FOO = "foo-value"
    BAR = "bar-value"
    BAZ = "baz-value"
    QUX = "qux-value"

    def fill_placeholders(self, text: str) -> str:
        text = (
            text.replace("%{FOO}%", self.FOO)
            .replace("%{BAR}%", self.BAR)
            .replace("%{BAZ}%", self.BAZ)
            .replace("%{QUX}%", self.QUX)
        )
        return super().fill_placeholders(text)


class MyDependencyProvider(DependencyProvider):
    def __init__(self, my_list: MyList, config: TestConfig) -> None:
        self._my_list = my_list
        self._config = config

    def get(self, typ: type[object]) -> object:
        if typ == MyList:
            return self._my_list
        elif typ == TestConfig:
            return self._config
        else:
            raise ValueError(f"Invalid type {typ}")


def add_foo(my_list: MyList, config: TestConfig):
    my_list.the_list.append(config.FOO)


def add_baz(my_list: MyList, config: TestConfig):
    my_list.the_list.append(config.BAZ)


def add_qux(my_list: MyList, config: TestConfig):
    my_list.the_list.append(config.QUX)


def raise_error():
    raise ValueError("This is an error raised by a task implementation.")
