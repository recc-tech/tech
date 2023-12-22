from typing import Union

from requests import Response

class BaseVimeoException(Exception):
    def __init__(self, response: Union[Exception, Response], message: str) -> None: ...

class ObjectLoadFailure(Exception):
    def __init__(self, message: object) -> None: ...

class UploadQuotaExceeded(Exception):
    def __init__(self, free_quota: float, message: str) -> None: ...

class UploadAttemptCreationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class UploadTicketCreationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class VideoCreationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class VideoUploadFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class PictureCreationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class PictureUploadFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class PictureActivationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class TexttrackCreationFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class TexttrackUploadFailure(BaseVimeoException):
    def __init__(self, esponse: Union[Exception, Response], message: str) -> None: ...

class APIRateLimitExceededFailure(BaseVimeoException): ...