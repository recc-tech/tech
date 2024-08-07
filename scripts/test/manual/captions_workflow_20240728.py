import sys
import typing
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import autochecklist
import lib.mcr_teardown as mcr_teardown
from args import ReccArgs
from autochecklist import TaskModel
from config import Config
from external_services import BoxCastApiClient
from lib import ReccDependencyProvider

_MCR_TEARDOWN_TASKS = (
    Path(__file__)
    .resolve()
    .parent.parent.parent.joinpath("config", "mcr_teardown_tasks.json")
)
_BROADCAST_ID = "ppdgxvvmkpni3fjfjlxx"
_ORIGINAL_CAPTIONS = Path(__file__).parent.joinpath(
    "data", "20240728-original-captions.vtt"
)
_FINAL_CAPTIONS = Path(__file__).parent.joinpath("data", "20240728-final-captions.vtt")


def _get_captions_task() -> TaskModel:
    """
    Extract the captions-related tasks from the real MCR teardown script's task
    list.
    """
    model = TaskModel.load(_MCR_TEARDOWN_TASKS)
    task = _find_task_called("captions", model)
    if task is None:
        raise ValueError(
            "The captions task in the MCR teardown script could not be found."
        )
    subsubtasks = [st for t in task.subtasks for st in t.subtasks]
    if len(subsubtasks) > 0:
        raise ValueError(
            "The captions task in the MCR teardown script has sub-sub-tasks, which was not expected."
        )
    # Rebuild the task model, but with filtered prerequisites
    subtask_names = {t.name for t in task.subtasks}
    task = TaskModel(
        name=task.name,
        description=task.description,
        prerequisites=set[str](),
        subtasks=[
            TaskModel(
                name=t.name,
                description=t.description,
                prerequisites={p for p in t.prerequisites if p in subtask_names},
                subtasks=t.subtasks,
                only_auto=t.only_auto,
            )
            for t in task.subtasks
        ],
        only_auto=task.only_auto,
    )
    return task


def _find_task_called(name: str, model: TaskModel) -> Optional[TaskModel]:
    if model.name == name:
        return model
    for subtask in model.subtasks:
        t = _find_task_called(name, subtask)
        if t is not None:
            return t
    return None


def main():
    # Use the real captions flow for the most realistic test possible
    captions_task = _get_captions_task()
    final_task = TaskModel(
        name="check_captions",
        description=(
            "Check that the captions are correct on BoxCast and Vimeo."
            " The captions should be on the latest Vimeo video."
            " Then delete the new captions from Vimeo and re-enable the old ones."
        ),
        prerequisites={captions_task.subtasks[-1].name},
    )
    captions_task = TaskModel(
        name=captions_task.name,
        description=captions_task.description,
        prerequisites=set[str](),
        subtasks=captions_task.subtasks + [final_task],
        only_auto=captions_task.only_auto,
    )

    args = ReccArgs.parse(sys.argv)
    args.start_time = datetime.combine(
        date(year=2024, month=7, day=28),
        datetime.now().time(),
    )
    config = Config(args=args)
    # We probably won't be running this test only on Sunday afternoons, so the
    # latest Vimeo video might be a while ago
    config.vimeo_new_video_hours = 24 * 7
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.log_dir.joinpath("test_captions_workflow.log"),
        script_name="Test Captions Workflow",
        description="Manually test the captions workflow.",
        show_statuses_by_default=True,
    )

    boxcast_client = typing.cast(
        BoxCastApiClient, dependency_provider.get(BoxCastApiClient)
    )
    print("Resetting the captions to how they originally were...")
    boxcast_client.upload_captions(
        broadcast_id=_BROADCAST_ID, path=_ORIGINAL_CAPTIONS, cancellation_token=None
    )
    # The captions get marked as read-only after being downloaded, so if we run
    # this test twice in a row the script will fail to save the captions the
    # second time
    print("Deleting old captions...")
    config.original_captions_file.unlink(missing_ok=True)
    config.auto_edited_captions_file.unlink(missing_ok=True)
    config.final_captions_file.unlink(missing_ok=True)
    try:
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dependency_provider,
            tasks=captions_task,
            module=mcr_teardown,
        )
    finally:
        print("Reuploading the edited captions...")
        boxcast_client.upload_captions(
            broadcast_id=_BROADCAST_ID,
            path=_FINAL_CAPTIONS,
            cancellation_token=None,
            wait=False,
        )


if __name__ == "__main__":
    main()
