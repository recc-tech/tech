from typing import Iterable, Tuple, Union

from .base import AuthenticationMixinBase

class AuthorizationCodeMixin(AuthenticationMixinBase):
    def auth_url(
        self, scope: Union[str, Iterable[str]], redirect: str, state: str
    ) -> str: ...
    def exchange_code(self, code: str, redirect: str) -> Tuple[str, str, str]: ...
