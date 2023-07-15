from enum import Enum

import keyring
from autochecklist import Messenger


# It's useful for testing purposes to keep a central list of passwords.
class Credential(Enum):
    BOXCAST_PASSWORD = ("boxcast_password", "BoxCast password")
    BOXCAST_USERNAME = ("boxcast_username", "BoxCast username")
    VIMEO_ACCESS_TOKEN = ("vimeo_access_token", "Vimeo access token")
    VIMEO_CLIENT_ID = ("vimeo_client_id", "Vimeo client ID")
    VIMEO_CLIENT_SECRET = ("vimeo_client_secret", "Vimeo client secret")


class CredentialStore:
    _KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(self, messenger: Messenger):
        self._messenger = messenger

    def get(
        self,
        credential: Credential,
        force_user_input: bool,
    ) -> str:
        (name, display_name) = credential.value

        if not force_user_input:
            value = keyring.get_password(CredentialStore._KEYRING_APP_NAME, name)
            if value:
                return value

        base_prompt = f"Enter {display_name}: "
        prompt = base_prompt
        while True:
            value = self._messenger.input_password(prompt)
            if not value:
                prompt = (
                    f"You just entered a blank value. Please try again. {base_prompt}"
                )
            elif value.upper() == "\x16":
                prompt = f"You just entered the value CTRL+V. Try right-clicking to paste. {base_prompt}"
            else:
                keyring.set_password(CredentialStore._KEYRING_APP_NAME, name, value)
                return value
