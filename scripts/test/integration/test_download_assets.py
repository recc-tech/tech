# pyright: reportPrivateUsage=false

import shutil
import unittest
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import create_autospec

import download_pco_assets as dpa
from args import ReccArgs
from autochecklist import CancellationToken, Messenger, ProblemLevel
from config import Config
from external_services import PlanningCenterClient
from lib import (
    AssetManager,
    Attachment,
    Download,
    DownloadDeduplicated,
    DownloadPlan,
    DownloadSkipped,
    DownloadSucceeded,
)

_TEST_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = Path(__file__).parent.joinpath("download_assets_data")
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
_KIDS_VID_FAKE = _DATA_DIR.joinpath("Kids_OnlineExperience_W2.mp4")
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
_BUMPER_VID_FAKE = _DATA_DIR.joinpath("Worthy Sermon Bumper.mp4")
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
_OPENER_VID_COPY_NEW_NAME = Attachment(
    id="169500434_copy_2",
    filename="Welcome Opener Video (New Name).mp4",
    num_bytes=72145534,
    pco_filetype="video",
    mime_type="application/mp4",
)
_OPENER_VID_FAKE = _DATA_DIR.joinpath("Welcome Opener Video.mp4")
_BAPTISM_VID = Attachment(
    id="baptism",
    filename="BaptismHD.mp4",
    num_bytes=42,
    pco_filetype="video",
    mime_type="application/mp4",
)
_BAPTISM_VID_FAKE = _DATA_DIR.joinpath("BaptismHD.mp4")
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
_SERIES_TITLE_IMG_COPY_NEW_NAME = Attachment(
    id="169501904_copy_2",
    filename="Title Slide.png",
    num_bytes=1999823,
    pco_filetype="image",
    mime_type="image/png",
)
_SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT = Attachment(
    id="169501904_copy_3",
    filename="WORTHY Title Slide.PNG",
    num_bytes=1999823,
    pco_filetype="image",
    mime_type="image/png",
)
_SERIES_TITLE_IMG_FAKE = _DATA_DIR.joinpath("WORTHY Title Slide.PNG")
_SERIES_TITLE_NEW_CONTENT_FAKE = _DATA_DIR.joinpath(
    "WORTHY Title Slide Different Content.PNG"
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
_ANNOUNCEMENT_VID_FAKE = _DATA_DIR.joinpath("Announcement Video.mov")
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
_SERMON_NOTES_DOCX_FAKE = _DATA_DIR.joinpath(
    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
)
_HOST_SCRIPT_DOCX = Attachment(
    id="169508360",
    filename="MC HOST SCRIPT – NEW FORMAT.docx",
    num_bytes=16813,
    pco_filetype="file",
    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


class DownloadAssetsTestCase(unittest.TestCase):
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
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
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
        )
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
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID: DownloadSkipped(
                    reason='assets in category "kids video" are not downloaded at this station'
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
                _ANNOUNCEMENT_VID: DownloadSkipped(
                    reason='assets in category "livestream announcements video" are not downloaded at this station'
                ),
                _SERMON_NOTES_DOCX: DownloadSkipped(
                    reason='assets in category "sermon notes" are not downloaded at this station',
                ),
                _HOST_SCRIPT_DOCX: DownloadSkipped(reason="unknown attachment"),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if some expected attachments are missing?

    def test_plan_missing_kids_video_mcr(self) -> None:
        attachments = {_ANNOUNCEMENT_VID, _SERMON_NOTES_DOCX}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        with self.assertRaises(ValueError) as cm:
            manager.plan_downloads(attachments, messenger=messenger)
        self.assertEqual(
            'No attachments found for category "kids video".', str(cm.exception)
        )

    def test_plan_missing_kids_video_foh(self) -> None:
        attachments = {_SERIES_TITLE_IMG}
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _SERIES_TITLE_IMG: Download(
                    destination=config.images_dir.joinpath("WORTHY Title Slide.PNG"),
                    is_required=False,
                    deduplicate=True,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_missing_announcements_mcr(self) -> None:
        attachments = {_KIDS_VID}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        with self.assertRaises(ValueError) as cm:
            manager.plan_downloads(attachments=attachments, messenger=messenger)
        self.assertEqual(
            'No attachments found for category "livestream announcements video".',
            str(cm.exception),
        )

    def test_plan_missing_announcements_foh(self) -> None:
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments=set(), messenger=messenger)
        self.assertEqual(DownloadPlan({}), plan)
        messenger.log_problem.assert_not_called()

    def test_plan_missing_sermon_notes_mcr(self) -> None:
        attachments = {_KIDS_VID, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
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
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message='No attachments found for category "sermon notes".',
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_missing_sermon_notes_foh(self) -> None:
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments=set(), messenger=messenger)
        self.assertEqual(DownloadPlan({}), plan)
        messenger.log_problem.assert_not_called()

    # What happens if there are multiple attachments with the same name?

    def test_plan_multiple_kids_videos(self) -> None:
        attachments = {_KIDS_VID, _ANNOUNCEMENT_VID, _KIDS_VID_COPY, _SERMON_NOTES_DOCX}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Kids_OnlineExperience_W2.mp4"
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
                _SERMON_NOTES_DOCX: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                    ),
                    is_required=False,
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
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message='Found 2 attachments for category "kids video".',
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_announcements_videos(self) -> None:
        attachments = {
            _KIDS_VID,
            _SERMON_NOTES_DOCX,
            _ANNOUNCEMENT_VID,
            _ANNOUNCEMENT_VID_COPY,
        }
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Kids_OnlineExperience_W2.mp4"
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
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message='Found 2 attachments for category "livestream announcements video".',
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_sermon_notes(self) -> None:
        attachments = {
            _KIDS_VID,
            _ANNOUNCEMENT_VID,
            _SERMON_NOTES_DOCX,
            _SERMON_NOTES_DOCX_COPY,
        }
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
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
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message='Found 2 attachments for category "sermon notes".',
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    def test_plan_multiple_images(self) -> None:
        attachments = {_SERIES_TITLE_IMG, _SERIES_TITLE_IMG_COPY}
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _SERIES_TITLE_IMG: Download(
                    destination=config.images_dir.joinpath("WORTHY Title Slide.PNG"),
                    is_required=False,
                    deduplicate=True,
                ),
                _SERIES_TITLE_IMG_COPY: Download(
                    destination=config.images_dir.joinpath(
                        "WORTHY Title Slide (1).PNG"
                    ),
                    is_required=False,
                    deduplicate=True,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_multiple_videos(self) -> None:
        attachments = {_OPENER_VID, _OPENER_VID_COPY}
        config = self._FOH_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _OPENER_VID: Download(
                    destination=config.videos_dir.joinpath("Welcome Opener Video.mp4"),
                    is_required=False,
                    deduplicate=True,
                ),
                _OPENER_VID_COPY: Download(
                    destination=config.videos_dir.joinpath(
                        "Welcome Opener Video (1).mp4"
                    ),
                    is_required=False,
                    deduplicate=True,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if the attachment has the same name as an existing file on
    # the computer?

    def test_plan_kids_video_name_taken(self) -> None:
        attachments = {_KIDS_VID, _SERMON_NOTES_DOCX, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        existing_vid = config.assets_by_service_dir.joinpath(
            "Kids_OnlineExperience_W2.mp4"
        )
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Kids_OnlineExperience_W2.mp4"
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
                _ANNOUNCEMENT_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Announcement Video 2024-04-14.mov"
                    ),
                    is_required=True,
                    deduplicate=False,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_announcements_video_name_taken(self) -> None:
        attachments = {_KIDS_VID, _SERMON_NOTES_DOCX, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        existing_vid = config.assets_by_service_dir.joinpath(
            "Announcement Video 2024-04-14.mov"
        )
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Kids_OnlineExperience_W2.mp4"
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
                _ANNOUNCEMENT_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Announcement Video 2024-04-14.mov"
                    ),
                    is_required=True,
                    deduplicate=False,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_sermon_notes_name_taken(self) -> None:
        attachments = {_KIDS_VID, _ANNOUNCEMENT_VID, _SERMON_NOTES_DOCX}
        config = self._MCR_CONFIG
        existing_docx = config.images_dir.joinpath(
            "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
        )
        existing_docx.parent.mkdir(exist_ok=True, parents=True)
        existing_docx.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
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
                _SERMON_NOTES_DOCX: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                    ),
                    is_required=False,
                    deduplicate=False,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_image_name_taken(self) -> None:
        attachments = {_SERIES_TITLE_IMG}
        config = self._FOH_CONFIG
        existing_img1 = config.images_dir.joinpath("WORTHY Title Slide.PNG")
        existing_img1.parent.mkdir(exist_ok=True, parents=True)
        existing_img1.write_text("")
        existing_img2 = config.images_dir.joinpath("WORTHY Title Slide (1).PNG")
        existing_img2.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _SERIES_TITLE_IMG: Download(
                    destination=config.images_dir.joinpath(
                        "WORTHY Title Slide (2).PNG"
                    ),
                    is_required=False,
                    deduplicate=True,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    def test_plan_video_name_taken(self) -> None:
        attachments = {_OPENER_VID}
        config = self._FOH_CONFIG
        existing_vid = config.videos_dir.joinpath("Welcome Opener Video.mp4")
        existing_vid.parent.mkdir(exist_ok=True, parents=True)
        existing_vid.write_text("")
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _OPENER_VID: DownloadSkipped(
                    reason=f"{existing_vid.resolve().as_posix()} already exists"
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_not_called()

    # What happens if the kids video has the wrong week number?

    def test_plan_kids_video_wrong_week(self) -> None:
        attachments = {_KIDS_VID_20240421, _SERMON_NOTES_DOCX, _ANNOUNCEMENT_VID}
        config = self._MCR_CONFIG
        manager = AssetManager(config=config)
        messenger = create_autospec(Messenger)
        plan = manager.plan_downloads(attachments, messenger=messenger)
        expected_plan = DownloadPlan(
            {
                _KIDS_VID_20240421: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Kids_OnlineExperience_W3.mp4"
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
                _ANNOUNCEMENT_VID: Download(
                    destination=config.assets_by_service_dir.joinpath(
                        "Announcement Video 2024-04-14.mov"
                    ),
                    is_required=True,
                    deduplicate=False,
                ),
            }
        )
        self.assertEqual(expected_plan, plan)
        messenger.log_problem.assert_called_with(
            level=ProblemLevel.WARN,
            message="The current week number is 2, but the Kids Connection video seems to be from week 3.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)

    # Full download test

    def test_full_download_mcr(self) -> None:
        config = self._MCR_CONFIG
        manager = AssetManager(config)
        pco_client = create_autospec(PlanningCenterClient)
        pco_client.download_attachments = _fake_download
        pco_client.find_attachments.return_value = {
            _KIDS_VID,
            _BUMPER_VID,
            _OPENER_VID,
            _SERIES_TITLE_IMG,
            _ANNOUNCEMENT_VID,
            _SERMON_NOTES_DOCX,
            _HOST_SCRIPT_DOCX,
        }
        messenger = create_autospec(Messenger)
        results = manager.download_pco_assets(client=pco_client, messenger=messenger)
        expected_results = {
            _KIDS_VID: DownloadSucceeded(
                config.assets_by_service_dir.joinpath("Kids_OnlineExperience_W2.mp4")
            ),
            _BUMPER_VID: DownloadSucceeded(
                config.videos_dir.joinpath("Worthy Sermon Bumper.mp4")
            ),
            _OPENER_VID: DownloadSucceeded(
                config.videos_dir.joinpath("Welcome Opener Video.mp4")
            ),
            _SERIES_TITLE_IMG: DownloadSucceeded(
                config.images_dir.joinpath("WORTHY Title Slide.PNG")
            ),
            _ANNOUNCEMENT_VID: DownloadSucceeded(
                config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                )
            ),
            _SERMON_NOTES_DOCX: DownloadSucceeded(
                config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                )
            ),
            _HOST_SCRIPT_DOCX: DownloadSkipped(reason="unknown attachment"),
        }
        self.assertEqual(expected_results, results)
        expected_files = {
            d.destination
            for d in expected_results.values()
            if isinstance(d, DownloadSucceeded)
        }
        actual_files = {
            p.resolve()
            for d in {
                config.images_dir,
                config.videos_dir,
                config.assets_by_service_dir,
            }
            for p in d.iterdir()
        }
        self.assertEqual(expected_files, actual_files)
        messenger.log_problem.assert_not_called()

        # Check that deduplication works properly
        pco_client.find_attachments.return_value = {
            _KIDS_VID,
            _SERMON_NOTES_DOCX,
            _SERIES_TITLE_IMG_COPY_NEW_NAME,
            _SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT,
            _ANNOUNCEMENT_VID,
            _OPENER_VID_COPY_NEW_NAME,
            _BAPTISM_VID,
        }
        results = manager.download_pco_assets(client=pco_client, messenger=messenger)
        expected_results = {
            _KIDS_VID: DownloadSucceeded(
                config.assets_by_service_dir.joinpath("Kids_OnlineExperience_W2.mp4")
            ),
            _SERMON_NOTES_DOCX: DownloadSucceeded(
                config.assets_by_service_dir.joinpath(
                    "Notes - Worthy - Week 2 - Worthy Of The Feast.docx"
                )
            ),
            _SERIES_TITLE_IMG_COPY_NEW_NAME: DownloadDeduplicated(
                original=config.images_dir.joinpath("WORTHY Title Slide.PNG")
            ),
            _SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT: DownloadSucceeded(
                config.images_dir.joinpath("WORTHY Title Slide (1).PNG")
            ),
            _ANNOUNCEMENT_VID: DownloadSucceeded(
                config.assets_by_service_dir.joinpath(
                    "Announcement Video 2024-04-14.mov"
                )
            ),
            _OPENER_VID_COPY_NEW_NAME: DownloadDeduplicated(
                original=config.videos_dir.joinpath("Welcome Opener Video.mp4")
            ),
            _BAPTISM_VID: DownloadSucceeded(
                config.videos_dir.joinpath("BaptismHD.mp4")
            ),
        }
        self.assertEqual(expected_results, results)
        expected_files = expected_files | {
            config.images_dir.joinpath("WORTHY Title Slide (1).PNG"),
            config.videos_dir.joinpath("BaptismHD.mp4"),
        }
        actual_files = {
            p.resolve()
            for d in {
                config.images_dir,
                config.videos_dir,
                config.assets_by_service_dir,
            }
            for p in d.iterdir()
        }
        self.assertEqual(expected_files, actual_files)
        messenger.log_problem.assert_not_called()

    def test_full_download_foh(self) -> None:
        config = self._FOH_CONFIG
        manager = AssetManager(config)
        pco_client = create_autospec(PlanningCenterClient)
        pco_client.download_attachments = _fake_download
        pco_client.find_attachments.return_value = {
            _KIDS_VID,
            _BUMPER_VID,
            _OPENER_VID,
            _SERIES_TITLE_IMG,
            _ANNOUNCEMENT_VID,
            _SERMON_NOTES_DOCX,
            _HOST_SCRIPT_DOCX,
        }
        messenger = create_autospec(Messenger)
        results = manager.download_pco_assets(client=pco_client, messenger=messenger)
        expected_results = {
            _BUMPER_VID: DownloadSucceeded(
                config.videos_dir.joinpath("Worthy Sermon Bumper.mp4")
            ),
            _OPENER_VID: DownloadSucceeded(
                config.videos_dir.joinpath("Welcome Opener Video.mp4")
            ),
            _SERIES_TITLE_IMG: DownloadSucceeded(
                config.images_dir.joinpath("WORTHY Title Slide.PNG")
            ),
            _KIDS_VID: DownloadSkipped(
                reason='assets in category "kids video" are not downloaded at this station'
            ),
            _ANNOUNCEMENT_VID: DownloadSkipped(
                reason='assets in category "livestream announcements video" are not downloaded at this station'
            ),
            _SERMON_NOTES_DOCX: DownloadSkipped(
                reason='assets in category "sermon notes" are not downloaded at this station'
            ),
            _HOST_SCRIPT_DOCX: DownloadSkipped(reason="unknown attachment"),
        }
        self.assertEqual(expected_results, results)
        expected_files = {
            d.destination
            for d in expected_results.values()
            if isinstance(d, DownloadSucceeded)
        }
        actual_files = {
            p.resolve()
            for d in {
                config.images_dir,
                config.videos_dir,
                config.assets_by_service_dir,
            }
            for p in d.iterdir()
        }
        self.assertEqual(expected_files, actual_files)
        messenger.log_problem.assert_not_called()

        # Check that deduplication works properly
        pco_client.find_attachments.return_value = {
            _KIDS_VID,
            _SERMON_NOTES_DOCX,
            _SERIES_TITLE_IMG_COPY_NEW_NAME,
            _SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT,
            _ANNOUNCEMENT_VID,
            _OPENER_VID_COPY_NEW_NAME,
            _BAPTISM_VID,
        }
        results = manager.download_pco_assets(client=pco_client, messenger=messenger)
        expected_results = {
            _SERIES_TITLE_IMG_COPY_NEW_NAME: DownloadDeduplicated(
                original=config.images_dir.joinpath("WORTHY Title Slide.PNG")
            ),
            _SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT: DownloadSucceeded(
                config.images_dir.joinpath("WORTHY Title Slide (1).PNG")
            ),
            _KIDS_VID: DownloadSkipped(
                reason='assets in category "kids video" are not downloaded at this station'
            ),
            _ANNOUNCEMENT_VID: DownloadSkipped(
                reason='assets in category "livestream announcements video" are not downloaded at this station'
            ),
            _SERMON_NOTES_DOCX: DownloadSkipped(
                reason='assets in category "sermon notes" are not downloaded at this station'
            ),
            _OPENER_VID_COPY_NEW_NAME: DownloadDeduplicated(
                original=config.videos_dir.joinpath("Welcome Opener Video.mp4")
            ),
            _BAPTISM_VID: DownloadSucceeded(
                config.videos_dir.joinpath("BaptismHD.mp4")
            ),
        }
        self.assertEqual(expected_results, results)
        expected_files = expected_files | {
            config.images_dir.joinpath("WORTHY Title Slide (1).PNG"),
            config.videos_dir.joinpath("BaptismHD.mp4"),
        }
        actual_files = {
            p.resolve()
            for d in {
                config.images_dir,
                config.videos_dir,
                config.assets_by_service_dir,
            }
            for p in d.iterdir()
        }
        self.assertEqual(expected_files, actual_files)
        messenger.log_problem.assert_not_called()

    def test_full_download_via_script(self) -> None:
        """
        The dedicated download_pco_assets.py script should go ahead and
        download whatever's available, even if some assets are missing.
        That way, if something is missing in the MCR, the person can fall back
        to using that script to download what's available so far and proceed.
        """
        args = dpa.DownloadAssetsArgs.parse(["", "--no-run"])
        config = dpa.DownloadAssetsConfig(
            args,
            # Pretend we're at the MCR, which requires certain assets (e.g.,
            # kids video and livestream announcements)
            profile="mcr_dev",
            allow_multiple_only_for_testing=True,
        )
        messenger = create_autospec(Messenger)
        pco_client = create_autospec(PlanningCenterClient)
        pco_client.download_attachments = _fake_download
        pco_client.find_attachments.return_value = {
            # Notice how the kids video, announcements video, and sermon notes
            # are all missing
            _BUMPER_VID,
            _OPENER_VID,
            _SERIES_TITLE_IMG,
            _HOST_SCRIPT_DOCX,
        }
        manager = AssetManager(config)
        dpa.download_PCO_assets(
            args=args,
            config=config,
            client=pco_client,
            manager=manager,
            messenger=messenger,
        )
        expected_files = {
            config.videos_dir.joinpath("Worthy Sermon Bumper.mp4"),
            config.videos_dir.joinpath("Welcome Opener Video.mp4"),
            config.images_dir.joinpath("WORTHY Title Slide.PNG"),
        }
        actual_files = {
            p.resolve()
            for d in {config.images_dir, config.videos_dir}
            for p in d.iterdir()
        }
        self.assertEqual(expected_files, actual_files)
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message='No attachments found for category "kids video".',
        )
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message='No attachments found for category "livestream announcements video".',
        )
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message='No attachments found for category "sermon notes".',
        )
        self.assertEqual(3, messenger.log_problem.call_count)


class LocateAssetsTestCase(unittest.TestCase):
    def setUp(self):
        self._config = Config(
            ReccArgs.parse([]),
            profile="mcr_dev",
            allow_multiple_only_for_testing=True,
        )
        self.assertTrue(
            _TEST_DIR in self._config.assets_by_service_dir.parents,
            "Assets by service directory must be within the test directory to avoid unintended data loss.",
        )
        shutil.rmtree(self._config.assets_by_service_dir, ignore_errors=True)
        self._config.assets_by_service_dir.mkdir(parents=True, exist_ok=False)
        self._manager = AssetManager(self._config)

    def test_locate_kids_video_1(self) -> None:
        p = self._config.assets_by_service_dir.joinpath("Kids_OnlineExperience_W2.mp4")
        with open(p, "w"):
            pass
        self.assertTrue(p.exists(), "File should exist.")
        self.assertEqual(self._manager.locate_kids_video(), p)

    def test_locate_kids_video_2(self) -> None:
        p = self._config.assets_by_service_dir.joinpath("Live_It_Out_W1.mp4")
        with open(p, "w"):
            pass
        self.assertTrue(p.exists(), "File should exist.")
        self.assertEqual(self._manager.locate_kids_video(), p)


async def _fake_download(
    downloads: Dict[Path, Attachment],
    messenger: Messenger,
    cancellation_token: Optional[CancellationToken],
) -> Dict[Path, Optional[BaseException]]:
    for p, a in downloads.items():
        src = {
            _KIDS_VID: _KIDS_VID_FAKE,
            _BUMPER_VID: _BUMPER_VID_FAKE,
            _OPENER_VID: _OPENER_VID_FAKE,
            _OPENER_VID_COPY_NEW_NAME: _OPENER_VID_FAKE,
            _SERIES_TITLE_IMG: _SERIES_TITLE_IMG_FAKE,
            _SERIES_TITLE_IMG_COPY_NEW_NAME: _SERIES_TITLE_IMG_FAKE,
            _SERIES_TITLE_IMG_SAME_NAME_NEW_CONTENT: _SERIES_TITLE_NEW_CONTENT_FAKE,
            _BAPTISM_VID: _BAPTISM_VID_FAKE,
            _ANNOUNCEMENT_VID: _ANNOUNCEMENT_VID_FAKE,
            _SERMON_NOTES_DOCX: _SERMON_NOTES_DOCX_FAKE,
        }[a]
        shutil.copy(src, p)
    return {p: None for p in downloads.keys()}
