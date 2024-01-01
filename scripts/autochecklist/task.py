from __future__ import annotations

import inspect
import json
import time
import traceback
from dataclasses import dataclass, field
from inspect import Parameter, Signature
from pathlib import Path
from threading import Thread
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Set

from autochecklist.base_config import BaseConfig
from autochecklist.messenger import (
    Messenger,
    ProblemLevel,
    TaskCancelledException,
    TaskStatus,
    UserResponse,
)


class TaskNotAutomatedError(Exception):
    def __init__(self, message: str = "", allow_retry: bool = False) -> None:
        self.message = message
        self.allow_retry = allow_retry


class TaskGraph:
    def __init__(
        self,
        task: TaskModel,
        messenger: Messenger,
        function_finder: FunctionFinder,
        config: BaseConfig,
    ):
        task_with_normalized_prereqs = _normalize_prerequisites(
            task, set(), _create_name_to_task_dict(task)
        )
        tasks = _get_leaf_tasks(task_with_normalized_prereqs)
        sorted_tasks = _sort_tasks(tasks)
        tasks_with_minimal_prereqs = _remove_redundant_prerequisites(sorted_tasks)
        runnable_tasks = _convert_models_to_tasks(
            tasks_with_minimal_prereqs, messenger, function_finder, config
        )

        messenger.set_task_index_table({t.name: t.index for t in runnable_tasks})

        self._threads = _assign_tasks_to_threads(runnable_tasks, messenger)
        self._messenger = messenger

    def run(self) -> None:
        tasks = [task for thread in self._threads for task in thread.tasks]
        sorted_tasks = sorted(tasks, key=lambda t: t.index)
        for task in sorted_tasks:
            self._messenger.log_status(TaskStatus.NOT_STARTED, "-", task_name=task.name)

        # You cannot join a thread that has not yet started, so the threads
        # must be in the right order
        for t in self._threads:
            t.start()

        # Periodically stop waiting for the thread to check whether the user
        # wants to exit
        for thread in self._threads:
            while thread.is_alive() and not self._messenger.is_closed:
                thread.join(timeout=0.5)
            if self._messenger.is_closed:
                return self._cancel_all()

    def _cancel_all(self) -> None:
        self._messenger.cancel_all()
        start = time.monotonic()
        timeout = 30
        iter_threads = iter(self._threads)
        while True:
            t = next(iter_threads, None)
            if t is None:
                break
            # Each thread gets at `timeout` seconds to exit
            t.join(timeout=max(0, timeout + start - time.monotonic()))
        raise KeyboardInterrupt()


class _TaskThread(Thread):
    """A sequence of tasks to be run one after the other."""

    def __init__(
        self,
        name: str,
        tasks: List[_Task],
        prerequisites: Set[_TaskThread],
        messenger: Messenger,
    ):
        """
        Creates a new `Thread` with the given name that runs the given tasks, but only after all prerequisite threads have finished.
        """
        self.tasks = tasks
        self.prerequisites = prerequisites
        self._messenger = messenger
        super().__init__(name=name, daemon=True)

    def run(self):
        # Wait for prerequisites
        for p in self.prerequisites:
            p.join()

        # Run tasks
        for t in self.tasks:
            self._messenger.set_current_task_name(t.name)
            try:
                t.run()
            except KeyboardInterrupt:
                # The program should already be in the process of shutting down
                # if this happens.
                return
            self._messenger.set_current_task_name(None)


class _Task:
    """A single, independent task."""

    def __init__(
        self,
        name: str,
        index: int,
        prerequisites: List[_Task],
        func: Optional[Callable[[], None]],
        description: str,
        only_auto: bool,
        messenger: Messenger,
    ):
        self.name = name
        """Unique name of the task."""
        self.index = index
        """
        Position of the task in the sorted task list. The first task has
        index 1.
        """
        self.prerequisites = prerequisites
        """Tasks that must be completed before this one can run."""
        self._run = func
        """
        Function provided by the client for performing the given task.
        """
        self._description = description
        """
        Instructions to show to the user in case the function raises an
        exception.
        """
        self._only_auto = only_auto
        """If `True`, this task cannot be completed manually."""
        self._messenger = messenger
        """
        Messenger to use for logging and input.
        """

    def run(self):
        while True:
            try:
                self._run_automatically()
                if self._messenger.get_status() not in {
                    TaskStatus.DONE,
                    TaskStatus.SKIPPED,
                }:
                    self._messenger.log_status(
                        TaskStatus.DONE, f"Task completed automatically."
                    )
                return
            except (KeyboardInterrupt, SystemExit):
                raise
            except TaskNotAutomatedError as e:
                self._messenger.log_status(
                    TaskStatus.WAITING_FOR_USER,
                    e.message or "This task is not automated.",
                )
                response = self._run_manually(allow_retry=e.allow_retry)
            except TaskCancelledException:
                self._messenger.log_status(
                    TaskStatus.WAITING_FOR_USER,
                    f"The task was cancelled by the user. Requesting user input.",
                )
                response = self._run_manually(allow_retry=True)
            except BaseException as e:
                self._messenger.log_problem(
                    ProblemLevel.ERROR,
                    f"An error occurred while trying to complete the task automatically: {e}",
                    stacktrace=traceback.format_exc(),
                )
                self._messenger.log_status(
                    TaskStatus.WAITING_FOR_USER,
                    f"The task automation failed. Requesting user input.",
                )
                response = self._run_manually(allow_retry=True)
            if response == UserResponse.DONE:
                self._messenger.log_status(TaskStatus.DONE, "Task completed manually.")
                return
            if response == UserResponse.SKIP:
                self._messenger.log_status(TaskStatus.SKIPPED, "Task skipped.")
                return

    def _run_automatically(self):
        try:
            if self._run is None:
                raise TaskNotAutomatedError()
            self._messenger.log_status(TaskStatus.RUNNING, f"Task started.")
            self._run()
        finally:
            # Disallow cancelling even if there's no task automation just in
            # case it somehow got enabled by accident (e.g., by another task
            # using the wrong name)
            self._messenger.disallow_cancel()

    def _run_manually(self, allow_retry: bool) -> UserResponse:
        allowed_responses = {UserResponse.DONE, UserResponse.RETRY, UserResponse.SKIP}
        if not allow_retry:
            allowed_responses.remove(UserResponse.RETRY)
        if self._only_auto:
            allowed_responses.remove(UserResponse.DONE)
        response = self._messenger.wait(
            self._description, allowed_responses=allowed_responses
        )
        return response


@dataclass(frozen=True)
class TaskModel:
    """Contents of the task list, as read directly from a file."""

    name: str
    description: str = ""
    prerequisites: Set[str] = field(default_factory=set)
    subtasks: List[TaskModel] = field(default_factory=list)
    only_auto: bool = False

    def __post_init__(self):
        object.__setattr__(self, "name", self.name.strip())
        if not self.name:
            raise ValueError("Every task must have a non-blank name.")
        # Needed for the --auto command-line argument
        if self.name.lower() == "none":
            raise ValueError("'none' cannot be used as a task name.")
        if not self.subtasks and not self.description.strip():
            raise ValueError(
                f"Task '{self.name}' has no description. Tasks without subtasks must have a description."
            )
        if self.subtasks and self.description.strip():
            raise ValueError(
                f"Task '{self.name}' has subtasks and a description. If a task has subtasks, its description will not be shown to the user. Prefix the field name with an underscore if you want to use it as a comment."
            )
        if self.subtasks and self.only_auto:
            raise ValueError(
                f"Task '{self.name}' has subtasks and only_auto=True. Tasks with subtasks will not be automated, so they cannot have only_auto=True."
            )

    @classmethod
    def load(cls, file: Path) -> TaskModel:
        """Parse the given file to a `TaskModel`."""
        with open(file, mode="r", encoding="utf-8") as f:
            task = json.load(f)
        return cls._parse(task)

    @classmethod
    def _parse(cls, task: object) -> TaskModel:
        if not isinstance(task, dict):
            raise ValueError(
                f"Expected a task in the form of a Python dictionary, but found an object of type '{type(task)}'."
            )
        task_dict: Dict[str, object] = task

        name = task_dict.get("name", "")
        if not isinstance(name, str):
            raise ValueError(
                f"Expected task name to be a string, but found '{str(name)}' (of type {type(name)})."
            )
        description = task_dict.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"Expected task description to be a string, but task '{name}' has a description of type {type(description)}."
            )
        only_auto = task_dict.get("only_auto", False)
        if not isinstance(only_auto, bool):
            raise ValueError(
                f"Expected only_auto to be a string, but task '{name}' has a value of type {type(only_auto)}."
            )

        unknown_fields = {
            key
            for key in task_dict
            if not str(key).startswith("_")
            and key
            not in {"name", "description", "prerequisites", "subtasks", "only_auto"}
        }
        if unknown_fields:
            raise ValueError(
                f"Task '{name}' has unknown fields: {', '.join(unknown_fields)}. Prefix them with an underscore if they are meant as comments.",
            )

        return cls(
            name=name,
            description=description,
            prerequisites=cls._parse_prerequisites(
                task_dict.get("prerequisites", None)
            ),
            subtasks=cls._parse_subtasks(task_dict.get("subtasks", None)),
            only_auto=only_auto,
        )

    @classmethod
    def _parse_prerequisites(cls, prerequisites: object) -> Set[str]:
        if prerequisites is None:
            prerequisites = []
        if not isinstance(prerequisites, list):
            raise ValueError(
                f"Expected the prerequisites to be a list, but found an object of type '{type(prerequisites)}'."
            )
        prereqs: List[object] = prerequisites
        str_prereqs: List[str] = []
        for i, p in enumerate(prereqs):
            if not isinstance(p, str):
                raise ValueError(
                    f"Expected the prerequisites to be a list of strings, but found that the element at index {i} is of type '{type(p)}'."
                )
            str_prereqs.append(p)
        return {p.strip() for p in str_prereqs}

    @classmethod
    def _parse_subtasks(cls, subtasks: object) -> List[TaskModel]:
        if subtasks is None:
            subtasks = []
        if not isinstance(subtasks, list):
            raise ValueError(
                f"Expected the subtasks to be a list, but found an object of type '{type(subtasks)}'."
            )
        subtasks_list: List[object] = subtasks
        return [cls._parse(st) for st in subtasks_list]


class FunctionFinder:
    def __init__(
        self,
        module: Optional[ModuleType],
        arguments: List[Any],
        messenger: Messenger,
    ):
        self._module = module
        self._arguments = arguments
        self._messenger = messenger

    def find_functions(
        self, names: List[str]
    ) -> Dict[str, Optional[Callable[[], None]]]:
        """
        Return a mapping from task name to function implementing that task, or
        `None` if there's no function for that task.
        """
        if self._module is None:
            self._messenger.log_debug(
                "No module with task implementations was provided.",
            )
            return {f: None for f in names}

        unused_function_names = self._detect_unused_functions(names)
        if len(unused_function_names) > 0:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"The following functions are not used by any task: {', '.join(unused_function_names)}",
            )

        function_assignments = {
            name: self._find_function_with_args(name) for name in names
        }

        auto_tasks = {k for (k, v) in function_assignments.items() if v is not None}
        self._messenger.log_debug(
            f"Implementations were found for the following tasks: {', '.join(auto_tasks)}."
        )
        manual_tasks = {k for (k, v) in function_assignments.items() if v is None}
        self._messenger.log_debug(
            f"No implementation was found for the following tasks: {', '.join(manual_tasks)}."
        )

        return function_assignments

    def _find_function_with_args(self, name: str) -> Optional[Callable[[], None]]:
        original_function = self._find_original_function(name)
        if original_function is None:
            return None
        signature = inspect.signature(original_function)

        if signature.return_annotation not in [None, "None", Signature.empty]:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"The function for task '{name}' should return nothing, but claims to have a return value.",
            )

        try:
            inputs = self._find_arguments(signature)
        except Exception as e:
            raise ValueError(f"Failed to find arguments for function '{name}'.") from e

        def f():
            original_function(**inputs)

        return f

    def _find_original_function(self, name: str) -> Optional[Callable[..., object]]:
        try:
            return getattr(self._module, name)
        except AttributeError:
            return None

    def _find_arguments(self, signature: Signature) -> Dict[str, object]:
        params = signature.parameters.values()
        # TODO: Check for unused args
        return {p.name: self._find_single_argument(p) for p in params}

    def _find_single_argument(self, param: Parameter) -> Any:
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

    def _detect_unused_functions(self, used_function_names: List[str]) -> Set[str]:
        all_functions = inspect.getmembers(self._module, inspect.isfunction)
        all_public_function_names = {
            name for (name, _) in all_functions if not name.startswith("_")
        }

        unused_function_names = {
            name
            for name in all_public_function_names
            if name not in used_function_names
        }
        return unused_function_names


def _create_name_to_task_dict(task: TaskModel) -> Dict[str, TaskModel]:
    """Create a dictionary that maps task names to tasks."""

    def _fill_dict(t: TaskModel, name_to_task: Dict[str, TaskModel]):
        if t.name in name_to_task:
            raise ValueError(f"The name '{t.name}' is used by more than one task.")
        name_to_task[t.name] = t
        for s in t.subtasks:
            _fill_dict(s, name_to_task)

    output: Dict[str, TaskModel] = {}
    _fill_dict(task, output)
    return output


def _normalize_prerequisites(
    task: TaskModel, upper_prereqs: Set[str], name_to_task: Dict[str, TaskModel]
) -> TaskModel:
    """
    Push the prerequisites down to the leaf tasks and expand them to only refer
    to leaf tasks.
    """
    combined_prerequisites = task.prerequisites.union(upper_prereqs)
    if not task.subtasks:
        expanded_prerequisites: Set[str] = set()
        for task_name in combined_prerequisites:
            try:
                prereq = name_to_task[task_name]
            except KeyError:
                raise ValueError(
                    f"The prerequisite '{task_name}' could not be found."
                ) from None
            expanded_prerequisites = expanded_prerequisites.union(
                {t.name for t in _get_leaf_tasks(prereq)}
            )
        return TaskModel(
            name=task.name,
            description=task.description,
            prerequisites=expanded_prerequisites,
            subtasks=task.subtasks,
            only_auto=task.only_auto,
        )
    else:
        return TaskModel(
            name=task.name,
            description=task.description,
            prerequisites=set(),
            subtasks=[
                _normalize_prerequisites(t, combined_prerequisites, name_to_task)
                for t in task.subtasks
            ],
            only_auto=task.only_auto,
        )


def _get_leaf_tasks(task: TaskModel) -> List[TaskModel]:
    if not task.subtasks:
        return [task]
    else:
        tasks: List[TaskModel] = []
        for t in task.subtasks:
            tasks.extend(_get_leaf_tasks(t))
        return tasks


def _sort_tasks(tasks: List[TaskModel]) -> List[TaskModel]:
    """
    Sort the list so that tasks only depend on tasks that come earlier in the
    list.
    """
    tasks = list(tasks)  # Avoid mutating the input list
    sorted_tasks: List[TaskModel] = []
    sorted_task_names: List[str] = []
    while tasks:
        found = False
        for t in tasks:
            if any([p not in sorted_task_names for p in t.prerequisites]):
                continue
            sorted_tasks.append(t)
            sorted_task_names.append(t.name)
            tasks.remove(t)
            found = True
            break
        if not found:
            try:
                cycle = _find_cycle(tasks)
            except Exception as e:
                raise ValueError(
                    "The task graph contains at least one cycle, but no example could be found."
                ) from e
            raise ValueError(
                f"The task graph contains at least one cycle. For example: {' -> '.join(cycle)}."
            )
    return sorted_tasks


def _find_cycle(tasks: List[TaskModel]) -> List[str]:
    """Find a single example of a cycle in the given task list."""
    name_to_task = {t.name: t for t in tasks}
    next = {
        n: [x for x in t.prerequisites if x in name_to_task][0]
        for (n, t) in name_to_task.items()
    }

    tortoise = list(name_to_task.keys())[0]
    hare = tortoise
    tortoise = next[tortoise]
    hare = next[next[hare]]
    while tortoise != hare:
        tortoise = next[tortoise]
        hare = next[next[hare]]

    cycle = [hare]
    t = next[hare]
    while t != hare:
        cycle.append(t)
        t = next[t]

    # Start the cycle with the minimum name. Having this be consistent makes
    # testing easier.
    first_element = min(cycle)
    first_index = cycle.index(first_element)
    cycle = cycle[first_index:] + cycle[0:first_index]

    # Show that the cycle loops back to the first element
    cycle.append(first_element)

    return cycle


def _remove_redundant_prerequisites(sorted_tasks: List[TaskModel]) -> List[TaskModel]:
    """
    Remove unnecessary prerequisites in the given task list.

    For example, consider the following two graphs:
      - Task B depends on task A, task C depends on tasks A and B.
      - Task B depends on Task A, task C depends on task B.

    In either case, the tasks can only be run in the order A -> B -> C.
    Therefore, so the dependency of task C on task A is redundant and can be
    removed.
    """
    all_prerequisites: Dict[str, Set[str]] = {}
    for task in sorted_tasks:
        all_prerequisites[task.name] = task.prerequisites.union(
            *[all_prerequisites[s] for s in task.prerequisites]
        )

    required_direct_prerequisites: Dict[str, Set[str]] = {}
    for task in sorted_tasks:
        required_direct_prerequisites[task.name] = task.prerequisites.difference(
            *[all_prerequisites[s] for s in task.prerequisites]
        )

    return [
        TaskModel(
            name=t.name,
            description=t.description,
            prerequisites=required_direct_prerequisites[t.name],
            subtasks=[],
            only_auto=t.only_auto,
        )
        for t in sorted_tasks
    ]


def _convert_models_to_tasks(
    models: List[TaskModel],
    messenger: Messenger,
    finder: FunctionFinder,
    config: BaseConfig,
) -> List[_Task]:
    all_task_names = {m.name for m in models}
    auto_tasks = all_task_names if config.auto_tasks is None else config.auto_tasks
    invalid_auto_tasks = [t for t in auto_tasks if t not in all_task_names]
    if invalid_auto_tasks:
        raise ValueError(
            f"The list of tasks to automate includes the following values, which are not valid task names: {','.join(invalid_auto_tasks)}."
        )
    name_to_func = finder.find_functions(list(all_task_names))
    name_to_task: Dict[str, _Task] = {}
    tasks: List[_Task] = []
    for i, m in enumerate(models, start=1):
        func = name_to_func.get(m.name, None)
        if func is None and m.only_auto:
            raise ValueError(
                f"Task '{m.name}' has only_auto=True, but no automation was found for it."
            )
        if func is None and m.name in auto_tasks:
            raise ValueError(
                f"The list of tasks to automate includes '{m.name}', but {m.name} is not automated in the first place."
            )
        if func is not None and m.name not in auto_tasks:
            func = _wrap_non_auto_task(func)
        task = _Task(
            name=m.name,
            index=i,
            prerequisites=[name_to_task[p] for p in m.prerequisites],
            func=func,
            description=config.fill_placeholders(m.description),
            only_auto=m.only_auto,
            messenger=messenger,
        )
        name_to_task[m.name] = task
        tasks.append(task)
    return tasks


def _wrap_non_auto_task(f: Callable[[], None]) -> Callable[[], None]:
    def g() -> None:
        nonlocal called
        if called:
            f()
        else:
            called = True
            raise TaskNotAutomatedError(
                "Task automation skipped because this task is not in the list of tasks to automate. You can retry if you want the task to be automated after all.",
                allow_retry=True,
            )

    called = False
    return g


def _assign_tasks_to_threads(
    tasks: List[_Task], messenger: Messenger
) -> List[_TaskThread]:
    tasks = list(tasks)  # Don't mutate the input
    threads: List[_TaskThread] = []
    task_name_to_thread: Dict[str, _TaskThread] = {}
    dependent_tasks = {
        t.name: [x for x in tasks if any(y.name == t.name for y in x.prerequisites)]
        for t in tasks
    }
    while tasks:
        current_task = tasks[0]
        current_thread_tasks = [current_task]
        # Put as many tasks as possible into the same thread
        while True:
            if len(dependent_tasks[current_task.name]) != 1:
                break
            next_task = dependent_tasks[current_task.name][0]
            if len(next_task.prerequisites) != 1:
                break
            current_thread_tasks.append(next_task)
            current_task = next_task
        thread = _TaskThread(
            name=_snake_case_to_pascal_case(current_thread_tasks[-1].name),
            tasks=current_thread_tasks,
            prerequisites={
                task_name_to_thread[p.name]
                # Every task after the first one depends on exactly one other
                # task, and that task must be the one before it in the list. So
                # only the first task will depend on tasks from other threads.
                for p in current_thread_tasks[0].prerequisites
            },
            messenger=messenger,
        )
        for t in current_thread_tasks:
            task_name_to_thread[t.name] = thread
            tasks = [x for x in tasks if x.name != t.name]
        threads.append(thread)
    return threads


def _snake_case_to_pascal_case(snake: str) -> str:
    """
    Convert a string from scake_case to PascalCase.
    """
    words = [x for x in snake.split("_") if x]
    capitalized_words = [w[0].upper() + w[1:] for w in words]
    return "".join(capitalized_words)
