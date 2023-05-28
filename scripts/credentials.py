from getpass import getpass

import keyring


_KEYRING_APP_NAME = "recc_tech_mcr_teardown"


def get_credential(
    credential_username: str,
    credential_display_name: str,
    force_user_input: bool = False,
) -> str:
    if not force_user_input:
        value = keyring.get_password(_KEYRING_APP_NAME, credential_username)
        if value:
            return value

    while True:
        value = getpass(f"Enter {credential_display_name}: ")
        if not value:
            print("You just entered a blank value. Please try again.")
        elif value.upper() == "^V":
            print("You just entered the value '^V'. Try right-clicking to paste.")
        else:
            keyring.set_password(_KEYRING_APP_NAME, credential_username, value)
            return value
