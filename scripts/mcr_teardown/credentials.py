from enum import Enum

import keyring
from autochecklist import Messenger


class Credential(Enum):
    # The values are in the format (name, display_name, is_secret)
    BOXCAST_PASSWORD = ("boxcast_password", "BoxCast password", True)
    BOXCAST_USERNAME = ("boxcast_username", "BoxCast username", False)
    VIMEO_ACCESS_TOKEN = ("vimeo_access_token", "Vimeo access token", True)
    VIMEO_CLIENT_ID = ("vimeo_client_id", "Vimeo client ID", True)
    VIMEO_CLIENT_SECRET = ("vimeo_client_secret", "Vimeo client secret", True)


# TODO: Add a method to enter multiple passwords on one screen (using messenger.input_multiple)?
class CredentialStore:
    _KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(self, messenger: Messenger, force_user_input: bool = False):
        self._messenger = messenger
        self._force_user_input = force_user_input

    def get(
        self,
        credential: Credential,
        force_user_input: bool,
    ) -> str:
        force = force_user_input or self._force_user_input

        (name, display_name, is_secret) = credential.value

        if not force:
            value = keyring.get_password(CredentialStore._KEYRING_APP_NAME, name)
            if value:
                return value

        base_prompt = f"Enter {display_name}: "
        prompt = base_prompt
        while True:
            value = (
                self._messenger.input(prompt, password=True)
                if is_secret
                else self._messenger.input(prompt)
            )
            if not value:
                prompt = (
                    f"You just entered a blank value. Please try again. {base_prompt}"
                )
            elif value.upper() == "\x16":
                prompt = f"You just entered the value CTRL+V. Try right-clicking to paste. {base_prompt}"
            else:
                keyring.set_password(CredentialStore._KEYRING_APP_NAME, name, value)
                return value
