from __future__ import annotations

import importlib
import json
from datetime import datetime
from logging import DEBUG, INFO, WARN
from pathlib import Path
from threading import Thread
from typing import Any, Callable, Dict, List, Set, Tuple

from messenger import Messenger


class Task:
    """
    Represents a single, independent task.
    """

    _run: Callable[[], None]
    """
    Function which performs the given task, but without logging or exception handling.
    """

    _fallback_message: str
    """
    Instructions to show to the user in case the function raises an exception.
    """

    _messenger: Messenger
    """
    Messenger to use for logging and input.
    """

    def __init__(
        self, func: Callable[[], None], fallback_message: str, messenger: Messenger
    ):
        self._run = func
        self._fallback_message = fallback_message
        self._messenger = messenger

    def run(self):
        self._messenger.log(DEBUG, f"Running task '{self._run.__name__}'.")
        try:
            self._run()
            self._messenger.log(
                INFO, f"Task '{self._run.__name__}' completed successfully."
            )
        except Exception as e:
            if isinstance(e, NotImplementedError):
                self._messenger.log(
                    DEBUG,
                    f"Task '{self._run.__name__}' is not yet implemented. Requesting user input.",
                )
            else:
                self._messenger.log(
                    WARN,
                    f"Task '{self._run.__name__}' failed with an exception: {e}",
                )

            message = f"{self._fallback_message} When you are done, press ENTER."
            self._messenger.wait_for_input(message)


class TaskThread(Thread):
    """
    Represents a sequence of tasks.
    """

    def __init__(
        self,
        name: str,
        tasks: List[Task],
        prerequisites: Set[TaskThread],
    ):
        """
        Creates a new `Thread` with the given name that runs the given tasks, but only after all prerequisite threads have finished.
        """
        self.tasks = tasks
        self.prerequisites = prerequisites
        super().__init__(name=name)

    def run(self):
        # Wait for prerequisites
        for p in self.prerequisites:
            p.join()

        # Run tasks
        for t in self.tasks:
            t.run()


class TaskGraph:
    _threads: Set[TaskThread]

    def __init__(self, threads: Set[TaskThread]):
        self._threads = threads

    @staticmethod
    def load(
        task_file: Path, message_series: str, message_title: str, messenger: Messenger
    ) -> TaskGraph:
        with open(task_file, "r") as f:
            tasks: List[Dict[str, Any]] = json.load(f)["tasks"]

        unsorted_task_names: Set[str] = {t["name"] for t in tasks}

        TaskGraph._validate_tasks(tasks)

        # Use a dictionary for fast access to tasks by name
        task_index: Dict[str, Tuple[str, List[str], List[str]]] = dict()
        for t in tasks:
            description = TaskGraph._fill_placeholders(
                t["description"],
                message_series=message_series,
                message_title=message_title,
            )
            task_index[t["name"]] = (description, t["depends_on"], [])

        # Add backwards links for convenience
        for t in unsorted_task_names:
            (_, depends_on, _) = task_index[t]
            for prereq in depends_on:
                prereq_info = task_index[prereq]
                prereq_info[2].append(t)
                task_index[prereq] = prereq_info

        sorted_task_names = TaskGraph._topological_sort(unsorted_task_names, task_index)

        threads = TaskGraph._create_and_combine_threads(
            sorted_task_names, task_index, task_file, messenger
        )

        return TaskGraph(threads)

    def start(self) -> None:
        # Need to start threads in order because you cannot join a thread that has not yet started
        started_thread_names: Set[str] = set()
        unstarted_threads = {t for t in self._threads}
        while len(unstarted_threads) > 0:
            thread_to_start = None
            for thread in unstarted_threads:
                prerequisite_names = {t.name for t in thread.prerequisites}
                if all([name in started_thread_names for name in prerequisite_names]):
                    thread_to_start = thread
            if thread_to_start is None:
                raise RuntimeError("Circular dependency in TaskGraph object.")
            thread_to_start.start()
            started_thread_names.add(thread_to_start.name)
            unstarted_threads.remove(thread_to_start)

    def join(self) -> None:
        for thread in self._threads:
            thread.join()

    @staticmethod
    def _validate_tasks(tasks: List[Dict[str, Any]]):
        # Check that required fields are present
        for t in tasks:
            if "name" not in t:
                raise ValueError('Missing field "name" in task.')
            name = t["name"]
            if "description" not in t:
                raise ValueError(f'Missing field "description" for task "{name}".')
            if "depends_on" not in t:
                raise ValueError(f'Missing field "depends_on" for task "{name}".')

        # Check for duplicate names
        task_name_list: List[str] = [t["name"] for t in tasks]
        task_name_set = set(task_name_list)
        for name in task_name_set:
            task_name_list.remove(name)
        if len(task_name_list) > 0:
            raise ValueError(
                f"The following task names are not unique: {', '.join(task_name_list)}"
            )

        # Check for invalid dependencies
        for t in tasks:
            for p in t["depends_on"]:
                if p not in task_name_set:
                    raise ValueError(f'Unrecognized dependency "{p}".')

    @staticmethod
    def _fill_placeholders(s: str, message_series: str, message_title: str) -> str:
        date_ymd = datetime.now().strftime("%Y-%m-%d")
        s = (
            s.replace("%{DATE_MDY}%", datetime.now().strftime("%B %d, %Y"))
            .replace("%{DATE_YMD}%", date_ymd)
            .replace("%{MESSAGE_SERIES}%", message_series)
            .replace("%{MESSAGE_TITLE}%", message_title)
            .replace(
                "%{CAPTIONS_DIR}%", f"D:\\Users\\Tech\\Documents\\Captions\\{date_ymd}"
            )
        )
        # TODO: Check if s still contains '%{' or '}%'
        return s

    @staticmethod
    def _topological_sort(
        task_names: Set[str], task_index: Dict[str, Tuple[str, List[str], List[str]]]
    ) -> List[str]:
        """
        Sorts the given set of tasks such that each task depends only on tasks that occur later in the list.
        """
        ordered_task_names: List[str] = []
        while len(task_names) > 0:
            # Find a task such that all the tasks that depend on it are already in the output list
            task_to_remove = None
            for t in task_names:
                (_, _, prerequisite_of) = task_index[t]
                if all([x in ordered_task_names for x in prerequisite_of]):
                    task_to_remove = t
                    break
            # A graph can be sorted topologically iff it is acyclic
            if task_to_remove is None:
                raise ValueError("The task graph contains circular dependencies.")
            # Add task to the output list
            ordered_task_names.append(task_to_remove)
            task_names.remove(task_to_remove)
        return ordered_task_names

    @staticmethod
    def _create_and_combine_threads(
        sorted_task_names: List[str],
        task_index: Dict[str, Tuple[str, List[str], List[str]]],
        task_filename: Path,
        messenger: Messenger,
    ) -> Set[TaskThread]:
        thread_for_task: Dict[str, TaskThread] = {}
        threads: Set[TaskThread] = set()
        while len(sorted_task_names) > 0:
            thread = TaskThread(name="", tasks=[], prerequisites=set())

            task_name = sorted_task_names.pop()
            (description, depends_on, prerequisite_of) = task_index[task_name]
            while True:
                # Look for functions in a Python module with the same name as the task list
                module_name = task_filename.with_suffix("").name
                f = TaskGraph._find_function(module_name, task_name)
                task_obj = Task(
                    func=f, fallback_message=description, messenger=messenger
                )
                thread.tasks.append(task_obj)

                thread_for_task[task_name] = thread

                for dependency_name in depends_on:
                    prerequisite_thread = thread_for_task[dependency_name]
                    # Don't let a thread depend on itself
                    if prerequisite_thread is thread:
                        continue
                    thread.prerequisites.add(prerequisite_thread)

                # Combine tasks into one thread as long as the current task is a prerequisite of only one task and that
                # task depends only on the current task
                if len(prerequisite_of) != 1:
                    break
                next_task_name = prerequisite_of[0]
                (next_description, next_depends_on, next_prerequisite_of) = task_index[
                    next_task_name
                ]
                if len(next_depends_on) != 1:
                    break

                task_name = next_task_name
                sorted_task_names.remove(task_name)
                (description, depends_on, prerequisite_of) = (
                    next_description,
                    next_depends_on,
                    next_prerequisite_of,
                )

            # Name each thread after its last task
            thread.name = TaskGraph._snake_case_to_pascal_case(task_name)

            threads.add(thread)

        return threads

    @staticmethod
    def _snake_case_to_pascal_case(snake: str) -> str:
        """
        Converts a string from scake_case to PascalCase.
        """
        words = [x for x in snake.split("_") if x]
        capitalized_words = [w[0].upper() + w[1:] for w in words]
        return "".join(capitalized_words)

    @staticmethod
    def _find_function(module_name: str, function_name: str) -> Callable[[], None]:
        module = importlib.import_module(module_name)
        try:
            function = getattr(module, function_name)
            # TODO: Check that the function has the right signature? Try using inspect.signature()
        except AttributeError:
            function = TaskGraph._unimplemented_task
        return function

    @staticmethod
    def _unimplemented_task() -> None:
        raise NotImplementedError()
