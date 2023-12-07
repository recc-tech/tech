from datetime import date

from common.planning_center import PlanningCenterClient
from mcr_setup.config import McrSetupConfig


def download_message_notes(client: PlanningCenterClient, config: McrSetupConfig):
    today = date.today()
    plan = client.find_plan_by_date(today)
    message_notes = client.find_message_notes(plan.id)
    config.message_notes_file.parent.mkdir(exist_ok=True, parents=True)
    with open(config.message_notes_file, "w", encoding="utf-8") as f:
        f.write(message_notes)
