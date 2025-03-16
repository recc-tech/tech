import inspect

from autochecklist import Messenger, ProblemLevel, TaskStatus
from config import McrSetupConfig
from external_services import PlanningCenterClient, TeamMemberStatus, VmixClient
from lib import AssetManager, SlideBlueprintReader, SlideGenerator


def save_new_vMix_preset(client: VmixClient, config: McrSetupConfig) -> None:
    client.save_preset(config.vmix_preset_file)


def save_vMix_preset(client: VmixClient, config: McrSetupConfig) -> None:
    client.save_preset(config.vmix_preset_file)


def save_final_vMix_preset(client: VmixClient, config: McrSetupConfig) -> None:
    client.save_preset(config.vmix_preset_file)


def download_assets(
    client: PlanningCenterClient, messenger: Messenger, manager: AssetManager
):
    results = manager.download_pco_assets(client=client, messenger=messenger)
    msg = "\n".join([f"* {a.filename}: {res}" for (a, res) in results.items()])
    messenger.log_status(TaskStatus.DONE, msg)


def import_Kids_Connection_video(
    client: VmixClient, config: McrSetupConfig, manager: AssetManager
) -> None:
    kids_video_path = manager.locate_kids_video()
    if kids_video_path is None:
        raise ValueError("The path to the Kids Connection video is not known.")
    client.list_remove_all(config.vmix_kids_connection_list_key)
    client.list_add(config.vmix_kids_connection_list_key, kids_video_path)


def import_livestream_announcements_video(
    client: VmixClient, config: McrSetupConfig, manager: AssetManager
) -> None:
    p = manager.locate_announcements_video()
    if p is None:
        raise ValueError("The path to the livestream announcements video is not known.")
    client.list_remove_all(config.vmix_announcements_list_key)
    client.list_add(config.vmix_announcements_list_key, p)


def restart_videos(client: VmixClient) -> None:
    client.restart_all()


def update_titles(
    vmix_client: VmixClient,
    pco_client: PlanningCenterClient,
    config: McrSetupConfig,
    messenger: Messenger,
) -> None:
    today = config.start_time.date()
    plan = pco_client.find_plan_by_date(today)
    people = pco_client.find_presenters(plan.id)
    error_count = 0

    confirmed_speakers = [
        p for p in people.speakers if p.status == TeamMemberStatus.CONFIRMED
    ]
    unconfirmed_speakers = [
        p for p in people.speakers if p.status == TeamMemberStatus.UNCONFIRMED
    ]
    for p in unconfirmed_speakers:
        messenger.log_problem(
            ProblemLevel.WARN,
            f'The speaker "{p.name}" is scheduled on Planning Center but did not confirm.',
        )
    if len(people.speakers) == 0:
        messenger.log_problem(
            ProblemLevel.WARN,
            f'No speaker is scheduled on Planning Center. Defaulting to "{config.default_speaker_name}".',
        )
        speaker_name = config.default_speaker_name
    elif len(people.speakers) == 1:
        speaker_name = list(people.speakers)[0].name
    elif len(confirmed_speakers) == 1:
        speaker_name = list(confirmed_speakers)[0].name
        speaker_list = ", ".join(
            [
                f"{p.name} ({p.status})"
                for p in sorted(people.speakers, key=lambda p: p.name)
            ]
        )
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Multiple speakers are listed on Planning Center: {speaker_list}."
            " Only the confirmed speaker has been given a title.",
        )
    else:
        error_count += 1
        messenger.log_problem(
            ProblemLevel.ERROR, "More than one speaker is confirmed for today."
        )
        # Just choose the speaker alphabetically from the confirmed list.
        # Any title is better than nothing.
        speaker_name = sorted(confirmed_speakers, key=lambda p: p.name)[0].name

    for h in people.hosts:
        if h.status == TeamMemberStatus.UNCONFIRMED:
            messenger.log_problem(
                ProblemLevel.WARN,
                f'The host "{h.name}" is scheduled on Planning Center but did not confirm.',
            )
    available_speakers = sorted(
        people.hosts,
        # Take confirmed hosts first, break ties by name
        key=lambda p: (p.status != TeamMemberStatus.CONFIRMED, p.name),
    )
    if len(available_speakers) == 0:
        error_count += 1
        messenger.log_problem(ProblemLevel.ERROR, "No hosts are scheduled for today.")
    elif len(available_speakers) > 2:
        error_count += 1
        messenger.log_problem(
            ProblemLevel.ERROR, "More than two hosts are scheduled for today."
        )

    # If two titles were chosen, sort them alphabetically regardless of status
    titles = [p.name for p in sorted(available_speakers[:2], key=lambda p: p.name)]
    mc_host1_name = titles[0] if len(titles) > 0 else ""
    mc_host2_name = titles[1] if len(titles) > 1 else ""

    pre_stream_title = inspect.cleandoc(
        f"""{plan.series_title}

            {plan.title}

            {speaker_name}

            {today.strftime('%B')} {today.day}, {today.year}"""
    )

    vmix_client.set_text(config.vmix_pre_stream_title_key, pre_stream_title)
    vmix_client.set_text(config.vmix_speaker_title_key, speaker_name)
    vmix_client.set_text(config.vmix_host1_title_key, mc_host1_name)
    vmix_client.set_text(config.vmix_host2_title_key, mc_host2_name)

    if error_count > 0:
        was_or_were = "was" if error_count == 1 else "were"
        error_or_errors = "error" if error_count == 1 else "errors"
        raise ValueError(
            f"There {was_or_were} {error_count} {error_or_errors}."
            ' See the "Problems" section for details.'
        )


def download_message_notes(client: PlanningCenterClient, config: McrSetupConfig):
    today = config.start_time.date()
    plan = client.find_plan_by_date(today)
    message_notes = client.find_message_notes(plan.id)
    if not message_notes:
        raise ValueError("No message notes have been posted to the plan yet.")
    config.message_notes_file.parent.mkdir(exist_ok=True, parents=True)
    with open(config.message_notes_file, "w", encoding="utf-8") as f:
        f.write(message_notes)


def generate_backup_slides(
    reader: SlideBlueprintReader,
    generator: SlideGenerator,
    config: McrSetupConfig,
    messenger: Messenger,
):
    messenger.log_status(
        TaskStatus.RUNNING,
        f"Reading input from {config.message_notes_file.as_posix()}.",
    )
    blueprints = reader.load_message_notes(config.message_notes_file)

    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide blueprints to {config.slide_blueprints_file}.",
    )
    reader.save_json(config.slide_blueprints_file, blueprints)

    messenger.log_status(TaskStatus.RUNNING, f"Generating images.")
    blueprints_with_prefix = [
        b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
        for i, b in enumerate(blueprints, start=1)
    ]
    slides = generator.generate_lower_third_slides(blueprints_with_prefix)

    messenger.log_status(TaskStatus.RUNNING, f"Saving images.")
    for s in slides:
        s.save(config.assets_by_service_dir)

    messenger.log_status(
        TaskStatus.DONE,
        f"Generated {len(slides)} slides in {config.assets_by_service_dir.as_posix()}.",
    )
