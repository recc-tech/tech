import keyring
from messenger import Messenger

_KEYRING_APP_NAME = "recc_tech_mcr_teardown"


def get_credential(
    credential_username: str,
    credential_display_name: str,
    force_user_input: bool,
    messenger: Messenger,
) -> str:
    if not force_user_input:
        value = keyring.get_password(_KEYRING_APP_NAME, credential_username)
        if value:
            return value

    base_prompt = f"Enter {credential_display_name}: "
    prompt = base_prompt
    while True:
        value = messenger.input_password(prompt)
        if not value:
            prompt = f"You just entered a blank value. Please try again. {base_prompt}"
        elif value.upper() == "^V":
            prompt = f"You just entered the value '^V'. Try right-clicking to paste. {base_prompt}"
        else:
            keyring.set_password(_KEYRING_APP_NAME, credential_username, value)
            return value
