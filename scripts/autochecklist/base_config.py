from datetime import datetime


class BaseConfig:
    """
    Central location for shared information like video titles, file paths, etc.
    """

    def fill_placeholders(self, text: str) -> str:
        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text

    @staticmethod
    def _date_mdy(dt: datetime) -> str:
        """
        Return the given date as a string in day month year format. The day of the month will not have a leading zero.

        Examples:
            - `_date_mdy(datetime(year=2023, month=6, day=4)) == 'June 4, 2023'`
            - `_date_mdy(datetime(year=2023, month=6, day=11)) == 'June 11, 2023'`
        """
        month = dt.strftime("%B")
        day = dt.strftime("%d")
        if day.startswith("0"):
            day = day[1:]
        year = dt.strftime("%Y")
        return f"{month} {day}, {year}"
