# pyright: reportPrivateUsage=false

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import List, Set
from unittest.mock import create_autospec, sentinel

from autochecklist.base_config import BaseConfig
from autochecklist.messenger import Messenger
from autochecklist.task import FunctionFinder, TaskGraph, TaskModel, _TaskThread


class TaskGraphTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_linear_graph_and_transformations(self):
        def fill_placeholders(text: str) -> str:
            return text + "*"

        config = create_autospec(BaseConfig)
        config.fill_placeholders.side_effect = fill_placeholders
        function_finder = create_autospec(FunctionFinder)
        # The value for task c is deliberately omitted. The TaskGraph
        # constructor should use None for missing keys.
        function_finder.find_functions.return_value = {"a": sentinel.func_a, "b": None}

        task = TaskModel(
            name="root",
            subtasks=[
                TaskModel(name="a", description="D A"),
                TaskModel(name="b", description="D B", prerequisites={"a"}),
                # The dependency of task c on task a is redundant. The
                # TaskGraph constructor should ignore it and put everything in
                # one thread.
                TaskModel(name="c", description="D C", prerequisites={"a", "b"}),
            ],
        )
        graph = TaskGraph(
            task,
            messenger=_get_noop_messenger(),
            function_finder=function_finder,
            config=config,
        )
        actual = [ThreadData.from_thread(th) for th in graph._threads]
        expected = [
            ThreadData(
                name="C",
                tasks=[
                    TaskData(
                        name="a", description="D A*", index=1, func=sentinel.func_a
                    ),
                    TaskData(name="b", description="D B*", index=2),
                    TaskData(name="c", description="D C*", index=3),
                ],
                prerequisites=set(),
            )
        ]
        self.assertEqual(expected, actual)

    def test_dependency_on_inner_task(self):
        # If you depend on an inner task, you depend on all its subtasks.
        # Resulting redundant dependencies should be removed.
        task = TaskModel(
            name="root",
            subtasks=[
                TaskModel(
                    name="a",
                    subtasks=[
                        TaskModel(name="a1", description="D a1"),
                        TaskModel(name="a2", description="D a2"),
                        TaskModel(name="a3", description="D a3", prerequisites={"a2"}),
                    ],
                ),
                TaskModel(name="b", description="D b", prerequisites={"a"}),
            ],
        )
        graph = TaskGraph(
            task,
            messenger=_get_noop_messenger(),
            function_finder=_get_noop_function_finder(),
            config=_get_noop_config(),
        )
        actual_threads = [ThreadData.from_thread(th) for th in graph._threads]

        expected_threads = [
            ThreadData(
                name="A1", tasks=[TaskData(name="a1", description="D a1", index=1)]
            ),
            ThreadData(
                name="A3",
                tasks=[
                    TaskData(name="a2", description="D a2", index=2),
                    TaskData(name="a3", description="D a3", index=3),
                ],
            ),
            ThreadData(
                name="B",
                tasks=[TaskData(name="b", description="D b", index=4)],
                prerequisites={"A1", "A3"},
            ),
        ]

        self.assertEqual(expected_threads, actual_threads)

    def test_dependency_from_inner_task(self):
        # If an inner task has a dependency, that dependency applies to all its
        # subtasks. Resulting redundant dependencies should be removed.
        task = TaskModel(
            name="root",
            subtasks=[
                TaskModel(name="a", description="D a"),
                TaskModel(
                    name="b",
                    prerequisites={"a"},
                    subtasks=[
                        TaskModel(name="b1", description="D b1"),
                        TaskModel(name="b2", description="D b2"),
                        TaskModel(name="b3", description="D b3", prerequisites={"b2"}),
                    ],
                ),
            ],
        )

        graph = TaskGraph(
            task,
            messenger=_get_noop_messenger(),
            function_finder=_get_noop_function_finder(),
            config=_get_noop_config(),
        )
        actual_threads = [ThreadData.from_thread(th) for th in graph._threads]

        expected_threads = [
            ThreadData(
                name="A", tasks=[TaskData(name="a", description="D a", index=1)]
            ),
            ThreadData(
                name="B1",
                tasks=[TaskData(name="b1", description="D b1", index=2)],
                prerequisites={"A"},
            ),
            ThreadData(
                name="B3",
                tasks=[
                    TaskData(name="b2", description="D b2", index=3),
                    TaskData(name="b3", description="D b3", index=4),
                ],
                prerequisites={"A"},
            ),
        ]

        self.assertEqual(expected_threads, actual_threads)

    def test_out_of_order_tasks(self):
        # If the tasks are inputted out of order, they should be sorted
        # properly (so that tasks only depend on earlier tasks), but as close
        # to the original order as possible.
        task = TaskModel(
            name="root",
            subtasks=[
                TaskModel(name="a", description="D a", prerequisites={"c"}),
                TaskModel(name="b", description="D b", prerequisites={"c"}),
                TaskModel(name="c", description="D c"),
            ],
        )
        graph = TaskGraph(
            task,
            messenger=_get_noop_messenger(),
            function_finder=_get_noop_function_finder(),
            config=_get_noop_config(),
        )
        actual_threads = [ThreadData.from_thread(th) for th in graph._threads]

        expected_threads = [
            ThreadData(
                name="C", tasks=[TaskData(name="c", description="D c", index=1)]
            ),
            ThreadData(
                name="A",
                tasks=[TaskData(name="a", description="D a", index=2)],
                prerequisites={"C"},
            ),
            ThreadData(
                name="B",
                tasks=[TaskData(name="b", description="D b", index=3)],
                prerequisites={"C"},
            ),
        ]

        self.assertEqual(expected_threads, actual_threads)

    def test_self_cycle(self):
        task = TaskModel(name="root", description="x", prerequisites={"root"})
        with self.assertRaises(ValueError) as cm:
            TaskGraph(
                task,
                messenger=_get_noop_messenger(),
                function_finder=_get_noop_function_finder(),
                config=_get_noop_config(),
            )
        self.assertEqual(
            "The task graph contains at least one cycle. For example: root -> root.",
            str(cm.exception),
        )

    def test_multiple_cycles(self):
        task = TaskModel(
            name="root",
            subtasks=[
                TaskModel(name="A", description="A", prerequisites={"B", "D"}),
                TaskModel(name="B", description="B", prerequisites={"C"}),
                TaskModel(name="C", description="C", prerequisites={"A"}),
                TaskModel(name="D", description="D", prerequisites={"E"}),
                TaskModel(name="E", description="E", prerequisites={"A"}),
            ],
        )
        with self.assertRaises(ValueError) as cm:
            TaskGraph(
                task,
                messenger=_get_noop_messenger(),
                function_finder=_get_noop_function_finder(),
                config=_get_noop_config(),
            )
        self.assertRegex(
            str(cm.exception),
            r"^The task graph contains at least one cycle\. For example: (A -> B -> C -> A|A -> D -> E -> A)\.$",
        )

    def test_invalid_prerequisite(self):
        task = TaskModel(name="foo", description="Desc", prerequisites={"bar"})
        with self.assertRaises(ValueError) as cm:
            TaskGraph(
                task,
                messenger=_get_noop_messenger(),
                function_finder=_get_noop_function_finder(),
                config=_get_noop_config(),
            )
        self.assertEqual(
            f"The prerequisite 'bar' could not be found.", str(cm.exception)
        )


@dataclass(frozen=True)
class ThreadData:
    name: str
    tasks: List[TaskData]
    prerequisites: Set[str] = field(default_factory=set)

    @staticmethod
    def from_thread(thread: _TaskThread) -> ThreadData:
        return ThreadData(
            name=thread.name,
            tasks=[
                TaskData(
                    name=ta.name,
                    description=ta._description,
                    index=ta.index,
                    func=ta._run,
                )
                for ta in thread.tasks
            ],
            prerequisites={p.name for p in thread.prerequisites},
        )


@dataclass(frozen=True)
class TaskData:
    name: str
    description: str
    index: int
    func: object = None


def _get_noop_messenger() -> Messenger:
    return create_autospec(Messenger)


def _get_noop_config() -> BaseConfig:
    def identity(x: str) -> str:
        return x

    config = create_autospec(BaseConfig)
    config.fill_placeholders.side_effect = identity
    return config


def _get_noop_function_finder() -> FunctionFinder:
    function_finder = create_autospec(FunctionFinder)
    function_finder.find_functions.return_value = {}
    return function_finder
