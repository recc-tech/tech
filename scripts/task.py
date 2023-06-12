from __future__ import annotations

import inspect
import json
import traceback
from inspect import Parameter, Signature
from pathlib import Path
from threading import Thread
from types import ModuleType
from typing import Any, Callable, Dict, List, Set, Tuple, Union

from base_config import BaseConfig
from messenger import LogLevel, Messenger


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

    _name: str
    """
    Name of the task.
    """

    def __init__(
        self,
        func: Callable[[], None],
        fallback_message: str,
        messenger: Messenger,
        name: str,
    ):
        self._run = func
        self._fallback_message = fallback_message
        self._messenger = messenger
        self._name = name

    def run(self):
        self._messenger.log(self._name, LogLevel.INFO, f"Task started.")
        try:
            self._run()
            self._messenger.log(
                self._name,
                LogLevel.INFO,
                f"Task completed automatically.",
            )
        except Exception as e:
            if isinstance(e, NotImplementedError):
                self._messenger.log(
                    self._name,
                    LogLevel.DEBUG,
                    f"Task is not yet implemented. Requesting user input.",
                )
            else:
                self._messenger.log_separate(
                    self._name,
                    LogLevel.ERROR,
                    f"Task failed with an exception: {e}",
                    f"Task failed with an exception:\n{traceback.format_exc()}",
                )

            self._messenger.wait(self._name, self._fallback_message)

            self._messenger.log(self._name, LogLevel.INFO, f"Task completed manually.")


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
        super().__init__(name=name, daemon=True)

    def run(self):
        # Wait for prerequisites
        for p in self.prerequisites:
            p.join()

        # Run tasks
        for t in self.tasks:
            t.run()


class TaskGraph:
    _before: Union[TaskGraph, None]
    _threads: Set[TaskThread]
    _after: Union[TaskGraph, None]

    def __init__(self, threads: Set[TaskThread], messenger: Messenger):
        self._threads = threads
        self._before = None
        self._after = None
        self._messenger = messenger

    def run(self) -> None:
        if self._before is not None:
            self._before.run()

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

        # Wait for main tasks to finish
        # Periodically stop waiting for the thread to check whether the user wants to exit
        for thread in self._threads:
            while thread.is_alive():
                thread.join(timeout=1)
                # If the messenger is shut down, it means the user wants to end the program
                if self._messenger.shutdown_requested():
                    raise KeyboardInterrupt()

        if self._after is not None:
            self._after.run()

    @staticmethod
    def load(
        task_list_file: Path,
        function_finder: FunctionFinder,
        messenger: Messenger,
        config: BaseConfig,
    ) -> TaskGraph:
        with open(task_list_file, "r") as f:
            json_data: Dict[str, Any] = json.load(f)
            tasks: List[Dict[str, Any]] = json_data["tasks"]
            before_tasks: List[Dict[str, Any]] = (
                json_data["before"] if "before" in json_data else []
            )
            after_tasks: List[Dict[str, Any]] = (
                json_data["after"] if "after" in json_data else []
            )

        all_task_names: List[str] = [
            t["name"] for t in before_tasks + tasks + after_tasks
        ]
        function_index = function_finder.find_functions(all_task_names)

        graph = TaskGraph._load(tasks, function_index, messenger, config)
        if len(before_tasks) > 0:
            graph._before = TaskGraph._load(
                before_tasks, function_index, messenger, config
            )
        if len(after_tasks) > 0:
            graph._after = TaskGraph._load(
                after_tasks, function_index, messenger, config
            )
        return graph

    @staticmethod
    def _load(
        tasks: List[Dict[str, Any]],
        function_index: Dict[str, Callable[[], None]],
        messenger: Messenger,
        config: BaseConfig,
    ) -> TaskGraph:
        unsorted_task_names: Set[str] = {t["name"] for t in tasks}

        TaskGraph._validate_tasks(tasks)

        # Use a dictionary for fast access to tasks by name
        task_index: Dict[str, Tuple[str, List[str], List[str]]] = dict()
        for t in tasks:
            description = config.fill_placeholders(t["description"])
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
            sorted_task_names, task_index, function_index, messenger
        )

        return TaskGraph(threads, messenger)

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
        function_index: Dict[str, Callable[[], None]],
        messenger: Messenger,
    ) -> Set[TaskThread]:
        thread_for_task: Dict[str, TaskThread] = {}
        threads: Set[TaskThread] = set()

        while len(sorted_task_names) > 0:
            thread = TaskThread(name="", tasks=[], prerequisites=set())

            task_name = sorted_task_names.pop()
            (description, depends_on, prerequisite_of) = task_index[task_name]
            while True:
                task_obj = Task(
                    func=function_index[task_name],
                    fallback_message=description,
                    messenger=messenger,
                    name=task_name,
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


class FunctionFinder:
    _TASK_NAME = "FUNCTION FINDER"

    def __init__(
        self, module: Union[ModuleType, None], arguments: Set[Any], messenger: Messenger
    ):
        self._module = module
        self._arguments = arguments
        self._messenger = messenger

    def find_functions(self, names: List[str]) -> Dict[str, Callable[[], None]]:
        if self._module is None:
            self._messenger.log(
                self._TASK_NAME,
                LogLevel.DEBUG,
                "No module with task implementations was provided.",
            )
            return {f: FunctionFinder._unimplemented_task for f in names}

        self._detect_unused_functions(names)
        return {name: self._find_function_with_args(name) for name in names}

    def _find_function_with_args(self, name: str) -> Callable[[], None]:
        original_function = self._find_original_function(name)
        if original_function is None:
            # TODO: Just return None instead of a fake function here?
            return FunctionFinder._unimplemented_task
        signature = inspect.signature(original_function)

        if signature.return_annotation not in [None, "None", Signature.empty]:
            self._messenger.log(
                self._TASK_NAME,
                LogLevel.WARN,
                f"The function for task '{name}' should return nothing, but claims to have a return value.",
            )

        try:
            inputs = self._find_arguments(signature, name)
        except Exception as e:
            raise ValueError(f"Failed to find arguments for function '{name}'.") from e

        def f():
            original_function(**inputs)

        return f

    def _find_original_function(self, name: str) -> Union[None, Callable[..., Any]]:
        try:
            function: Callable[..., None] = getattr(self._module, name)
            self._messenger.log(
                self._TASK_NAME,
                LogLevel.DEBUG,
                f"Found implementation for task '{name}'.",
            )
        except AttributeError:
            self._messenger.log(
                self._TASK_NAME,
                LogLevel.DEBUG,
                f"No implementation found for task '{name}'.",
            )
            return None
        return function

    def _find_arguments(self, signature: Signature, task_name: str) -> Dict[str, Any]:
        params = signature.parameters.values()
        # TODO: Check for unused args
        return {p.name: self._find_single_argument(p, task_name) for p in params}

    def _find_single_argument(self, param: Parameter, task_name: str) -> Any:
        if param.name == "task_name" and param.annotation == str:
            return task_name

        matching_args = [
            a for a in self._arguments if issubclass(type(a), param.annotation)
        ]
        if len(matching_args) < 1:
            raise ValueError(f"Parameter '{param.name}' is unknown.")
        elif len(matching_args) > 1:
            raise ValueError(
                f"Parameter '{param.name}' is ambiguous - there are multiple arguments that could be assigned to it."
            )
        else:
            return matching_args[0]

    def _detect_unused_functions(self, used_function_names: List[str]):
        all_functions = inspect.getmembers(self._module, inspect.isfunction)
        all_public_function_names = {
            name for (name, _) in all_functions if not name.startswith("_")
        }

        unused_function_names = {
            name
            for name in all_public_function_names
            if name not in used_function_names
        }
        for name in unused_function_names:
            self._messenger.log(
                self._TASK_NAME,
                LogLevel.WARN,
                f"Function '{name}' is not used by any task.",
            )

    @staticmethod
    def _unimplemented_task() -> None:
        raise NotImplementedError()
