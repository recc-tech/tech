import lib
from autochecklist import Messenger, TaskStatus
from lib import PlanningCenterClient, SlideBlueprintReader, SlideGenerator
from mcr_setup.config import McrSetupConfig


def download_message_notes(client: PlanningCenterClient, config: McrSetupConfig):
    today = config.now.date()
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
    blueprints = reader.load_message_notes(config.message_notes_file)

    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide blueprints to {config.backup_slides_json_file}.",
    )
    reader.save_json(config.backup_slides_json_file, blueprints)

    messenger.log_status(TaskStatus.RUNNING, f"Generating images.")
    blueprints_with_prefix = [
        b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
        for i, b in enumerate(blueprints, start=1)
    ]
    slides = generator.generate_lower_third_slide(
        blueprints_with_prefix, show_backdrop=True
    )

    messenger.log_status(TaskStatus.RUNNING, f"Saving images.")
    for s in slides:
        s.save(config.assets_by_service_dir)

    messenger.log_status(
        TaskStatus.DONE,
        f"Generated {len(slides)} slides in {config.assets_by_service_dir.as_posix()}.",
    )


def download_assets(
    client: PlanningCenterClient, config: McrSetupConfig, messenger: Messenger
):
    lib.download_pco_assets(
        client=client,
        messenger=messenger,
        today=config.now.date(),
        assets_by_service_dir=config.assets_by_service_dir,
        temp_assets_dir=config.temp_assets_dir,
        assets_by_type_videos_dir=config.assets_by_type_videos_dir,
        assets_by_type_images_dir=config.assets_by_type_images_dir,
        download_kids_video=True,
        download_notes_docx=True,
    )
