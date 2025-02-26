# pyright: reportPrivateUsage=false

import unittest
from typing import Optional

from args import ReccArgs
from config import Config
from lib import Attachment
from lib.assets import AssetManager, Attachment


class DownloadPcoAssetsTestCase(unittest.TestCase):
    def test_classify_announcements_0(self) -> None:
        # TODO: Add more recent tests for this
        attachment = Attachment(
            id="168445080",
            filename="Announcement Video.mov",
            num_bytes=65454784,
            pco_filetype="video",
            mime_type="video/quicktime",
        )
        self.assertEqual(
            "livestream announcements video",
            self._classify(attachment),
        )

    def test_classify_announcements_1(self) -> None:
        attachment = Attachment(
            id="168975407",
            filename="Announcements.mov",
            num_bytes=9087846,
            pco_filetype="video",
            mime_type="video/quicktime",
        )
        self.assertEqual(
            "livestream announcements video",
            self._classify(attachment),
        )

    def test_classify_kids_video_0(self) -> None:
        kids_video = Attachment(
            id="163865496",
            filename="Kids_OnlineExperience_W1.mp4",
            num_bytes=547786017,
            pco_filetype="video",
            mime_type="application/mp4",
        )
        self.assertEqual("kids video", self._classify(kids_video))

    def test_classify_kids_video_1(self) -> None:
        kids_video = Attachment(
            id="163865496",
            filename="2402_Kids_OnlineExperience_W1.mp4",
            num_bytes=547786017,
            pco_filetype="video",
            mime_type="application/mp4",
        )
        self.assertEqual("kids video", self._classify(kids_video))

    def test_classify_sermon_notes(self) -> None:
        notes = Attachment(
            id="163869600",
            filename="Notes – Clean Slate – Victory Through Dreams.docx",
            num_bytes=16251,
            pco_filetype="file",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual("sermon notes", self._classify(notes))

    def test_classify_jpg(self) -> None:
        image = Attachment(
            id="163862630",
            filename="Save The Date.jpeg",
            num_bytes=15111396,
            pco_filetype="image",
            mime_type="image/jpeg",
        )
        self.assertEqual("images", self._classify(image))

    def test_classify_png(self) -> None:
        image = Attachment(
            id="163863943",
            filename="Clean_Slate_Title.png",
            num_bytes=215905,
            pco_filetype="image",
            mime_type="image/png",
        )
        self.assertEqual("images", self._classify(image))

    def test_classify_mov_0(self) -> None:
        video = Attachment(
            id="162216121",
            filename="clean_slate_bumper.mov",
            num_bytes=43767222,
            pco_filetype="video",
            mime_type="video/quicktime",
        )
        self.assertEqual("videos", self._classify(video))

    def test_classify_mov_1(self) -> None:
        video = Attachment(
            id="161125310",
            filename="clean_slate_intro.mov",
            num_bytes=73018536,
            pco_filetype="video",
            mime_type="video/quicktime",
        )
        self.assertEqual("videos", self._classify(video))

    def test_classify_mp4(self) -> None:
        video = Attachment(
            id="168543182",
            filename="Worthy Sermon Bumper.mp4",
            num_bytes=66443050,
            pco_filetype="video",
            mime_type="application/mp4",
        )
        self.assertEqual("videos", self._classify(video))

    def test_classify_unknown(self) -> None:
        attachment = Attachment(
            id="163863127",
            filename="MC Host Script.docx",
            num_bytes=29471,
            pco_filetype="file",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(None, self._classify(attachment))

    def _classify(self, a: Attachment) -> Optional[str]:
        config = Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)
        manager = AssetManager(config=config)
        c = manager._classify(a)
        if c is None:
            return None
        else:
            return c.name
