from args import ReccArgs
from autochecklist import DependencyProvider
from config import Config

from .unused_function import main

if __name__ == "__main__":
    import os
    from pathlib import Path

    args = ReccArgs.parse([])
    config = Config(args)
    dep = DependencyProvider(
        args=args,
        config=config,
        messenger=None,
        log_file=Path(os.devnull),
        script_name="Test",
        description="Test",
        show_statuses_by_default=True,
        ui_theme="dark",
    )
    main(args, config, dep)
