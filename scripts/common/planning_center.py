"""
Code for interacting with the Planning Center Services API.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import requests
from autochecklist import Messenger
from common.credentials import Credential, CredentialStore, InputPolicy
from requests.auth import HTTPBasicAuth


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    series_title: str


class PlanningCenterClient:
    BASE_URL = "https://api.planningcenteronline.com"
    SUNDAY_GATHERINGS_SERVICE_TYPE_ID = "882857"

    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        lazy_login: bool = False,
    ):
        self._messenger = messenger
        self._credential_store = credential_store

        if not lazy_login:
            self._test_credentials(max_attempts=3)

    def find_plan_by_date(
        self, dt: date, service_type: str = SUNDAY_GATHERINGS_SERVICE_TYPE_ID
    ) -> Plan:
        today_str = dt.strftime("%Y-%m-%d")
        tomorrow_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        response = requests.get(
            url=f"{self.BASE_URL}/services/v2/service_types/{service_type}/plans?filter=before%2Cafter&after={today_str}&before={tomorrow_str}",
            auth=self._get_auth(),
        )
        if response.status_code // 100 != 2:
            raise ValueError(f"Request failed with status code {response.status_code}")
        plans = response.json()["data"]
        if len(plans) != 1:
            raise ValueError(f"Found {len(plans)} plans on {today_str}.")
        plan = plans[0]
        return Plan(
            id=plan["id"],
            title=plan["attributes"]["title"],
            series_title=plan["attributes"]["series_title"],
        )

    def _test_credentials(self, max_attempts: int):
        for attempt_num in range(1, max_attempts + 1):
            url = f"{self.BASE_URL}/people/v2/me"
            response = requests.get(url, auth=self._get_auth())
            if response.status_code // 100 == 2:
                return
            elif response.status_code == 401:
                self._messenger.log_debug(
                    f"Test request to GET {url} failed with status code {response.status_code} (attempt {attempt_num}/{max_attempts})."
                )
            else:
                raise ValueError(
                    f"Test request to GET {url} failed with status code {response.status_code}."
                )

    def _get_auth(self) -> HTTPBasicAuth:
        credentials = self._credential_store.get_multiple(
            prompt="Enter the Planning Center credentials.",
            credentials=[
                Credential.PLANNING_CENTER_APP_ID,
                Credential.PLANNING_CENTER_SECRET,
            ],
            request_input=InputPolicy.AS_REQUIRED,
        )
        app_id = credentials[Credential.PLANNING_CENTER_APP_ID]
        secret = credentials[Credential.PLANNING_CENTER_SECRET]
        return HTTPBasicAuth(app_id, secret)
