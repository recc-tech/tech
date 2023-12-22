from typing import Any, Dict, Union

from requests.structures import CaseInsensitiveDict

class AuthenticationMixinBase:
    def call_grant(
        self, path: str, data: Union[None, bytes, Dict[str, Any]]
    ) -> tuple[int, CaseInsensitiveDict[str], Dict[str, Any]]: ...
