class BaseConfig:
    """
    Central location for shared information like video titles, file paths, etc.
    """

    def fill_placeholders(self, text: str) -> str:
        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text
