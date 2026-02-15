from typing import Literal

from config import Config
from requests import Session


def log_in(
    camera: Literal[1, 2, 3],
    s: Session,
    config: Config,
    password: str,
) -> None:
    base_url = config.cam_base_url[camera]
    s.post(
        f"{base_url}/login",
        data=f"auth_password={password}",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
