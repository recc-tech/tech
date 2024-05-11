from __future__ import annotations

from argparse import ArgumentTypeError
from enum import Enum, auto
from typing import Dict, List, Optional

import keyring
from autochecklist import Messenger, Parameter


class Credential(Enum):
    # The names (the first element in each tuple) MUST be unique
    BOXCAST_CLIENT_ID = ("boxcast_client_id", "BoxCast client ID", True)
    BOXCAST_CLIENT_SECRET = ("boxcast_client_secret", "BoxCast client secret", True)
    VIMEO_ACCESS_TOKEN = ("vimeo_access_token", "Vimeo access token", True)
    VIMEO_CLIENT_ID = ("vimeo_client_id", "Vimeo client ID", True)
    VIMEO_CLIENT_SECRET = ("vimeo_client_secret", "Vimeo client secret", True)
    PLANNING_CENTER_APP_ID = ("planning_center_app_id", "Planning Center app ID", True)
    PLANNING_CENTER_SECRET = ("planning_center_secret", "Planning Center secret", True)

    @property
    def name(self) -> str:
        return self.value[0]

    @property
    def display_name(self) -> str:
        return self.value[1]

    @property
    def is_password(self) -> bool:
        return self.value[2]

    @staticmethod
    def from_name(name: str) -> Credential:
        matching_values = [c for c in Credential if c.name == name]
        if not matching_values:
            raise ValueError(f"The name '{name}' does not match any credentials.")
        return matching_values[0]


class InputPolicy(Enum):
    NEVER = auto()
    AS_REQUIRED = auto()
    ALWAYS = auto()


class CredentialStore:
    _KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(
        self,
        messenger: Messenger,
        request_input: Optional[InputPolicy] = None,
    ):
        self._messenger = messenger
        self._request_input = request_input

    def get_multiple(
        self,
        prompt: str,
        credentials: List[Credential],
        request_input: InputPolicy,
    ) -> Dict[Credential, str]:
        input_policy = self._request_input or request_input
        saved_credentials = {
            c: keyring.get_password(CredentialStore._KEYRING_APP_NAME, c.name)
            for c in credentials
        }
        match input_policy:
            case InputPolicy.NEVER:
                unknown_credentials = [
                    c for (c, v) in saved_credentials.items() if not v
                ]
                if unknown_credentials:
                    raise ValueError(
                        f"The following credentials are not saved and this credential store is not allowed to request user input: {', '.join([c.display_name for c in unknown_credentials])}"
                    )
                credentials_to_input: List[Credential] = []
            case InputPolicy.AS_REQUIRED:
                credentials_to_input = [
                    c for (c, v) in saved_credentials.items() if not v
                ]
            case InputPolicy.ALWAYS:
                credentials_to_input = credentials

        known_credentials = {c: v for (c, v) in saved_credentials.items() if v}
        if credentials_to_input:
            unknown_credential_raw_values = self._messenger.input_multiple(
                prompt=prompt,
                title="Input credentials",
                params={
                    c.name: Parameter(
                        display_name=c.display_name,
                        parser=_validate_input,
                        password=c.is_password,
                    )
                    for c in credentials_to_input
                },
            )
            unknown_credential_values = {
                Credential.from_name(name): str(value)
                for (name, value) in unknown_credential_raw_values.items()
            }
            for credential, value in unknown_credential_values.items():
                keyring.set_password(
                    CredentialStore._KEYRING_APP_NAME, credential.name, value
                )
                known_credentials[credential] = value
        return known_credentials

    def get(
        self,
        credential: Credential,
        request_input: InputPolicy,
    ) -> str:
        value_dict = self.get_multiple(
            prompt="",
            credentials=[credential],
            request_input=request_input,
        )
        return value_dict[credential]


def _validate_input(text: str) -> str:
    if not text:
        raise ArgumentTypeError("You entered a blank value.")
    elif all(char == "\x16" for char in text):
        raise ArgumentTypeError(
            "You entered the literal value CTRL+V. Try right-clicking to paste."
        )
    else:
        return text
