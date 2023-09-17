import time
from datetime import timedelta
from typing import Optional

from autochecklist.messenger import CancellationToken


def sleep_attentively(
    timeout: timedelta,
    cancellation_token: Optional[CancellationToken],
    poll_frequency: timedelta = timedelta(seconds=0.1),
):
    if poll_frequency >= timeout:
        time.sleep(timeout.total_seconds())
        return
    timeout_seconds = timeout.total_seconds()
    poll_frequency_seconds = poll_frequency.total_seconds()
    start = time.monotonic()
    while True:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()
        time.sleep(poll_frequency_seconds)
        if time.monotonic() - start >= timeout_seconds:
            return
