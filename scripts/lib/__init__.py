"""
Code that is shared by the packages for multiple scripts.
"""

# pyright: reportUnusedImport=false

from .assets import (
    AssetManager,
    Attachment,
    Download,
    DownloadDeduplicated,
    DownloadFailed,
    DownloadPlan,
    DownloadResult,
    DownloadSkipped,
    DownloadSucceeded,
)
from .dependency_provider import ReccDependencyProvider
from .slides import Slide, SlideBlueprint, SlideBlueprintReader, SlideGenerator
from .summarize_plan import (
    AnnotatedItem,
    AnnotatedSong,
    PlanItemsSummary,
    get_plan_summary,
    load_plan_summary,
    plan_summary_to_html,
    plan_summary_to_json,
)
