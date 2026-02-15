import sys
from typing import List, Literal

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from external_services import Credential, CredentialStore, InputPolicy, bird_dog
from lib import ReccDependencyProvider, SimplifiedMessengerSettings
from requests import Session


class ApplyCamSettingsArgs(ReccArgs):
    NAME = "apply_cam_settings"
    DESCRIPTION = (
        "This script will apply the stored settings to each BirdDog PTZ camera,"
        " allowing quicker setup after power interruptions."
    )


def _make_task(
    camera: Literal[1, 2, 3],
    config: Config,
    messenger: Messenger,
    credential_store: CredentialStore,
):
    def apply_cam_settings() -> None:
        base_url = config.cam_base_url[camera]
        settings_path = config.cam_settings_path[camera]
        settings = settings_path.read_text()
        with Session() as s:
            messenger.log_status(TaskStatus.RUNNING, "Logging in...")
            password = credential_store.get(
                Credential.BIRD_DOG_PASSWORD,
                request_input=InputPolicy.AS_REQUIRED,
            )
            bird_dog.log_in(camera, s, config, password)
            if not s.cookies.get("BirdDogSession"):
                raise RuntimeError(
                    "Failed to log in (cookie 'BirdDogSession' is not set)"
                )
            messenger.log_status(
                TaskStatus.RUNNING,
                f"Sending settings (from {settings_path})...",
            )
            s.post(
                f"{base_url}/videoset",
                data=settings,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={config.cam_settings_form_boundary}",
                },
            )

    return apply_cam_settings


def main(
    args: ReccArgs,
    config: Config,
    dep: ReccDependencyProvider,
) -> None:
    all_cameras: List[Literal[1, 2, 3]] = [1, 2, 3]
    tasks = TaskModel(
        name="apply_cam_settings",
        subtasks=[
            TaskModel(
                name=f"setup_cam_{camera}",
                description=f"Failed to apply settings for camera {camera}",
                only_auto=True,
                func=_make_task(
                    camera=camera,
                    config=config,
                    messenger=dep.messenger,
                    credential_store=dep.get(CredentialStore),
                ),
            )
            for camera in all_cameras
        ],
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )


if __name__ == "__main__":
    args = ApplyCamSettingsArgs.parse(sys.argv)
    config = Config(args)
    msg = SimplifiedMessengerSettings(
        log_file=config.apply_cam_settings_log,
        script_name="Apply Camera Settings",
        description=ApplyCamSettingsArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=args, config=config, messenger=msg
    )
    main(args, config, dependency_provider)
