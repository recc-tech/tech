from typing import Dict, Optional, Tuple, Union

import requests
import requests.auth
from requests import PreparedRequest, Response

from .auth.authorization_code import AuthorizationCodeMixin
from .auth.client_credentials import ClientCredentialsMixin
from .upload import UploadMixin

class VimeoClient(ClientCredentialsMixin, AuthorizationCodeMixin, UploadMixin):
    API_ROOT: str = ...
    HTTP_METHODS: str = ...
    ACCEPT_HEADER: str = ...
    USER_AGENT: str = ...
    def __init__(
        self,
        token: Optional[str] = ...,
        key: Optional[str] = ...,
        secret: Optional[str] = ...,
        *args: object,
        **kwargs: object
    ) -> None: ...
    @property
    def token(self) -> str: ...
    @token.setter
    def token(self, value: str) -> None: ...
    def head(
        self, url: str, timeout: Union[float, Tuple[float, float]]
    ) -> Response: ...
    def options(
        self, url: str, timeout: Union[float, Tuple[float, float]]
    ) -> Response: ...
    def get(
        self,
        url: str,
        params: Optional[Dict[str, object]],
        timeout: Union[float, Tuple[float, float]],
        **kwargs: object
    ) -> Response: ...
    def post(
        self,
        url: str,
        data: Union[None, bytes, Dict[str, object]],
        timeout: Union[float, Tuple[float, float]],
        **kwargs: object
    ) -> Response: ...
    def put(
        self,
        url: str,
        data: Union[None, bytes, Dict[str, object]],
        timeout: Union[float, Tuple[float, float]],
        **kwargs: object
    ) -> Response: ...
    def patch(
        self,
        url: str,
        data: Union[None, bytes, Dict[str, object]],
        timeout: Union[float, Tuple[float, float]],
        **kwargs: object
    ) -> Response: ...
    def delete(
        self, url: str, timeout: Union[float, Tuple[float, float]], **kwargs: object
    ) -> Response: ...

class _BearerToken(requests.auth.AuthBase):
    """Model the bearer token and apply it to the request."""

    def __init__(self, token: str) -> None: ...
    def __call__(self, request: PreparedRequest) -> PreparedRequest: ...
