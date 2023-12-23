from typing import Iterable

from .base import AuthenticationMixinBase

class ClientCredentialsMixin(AuthenticationMixinBase):
    def load_client_credentials(self, scope: Iterable[str]) -> str: ...
