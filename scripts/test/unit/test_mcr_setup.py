import unittest
from datetime import date
from typing import Set
from unittest.mock import call, create_autospec

from autochecklist import Messenger, ProblemLevel
from config import McrSetupConfig
from external_services import (
    Plan,
    PlanningCenterClient,
    PresenterSet,
    TeamMember,
    TeamMemberStatus,
    VmixClient,
)
from lib import mcr_setup
from mcr_setup import McrSetupArgs


class McrSetupTestCase(unittest.TestCase):
    def test_update_titles_1c_speaker_1c_host(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Sheriff", status=TeamMemberStatus.DECLINED),
            },
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Sheriff", status=TeamMemberStatus.DECLINED),
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_not_called()
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + "\n\nMater"
            + "\n\nMarch 9, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_1c_speaker_2c_hosts(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Sheriff", status=TeamMemberStatus.DECLINED),
            },
            hosts={
                TeamMember(name="Sally Carrera", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Sheriff", status=TeamMemberStatus.DECLINED),
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_not_called()
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + "\n\nMater"
            + "\n\nMarch 9, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                # Alphabetical order
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value="Sally Carrera"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_0_speakers(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Sheriff", status=TeamMemberStatus.DECLINED),
            },
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED)
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message=f'No speaker is scheduled on Planning Center. Defaulting to "{cfg.default_speaker_name}".',
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\n{cfg.default_speaker_name}"
            + "\n\nMarch 16, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value=cfg.default_speaker_name),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_1u_speaker(self) -> None:
        dt = date(year=2025, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Mater", status=TeamMemberStatus.UNCONFIRMED)},
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED)
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message=f'The speaker "Mater" is scheduled on Planning Center but did not confirm.',
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nMater"
            + "\n\nMarch 16, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_2u_speaker(self) -> None:
        dt = date(year=2025, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.UNCONFIRMED),
                TeamMember(
                    name="Lightning McQueen", status=TeamMemberStatus.UNCONFIRMED
                ),
            },
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED)
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.ERROR,
                    message="More than one speaker is scheduled for today.",
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The speaker "Lightning McQueen" is scheduled on Planning Center but did not confirm.',
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The speaker "Mater" is scheduled on Planning Center but did not confirm.',
                ),
            ],
            any_order=True,
        )
        self.assertEqual(3, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nLightning McQueen"
            + "\n\nMarch 9, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_1c_1u_speaker(self) -> None:
        dt = date(year=2025, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED),
                TeamMember(
                    name="Lightning McQueen", status=TeamMemberStatus.UNCONFIRMED
                ),
            },
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED)
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.ERROR,
                    message="More than one speaker is scheduled for today.",
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The speaker "Lightning McQueen" is scheduled on Planning Center but did not confirm.',
                ),
            ],
            any_order=True,
        )
        self.assertEqual(2, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nMater"
            + "\n\nMarch 9, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_2c_speakers(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED),
            },
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED)
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.ERROR,
            message="More than one speaker is scheduled for today.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nLightning McQueen"
            + "\n\nMarch 16, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_2c_1u_speaker(self) -> None:
        dt = date(year=2025, month=3, day=2)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Alice", status=TeamMemberStatus.UNCONFIRMED),
                TeamMember(name="Bob", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Charlie", status=TeamMemberStatus.CONFIRMED),
            },
            hosts={TeamMember(name="Daniel", status=TeamMemberStatus.CONFIRMED)},
            series="Series",
            title="Title",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.ERROR,
                    message="More than one speaker is scheduled for today.",
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The speaker "Alice" is scheduled on Planning Center but did not confirm.',
                ),
            ],
            any_order=True,
        )
        self.assertEqual(2, messenger.log_problem.call_count)
        pre_stream_title = "Series\n\nTitle\n\nBob\n\nMarch 2, 2025"
        vmix_client.set_text.assert_has_calls(
            [
                # Take the first *confirmed* speaker alphabetically
                call(input=cfg.vmix_speaker_title_key, value="Bob"),
                call(input=cfg.vmix_host1_title_key, value="Daniel"),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_0_hosts(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED)},
            hosts=set(),
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.ERROR, message="No hosts are scheduled for today."
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nMater"
            + "\n\nMarch 16, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                # Take the first speaker alphabetically
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value=""),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_1c_1u_host(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED)},
            hosts={
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Mater", status=TeamMemberStatus.UNCONFIRMED),
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_any_call(
            level=ProblemLevel.WARN,
            message='The host "Mater" is scheduled on Planning Center but did not confirm.',
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + "\n\nMater"
            + "\n\nMarch 9, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value="Mater"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_2u_hosts(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED)},
            hosts={
                TeamMember(
                    name="Lightning McQueen", status=TeamMemberStatus.UNCONFIRMED
                ),
                TeamMember(name="Mater", status=TeamMemberStatus.UNCONFIRMED),
            },
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        mcr_setup.update_titles(
            vmix_client=vmix_client,
            pco_client=pco_client,
            config=cfg,
            messenger=messenger,
        )

        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.WARN,
                    message='The host "Mater" is scheduled on Planning Center but did not confirm.',
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The host "Lightning McQueen" is scheduled on Planning Center but did not confirm.',
                ),
            ],
            any_order=True,
        )
        self.assertEqual(2, messenger.log_problem.call_count)
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + "\n\nMater"
            + "\n\nMarch 9, 2024"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Mater"),
                call(input=cfg.vmix_host1_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host2_title_key, value="Mater"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_1c_2u_hosts(self) -> None:
        dt = date(year=2025, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Stephen", status=TeamMemberStatus.CONFIRMED)},
            hosts={
                TeamMember(name="Alice", status=TeamMemberStatus.UNCONFIRMED),
                TeamMember(name="Bob", status=TeamMemberStatus.UNCONFIRMED),
                TeamMember(name="Charlie", status=TeamMemberStatus.CONFIRMED),
            },
            series="My Series Title",
            title="My Sermon Title",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.WARN,
                    message='The host "Alice" is scheduled on Planning Center but did not confirm.',
                ),
                call(
                    level=ProblemLevel.WARN,
                    message='The host "Bob" is scheduled on Planning Center but did not confirm.',
                ),
                call(
                    level=ProblemLevel.ERROR,
                    message="More than two hosts are scheduled for today.",
                ),
            ],
            any_order=True,
        )
        self.assertEqual(3, messenger.log_problem.call_count)
        pre_stream_title = (
            "My Series Title"
            + "\n\nMy Sermon Title"
            + "\n\nStephen"
            + "\n\nMarch 16, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Stephen"),
                call(input=cfg.vmix_host1_title_key, value="Alice"),
                call(input=cfg.vmix_host2_title_key, value="Charlie"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_2c_1u_hosts(self) -> None:
        dt = date(year=2025, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Stephen", status=TeamMemberStatus.CONFIRMED)},
            hosts={
                TeamMember(name="Alice", status=TeamMemberStatus.UNCONFIRMED),
                TeamMember(name="Bob", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Charlie", status=TeamMemberStatus.CONFIRMED),
            },
            series="My Series Title",
            title="My Sermon Title",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.WARN,
                    message='The host "Alice" is scheduled on Planning Center but did not confirm.',
                ),
                call(
                    level=ProblemLevel.ERROR,
                    message="More than two hosts are scheduled for today.",
                ),
            ],
            any_order=True,
        )
        self.assertEqual(2, messenger.log_problem.call_count)
        pre_stream_title = (
            "My Series Title"
            + "\n\nMy Sermon Title"
            + "\n\nStephen"
            + "\n\nMarch 16, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Stephen"),
                call(input=cfg.vmix_host1_title_key, value="Bob"),
                call(input=cfg.vmix_host2_title_key, value="Charlie"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_3c_hosts(self) -> None:
        dt = date(year=2025, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={TeamMember(name="Stephen", status=TeamMemberStatus.CONFIRMED)},
            hosts={
                TeamMember(name="Alice", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Bob", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Charlie", status=TeamMemberStatus.CONFIRMED),
            },
            series="My Series Title",
            title="My Sermon Title",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There was 1 error. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_any_call(
            level=ProblemLevel.ERROR,
            message="More than two hosts are scheduled for today.",
        )
        self.assertEqual(1, messenger.log_problem.call_count)
        pre_stream_title = (
            "My Series Title"
            + "\n\nMy Sermon Title"
            + "\n\nStephen"
            + "\n\nMarch 16, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                call(input=cfg.vmix_speaker_title_key, value="Stephen"),
                call(input=cfg.vmix_host1_title_key, value="Alice"),
                call(input=cfg.vmix_host2_title_key, value="Bob"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_multiple_errors(self) -> None:
        dt = date(year=2025, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers={
                TeamMember(name="Mater", status=TeamMemberStatus.CONFIRMED),
                TeamMember(name="Lightning McQueen", status=TeamMemberStatus.CONFIRMED),
            },
            hosts=set(),
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(ValueError) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            'There were 2 errors. See the "Problems" section for details.',
            str(cm.exception),
        )
        messenger.log_problem.assert_has_calls(
            [
                call(
                    level=ProblemLevel.ERROR,
                    message="More than one speaker is scheduled for today.",
                ),
                call(
                    level=ProblemLevel.ERROR,
                    message="No hosts are scheduled for today.",
                ),
            ],
            any_order=True,
        )
        self.assertEqual(2, messenger.log_problem.call_count)
        # Still set the other titles so that the user doesn't need to do it all
        # manually
        pre_stream_title = (
            "Radiator Springs"
            + "\n\nHow to Tip Tractors"
            + f"\n\nLightning McQueen"
            + "\n\nMarch 16, 2025"
        )
        vmix_client.set_text.assert_has_calls(
            [
                # Take the first speaker alphabetically
                call(input=cfg.vmix_speaker_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_host1_title_key, value=""),
                call(input=cfg.vmix_host2_title_key, value=""),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def _create_pco_client(
        self,
        speakers: Set[TeamMember],
        hosts: Set[TeamMember],
        series: str,
        title: str,
        date: date,
    ) -> PlanningCenterClient:
        pco_client = create_autospec(PlanningCenterClient)
        pco_client.find_plan_by_date.return_value = Plan(
            id="123456",
            title=title,
            series_title=series,
            date=date,
            web_page_url="https://example.com",
        )
        pco_client.find_presenters.return_value = PresenterSet(
            speakers=speakers,
            hosts=hosts,
        )
        return pco_client

    def _create_config(self, date: date) -> McrSetupConfig:
        cfg = McrSetupConfig(
            args=McrSetupArgs.parse(["", "--date", date.strftime("%Y-%m-%d")]),
            profile="mcr",
            allow_multiple_only_for_testing=True,
        )
        return cfg
