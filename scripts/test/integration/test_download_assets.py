# pyright: reportPrivateUsage=false

import shutil
import unittest
from pathlib import Path
from unittest.mock import create_autospec

from args import ReccArgs
from autochecklist import Messenger, ProblemLevel
from config import Config
from lib import AssetManager, Attachment, Download, DownloadSkipped

_TEST_DIR = Path(__file__).resolve().parent.parent
_KIDS_VID = Attachment(
    id="168545664",
    filename="Kids_OnlineExperience_W2.mp4",
    num_bytes=509892510,
    pco_filetype="video",
    mime_type="application/mp4",
)
_KIDS_VID_COPY = Attachment(
    id="168545664_copy",
    filename="Kids_OnlineExperience_W2.mp4",
    num_bytes=509892510,
    pco_filetype="video",
    mime_type="application/mp4",
)
_KIDS_VID_20240421 = Attachment(
    id="168545806",
    filename="Kids_OnlineExperience_W3.mp4",
    num_bytes=453376672,
    pco_filetype="video",
    mime_type="application/mp4",
)
_BUMPER_VID = Attachment(
    id="169500433",
    filename="Worthy Sermon Bumper.mp4",
    num_bytes=66443050,
    pco_filetype="video",
    mime_type="application/mp4",
)
_OPENER_VID = Attachment(
    id="169500434",
    filename="Welcome Opener Video.mp4",
    num_bytes=72145534,
    pco_filetype="video",
    mime_type="application/mp4",
)
_OPENER_VID_COPY = Attachment(
    id="169500434_copy",
    filename="Welcome Opener Video.mp4",
    num_bytes=72145534,
    pco_filetype="video",
    mime_type="application/mp4",
)
_SERIES_TITLE_IMG = Attachment(
    id="169501904",
    filename="WORTHY Title Slide.PNG",
    num_bytes=1999823,
    pco_filetype="image",
    mime_type="image/png",
)
_SERIES_TITLE_IMG_COPY = Attachment(
    id="169501904_copy",
    filename="WORTHY Title Slide.PNG",
    num_bytes=1999823,
    pco_filetype="image",
    mime_type="image/png",
)
_ANNOUNCEMENT_VID = Attachment(
    id="169505461",
    filename="Announcement Video.mov",
    num_bytes=48274579,
    pco_filetype="video",
    mime_type="video/quicktime",
)
_ANNOUNCEMENT_VID_COPY = Attachment(
    id="169505461_copy",
    filename="Announcement Video.mov",
    num_bytes=48274579,
    pco_filetype="video",
    mime_type="video/quicktime",
)
_SERMON_NOTES_DOCX = Attachment(
    id="169508339",
    filename="Notes - Worthy - Week 2 - Worthy Of The Feast.docx",
    num_bytes=18780,
    pco_filetype="file",
    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
_SERMON_NOTES_DOCX_COPY = Attachment(
    id="169508339_copy",
    filename="Notes - Worthy - Week 2 - Worthy Of The Feast.docx",
    num_bytes=18780,
    pco_filetype="file",
    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
_HOST_SCRIPT_DOCX = Attachment(
    id="169508360",
    filename="MC HOST SCRIPT – NEW FORMAT.docx",
    num_bytes=16813,
    pco_filetype="file",
    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


class PlanDownloadAssetsTestCase(unittest.TestCase):
    _FOH_CONFIG = Config(
        ReccArgs.parse(["", "--date", "2024-04-14"]),
        profile="foh_dev",
        strict=True,
        allow_multiple_only_for_testing=True,
    )
    _MCR_CONFIG = Config(
        ReccArgs.parse(["", "--date", "2024-04-14"]),
        profile="mcr_dev",
        strict=True,
        allow_multiple_only_for_testing=True,
    )

    def setUp(self) -> None:
        # Try to avoid wiping any important data
        self.assertTrue(
            self._FOH_CONFIG.assets_by_service_dir.is_relative_to(_TEST_DIR),
            f"The FOH assets by service directory ({self._FOH_CONFIG.assets_by_service_dir.resolve().as_posix()})"
            f" must be inside the test directory ({_TEST_DIR.resolve().as_posix()}).",
        )
        self.assertTrue(
            self._FOH_CONFIG.assets_by_type_dir.is_relative_to(_TEST_DIR),
            f"The FOH assets by type directory ({self._FOH_CONFIG.assets_by_type_dir.resolve().as_posix()})"
            f" must be inside the test directory ({_TEST_DIR.resolve().as_posix()}).",
        )
        self.assertTrue(
            self._MCR_CONFIG.assets_by_service_dir.is_relative_to(_TEST_DIR),
            f"The MCR assets by service directory ({self._MCR_CONFIG.assets_by_service_dir.resolve().as_posix()})"
            f" must be inside the test directory ({_TEST_DIR.resolve().as_posix()}).",
        )
        self.assertTrue(
            self._MCR_CONFIG.assets_by_type_dir.is_relative_to(_TEST_DIR),
            f"The MCR assets by type directory ({self._MCR_CONFIG.assets_by_type_dir.resolve().as_posix()})"
            f" must be inside the test directory ({_TEST_DIR.resolve().as_posix()}).",
        )

        if self._FOH_CONFIG.assets_by_service_dir.is_dir():
            shutil.rmtree(self._FOH_CONFIG.assets_by_service_dir)
        if self._FOH_CONFIG.assets_by_type_dir.is_dir():
            shutil.rmtree(self._FOH_CONFIG.assets_by_type_dir)
        if self._MCR_CONFIG.assets_by_service_dir.is_dir():
            shutil.rmtree(self._MCR_CONFIG.assets_by_service_dir)
        if self._MCR_CONFIG.assets_by_type_dir.is_dir():
            shutil.rmtree(self._MCR_CONFIG.assets_by_type_dir)

        self.maxDiff = None

    def test_plan_all_mcr(self) -> None:
        attachments = {
            _KIDS_VID,
            _BUMPER_VID,
            _OPENER_VID,
            _SERIES_TITLE_IMG,
            _ANNOUNCEMENT_VID,
            _SERMON_NOTES_DOCX,
            _HOST_SCRIPT_DOCX,
        }
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=True,
            download_notes_docx=True,
            require_announcements=True,
        )
        expected_plan = {
            _KIDS_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Kids_OnlineExperience_W2.mp4"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _BUMPER_VID: Download(
                destination=config.videos_dir.joinpath("Worthy Sermon Bumper.mp4"),
                is_required=False,
                deduplicate=True,
            ),
            _OPENER_VID: Download(
                destination=config.videos_dir.joinpath("Welcome Opener Video.mp4"),
                is_required=False,
                deduplicate=True,
            ),
            _SERIES_TITLE_IMG: Download(
                destination=config.images_dir.joinpath("WORTHY Title Slide.PNG"),
                is_required=False,
                deduplicate=True,
            ),
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERMON_NOTES_DOCX: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                ),
                is_required=False,
                deduplicate=False,
            ),
            _HOST_SCRIPT_DOCX: DownloadSkipped(reason="unknown attachment"),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_all_foh(self) -> None:
        attachments = {
            _KIDS_VID,
            _BUMPER_VID,
            _OPENER_VID,
            _SERIES_TITLE_IMG,
            _ANNOUNCEMENT_VID,
            _SERMON_NOTES_DOCX,
            _HOST_SCRIPT_DOCX,
        }
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _KIDS_VID: DownloadSkipped(reason="kids video"),
            _BUMPER_VID: Download(
                destination=config.videos_dir.joinpath("Worthy Sermon Bumper.mp4"),
                is_required=False,
                deduplicate=True,
            ),
            _OPENER_VID: Download(
                destination=config.videos_dir.joinpath("Welcome Opener Video.mp4"),
                is_required=False,
                deduplicate=True,
            ),
            _SERIES_TITLE_IMG: Download(
                destination=config.images_dir.joinpath("WORTHY Title Slide.PNG"),
                is_required=False,
                deduplicate=True,
            ),
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERMON_NOTES_DOCX: DownloadSkipped(
                reason="sermon notes",
            ),
            _HOST_SCRIPT_DOCX: DownloadSkipped(reason="unknown attachment"),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if some expected attachments are missing?

    def test_plan_missing_kids_video_mcr(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERMON_NOTES_DOCX}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        with self.assertRaises(ValueError) as cm:
            manager._plan_downloads(
                attachments,
                messenger=messenger,
                download_kids_video=True,
                download_notes_docx=True,
                require_announcements=True,
            )
        self.assertEqual("No Kids Connection video found.", str(cm.exception))

    def test_plan_missing_kids_video_foh(self) -> None:
        attachments = {
            _ANNOUNCEMENT_VID,
        }
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_missing_announcements_nonrequired(self) -> None:
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments=set(),
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=False,
        )
        self.assertEqual({}, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="Found 0 attachments that look like the announcements video.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_missing_announcements_required(self) -> None:
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        with self.assertRaises(ValueError) as cm:
            manager._plan_downloads(
                attachments=set(),
                messenger=messenger,
                download_kids_video=False,
                download_notes_docx=False,
                require_announcements=True,
            )
        self.assertEqual("No announcements video found.", str(cm.exception))

    def test_plan_missing_sermon_notes_mcr(self) -> None:
        attachments = {_ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=True,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="Found 0 attachments that look like sermon notes.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_missing_sermon_notes_foh(self) -> None:
        attachments = {_ANNOUNCEMENT_VID}
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if there are multiple attachments with the same name?

    def test_plan_multiple_kids_videos(self) -> None:
        attachments = {_KIDS_VID, _ANNOUNCEMENT_VID, _KIDS_VID_COPY}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=True,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _KIDS_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Kids_OnlineExperience_W2.mp4"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _KIDS_VID_COPY: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Kids_OnlineExperience_W2 (1).mp4",
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="Found 2 attachments that look like the Kids Connection video.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_announcements_videos(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _ANNOUNCEMENT_VID_COPY}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _ANNOUNCEMENT_VID_COPY: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14 (1).mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="Found 2 attachments that look like the announcements video.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_sermon_notes(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERMON_NOTES_DOCX, _SERMON_NOTES_DOCX_COPY}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=True,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERMON_NOTES_DOCX: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                ),
                is_required=False,
                deduplicate=False,
            ),
            _SERMON_NOTES_DOCX_COPY: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast (1).docx"
                ),
                is_required=False,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="Found 2 attachments that look like sermon notes.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_images(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERIES_TITLE_IMG, _SERIES_TITLE_IMG_COPY}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERIES_TITLE_IMG: Download(
                destination=config.images_dir.joinpath("WORTHY Title Slide.PNG"),
                is_required=False,
                deduplicate=True,
            ),
            _SERIES_TITLE_IMG_COPY: Download(
                destination=config.images_dir.joinpath("WORTHY Title Slide (1).PNG"),
                is_required=False,
                deduplicate=True,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_multiple_videos(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _OPENER_VID, _OPENER_VID_COPY}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _OPENER_VID: Download(
                destination=config.videos_dir.joinpath("Welcome Opener Video.mp4"),
                is_required=False,
                deduplicate=True,
            ),
            _OPENER_VID_COPY: Download(
                destination=config.videos_dir.joinpath("Welcome Opener Video (1).mp4"),
                is_required=False,
                deduplicate=True,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if the attachment has the same name as an existing file on
    # the computer?

    def test_plan_kids_video_name_taken(self) -> None:
        attachments = {_KIDS_VID, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        existing_vid = config.assets_by_service_dir.joinpath(
            "Kids_OnlineExperience_W2.mp4"
        )
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=True,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _KIDS_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Kids_OnlineExperience_W2.mp4"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_announcements_video_name_taken(self) -> None:
        attachments = {_ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        existing_vid = config.assets_by_service_dir.joinpath(
            "Announcement Video 2024-04-14.mov"
        )
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_sermon_notes_name_taken(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERMON_NOTES_DOCX}
        config = self._MCR_CONFIG
        existing_docx = config.images_dir.joinpath(
            "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
        )
        existing_docx.parent.mkdir(exist_ok=True, parents=True)
        existing_docx.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=True,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERMON_NOTES_DOCX: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                ),
                is_required=False,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_image_name_taken(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERIES_TITLE_IMG}
        config = self._MCR_CONFIG
        existing_img1 = config.images_dir.joinpath("WORTHY Title Slide.PNG")
        existing_img1.parent.mkdir(exist_ok=True, parents=True)
        existing_img1.write_text("")
        existing_img2 = config.images_dir.joinpath("WORTHY Title Slide (1).PNG")
        existing_img2.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _SERIES_TITLE_IMG: Download(
                destination=config.images_dir.joinpath("WORTHY Title Slide (2).PNG"),
                is_required=False,
                deduplicate=True,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_video_name_taken(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _OPENER_VID}
        config = self._MCR_CONFIG
        existing_vid = config.videos_dir.joinpath("Welcome Opener Video.mp4")
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=False,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _OPENER_VID: DownloadSkipped(
                reason=f"{existing_vid.resolve().as_posix()} already exists"
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if the kids video has the wrong week number?

    def test_plan_kids_video_wrong_week(self) -> None:
        attachments = {_KIDS_VID_20240421, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager._plan_downloads(
            attachments,
            messenger=messenger,
            download_kids_video=True,
            download_notes_docx=False,
            require_announcements=True,
        )
        expected_plan = {
            _KIDS_VID_20240421: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Kids_OnlineExperience_W3.mp4"
                ),
                is_required=True,
                deduplicate=False,
            ),
            _ANNOUNCEMENT_VID: Download(
                destination=config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                ),
                is_required=True,
                deduplicate=False,
            ),
        }
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="The current week number is 2, but the Kids Connection video seems to be from week 3.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)
