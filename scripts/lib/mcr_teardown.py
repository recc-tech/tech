import stat
import traceback
from datetime import date, datetime, timedelta
from typing import Dict

import args.parsing_helpers as parse
import autochecklist
import captions
from args import McrTeardownArgs
from autochecklist import Messenger, Parameter, ProblemLevel, TaskStatus
from config import Config, McrTeardownConfig
from external_services import (
    BoxCastApiClient,
    NoCaptionsError,
    PlanningCenterClient,
    ReccVimeoClient,
)


def get_service_info(
    args: McrTeardownArgs,
    config: Config,
    messenger: Messenger,
    planning_center_client: PlanningCenterClient,
) -> None:
    message_series = ""
    message_title = ""
    if not (args.message_series and args.message_title):
        try:
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
            parser=parse.parse_non_empty_string,
            description='This is the name of the series to which today\'s sermon belongs. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the series was "Getting There".',
            default=message_series,
        )
    if not args.message_title:
        params["message_title"] = Parameter(
            "Message Title",
            parser=parse.parse_non_empty_string,
            description='This is the title of today\'s sermon. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the title was "Avoiding Road Rage".',
            default=message_title,
        )
    if len(params) == 0:
        return

    inputs = messenger.input_multiple(
        params, prompt="The script needs some information to get started."
    )
    if "message_series" in inputs:
        args.message_series = str(inputs["message_series"])
    if "message_title" in inputs:
        args.message_title = str(inputs["message_title"])

    # Need to reload so that the Vimeo video title, BoxCast URLs, etc. get
    # updated with today's service info
    config.reload()


def wait_for_BoxCast_recording(
    client: BoxCastApiClient, messenger: Messenger, config: Config
) -> None:
    cancel_token = messenger.allow_cancel()
    retry_delay = timedelta(seconds=60)
    while True:
        broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
        if broadcast is not None:
            messenger.log_debug(f"Today's broadcast ID is {broadcast.id}.")
            return
        else:
            messenger.log_status(
                TaskStatus.RUNNING,
                f"The BoxCast recording does not seem to be ready as of {datetime.now().strftime('%H:%M:%S')}."
                f" Retrying in {retry_delay.total_seconds():.2f} seconds.",
            )
            autochecklist.sleep_attentively(
                timeout=retry_delay, cancellation_token=cancel_token
            )


def create_rebroadcast_1pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=13, minute=0, second=0),
        )


def create_rebroadcast_5pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=17, minute=0, second=0),
        )


def create_rebroadcast_7pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=19, minute=0, second=0),
        )


def export_to_Vimeo(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.export_to_vimeo(
            broadcast_id=broadcast.id,
            vimeo_user_id=config.vimeo_user_id,
            title=config.vimeo_video_title,
        )


def generate_captions(
    client: BoxCastApiClient, config: McrTeardownConfig, messenger: Messenger
) -> None:
    messenger.log_status(TaskStatus.RUNNING, "Finding today's broadcast on BoxCast.")
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    cancellation_token = messenger.allow_cancel()

    messenger.log_status(TaskStatus.RUNNING, "Looking for captions on BoxCast")
    start = datetime.now()
    while (datetime.now() - start) < config.max_captions_wait_time:
        try:
            cues = client.get_captions(broadcast_id=broadcast.id)
            if len(cues) > 0:
                messenger.log_status(TaskStatus.DONE, "Found some captions on BoxCast.")
                return
        except NoCaptionsError:
            pass
        t = config.generate_captions_retry_delay
        messenger.log_status(
            TaskStatus.RUNNING,
            f"No captions found yet. Retrying in {t.total_seconds()} seconds.",
        )
        autochecklist.sleep_attentively(
            timeout=t, cancellation_token=cancellation_token
        )
    raise ValueError(
        "The captions still do not appear to be ready. Check the progress on BoxCast."
    )


def automatically_edit_captions(
    client: BoxCastApiClient, config: McrTeardownConfig, messenger: Messenger
) -> None:
    messenger.log_status(TaskStatus.RUNNING, "Finding today's broadcast on BoxCast.")
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")

    messenger.log_status(TaskStatus.RUNNING, "Downloading the captions.")
    client.download_captions(
        broadcast_id=broadcast.id, path=config.original_captions_file
    )

    messenger.log_status(TaskStatus.RUNNING, "Editing the captions.")
    # Prevent user from mistakenly editing the wrong file
    config.original_captions_file.chmod(stat.S_IREAD)
    original_cues = list(captions.load(config.original_captions_file))
    filtered_cues = captions.remove_worship_captions(original_cues)
    # TODO: Also perform capitalization check (using the old caption_substitutions.csv in lib, which should maybe be moved to config)
    captions.save(filtered_cues, config.auto_edited_captions_file)
    # Prevent user from mistakenly editing the wrong file
    config.auto_edited_captions_file.chmod(stat.S_IREAD)

    messenger.log_status(TaskStatus.RUNNING, "Re-uploading the edited captions.")
    client.upload_captions(
        broadcast_id=broadcast.id, path=config.auto_edited_captions_file
    )


def disable_automatic_captions(vimeo_client: ReccVimeoClient, messenger: Messenger):
    cancellation_token = messenger.allow_cancel()
    (_, texttrack_uri) = vimeo_client.get_video_data(cancellation_token)
    vimeo_client.disable_automatic_captions(
        texttracks_uri=texttrack_uri, cancellation_token=cancellation_token
    )


def upload_captions_to_Vimeo(
    messenger: Messenger,
    boxcast_client: BoxCastApiClient,
    vimeo_client: ReccVimeoClient,
    config: McrTeardownConfig,
) -> None:
    messenger.log_status(TaskStatus.RUNNING, "Finding today's broadcast on BoxCast.")
    broadcast = boxcast_client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")

    messenger.log_status(TaskStatus.RUNNING, "Downloading the captions.")
    boxcast_client.download_captions(
        broadcast_id=broadcast.id, path=config.final_captions_file
    )

    # Sanity check: there should be no more low-confidence cues left.
    # If there are, maybe we downloaded the old captions; i.e., not the
    # manually-reviewed ones.
    # This may be due to the bug in github.com/recc-tech/tech/issues/337.
    # Or maybe the user just left one or two low-confidence cues, in which case
    # there's no problem.
    messenger.log_status(
        TaskStatus.RUNNING, "Checking for remaining low-confidence cues."
    )
    cues = captions.load(config.final_captions_file)
    num_low_confidence = len([c for c in cues if c.confidence != 1.0])
    if num_low_confidence == 0:
        messenger.log_status(TaskStatus.RUNNING, "No low-confidence cues found.")
    else:
        msg = (
            f"There still seem to be {num_low_confidence} low-confidence cues in the published captions."
            " Are these the right captions?"
        )
        messenger.log_problem(ProblemLevel.WARN, msg)
        is_ok = messenger.input_bool(prompt=msg, title="Confirm captions")
        if not is_ok:
            raise ValueError(
                "The script seems to have downloaded the wrong captions."
                + " Retry this task once the manually-reviewed captions are published."
                + " If this still does not work, then perform this task manually instead."
            )

    messenger.log_status(TaskStatus.RUNNING, "Uploading the captions to Vimeo.")
    (_, texttrack_uri) = vimeo_client.get_video_data(messenger.allow_cancel())
    vimeo_client.upload_captions_to_vimeo(config.final_captions_file, texttrack_uri)
