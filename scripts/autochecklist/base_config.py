class BaseConfig:
    def reload(self) -> None:
        pass

    def fill_placeholders(self, text: str) -> str:
        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')
        return text
