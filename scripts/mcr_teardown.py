from __future__ import annotations

import re
import traceback
import typing
from argparse import ArgumentParser, ArgumentTypeError
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

import mcr_teardown.tasks
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Parameter,
    ProblemLevel,
    Script,
    TaskModel,
    TkMessenger,
)
from external_services import (
    BoxCastClientFactory,
    CredentialStore,
    PlanningCenterClient,
    ReccVimeoClient,
)
from lib import parse_directory, parse_non_empty_string
from mcr_teardown import McrTeardownConfig

_DESCRIPTION = "This script will guide you through the steps to shutting down the MCR video station after a Sunday gathering."


class McrTeardownScript(Script[McrTeardownConfig]):
    def create_config(self) -> McrTeardownConfig:
        parser = ArgumentParser(
            description="Script to guide and automate the teardown process in the MCR."
        )

        parser.add_argument(
            "-s",
            "--message-series",
            type=parse_non_empty_string,
            help="Name of the series to which today's sermon belongs.",
        )
        parser.add_argument(
            "-t",
            "--message-title",
            type=parse_non_empty_string,
            help="Title of today's sermon.",
        )

        boxcast_event_id_group = parser.add_mutually_exclusive_group()
        boxcast_event_id_group.add_argument(
            "-b",
            "--boxcast-event-url",
            type=_parse_boxcast_event_url,
            help="URL of today's live event on BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
        )
        boxcast_event_id_group.add_argument(
            "--boxcast-event-id",
            type=parse_non_empty_string,
            help='ID of today\'s live event on BoxCast. For example, in the URL https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
        )

        advanced_args = parser.add_argument_group("Advanced arguments")
        advanced_args.add_argument(
            "--home-dir",
            type=parse_directory,
            default="D:\\Users\\Tech\\Documents",
            help="The home directory.",
        )
        advanced_args.add_argument(
            "--downloads-dir",
            type=parse_directory,
            default="D:\\Users\\Tech\\Downloads",
            help="The downloads directory, where the browser automatically places files after downloading them.",
        )
        advanced_args.add_argument(
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )
        advanced_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the flag --text-ui is also provided. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )
        advanced_args.add_argument(
            "--lazy-login",
            action="store_true",
            help="If this flag is provided, then the script will not immediately log in to services like Vimeo and BoxCast. Instead, it will wait until that particular service is specifically requested.",
        )

        debug_args = parser.add_argument_group("Debug arguments")
        debug_args.add_argument(
            "--no-run",
            action="store_true",
            help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
        )
        debug_args.add_argument(
            "--auto",
            action="append",
            default=None,
            help="Specify which tasks to automate. You can also provide 'none' to automate none of the tasks. By default, all tasks that can be automated are automated.",
        )
        debug_args.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        debug_args.add_argument(
            "--date",
            type=lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
            help="Pretend the script is running on a different date.",
        )

        args = parser.parse_args()
        if args.boxcast_event_url:
            args.boxcast_event_id = args.boxcast_event_url
        # For some reason Pylance complains about the del keyword but not delattr
        delattr(args, "boxcast_event_url")
        if args.auto is not None:
            if "none" in args.auto and len(args.auto) > 1:
                parser.error(
                    "If 'none' is included in --auto, it must be the only value."
                )
            if args.auto == ["none"]:
                args.auto = typing.cast(List[str], [])

        return McrTeardownConfig(
            message_series=args.message_series or "",
            message_title=args.message_title or "",
            boxcast_event_id=args.boxcast_event_id or "",
            home_dir=args.home_dir,
            downloads_dir=args.downloads_dir,
            lazy_login=args.lazy_login,
            show_browser=args.show_browser,
            ui=args.ui,
            now=(
                datetime.combine(args.date, datetime.now().time())
                if args.date
                else datetime.now()
            ),
            verbose=args.verbose,
            no_run=args.no_run,
            auto_tasks=set(args.auto) if args.auto is not None else None,
        )

    def create_messenger(self, config: McrTeardownConfig) -> Messenger:
        file_messenger = FileMessenger(config.log_file)
        input_messenger = (
            ConsoleMessenger(
                f"{_DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
                show_task_status=config.verbose,
            )
            if config.ui == "console"
            else TkMessenger(
                title="MCR Teardown",
                description=_DESCRIPTION,
            )
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, config: McrTeardownConfig, messenger: Messenger
    ) -> Tuple[TaskModel | Path, FunctionFinder]:
        credential_store = CredentialStore(messenger=messenger)
        self._get_todays_service_info(config, messenger, credential_store)
        vimeo_client = ReccVimeoClient(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            lazy_login=config.lazy_login,
        )
        boxcast_client_factory = BoxCastClientFactory(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            headless=not config.show_browser,
            lazy_login=config.lazy_login,
            log_directory=config.log_dir,
            log_file_name="mcr_teardown_web_driver",
        )
        function_finder = FunctionFinder(
            module=mcr_teardown.tasks,
            arguments=[boxcast_client_factory, config, messenger, vimeo_client],
            messenger=messenger,
        )
        task_list_file = (
            Path(__file__).parent.joinpath("mcr_teardown").joinpath("tasks.json")
        )
        return task_list_file, function_finder

    def _get_todays_service_info(
        self,
        config: McrTeardownConfig,
        messenger: Messenger,
        credential_store: CredentialStore,
    ) -> None:
        message_series = ""
        message_title = ""
        if not (config.message_series and config.message_title):
            try:
                planning_center_client = PlanningCenterClient(
                    messenger=messenger,
                    credential_store=credential_store,
                    lazy_login=config.lazy_login,
                )
                today = config.now.date() or date.today()
                todays_plan = planning_center_client.find_plan_by_date(today)
                message_series = todays_plan.series_title
                message_title = todays_plan.title
            except:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    "Failed to fetch today's plan from Planning Center.",
                    stacktrace=traceback.format_exc(),
                )

        params: Dict[str, Parameter] = {}
        if not config.message_series:
            params["message_series"] = Parameter(
                "Message Series",
                parser=parse_non_empty_string,
                description='This is the name of the series to which today\'s sermon belongs. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the series was "Getting There".',
                default=message_series,
            )
        if not config.message_title:
            params["message_title"] = Parameter(
                "Message Title",
                parser=parse_non_empty_string,
                description='This is the title of today\'s sermon. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the title was "Avoiding Road Rage".',
                default=message_title,
            )
        if not config.boxcast_event_id:
            params["boxcast_event_id"] = Parameter(
                "BoxCast Event URL",
                parser=_parse_boxcast_event_url,
                description="This is the URL of today's live event on BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
            )
        if len(params) == 0:
            return

        inputs = messenger.input_multiple(
            params, prompt="The script needs some more information to get started."
        )
        if "message_series" in inputs:
            config.message_series = str(inputs["message_series"])
        if "message_title" in inputs:
            config.message_title = str(inputs["message_title"])
        if "boxcast_event_id" in inputs:
            config.boxcast_event_id = str(inputs["boxcast_event_id"])


def _parse_boxcast_event_url(event_url: str) -> str:
    if not event_url:
        raise ArgumentTypeError("Empty input. The event URL is required.")
    if all(c == "\x16" for c in event_url):
        raise ArgumentTypeError(
            "You entered the value CTRL+V, which is not a valid event URL. Try right-clicking to paste."
        )

    # The event URL should be in the form "https://dashboard.boxcast.com/broadcasts/<EVENT-ID>"
    # Allow a trailing forward slash just in case
    event_url = event_url.strip()
    regex = "^https://dashboard\\.boxcast\\.com/broadcasts/([a-zA-Z0-9]{20,20})/?(?:\\?.*)?$"
    pattern = re.compile(regex)
    regex_match = pattern.search(event_url)
    if not regex_match:
        raise ArgumentTypeError(
            f"Expected the BoxCast event URL to match the regular expression '{regex}', but received '{event_url}'. Are you sure you copied the URL correctly? If you think there is a problem with the script, try entering the BoxCast event ID directly instead."
        )
    event_id = regex_match.group(1)
    return event_id


if __name__ == "__main__":
    McrTeardownScript().run()
