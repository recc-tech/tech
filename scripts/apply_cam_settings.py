import sys
from typing import List, Literal

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from external_services import Credential, CredentialStore, InputPolicy
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
        password = credential_store.get(
            Credential.BIRD_DOG_PASSWORD,
            request_input=InputPolicy.AS_REQUIRED,
        )
        base_url = config.cam_base_url[camera]
        settings_path = config.cam_settings_path[camera]
        settings = settings_path.read_text()
        with Session() as s:
            messenger.log_status(TaskStatus.RUNNING, "Logging in...")
            url = f"{base_url}/login"
            messenger.log_debug(f"Sending login request to {url}")
            s.post(
                url,
                data=f"auth_password={password}",
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cookie": "mod_sel=none; av_settings=none; exp_settings=block; wb_settings=none; pic1_settings=none; pic2_settings=none; cm_settings=none; ci_settings=none; cex_settings=none",
                    "Host": base_url[len("http://") :],
                    "Origin": base_url,
                    "Priority": "u=0, i",
                    "Referer": f"{base_url}/login",
                    "Upgrade-Insecure-Requests": "1",
                },
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
