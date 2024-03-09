from __future__ import annotations

import re
import sys
import traceback
from argparse import ArgumentTypeError
from datetime import date
from pathlib import Path
from typing import Dict, Tuple

import lib.mcr_teardown as mcr_teardown
from args import parse_non_empty_string
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
from config import Config, McrTeardownArgs, McrTeardownConfig
from external_services import (
    BoxCastClientFactory,
    CredentialStore,
    PlanningCenterClient,
    ReccVimeoClient,
)


class McrTeardownScript(Script[McrTeardownArgs, McrTeardownConfig]):
    def parse_args(self) -> McrTeardownArgs:
        return McrTeardownArgs.parse(sys.argv)

    def create_config(self, args: McrTeardownArgs) -> McrTeardownConfig:
        return McrTeardownConfig(args)

    def create_messenger(self, args: McrTeardownArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.mcr_teardown_log)
        input_messenger = (
            ConsoleMessenger(
                f"{McrTeardownArgs.DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
                show_task_status=args.verbose,
            )
            if args.ui == "console"
            else TkMessenger(
                title="MCR Teardown",
                description=McrTeardownArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=False,
            )
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, args: McrTeardownArgs, config: Config, messenger: Messenger
    ) -> Tuple[TaskModel | Path, FunctionFinder]:
        credential_store = CredentialStore(messenger=messenger)
        self._get_todays_service_info(args, config, messenger, credential_store)
        # Need to reload so that the Vimeo video title, BoxCast URLs, etc. get
        # updated with today's service info
        config.reload()
        vimeo_client = ReccVimeoClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            cancellation_token=None,
            lazy_login=args.lazy_login,
        )
        boxcast_client_factory = BoxCastClientFactory(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            headless=not args.show_browser,
            lazy_login=args.lazy_login,
            log_directory=config.log_dir,
            log_file_name=config.mcr_teardown_webdriver_log_name,
        )
        function_finder = FunctionFinder(
            module=mcr_teardown,
            arguments=[boxcast_client_factory, config, messenger, vimeo_client],
            messenger=messenger,
        )
        task_list_file = (
            Path(__file__).parent.joinpath("config").joinpath("mcr_teardown_tasks.json")
        )
        return task_list_file, function_finder

    def _get_todays_service_info(
        self,
        args: McrTeardownArgs,
        config: Config,
        messenger: Messenger,
        credential_store: CredentialStore,
    ) -> None:
        message_series = ""
        message_title = ""
        if not (args.message_series and args.message_title):
            try:
                planning_center_client = PlanningCenterClient(
                    messenger=messenger,
                    credential_store=credential_store,
                    config=config,
                    lazy_login=args.lazy_login,
                )
                today = args.start_time.date() or date.today()
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
        if not args.message_series:
            params["message_series"] = Parameter(
                "Message Series",
                parser=parse_non_empty_string,
                description='This is the name of the series to which today\'s sermon belongs. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the series was "Getting There".',
                default=message_series,
            )
        if not args.message_title:
            params["message_title"] = Parameter(
                "Message Title",
                parser=parse_non_empty_string,
                description='This is the title of today\'s sermon. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the title was "Avoiding Road Rage".',
                default=message_title,
            )
        if not args.boxcast_event_id:
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
            args.message_series = str(inputs["message_series"])
        if "message_title" in inputs:
            args.message_title = str(inputs["message_title"])
        if "boxcast_event_id" in inputs:
            args.boxcast_event_id = str(inputs["boxcast_event_id"])


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
