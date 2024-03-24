import unittest
from datetime import date
from typing import List
from unittest.mock import call, create_autospec

from args import McrSetupArgs
from autochecklist import Messenger, ProblemLevel
from config import McrSetupConfig
from external_services import Plan, PlanningCenterClient, PresenterSet, VmixClient
from lib import mcr_setup


class McrSetupTestCase(unittest.TestCase):
    def test_update_titles(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers=["Mater"],
            hosts=["Lightning McQueen"],
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
                call(input=cfg.vmix_host_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_no_speaker(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers=[],
            hosts=["Lightning McQueen"],
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
                    message=f"No speaker is confirmed for today. Defaulting to {cfg.default_speaker_name}.",
                )
            ],
            any_order=True,
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
                call(input=cfg.vmix_host_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_multiple_speakers(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers=["Mater", "Lightning McQueen"],
            hosts=["Lightning McQueen"],
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(Exception) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            "More than one speaker is confirmed for today.", str(cm.exception)
        )

    def test_update_titles_no_host(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers=["Mater"],
            hosts=[],
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(Exception) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual("No MC host is scheduled for today.", str(cm.exception))

    def test_update_titles_two_hosts(self) -> None:
        dt = date(year=2024, month=3, day=9)
        pco_client = self._create_pco_client(
            speakers=["Mater"],
            hosts=["Sally Carrera", "Lightning McQueen"],
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
                    message="More than one MC host is scheduled for today. The second one's name has been written to the special announcer title.",
                )
            ],
            any_order=True,
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
                # Alphabetical order
                call(input=cfg.vmix_host_title_key, value="Lightning McQueen"),
                call(input=cfg.vmix_extra_presenter_title_key, value="Sally Carrera"),
                call(input=cfg.vmix_pre_stream_title_key, value=pre_stream_title),
            ],
            any_order=True,
        )

    def test_update_titles_three_hosts(self) -> None:
        dt = date(year=2024, month=3, day=16)
        pco_client = self._create_pco_client(
            speakers=["Mater"],
            hosts=["Lightning McQueen", "Doc Hudson", "Sally Carrera"],
            series="Radiator Springs",
            title="How to Tip Tractors",
            date=dt,
        )
        vmix_client = create_autospec(VmixClient)
        cfg = self._create_config(date=dt)
        messenger = create_autospec(Messenger)

        with self.assertRaises(Exception) as cm:
            mcr_setup.update_titles(
                vmix_client=vmix_client,
                pco_client=pco_client,
                config=cfg,
                messenger=messenger,
            )
        self.assertEqual(
            "More than two MC hosts are scheduled for today.", str(cm.exception)
        )

    def _create_pco_client(
        self,
        speakers: List[str],
        hosts: List[str],
        series: str,
        title: str,
        date: date,
    ) -> PlanningCenterClient:
        pco_client = create_autospec(PlanningCenterClient)
        pco_client.find_plan_by_date.return_value = Plan(
            id="123456", title=title, series_title=series, date=date
        )
        pco_client.find_presenters.return_value = PresenterSet(
            speaker_names=speakers,
            mc_host_names=hosts,
        )
        return pco_client

    def _create_config(self, date: date) -> McrSetupConfig:
        cfg = McrSetupConfig(
            args=McrSetupArgs.parse(["", "--date", date.strftime("%Y-%m-%d")]),
            profile="mcr",
            allow_multiple_only_for_testing=True,
        )
        return cfg
