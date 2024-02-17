# pyright: reportPrivateUsage=false

import unittest
from unittest.mock import Mock

from lib.download_pco_assets import Attachment, _classify_attachments


class DownloadPcoAssetsTestCase(unittest.TestCase):
    def test_classify_attachments(self):
        kids_video = {
            Attachment(
                id="163865496",
                filename="Kids_OnlineExperience_W1.mp4",
                num_bytes=547786017,
                pco_filetype="video",
                mime_type="application/mp4",
            )
        }
        notes = {
            Attachment(
                id="163869600",
                filename="Notes – Clean Slate – Victory Through Dreams.docx",
                num_bytes=16251,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        images = {
            Attachment(
                id="163862630",
                filename="Save The Date.jpeg",
                num_bytes=15111396,
                pco_filetype="image",
                mime_type="image/jpeg",
            ),
            Attachment(
                id="163863943",
                filename="Clean_Slate_Title.png",
                num_bytes=215905,
                pco_filetype="image",
                mime_type="image/png",
            ),
        }
        videos = {
            Attachment(
                id="162216121",
                filename="clean_slate_bumper.mov",
                num_bytes=43767222,
                pco_filetype="video",
                mime_type="video/quicktime",
            ),
            Attachment(
                id="161125310",
                filename="clean_slate_intro.mov",
                num_bytes=73018536,
                pco_filetype="video",
                mime_type="video/quicktime",
            ),
        }
        unknown_assets = {
            Attachment(
                id="163863127",
                filename="MC Host Script.docx",
                num_bytes=29471,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        all_attachments = kids_video.union(notes, images, videos, unknown_assets)
        original_all_attachments = set(all_attachments)

        messenger = Mock()

        k, n, i, v, u = _classify_attachments(all_attachments, messenger)

        # Classifier should not mutate input
        self.assertEqual(original_all_attachments, all_attachments)
        self.assertEqual(kids_video, k)
        self.assertEqual(notes, n)
        self.assertEqual(images, i)
        self.assertEqual(videos, v)
        self.assertEqual(unknown_assets, u)

    def test_classify_kids_video_different_name(self):
        kids_video = Attachment(
            id="163865496",
            filename="2402_Kids_OnlineExperience_W1.mp4",
            num_bytes=547786017,
            pco_filetype="video",
            mime_type="application/mp4",
        )
        messenger = Mock()
        k, *_ = _classify_attachments({kids_video}, messenger)
        self.assertEqual({kids_video}, k)
