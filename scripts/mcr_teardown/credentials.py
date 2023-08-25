from __future__ import annotations

from argparse import ArgumentTypeError
from enum import Enum
from typing import Dict, List

import keyring
from autochecklist import Messenger, Parameter


class Credential(Enum):
    # The names (the first element in each tuple) MUST be unique
    BOXCAST_PASSWORD = ("boxcast_password", "BoxCast password", True)
    BOXCAST_USERNAME = ("boxcast_username", "BoxCast username", False)
    VIMEO_ACCESS_TOKEN = ("vimeo_access_token", "Vimeo access token", True)
    VIMEO_CLIENT_ID = ("vimeo_client_id", "Vimeo client ID", True)
    VIMEO_CLIENT_SECRET = ("vimeo_client_secret", "Vimeo client secret", True)

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


class CredentialStore:
    _KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(self, messenger: Messenger, force_user_input: bool = False):
        self._messenger = messenger
        self._force_user_input = force_user_input

    def get_multiple(
        self, prompt: str, credentials: List[Credential], force_user_input: bool
    ) -> Dict[Credential, str]:
        force = force_user_input or self._force_user_input

        credential_values: Dict[Credential, str] = {}
        unknown_credentials: List[Credential] = []
        for c in credentials:
            if force:
                unknown_credentials.append(c)
            else:
                value = keyring.get_password(CredentialStore._KEYRING_APP_NAME, c.name)
                if value:
                    credential_values[c] = value
                else:
                    unknown_credentials.append(c)

        if unknown_credentials:
            unknown_credential_raw_values = self._messenger.input_multiple(
                prompt=prompt,
                title="Input credentials",
                params={
                    c.name: Parameter(
                        display_name=c.display_name,
                        parser=_validate_input,
                        password=c.is_password,
                    )
                    for c in unknown_credentials
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
            credential_values |= unknown_credential_values

        return credential_values

    def get(
        self,
        credential: Credential,
        force_user_input: bool,
    ) -> str:
        value_dict = self.get_multiple(
            prompt="",
            credentials=[credential],
            force_user_input=force_user_input,
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
