import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

import requests
from config import Config


@dataclass
class Issue:
    title: str
    html_url: str


class IssueType(Enum):
    FOH_SETUP = "foh_setup_checklist"
    MCR_SETUP = "mcr_setup_checklist"
    MCR_TEARDOWN = "mcr_teardown_checklist"


def find_latest_github_issue(type: IssueType, config: Config) -> Issue:
    url = f"{config.github_api_repo_url}/issues"
    api_token = os.environ.get("RECC_GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {api_token}"} if api_token is not None else {}
    # Include closed issues and search by date for testing purposes
    response = requests.get(
        url=url,
        params={
            "state": "all",
            "labels": type.value,
            "per_page": 1,
            "sort": "created",
            "direction": "desc",
        },
        timeout=config.timeout_seconds,
        headers=headers,
    )
    if response.status_code // 100 != 2:
        raise ValueError(
            f"Request to {url} failed with status code {response.status_code}."
        )
    results: List[Dict[str, object]] = response.json()
    if len(results) == 0:
        raise ValueError("No results found.")
    issue = results[0]
    if "url" not in issue or not isinstance(issue["html_url"], str):
        raise ValueError("Missing or invalid URL in response from GitHub.")
    if "title" not in issue or not isinstance(issue["title"], str):
        raise ValueError("Missing or invalid title in response from GitHub.")
    return Issue(title=issue["title"], html_url=issue["html_url"])
