import inspect

from autochecklist import Messenger, ProblemLevel, TaskStatus
from config import McrSetupConfig
from external_services import PlanningCenterClient, VmixClient
from lib import AssetManager, SlideBlueprintReader, SlideGenerator


def download_assets(
    client: PlanningCenterClient, messenger: Messenger, manager: AssetManager
):
    results = manager.download_pco_assets(
        client=client,
        messenger=messenger,
        download_kids_video=True,
        download_notes_docx=True,
        require_announcements=False,
        dry_run=False,
    )
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


def import_announcements_video(
    client: VmixClient, config: McrSetupConfig, manager: AssetManager
) -> None:
    announcements_video_path = manager.locate_announcements_video()
    if announcements_video_path is None:
        raise ValueError("The path to the announcements video is not known.")
    client.list_remove_all(config.vmix_announcements_list_key)
    client.list_add(config.vmix_announcements_list_key, announcements_video_path)


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

    if len(people.speaker_names) == 0:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"No speaker is confirmed for today. Defaulting to {config.default_speaker_name}.",
        )
        speaker_name = config.default_speaker_name
    elif len(people.speaker_names) == 1:
        speaker_name = people.speaker_names[0]
    else:
        raise ValueError("More than one speaker is confirmed for today.")

    if len(people.mc_host_names) == 0:
        raise ValueError("No MC host is scheduled for today.")
    if len(people.mc_host_names) > 2:
        raise ValueError("More than two MC hosts are scheduled for today.")
    mc_hosts = sorted(people.mc_host_names)
    mc_host1_name = mc_hosts[0]
    mc_host2_name = mc_hosts[1] if len(mc_hosts) > 1 else None

    pre_stream_title = inspect.cleandoc(
        f"""{plan.series_title}

            {plan.title}

            {speaker_name}

            {today.strftime('%B')} {today.day}, {today.year}"""
    )

    vmix_client.set_text(config.vmix_pre_stream_title_key, pre_stream_title)
    vmix_client.set_text(config.vmix_speaker_title_key, speaker_name)
    vmix_client.set_text(config.vmix_host_title_key, mc_host1_name)
    if mc_host2_name:
        vmix_client.set_text(config.vmix_extra_presenter_title_key, mc_host2_name)


def download_message_notes(client: PlanningCenterClient, config: McrSetupConfig):
    today = config.start_time.date()
    plan = client.find_plan_by_date(today)
    message_notes = client.find_message_notes(plan.id)
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
    token = messenger.allow_cancel()
    blueprints = reader.load_message_notes(
        config.message_notes_file, cancellation_token=token
    )

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
