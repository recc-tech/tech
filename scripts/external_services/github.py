from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Dict, List

import requests
from config import Config


@dataclass
class Issue:
    html_url: str


class IssueType(Enum):
    FOH_SETUP = "foh_setup_checklist"
    MCR_SETUP = "mcr_setup_checklist"
    MCR_TEARDOWN = "mcr_teardown_checklist"


def find_github_issue(type: IssueType, dt: date, config: Config) -> Issue:
    url = f"{config.github_api_repo_url}/issues"
    # Include closed issues and search by date for testing purposes
    response = requests.get(
        url=url,
        params={
            "state": "all",
            "labels": type.value,
            "per_page": 1,
            "since": datetime.combine(dt, time()).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sort": "updated",
            "direction": "asc",
        },
        timeout=config.timeout_seconds,
    )
    if response.status_code // 100 != 2:
        raise ValueError(
            f"Request to {url} failed with status code {response.status_code}."
        )
    results: List[Dict[str, object]] = response.json()
    if len(results) == 0:
        raise ValueError("No results found.")
    issue = results[0]
    if (
        "url" not in issue
        or issue["html_url"] is None
        or not isinstance(issue["html_url"], str)
    ):
        raise ValueError("Missing or invalid URL in response from GitHub.")
    return Issue(html_url=issue["html_url"])
