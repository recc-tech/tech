from typing import Optional

from args import ReccArgs

from .config import Config


class McrSetupConfig(Config):
    def __init__(
        self,
        args: ReccArgs,
        profile: Optional[str] = None,
        strict: bool = False,
        allow_multiple_only_for_testing: bool = False,
    ) -> None:
        self._args = args
        super().__init__(
            args,
            profile=profile,
            strict=strict,
            allow_multiple_only_for_testing=allow_multiple_only_for_testing,
            create_dirs=False,
        )
